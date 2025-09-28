# Sistema de Monitoramento com Visão Computacional — **Olhar Vivo v2**

Projeto acadêmico de **Visão Computacional Embarcada** que detecta **pessoas em tempo real** na **borda** (SBC/PC), captura evidências (imagens) e envia **notificações** (Telegram). Integração opcional com **ESP32-S3-N16R8 + sensor PIR** para reforçar a decisão.

> **Apresentação na faculdade:** usaremos **Orange Pi Zero 2 + ESP32-S3-N16R8 + PIR**. Este README também cobre ambiente de desenvolvimento em **Windows** e **macOS**.

---

## 🧠 Visão Geral

* **Script principal:** `olhar_vivo_v2.py`
* **Fluxo:** Movimento (MOG2) → YOLOv8 (classe pessoa) → Filtros geométricos → Cooldown → Snapshot + **Telegram**
* **Configuração:** `.env` (parâmetros) + `roi_config.yaml` (polígono da ROI)
* **Execução:** interativa (com janela) ou **headless** (produção)

---

## 🚀 Funcionalidades

* **Detecção de Pessoas:** YOLOv8 (classe 0) com confiança ajustável.
* **Filtro Inteligente:** gateamento por **movimento (MOG2)** + **filtros de tamanho e razão de aspecto** → menos falsos positivos.
* **ROI (Zona de Interesse):** polígono configurável em `roi_config.yaml`.
* **Eventos:** salva imagem anotada com timestamp e **envia para Telegram** (opcional).
* **Operação de Campo:** configuração via `.env`, logs rotativos, modo headless e unit `systemd` (SBC).
* **Integração MCU (opcional):** firmware `esp32_pir_mqtt.ino` (PIR → MQTT) para fusão visão ∧ PIR.

---

## 🧩 Tecnologias

* **Python 3.10+**
* **OpenCV** (captura, MOG2, desenho de overlays)
* **Ultralytics / YOLOv8**
* **PyYAML** (ROI)
* **python-dotenv** (carregar `.env`)
* **requests** (Telegram)
* **ESP32 + PIR** (opcional, com MQTT)

---

## 📁 Estrutura (v2)

```
sistema-monitoramento/
├─ olhar_vivo_v2.py           # script principal
├─ .env.sample                 # template de variáveis de ambiente
├─ roi_config.yaml             # polígono da ROI
├─ requirements.txt            # dependências
├─ olhar_vivo.service          # (opcional) systemd para SBC (Linux)
├─ esp32_pir_mqtt.ino          # (opcional) firmware ESP32 + PIR → MQTT
└─ README.md                   # este arquivo
```

Durante a execução são criadas:

* `prints_eventos/` (evidências)
* `logs/` (log rotativo)

---

## 🔧 Configuração via `.env`

Copie o template e edite:

```bash
# Windows (PowerShell)
copy .env.sample .env
# macOS / Linux
cp .env.sample .env
```

Campos importantes (exemplos):

```ini
# Diretórios
OLHARVIVO_BASEDIR=.
OLHARVIVO_EVENT_DIR=prints_eventos
OLHARVIVO_LOG_DIR=logs

# Câmera
OLHARVIVO_CAMERA_INDEX=0        # 0 = webcam padrão; teste 1,2... se tiver mais
OLHARVIVO_FRAME_WIDTH=1280
OLHARVIVO_FRAME_HEIGHT=720
OLHARVIVO_SHOW_WINDOW=true      # false = headless (produção)

# Movimento (MOG2)
OLHARVIVO_MOG2_HISTORY=500
OLHARVIVO_MOG2_VARTHRESH=16
OLHARVIVO_MOG2_SHADOWS=true
OLHARVIVO_MOTION_MIN_AREA=500   # ↑ = mais robusto; ↓ = mais sensível
OLHARVIVO_MOTION_DILATE_ITR=2

# YOLO + filtros geométricos
OLHARVIVO_YOLO_MODEL=yolov8n.pt
OLHARVIVO_YOLO_CONF=0.60
OLHARVIVO_MIN_BOX_W=50
OLHARVIVO_MIN_BOX_H=100
OLHARVIVO_MAX_BOX_W=400
OLHARVIVO_MAX_BOX_H=700
OLHARVIVO_MIN_ASPECT_RATIO=1.5

# Eventos
OLHARVIVO_EVENT_COOLDOWN_SEC=5.0
OLHARVIVO_ANNOTATE_BOX=true
OLHARVIVO_ROI_FILE=roi_config.yaml

# Telegram (opcional)
OLHARVIVO_TG_TOKEN=
OLHARVIVO_TG_CHATID=
```

