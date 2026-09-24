# PayAI 🤖💳

Sistema inteligente de acessibilidade para leitura de valores e QR Codes em maquininhas de cartão.

O entrypoint permanece em [PayAI.py](PayAI.py), mas a arquitetura foi modularizada
no pacote [`payai/`](payai). O sistema usa visão computacional, OCR e síntese de
voz para fornecer feedback sonoro sobre valores e QR Codes detectados pela câmera.

---

## ✨ Principais funcionalidades

- Reconhecimento automático de valores monetários na tela da maquininha
- Detecção de QR Codes em tempo real
- Feedback por voz (suporte a múltiplos backends)
- Suporte a Português (PT-BR) e Espanhol (ES-CO)
- Antirrepetição inteligente e histórico curto para evitar leituras duplicadas
- Estatísticas em tempo real e overlay na imagem
- Captura de screenshots

---

## 🛠 Tecnologias

- Python
- OpenCV
- EasyOCR
- Pillow (PIL)
- NumPy
- pyttsx3 / edge-tts (síntese de voz)
- pygame (reprodução de áudio)

---

## 📦 Instalação

1. Crie e ative um ambiente virtual:

Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1  # ou .venv\Scripts\activate
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Instale as dependências:

```bash
pip install -r requirements.txt
```

> Se preferir, verifique `requirements.txt` para versões específicas.

---

## ▶️ Uso

Execute diretamente o arquivo principal:

```bash
python PayAI.py
```

Observações:
- No Windows, o script tenta carregar fontes em `C:/Windows/Fonts/` (Segoe UI). Se não encontradas, usa a fonte padrão do PIL.
- O programa acessa a câmera; garanta permissão de uso e conexão de dispositivo.

---

## ⌨️ Atalhos (em tempo de execução)

- `A` — Modo Automático (valores + QR)
- `V` — Modo Leitura de Valores
- `Q` — Modo QR Code
- `I` — Alternar idioma (PT-BR / ES-CO)
- `R` — Repetir última leitura
- `S` — Salvar screenshot
- `ESC` — Sair

---

## 📁 Estrutura do repositório

```text
.
├── PayAI.py
├── payai
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── detectors.py
│   ├── rendering.py
│   └── speech.py
├── tests
│   ├── test_money_parser.py
│   ├── test_speech_formatting.py
│   └── test_speech_worker.py
├── prepare_yolo_dataset.py
├── train_banknotes.py
├── requirements-yolo.txt
├── README.md
└── requirements.txt
```

## Treinamento experimental de cédulas

O dataset de cédulas atualmente está organizado por denominação, mas não
possui caixas delimitadoras. Para validar o pipeline de detecção, gere rótulos
iniciais cobrindo a imagem inteira:

```powershell
python prepare_yolo_dataset.py
pip install -r requirements-yolo.txt
python train_banknotes.py
```

Esse treinamento é apenas um protótipo: as imagens atuais mostram a cédula
isolada e ocupando quase todo o quadro. Para reconhecer cédulas na câmera,
adicione fotos com diferentes distâncias, ângulos, iluminação e fundos, e
anote a caixa real de cada cédula. O modelo treinado será salvo em
`runs/banknotes/weights/best.pt`.

---

## Notas e dicas

- O processamento OCR pode usar GPU se o `easyocr.Reader` for inicializado com `gpu=True` e houver suporte.
- Se houver problemas com o backend de áudio, experimente instalar apenas `pyttsx3` ou `edge-tts` conforme sua preferência.
- Logs são gravados em `payai.log` no diretório de execução.

---

## Autor

Bernardo Girardi Frigeri