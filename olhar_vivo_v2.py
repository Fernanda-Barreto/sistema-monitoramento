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
from datetime import datetime
from logging.handlers import RotatingFileHandler
from ultralytics import YOLO
from dotenv import load_dotenv

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
    logger.info("Iniciando Olhar Vivo (main.py atualizado)")

    # Modelo YOLO
    try:
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

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                logger.warning("Falha ao capturar frame. Retentando...")
                time.sleep(0.05)
                continue

            # 1) Pré-processamento e ROI
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            if roi_mask.shape[:2] != gray.shape[:2]:
                roi_mask = load_roi_mask(gray.shape[1], gray.shape[0], ROI_FILE)
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
                results = model(frame, stream=True, classes=0, conf=CONFIDENCE_TH)
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
                fname = os.path.join(EVENT_DIR, f"evento_{ts}.jpg")
                try:
                    cv2.imwrite(fname, annotated)
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
                        overlay = cv2.cvtColor(roi_mask, cv2.COLOR_GRAY2BGR)
                        disp = cv2.addWeighted(disp, 1.0, overlay, 0.2, 0)
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
        logger.info("Encerrado.")

if __name__ == "__main__":
    main()