import logging
import os

from PIL import ImageFont

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# --Configurações do sistema--

# --Tamanho da janela de captura:
LARGURA = 640
ALTURA = 480

# --Configurações de OCR:
OCR_INTERVAL = 0.35
SKIP_FRAMES = 4
RESIZE_OCR = (320, 240)
OCR_CONFIANCA_MINIMA = 0.55
CONTORNO_TEMPO_VIDA = 0.8
OCR_QUEUE_SIZE = 1
VALOR_HISTORY_BUFFER = 5
OCR_USAR_GPU = os.environ.get('PAYAI_USAR_GPU', '0') == '1'
YOLO_INTERVAL = 0.5
YOLO_CONFIANCA_MINIMA = 0.01
YOLO_MODELO = os.path.join(
    BASE_DIR,
    'runs',
    'banknotes-3',
    'weights',
    'best.pt',
)
QRCODE_PERDA_GRACA = 1.5

# Obs. sobre a função acima:
# Raspberry Pi normalmente não possui GPU compatível com o EasyOCR. Para usar
# uma GPU compatível em outro equipamento, execute com PAYAI_USAR_GPU=1.

# --Configurações de fala:
MODOS = {
    'AUTO': 0,
    'VALORES': 1,
    'QRCODE': 2,
}

# --Idiomas suportados:
IDIOMAS = {
    'PT_BR': 0,
    'ES_CO': 1,
}

# --Cores usadas na interface:
CORES = {
    'BRANCO':       (255, 255, 255),
    'PRETO':        (0,   0,   0),
    'BG':           (0,  0,  0),
    'CARD_BG':      (30,  35,  44),
    'BORDA':        (48,  54,  64),
    'TEXTO_SEC':    (130, 140, 160),
    'TEXTO_PRIM':   (220, 225, 235),
    'ACENTO':       (0,   200, 180),
    'ACENTO_DIM':   (0,   60,  54),
    'AMARELO':      (230, 180,   0),
    'AZUL':         (80,  150, 255),
    'VERDE_STATUS': (50,  200, 100),
}

# --Configuração de logging--
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('payai.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger('payai')


def carregar_fontes():
    base = os.path.join(BASE_DIR, 'fonts')
    try:
        return {
            'logo_pay': ImageFont.truetype(os.path.join(base, 'GOTHICI.TTF'), 24),
            'logo_ai': ImageFont.truetype(os.path.join(base, 'GOTHICI.TTF'), 24),
            'subtitulo': ImageFont.truetype(os.path.join(base, 'GOTHICI.TTF'), 13),
            'secao': ImageFont.truetype(os.path.join(base, 'GOTHICI.TTF'), 14),
            'corpo': ImageFont.truetype(os.path.join(base, 'GOTHICI.TTF'), 14),
            'corpo_b': ImageFont.truetype(os.path.join(base, 'GOTHICBI.TTF'), 14),
            'pequena': ImageFont.truetype(os.path.join(base, 'GOTHICI.TTF'), 11),
            'badge': ImageFont.truetype(os.path.join(base, 'GOTHICBI.TTF'), 13),
            'modo': ImageFont.truetype(os.path.join(base, 'GOTHICBI.TTF'), 14),
            'contorno': ImageFont.truetype(os.path.join(base, 'GOTHICBI.TTF'), 13),
            'hotkey': ImageFont.truetype(os.path.join(base, 'GOTHICBI.TTF'), 15),
            'hotlabel': ImageFont.truetype(os.path.join(base, 'GOTHICI.TTF'), 11),
        }
    except Exception as erro:
        logger.warning(f"Fontes do projeto nao encontradas: {erro}")
        fonte_padrao = ImageFont.load_default()
        return {
            chave: fonte_padrao
            for chave in [
                'logo_pay',
                'logo_ai',
                'subtitulo',
                'secao',
                'corpo',
                'corpo_b',
                'pequena',
                'badge',
                'modo',
                'contorno',
                'hotkey',
                'hotlabel',
            ]
        }

