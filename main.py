import cv2
from ultralytics import YOLO
import os
from datetime import datetime
import time

# Carrega o modelo YOLO
try:
    model = YOLO('yolov8n.pt')
except Exception as e:
    print(f"Erro ao carregar o modelo YOLO: {e}")
    print("Verifique se a biblioteca ultralytics está instalada e o modelo 'yolov8n.pt' está disponível.")
    exit()

# Inicia a captura de vídeo
try:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise IOError("Não foi possível abrir a webcam.")
except IOError as e:
    print(f"Erro: {e}")
    exit()

# Cria a pasta para salvar os prints
FOTOS_DIR = "prints_eventos"
os.makedirs(FOTOS_DIR, exist_ok=True)

# Variáveis para controlar o intervalo entre os prints
last_capture_time = 0
CAPTURE_INTERVAL_SECONDS = 5

# Variáveis para detecção de movimento (Background Subtraction)
background_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=True)
MOTION_THRESHOLD_AREA = 500  # Área mínima para considerar movimento

# Limites de detecção de pessoa (CALIBRAGEM DE DISTÂNCIA)
CONFIDENCE_THRESHOLD = 0.60  # Aceita detecções com 60% de confiança
MIN_WIDTH = 50       # Largura mínima para uma detecção
MIN_HEIGHT = 100     # Altura mínima para uma detecção
MAX_WIDTH = 400      # **Largura MÁXIMA para uma detecção (novo)**
MAX_HEIGHT = 700     # **Altura MÁXIMA para uma detecção (novo)**
MIN_ASPECT_RATIO = 1.5 # Relação mínima entre altura/largura

while True:
    ret, frame = cap.read()
    if not ret:
        print("Aviso: Falha ao capturar o frame. Tentando novamente...")
        continue

    # 1. Pré-processamento: Reduz o ruído
    blurred_frame = cv2.GaussianBlur(frame, (21, 21), 0)

    # 2. Detecção de movimento
    fg_mask = background_subtractor.apply(blurred_frame)
    fg_mask = cv2.threshold(fg_mask, 250, 255, cv2.THRESH_BINARY)[1]
    fg_mask = cv2.dilate(fg_mask, None, iterations=2)
    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    motion_detected = False
    for contour in contours:
        if cv2.contourArea(contour) > MOTION_THRESHOLD_AREA:
            motion_detected = True
            break
    
    person_confirmed = False
    
    # 3. Se houver movimento, executa a detecção de pessoas com YOLO
    if motion_detected:
        results = model(frame, stream=True, classes=0, conf=CONFIDENCE_THRESHOLD)

        for result in results:
            boxes = result.boxes.cpu().numpy()
            for box in boxes:
                confidence = box.conf[0]
                x1, y1, x2, y2 = box.xyxy[0].astype(int)
                width = x2 - x1
                height = y2 - y1

                # Aplica todos os filtros, incluindo os novos limites MÁXIMOS
                if width >= MIN_WIDTH and height >= MIN_HEIGHT and \
                   width <= MAX_WIDTH and height <= MAX_HEIGHT and \
                   (height / width) >= MIN_ASPECT_RATIO:
                    
                    person_confirmed = True
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f'Pessoa: {confidence:.2f}', (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # 4. Lógica para salvar a imagem
    current_time = time.time()
    if person_confirmed and (current_time - last_capture_time > CAPTURE_INTERVAL_SECONDS):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{FOTOS_DIR}/evento_{timestamp}.jpg"
        cv2.imwrite(filename, frame)
        print(f"Pessoa detectada! Foto salva em: {filename}")
        last_capture_time = current_time

    cv2.imshow('Detecção de Pessoas', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()