import os
import re

import cv2
import easyocr
from ultralytics import YOLO

from payai.config import OCR_USAR_GPU, YOLO_CONFIANCA_MINIMA, YOLO_MODELO, logger


class Camera:
    def __init__(self, device=0, width=640, height=480, fps=30):
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.cap = None

    def start(self):
        logger.info('Inicializando camera...')
        self.cap = cv2.VideoCapture(self.device)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        if not self.cap.isOpened():
            logger.error('Erro ao acessar camera.')
            return False

        logger.info('Camera pronta.')
        return True

    def read(self):
        if not self.cap:
            return False, None
        return self.cap.read()

    def release(self):
        if self.cap:
            self.cap.release()


def carregar_ocr(usar_gpu=OCR_USAR_GPU):
    try:
        logger.info('Carregando OCR...')
        reader = easyocr.Reader(
            ['pt', 'es'],
            gpu=usar_gpu,
            download_enabled=True,
        )
        logger.info('OCR carregado (%s).', 'GPU' if usar_gpu else 'CPU')
        return reader
    except Exception as erro:
        logger.error(f'Erro carregando OCR: {erro}')
        print(erro)
        return None


def carregar_yolo(caminho_modelo=YOLO_MODELO):
    if not os.path.exists(caminho_modelo):
        logger.warning('Modelo YOLO não encontrado: %s', caminho_modelo)
        return None
    try:
        logger.info('Carregando modelo YOLO de cédulas...')
        yolo_modelo = YOLO(caminho_modelo)
        logger.info('Modelo YOLO de cédulas pronto.')
        return yolo_modelo
    except Exception as erro:
        logger.error(f'Erro carregando modelo YOLO: {erro}')
        return None


def detectar_cedulas(frame, yolo_modelo, confianca_minima=YOLO_CONFIANCA_MINIMA):
    if yolo_modelo is None:
        return []
    resultado = yolo_modelo.predict(
        source=frame,
        conf=confianca_minima,
        verbose=False,
        device='cpu',
    )[0]
    deteccoes = []
    for caixa in resultado.boxes:
        confianca = float(caixa.conf[0])
        classe = int(caixa.cls[0])
        nome = resultado.names[classe]
        x1, y1, x2, y2 = caixa.xyxy[0].int().tolist()
        deteccoes.append((confianca, nome, (x1, y1), (x2, y2)))
    return deteccoes


def detectar_qrcode(frame, detector):
    return detector.detectAndDecode(frame)


def validar_valor(valor):
    try:
        valor = valor.strip().replace(' ', '')
        if ',' not in valor and valor.count('.') == 1:
            valor = valor.replace('.', ',')
        inteiro, centavos = valor.rsplit(',', 1)
        inteiro = inteiro.replace('.', '')
        if not inteiro.isdigit() or not centavos.isdigit() or len(centavos) != 2:
            return False
        return 0.01 <= float(f'{inteiro}.{centavos}') <= 10000
    except (ValueError, AttributeError):
        return False


def filtrar_valor_monetario(texto):
    if not texto:
        return None

    # O EasyOCR confunde O/0 com frequência em displays de sete segmentos.
    texto = texto.upper().replace('O', '0').replace(' ', '')
    padroes = (
        r'R\$?((?:\d{1,3}(?:\.\d{3})+|\d+),\d{2})',
        r'((?:\d{1,3}(?:\.\d{3})+|\d+),\d{2})R\$?',
        r'(?<!\d)((?:\d{1,3}(?:\.\d{3})+|\d+),\d{2})(?!\d)',
        r'(?<!\d)(\d+\.\d{2})(?!\d)',
    )
    for padrao in padroes:
        for encontrado in re.finditer(padrao, texto):
            valor = encontrado.group(1)
            if ',' not in valor and valor.count('.') == 1:
                valor = valor.replace('.', ',')
            if validar_valor(valor):
                return valor
    return None


def buscar_valor_global(frame, reader):
    if reader is None:
        return None

    # -- Redimensiona o quadro para acelerar o OCR, mantendo a proporção:
    altura, largura = frame.shape[:2]

    # -- 640px já é a resolução nativa da câmera. Ampliar todo quadro para 960px
    # aumentava muito o tempo de OCR em CPU sem melhorar proporcionalmente.
    escala = min(1.0, 640 / max(largura, 1))
    imagem = cv2.resize(
        frame,
        None,
        fx=escala,
        fy=escala,
        interpolation=cv2.INTER_CUBIC,
    ) if escala != 1 else frame
    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    cinza = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(cinza)

    # -- Executa o OCR com configuração de allowlist para números e símbolos monetários:
    deteccoes = reader.readtext(
        cinza,
        detail=1,
        paragraph=False,
        batch_size=1,
        width_ths=1.5,
        height_ths=1.0,
        allowlist='0123456789R$,.',
        mag_ratio=1.5,
    )
    candidatos = []
    for bbox, texto, confianca in deteccoes:
        valor = filtrar_valor_monetario(texto)
        if not valor:
            continue
        x = [p[0] / escala for p in bbox]
        y = [p[1] / escala for p in bbox]
        area = (max(x) - min(x)) * (max(y) - min(y))
        # Uma pequena margem evita cortar os caracteres nas bordas do bbox.
        margem_x, margem_y = 5, 4
        topo_esq = (
            max(0, int(min(x)) - margem_x),
            max(0, int(min(y)) - margem_y),
        )
        baixo_dir = (
            min(largura - 1, int(max(x)) + margem_x),
            min(altura - 1, int(max(y)) + margem_y),
        )
        candidatos.append((confianca, area, valor, topo_esq, baixo_dir))

    if not candidatos:
        return None
    confianca, _, valor, topo_esq, baixo_dir = max(
        candidatos,
        key=lambda item: (item[0], item[1]),
    )
    return valor, confianca, topo_esq, baixo_dir
