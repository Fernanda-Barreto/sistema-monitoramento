# Sistema de Monitoramento com Visão Computacional

Este é um sistema de monitoramento de segurança que utiliza visão computacional para detectar a presença de pessoas em tempo real. O sistema captura imagens da webcam, filtra movimentos e, se uma pessoa for detectada, salva uma foto do evento.

---

## 🚀 Funcionalidades

* **Detecção de Pessoas**: Utiliza o modelo YOLOv8 para identificar pessoas com alta precisão.
* **Filtro Inteligente**: Combina detecção de movimento e filtros de confiança, tamanho e proporção para evitar falsos positivos (como carros ou sombras).
* **Captura de Eventos**: Salva automaticamente prints da tela quando uma pessoa é confirmada, com um timestamp único.
* **Ambiente Virtual**: O projeto é executado em um ambiente virtual para garantir isolamento de dependências.

---

## 🛠️ Requisitos de Instalação

Antes de executar o projeto, você precisa ter o **Python 3.x** instalado.

1.  **Clone o repositório ou baixe os arquivos** do projeto para o seu computador.

2.  **Crie e ative um ambiente virtual** na pasta do projeto.

    * No **Windows**:
        ```bash
        python -m venv venv
        .\venv\Scripts\activate
        ```
    * No **Linux/macOS**:
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```

3.  **Instale as bibliotecas necessárias**. Todas as dependências do projeto estão listadas no arquivo `requirements.txt`.

    ```bash
    pip install -r requirements.txt
    ```

---

## 💻 Como Executar

Com o ambiente virtual ativado, você pode iniciar o sistema com um único comando:

```bash
python main.py