### Ajustes rápidos (câmera & sensibilidade)

* **Câmera USB:** use `OLHARVIVO_CAMERA_INDEX` (0/1/2…).
* **Câmera IP (RTSP):** substitua no código o `VideoCapture` por `cv2.VideoCapture("rtsp://...")` (se necessário).
* **Resolução/FPS:** 1280×720 @ 15 FPS é um bom começo; reduza se a CPU estiver alta.
* **MOTION_MIN_AREA:** aumente se houver ruído (árvore/vento/sombra); diminua para sensibilidade maior.
* **YOLO_CONF:** 0.55–0.70 equilibra precisão × recall.
* **Caixas & Aspect Ratio:** ajuste para a distância típica do cenário.

---

## 🎯 ROI (Área de Interesse)

Arquivo `roi_config.yaml` (exemplo):

```yaml
polygon:
  - [50, 50]
  - [1230, 50]
  - [1230, 670]
  - [50, 670]
```

Dicas:

* Desenhe um retângulo/ polígono que **exclua** áreas que causam detecções indevidas (rua, árvores, reflexos).
* Pode começar com o frame inteiro e ir **reduzindo**.

---

## 💬 Telegram — Token & Chat ID

> **Obs.: o Lucas já possui TOKEN e CHAT_ID.**
> Caso outro integrante precise gerar:

1. **Token:** @BotFather → `/newbot` → copie o **HTTP API token**.
2. **Chat ID (DM/pessoal):** @userinfobot → retorna um ID **positivo**.
3. **Chat ID (grupo):** adicione o bot no grupo, mande uma mensagem e recupere via API:

**macOS (Terminal):**

```bash
export TOKEN="SEU_TOKEN_AQUI"
curl -s "https://api.telegram.org/bot$TOKEN/getUpdates" | jq .
# apenas o último chat_id
curl -s "https://api.telegram.org/bot$TOKEN/getUpdates" \
 | jq -r '.result[] | (.message // .edited_message // .channel_post // .my_chat_member // .chat_member) | .chat.id' \
 | tail -n1
```

**Windows (PowerShell):**

```powershell
$TOKEN="SEU_TOKEN_AQUI"
(Invoke-WebRequest "https://api.telegram.org/bot$TOKEN/getUpdates").Content
```

Preencha `OLHARVIVO_TG_TOKEN` e `OLHARVIVO_TG_CHATID` no `.env`.

---

## ▶️ Como Rodar

### Windows (PowerShell)

```powershell
cd C:\Users\<SEU_USUARIO>\Desktop\sistema-monitoramento

# 1) venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) dependências
python -m pip install -U pip setuptools wheel
python -m pip install -r .\requirements.txt

# 3) .env e ROI
copy .env.sample .env
notepad .env
notepad roi_config.yaml

# 4) executar
python .\olhar_vivo_v2.py   # pressione 'q' para sair quando houver janela
```

> Se for rodar **sem janela**, defina `OLHARVIVO_SHOW_WINDOW=false` no `.env`.

### macOS (Terminal)

```bash
cd ~/Desktop/sistema-monitoramento

# 1) venv
python3 -m venv .venv
source .venv/bin/activate

# 2) dependências
python -m pip install -U pip setuptools wheel
python -m pip install -r requirements.txt

# 3) .env e ROI
cp .env.sample .env
nano .env
nano roi_config.yaml

# 4) executar
python olhar_vivo_v2.py     # Ctrl+C para sair
```

