# Olhar Vivo — Entrega Técnica v2 (Edge + MCU)

Este pacote traz:
- `olhar_vivo_v2.py`: detector com gateamento por movimento + YOLO, ROI opcional, cooldown e envio para Telegram.
- `.env.sample`: parâmetros de calibração e chaves (copie para `.env` e ajuste).
- `roi_config.yaml`: exemplo de polígono de área de interesse.
- `olhar_vivo.service`: unit `systemd` para rodar em produção no SBC.
- `esp32_pir_mqtt.ino`: firmware opcional para ESP32 com PIR publicando em MQTT.

## Instalação rápida (SBC Debian/Ubuntu/Armbian)
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env  # edite tokens, limites e câmera
python3 olhar_vivo_v2.py  # teste interativo (pressione 'q' para sair)
```

## Produção com systemd
```bash
sudo mkdir -p /opt/olharvivo && sudo cp olhar_vivo_v2.py .env roi_config.yaml -t /opt/olharvivo
sudo mkdir -p /opt/olharvivo/logs /opt/olharvivo/prints_eventos
sudo cp olhar_vivo.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now olhar_vivo.service
journalctl -u olhar_vivo -f
```

## Dicas de calibração
1. **ROI**: reduza a área monitorada no `roi_config.yaml` para eliminar árvores, rua ou reflexos externos.
2. **MOTION_MIN_AREA**: aumente se houver muito ruído de fundo; reduza para maior sensibilidade.
3. **YOLO_CONF**: 0.55–0.70 costuma ser bom; maior = menos falsos positivos.
4. **Tamanhos de caixa**: ajuste `MIN/MAX_BOX_W/H` conforme a geometria da cena (distância típica das pessoas).
5. **Cooldown**: `EVENT_COOLDOWN_SEC` evita spam quando a pessoa permanece na cena.
6. **Resolução**: 1280x720 é um bom compromisso; para SBCs fracos, use 960x540 ou 640x480.
7. **Headless**: defina `OLHARVIVO_SHOW_WINDOW=false` para rodar sem janela.

## Integração com Telegram
- Crie um bot no **@BotFather**, copie o token e o `chat_id` (pode ser seu usuário ou um grupo).
- Preencha `OLHARVIVO_TG_TOKEN` e `OLHARVIVO_TG_CHATID` no `.env`.
- O script envia a foto salva assim que um evento é disparado.

## Integração com ESP32 (opcional)
- Grave `esp32_pir_mqtt.ino` no seu ESP32 com o sensor PIR no **GPIO 13**.
- Suba um broker MQTT (ex.: Mosquitto) na rede local.
- Futuro: assinar o tópico no SBC para reforçar a decisão (fusão sensor + visão).

## Segurança & Resiliência
- Use **UPS DC** (12V/5V) para manter SBC e câmera durante quedas breves.
- Armazene eventos em `/opt/olharvivo/prints_eventos` e replique com `rclone` (S3/Backblaze).
- Restrinja permissões do `.env` (contém tokens).

## Roadmap sugerido
- Fusão de evidências (visão + PIR) e publicação de eventos em MQTT.
- Geração de **clips** (5–10 s) com `ffmpeg` a partir de buffer circular.
- Painel web leve (Flask/FastAPI) para dashboards e zonas.
- Quantização do modelo (int8) ou modelo `nano`/`tiny` para SBCs modestos.
```