#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Olhar Vivo — main.py (atualizado)
---------------------------------
Baseado no seu script original, com melhorias:
- Configuração por .env (python-dotenv)
- ROI opcional via roi_config.yaml (polígono)
- Logs com RotatingFileHandler + console
- Gateamento por movimento (MOG2) antes do YOLO (classes=0/pessoa)
- Filtros min/max de caixa + razão de aspecto (calibráveis)
- Cooldown para prints + envio opcional ao Telegram
- Execução headless opcional (sem janela)

Dependências principais: ultralytics, opencv-python, PyYAML, requests, python-dotenv
"""

import os
import cv2
import time
import yaml
import numpy as np
import logging
import requests
import queue
from datetime import datetime
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from threading import Thread

# =====================
# Configuração (.env)
# =====================
load_dotenv()  # carrega variáveis do arquivo .env se existir

def getenv(key, default=None, cast=str):
    val = os.environ.get(key, None)
    if val is None or val == "":
        return default
    try:
        if cast is bool:
            return str(val).lower() in ("1","true","on","yes")
        return cast(val)
    except Exception:
        return default

# Diretórios
BASE_DIR   = os.path.abspath(getenv("OLHARVIVO_BASEDIR", os.getcwd()))
EVENT_DIR  = os.path.join(BASE_DIR, getenv("OLHARVIVO_EVENT_DIR", "prints_eventos"))
LOG_DIR    = os.path.join(BASE_DIR, getenv("OLHARVIVO_LOG_DIR", "logs"))
os.makedirs(EVENT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Logging
logger = logging.getLogger("olharvivo")
logger.setLevel(logging.INFO)
_handler = RotatingFileHandler(os.path.join(LOG_DIR, "olhar_vivo.log"), maxBytes=2_000_000, backupCount=5, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_handler)
_console = logging.StreamHandler()
_console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_console)

# Câmera e janela
CAMERA_INDEX = getenv("OLHARVIVO_CAMERA_INDEX", 0, int)
FRAME_WIDTH  = getenv("OLHARVIVO_FRAME_WIDTH", 1280, int)
FRAME_HEIGHT = getenv("OLHARVIVO_FRAME_HEIGHT", 720, int)
SHOW_WINDOW  = getenv("OLHARVIVO_SHOW_WINDOW", True, bool)

# Movimento (MOG2)
MOG2_HISTORY      = getenv("OLHARVIVO_MOG2_HISTORY", 500, int)
MOG2_VARTHRESH    = getenv("OLHARVIVO_MOG2_VARTHRESH", 16, int)
MOG2_SHADOWS      = getenv("OLHARVIVO_MOG2_SHADOWS", True, bool)
MOTION_MIN_AREA   = getenv("OLHARVIVO_MOTION_MIN_AREA", 500, int)
MOTION_DILATE_ITR = getenv("OLHARVIVO_MOTION_DILATE_ITR", 2, int)

# YOLO e filtros de caixa
YOLO_MODEL       = getenv("OLHARVIVO_YOLO_MODEL", "yolov8n.pt")
CONFIDENCE_TH    = getenv("OLHARVIVO_YOLO_CONF", 0.60, float)
MIN_WIDTH        = getenv("OLHARVIVO_MIN_BOX_W", 50, int)
MIN_HEIGHT       = getenv("OLHARVIVO_MIN_BOX_H", 100, int)
MAX_WIDTH        = getenv("OLHARVIVO_MAX_BOX_W", 400, int)
MAX_HEIGHT       = getenv("OLHARVIVO_MAX_BOX_H", 700, int)
MIN_ASPECT_RATIO = getenv("OLHARVIVO_MIN_ASPECT_RATIO", 1.5, float)

# Eventos / cooldown
CAPTURE_INTERVAL_SECONDS = getenv("OLHARVIVO_EVENT_COOLDOWN_SEC", 5.0, float)
ANNOTATE_BOX             = getenv("OLHARVIVO_ANNOTATE_BOX", True, bool)
ROI_FILE                 = getenv("OLHARVIVO_ROI_FILE", "roi_config.yaml")

# Telegram (opcional)
TELEGRAM_TOKEN  = getenv("OLHARVIVO_TG_TOKEN", None)
TELEGRAM_CHATID = getenv("OLHARVIVO_TG_CHATID", None)

# Desempenho / qualidade (configuráveis)
EVENT_JPEG_QUALITY = getenv("OLHARVIVO_EVENT_JPEG_QUALITY", 70, int)  # 1..100
EVENT_MAX_WIDTH    = getenv("OLHARVIVO_EVENT_MAX_WIDTH", 960, int)     # redimensiona antes de salvar/enviar (0 = desativa)
ASYNC_IO           = getenv("OLHARVIVO_ASYNC_IO", True, bool)          # salva/enviar em thread separada
IO_QUEUE_SIZE      = getenv("OLHARVIVO_IO_QUEUE_SIZE", 4, int)
YOLO_IMGSZ         = getenv("OLHARVIVO_YOLO_IMGSZ", 640, int)          # resolução de inferência
BLUR_KSIZE         = getenv("OLHARVIVO_BLUR_KSIZE", 11, int)           # ímpar; 0/1 para desativar

# =====================
# ROI utilitário
# =====================
def load_roi_mask(w, h, roi_file=ROI_FILE):
    """
    Lê roi_config.yaml (lista de pontos [[x,y],...]) e gera máscara binária (uint8).
    Se não existir ou estiver vazio, retorna máscara full-frame.
    """
    try:
        if os.path.isfile(roi_file):
            with open(roi_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                pts = data.get("polygon", None)
                if pts and isinstance(pts, list) and len(pts) >= 3:
                    mask = np.zeros((h, w), dtype="uint8")
                    polygon = np.array(pts, dtype="int32")
                    cv2.fillPoly(mask, [polygon], 255)
                    return mask
    except Exception as e:
        logger.warning(f"Falha ao carregar ROI '{roi_file}': {e}")
    return np.ones((h, w), dtype="uint8") * 255  # full-frame

# =====================
# Notificação Telegram
# =====================
def send_telegram_photo(token, chat_id, filepath, caption=None):
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        with open(filepath, "rb") as f:
            files = {"photo": f}
            data = {"chat_id": chat_id, "caption": caption or ""}
            r = requests.post(url, data=data, files=files, timeout=8)
        if r.status_code == 200:
            logger.info("Notificação Telegram enviada.")
            return True
        else:
            logger.warning(f"Falha Telegram: {r.status_code} {r.text[:120]}")
            return False
    except Exception as e:
        logger.warning(f"Erro no Telegram: {e}")
        return False

# =====================
# Worker assíncrono (IO)
# =====================
class EventIOWorker(Thread):
    def __init__(self, event_dir, tg_token, tg_chatid, jpeg_quality, max_width, q: "queue.Queue"):
        super().__init__(daemon=True)
        self.event_dir = event_dir
        self.tg_token = tg_token
        self.tg_chatid = tg_chatid
        self.jpeg_quality = int(max(1, min(100, jpeg_quality)))
        self.max_width = int(max(0, max_width))
        self.q = q
        self.session = requests.Session()

    def _encode_jpeg(self, image_bgr):
        img = image_bgr
        if self.max_width and img.shape[1] > self.max_width:
            scale = self.max_width / float(img.shape[1])
            new_w = self.max_width
            new_h = int(round(img.shape[0] * scale))
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
        ok, buf = cv2.imencode(".jpg", img, encode_params)
        if not ok:
            raise RuntimeError("Falha no cv2.imencode")
        return buf.tobytes()

    def run(self):
        while True:
            item = self.q.get()
            if item is None:
                self.q.task_done()
                break
            annotated, ts = item
            try:
                # Codifica JPEG (com redimensionamento opcional)
                t0 = time.perf_counter()
                jpeg_bytes = self._encode_jpeg(annotated)
                t1 = time.perf_counter()

                # Salva em disco
                filename = os.path.join(self.event_dir, f"evento_{ts}.jpg")
                with open(filename, "wb") as f:
                    f.write(jpeg_bytes)
                t2 = time.perf_counter()
                logger.info(f"Pessoa detectada — salvo: {filename} (encode {int((t1-t0)*1000)} ms, write {int((t2-t1)*1000)} ms)")

                # Envia Telegram (opcional)
                if self.tg_token and self.tg_chatid:
                    try:
                        url = f"https://api.telegram.org/bot{self.tg_token}/sendPhoto"
                        files = {"photo": ("evento.jpg", jpeg_bytes, "image/jpeg")}
                        data = {"chat_id": self.tg_chatid, "caption": f"Olhar Vivo — pessoa detectada em {ts}"}
                        rt0 = time.perf_counter()
                        r = self.session.post(url, data=data, files=files, timeout=(3.05, 10))
                        rt1 = time.perf_counter()
                        if r.status_code == 200:
                            logger.info(f"Notificação Telegram enviada ({int((rt1-rt0)*1000)} ms)")
                        else:
                            logger.warning(f"Falha Telegram: {r.status_code} {r.text[:120]}")
                    except Exception as e:
                        logger.warning(f"Erro no Telegram: {e}")
            except Exception as e:
                logger.error(f"Erro no worker IO: {e}")
            finally:
                self.q.task_done()

# =====================
# Inicialização
# =====================
def init_camera(index=0, w=1280, h=720):
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise IOError("Não foi possível abrir a webcam.")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    return cap

def main():
    global SHOW_WINDOW
    logger.info("Iniciando Olhar Vivo (main.py atualizado)")

    # Modelo YOLO
    try:
        from ultralytics import YOLO
        model = YOLO(YOLO_MODEL)
    except Exception as e:
        logger.error(f"Erro ao carregar YOLO '{YOLO_MODEL}': {e}")
        return

    # Câmera
    try:
        cap = init_camera(CAMERA_INDEX, FRAME_WIDTH, FRAME_HEIGHT)
    except IOError as e:
        logger.error(str(e))
        return

    # BG Subtractor
    bg = cv2.createBackgroundSubtractorMOG2(
        history=MOG2_HISTORY, varThreshold=MOG2_VARTHRESH, detectShadows=MOG2_SHADOWS
    )

    last_capture_time = 0.0
    roi_mask = load_roi_mask(int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), ROI_FILE)
    roi_overlay = None

    # Blur kernel (configurável)
    k = int(max(0, BLUR_KSIZE))
    if k > 1 and (k % 2 == 0):
        k += 1

    # Fila/worker para IO assíncrono
    io_q = None
    io_worker = None
    if ASYNC_IO:
        io_q = queue.Queue(maxsize=IO_QUEUE_SIZE)
        io_worker = EventIOWorker(EVENT_DIR, TELEGRAM_TOKEN, TELEGRAM_CHATID, EVENT_JPEG_QUALITY, EVENT_MAX_WIDTH, io_q)
        io_worker.start()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                logger.warning("Falha ao capturar frame. Retentando...")
                time.sleep(0.05)
                continue

            # 1) Pré-processamento e ROI
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if k > 1:
                gray = cv2.GaussianBlur(gray, (k, k), 0)
            if roi_mask.shape[:2] != gray.shape[:2]:
                roi_mask = load_roi_mask(gray.shape[1], gray.shape[0], ROI_FILE)
                roi_overlay = None
            roi_gray = cv2.bitwise_and(gray, roi_mask)

            # 2) Movimento
            fg = bg.apply(roi_gray)
            _, fg = cv2.threshold(fg, 250, 255, cv2.THRESH_BINARY)
            fg = cv2.dilate(fg, None, iterations=MOTION_DILATE_ITR)
            contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            motion_detected = any(cv2.contourArea(c) > MOTION_MIN_AREA for c in contours)

            person_confirmed = False
            annotated = frame

            # 3) Se há movimento, roda YOLO (apenas classe pessoa=0)
            if motion_detected:
                results = model(frame, stream=True, classes=0, conf=CONFIDENCE_TH, imgsz=YOLO_IMGSZ)
                for r in results:
                    boxes = r.boxes.cpu().numpy()
                    for b in boxes:
                        x1, y1, x2, y2 = b.xyxy[0].astype(int)
                        conf = float(b.conf[0])
                        w = x2 - x1
                        h = y2 - y1

                        if w >= MIN_WIDTH and h >= MIN_HEIGHT and \
                           w <= MAX_WIDTH and h <= MAX_HEIGHT and \
                           (h / max(w, 1)) >= MIN_ASPECT_RATIO:
                            person_confirmed = True
                            if ANNOTATE_BOX:
                                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                cv2.putText(annotated, f"Pessoa: {conf:.2f}", (x1, max(0, y1 - 8)),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            # 4) Salva print + notifica (cooldown)
            now = time.time()
            if person_confirmed and (now - last_capture_time > CAPTURE_INTERVAL_SECONDS):
                ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                try:
                    if ASYNC_IO and io_q is not None:
                        try:
                            io_q.put_nowait((annotated.copy(), ts))
                        except queue.Full:
                            logger.warning("Fila de IO cheia — evento descartado para evitar travamento.")
                    else:
                        # Fallback síncrono com compressão
                        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(max(1, min(100, EVENT_JPEG_QUALITY)))]
                        out_img = annotated
                        if EVENT_MAX_WIDTH and out_img.shape[1] > EVENT_MAX_WIDTH:
                            scale = EVENT_MAX_WIDTH / float(out_img.shape[1])
                            new_w = EVENT_MAX_WIDTH
                            new_h = int(round(out_img.shape[0] * scale))
                            out_img = cv2.resize(out_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                        fname = os.path.join(EVENT_DIR, f"evento_{ts}.jpg")
                        cv2.imwrite(fname, out_img, encode_params)
                        logger.info(f"Pessoa detectada — salvo: {fname}")
                        send_telegram_photo(TELEGRAM_TOKEN, TELEGRAM_CHATID, fname, f"Olhar Vivo — pessoa detectada em {ts}")
                except Exception as e:
                    logger.error(f"Erro ao salvar/alertar: {e}")
                last_capture_time = now

            # 5) Janela (opcional)
            if SHOW_WINDOW:
                try:
                    disp = frame.copy()
                    # Desenha a ROI na janela para feedback visual
                    if roi_mask is not None:
                        if roi_overlay is None:
                            roi_overlay = cv2.cvtColor(roi_mask, cv2.COLOR_GRAY2BGR)
                        disp = cv2.addWeighted(disp, 1.0, roi_overlay, 0.2, 0)
                    cv2.imshow("Olhar Vivo — Detecção", disp)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                except Exception as e:
                    logger.warning(f"Falha ao renderizar janela: {e}")
                    SHOW_WINDOW = False  # segue headless

    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário (Ctrl+C).")
    finally:
        try:
            cap.release()
        except Exception:
            pass
        cv2.destroyAllWindows()
        # encerra worker
        try:
            if ASYNC_IO and io_q is not None:
                io_q.put_nowait(None)
                io_q.join()
        except Exception:
            pass
        logger.info("Encerrado.")

if __name__ == "__main__":
    main()