> macOS pode pedir permissão de câmera (Ajustes → Privacidade → Câmera).

### Orange Pi Zero 2 (Armbian/Debian/Ubuntu)

```bash
# pacotes base
sudo apt update && sudo apt install -y python3-pip python3-venv git

# clonar (ou copiar a pasta do projeto)
git clone <seu_repo> && cd sistema-monitoramento

# venv
python3 -m venv venv
source venv/bin/activate

# dependências
pip install -U pip setuptools wheel
pip install -r requirements.txt

# configurar
cp .env.sample .env
nano .env
nano roi_config.yaml

# teste interativo
python3 olhar_vivo_v2.py
```

**Produção (systemd):**

```bash
sudo mkdir -p /opt/olharvivo/{logs,prints_eventos}
sudo cp olhar_vivo_v2.py .env roi_config.yaml -t /opt/olharvivo
sudo cp olhar_vivo.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now olhar_vivo
journalctl -u olhar_vivo -f
```

---

## ✅ Validação

1. Ajuste a **ROI**.
2. Gere movimento/pessoa na cena.
3. Verifique:

   * 📸 imagem em `prints_eventos/`
   * 📨 mensagem/foto no **Telegram** (se configurado)
   * 🧾 logs em `logs/olhar_vivo.log`

---

## 🧯 Troubleshooting (rápido)

* **`ModuleNotFoundError: cv2`** → instalar dentro da venv:
  `python -m pip install opencv-python`
* **Rodou fora da venv** → garanta que o Python aponta para `...\projeto\.venv\Scripts\python.exe`.
* **Janela não abre no Windows** → `OLHARVIVO_SHOW_WINDOW=false` (headless).
* **Câmera não abre** → feche apps que usam a webcam; teste `OLHARVIVO_CAMERA_INDEX=1`.
* **`.env` não lido** → verifique permissões (Windows: `icacls .env`; Linux: `chmod 600 .env`).
* **Telegram não chega** → teste com uma chamada direta de `sendMessage` (ver seção do Telegram).

---

## 🔌 ESP32-S3-N16R8 + PIR (opcional)

* Firmware: `esp32_pir_mqtt.ino`

  * **GPIO PIR**: 13
  * Publica em: `olharvivo/sensor/pir`
* Requisitos: broker **MQTT** (ex.: Mosquitto) e credenciais no `.ino`.
* **Fusão sugerida (roadmap):** no `olhar_vivo_v2.py`, assinar o tópico e disparar somente se **(visão ∧ PIR)** dentro de 2–5 s.

---

## 🔒 Segurança & Retenção

* **Nunca versione** o `.env` (use `.env.sample`).
* **Proteja** o `.env`:

  * Windows: `icacls .env /reset & icacls .env /inheritance:e & icacls .env /grant:r "%USERNAME%:(R,W)"`
  * Linux: `chmod 600 .env`
* **Retenção** de imagens:

  * Por **tempo** (ex.: 14 dias), **quantidade** (ex.: 1000 arquivos) ou **tamanho** (ex.: 2 GB).
  * Podemos adicionar scripts prontos (PowerShell/Bash) conforme necessidade.

---

## 🗺️ Expansões Futuras (conforme tempo & recursos)

* **Fusão visão ∧ PIR (MQTT)** no detector (reduz ainda mais falsos positivos).
* **Clips de vídeo** (5–10 s) com `ffmpeg` via buffer circular.
* **Painel web** (FastAPI/Flask) com últimos eventos, ROI editável e status.
* **Aceleração por hardware**: TensorRT (Jetson), NPU (RK3588), OpenVINO.
* **Quantização/ONNX** para reduzir latência/consumo.
* **Backup/sincronização** com `rclone` (S3/Backblaze) com criptografia.
* **Telemetria/healthcheck** (uptime, FPS, CPU/RAM).

---

## ✅ Status atual

* **Lucas já possui** `OLHARVIVO_TG_TOKEN` e `OLHARVIVO_TG_CHATID`.
* Branch v2 com arquivos organizados e prontos para teste/produção.