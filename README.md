# Sistema de Monitoramento com Visão Computacional — **Olhar Vivo v2**

Projeto acadêmico para **detecção de pessoas em tempo real** usando visão computacional embarcada. Captura evidências (imagens), envia notificações via **Telegram** e integra opcionalmente com **ESP32-S3-N16R8 + sensor PIR** para reforço de decisão.

---

## 🧠 Visão Geral

- **Script principal:** `olhar_vivo_v2.py`
- **Pipeline:** Movimento (MOG2) → YOLOv8 (classe pessoa) → Filtros geométricos → Cooldown → Snapshot + Telegram
- **Configuração:** `.env` (parâmetros) + `roi_config.yaml` (polígono da ROI)
- **Execução:** Interativa (com janela) ou headless (produção)

---

## 🧩 Tecnologias Utilizadas

- **Python 3.10+**
- **OpenCV** (captura, MOG2, overlays)
- **Ultralytics YOLOv8** (detecção de pessoas)
- **PyYAML** (ROI)
- **python-dotenv** (configuração)
- **requests** (Telegram)
- **ESP32 + PIR** (opcional, MQTT)

---

## 📁 Estrutura do Projeto

```
sistema-monitoramento/
├─ olhar_vivo_v2.py           # Script principal
├─ .env.sample                # Template de variáveis de ambiente
├─ roi_config.yaml            # Polígono da ROI
├─ requirements.txt           # Dependências
├─ olhar_vivo.service         # (Opcional) systemd para SBC (Linux)
├─ esp32_pir_mqtt.ino         # (Opcional) firmware ESP32 + PIR → MQTT
└─ README.md                  # Este arquivo
```

Durante a execução são criadas:

- `prints_eventos/` (evidências)
- `logs/` (log rotativo)

---

## 🔧 Configuração Rápida

1. **Copie e edite o arquivo de ambiente:**
   ```bash
   cp .env.sample .env
   nano .env
   nano roi_config.yaml
   ```

2. **Principais parâmetros do `.env`:**
   - Diretórios: `OLHARVIVO_BASEDIR`, `OLHARVIVO_EVENT_DIR`, `OLHARVIVO_LOG_DIR`
   - Câmera: `OLHARVIVO_CAMERA_INDEX`, `OLHARVIVO_FRAME_WIDTH`, `OLHARVIVO_FRAME_HEIGHT`, `OLHARVIVO_SHOW_WINDOW`
   - Movimento: `OLHARVIVO_MOG2_HISTORY`, `OLHARVIVO_MOG2_VARTHRESH`, etc.
   - YOLO: `OLHARVIVO_YOLO_MODEL`, `OLHARVIVO_YOLO_CONF`, filtros geométricos
   - Eventos: `OLHARVIVO_EVENT_COOLDOWN_SEC`, `OLHARVIVO_ANNOTATE_BOX`
   - Telegram: `OLHARVIVO_TG_TOKEN`, `OLHARVIVO_TG_CHATID`

---

## 🎯 ROI (Área de Interesse)

Configure o polígono da área de interesse em `roi_config.yaml` para evitar detecções indesejadas (ex: rua, árvores).

```yaml
polygon:
  - [50, 50]
  - [1230, 50]
  - [1230, 670]
  - [50, 670]
```

---

## 💬 Telegram — Token & Chat ID

1. **Token:** Crie com @BotFather.
2. **Chat ID:** Use @userinfobot ou obtenha via API.
3. **Preencha no `.env`:**
   ```
   OLHARVIVO_TG_TOKEN=SEU_TOKEN_AQUI
   OLHARVIVO_TG_CHATID=SEU_CHAT_ID_AQUI
   ```

---

## ▶️ Instalação e Execução no Orange Pi 2

### **Pré-requisitos**

- Orange Pi 2 com Armbian/Debian/Ubuntu
- Python 3.10+ instalado
- Conexão à internet

### **Passo a Passo**

1. **Atualize o sistema e instale pacotes básicos:**
   ```bash
   sudo apt update && sudo apt install -y python3-pip python3-venv git
   ```

2. **Clone o projeto ou copie a pasta:**
   ```bash
   git clone <seu_repo> && cd sistema-monitoramento
   ```

3. **Crie e ative o ambiente virtual:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

4. **Instale as dependências:**
   ```bash
   pip install -U pip setuptools wheel
   pip install -r requirements.txt
   ```
   > **Atenção:** A instalação do PyTorch/YOLO pode ser lenta ou exigir ajustes. Se falhar, considere usar apenas detecção de movimento (MOG2).

5. **Configure os arquivos de ambiente e ROI:**
   ```bash
   cp .env.sample .env
   nano .env
   nano roi_config.yaml
   ```

6. **Execute o script:**
   ```bash
   python3 olhar_vivo_v2.py
   ```
   > Para rodar sem janela, defina `OLHARVIVO_SHOW_WINDOW=false` no `.env`.

### **Execução como Serviço (Opcional)**

1. **Copie arquivos para `/opt/olharvivo`:**
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

1. Ajuste a ROI.
2. Gere movimento/pessoa na cena.
3. Verifique:
   - Imagem em `prints_eventos/`
   - Mensagem/foto no Telegram (se configurado)
   - Logs em `logs/olhar_vivo.log`

---

## 🧯 Troubleshooting

- **Erro ao importar cv2:**  
  Instale dentro da venv: `pip install opencv-python`
- **Janela não abre:**  
  Defina `OLHARVIVO_SHOW_WINDOW=false`
- **Câmera não abre:**  
  Teste outros índices (`OLHARVIVO_CAMERA_INDEX=1`)
- **Telegram não envia:**  
  Teste envio manual via API
- **PyTorch/YOLO não instala:**  
  Use apenas detecção de movimento ou procure versões ARM compatíveis

---

## 🔌 Integração ESP32 + PIR (Opcional)

- Firmware: `esp32_pir_mqtt.ino`
- Publica eventos PIR via MQTT para fusão com visão computacional

---

## 🔒 Segurança & Retenção

- Não versionar `.env`
- Proteja permissões do `.env` (`chmod 600 .env`)
- Use scripts de limpeza para prints antigos (exemplo: `cleanup_prints_days.ps1`)

---

## 🗺️ Expansões Futuras

- Fusão visão ∧ PIR (MQTT)
- Clips de vídeo com ffmpeg
- Painel web (FastAPI/Flask)
- Aceleração por hardware (TensorRT, NPU, OpenVINO)
- Backup/sincronização (rclone)
- Telemetria/healthcheck

---

## ⚠️ Observações Importantes

- O maior gargalo é rodar YOLOv8/PyTorch em ARM. Se não funcionar, use apenas detecção de movimento.
- Reduza resolução da câmera para melhor desempenho (`OLHARVIVO_FRAME_WIDTH=640`, `OLHARVIVO_FRAME_HEIGHT=480`).
- Monitore uso de CPU/RAM durante testes (`htop`, `top`).

---

## 📚 Referências

- [Ultralytics YOLOv8](https://docs.ultralytics.com/)
- [OpenCV Python](https://docs.opencv.org/)
- [Telegram Bot API](https://core.telegram.org/bots/api)

---