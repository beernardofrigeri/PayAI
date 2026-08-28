import cv2
import easyocr
import asyncio
import edge_tts
import os
import time
import re
import logging
import threading
import numpy as np
from PIL import ImageFont, ImageDraw, Image
import pygame
import tempfile
from queue import Queue, Empty, Full
from ultralytics import YOLO

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
    os.path.dirname(__file__),
    'runs', 'banknotes-3', 'weights', 'best.pt'
)
# Obs. sobre a função acima:
# Raspberry Pi normalmente não possui GPU compatível com o EasyOCR. Para usar
# uma GPU compatível em outro equipamento, execute com PAYAI_USAR_GPU=1.

# --Configurações de fala:
MODOS = {
    'AUTO': 0,
    'VALORES': 1,
    'QRCODE': 2
}

# --Idiomas suportados:
IDIOMAS = {
    'PT_BR': 0,
    'ES_CO': 1
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
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('payai')

# -- OCR / voz do sistema --
reader = None
ocr_pronto = False
yolo_modelo = None
yolo_pronto = False

# -- Câmera --
cap = None
camera_pronta = False

# -- Classes e funções auxiliares --
class Camera:
    def __init__(self, device=0, width=LARGURA, height=ALTURA, fps=30):
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.cap = None

    def start(self):
        logger.info("Inicializando camera...")
        self.cap = cv2.VideoCapture(self.device)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        if not self.cap.isOpened():
            logger.error("Erro ao acessar camera.")
            return False

        logger.info("Camera pronta.")
        return True

    def read(self):
        if not self.cap:
            return False, None
        return self.cap.read()

    def release(self):
        if self.cap:
            self.cap.release()

# -- Carregamento de fontes --
def carregar_fontes():
    base = os.path.join(os.path.dirname(__file__), "fonts")
    try:
        return {
            'logo_pay':  ImageFont.truetype(os.path.join(base, "GOTHICI.TTF"), 24),
            'logo_ai':   ImageFont.truetype(os.path.join(base, "GOTHICI.TTF"), 24),
            'subtitulo': ImageFont.truetype(os.path.join(base, "GOTHICI.TTF"), 13),
            'secao':     ImageFont.truetype(os.path.join(base, "GOTHICI.TTF"), 14),
            'corpo':     ImageFont.truetype(os.path.join(base, "GOTHICI.TTF"), 14),
            'corpo_b':   ImageFont.truetype(os.path.join(base, "GOTHICBI.TTF"), 14),
            'pequena':   ImageFont.truetype(os.path.join(base, "GOTHICI.TTF"), 11),
            'badge':     ImageFont.truetype(os.path.join(base, "GOTHICBI.TTF"), 13),
            'modo':      ImageFont.truetype(os.path.join(base, "GOTHICBI.TTF"), 14),
            'contorno':  ImageFont.truetype(os.path.join(base, "GOTHICBI.TTF"), 13),
            'hotkey':    ImageFont.truetype(os.path.join(base, "GOTHICBI.TTF"), 15),
            'hotlabel':  ImageFont.truetype(os.path.join(base, "GOTHICI.TTF"), 11),
        }
    except Exception as e:
        logger.warning(f"Fontes do projeto nao encontradas: {e}")
        f = ImageFont.load_default()
        return {k: f for k in ['logo_pay','logo_ai','subtitulo','secao','corpo',
                                'corpo_b','pequena','badge','modo','contorno',
                                'hotkey','hotlabel']}

# -- Inicialização direta das fontes --
FONTES = carregar_fontes()

# -- Variáveis globais de estado --
progresso_loading = 0.0
detector = cv2.QRCodeDetector()
ultimo_tempo         = time.time()
texto_anterior       = ""
frame_count          = 0
ultimo_processamento = 0
ultimo_yolo_processamento = 0
contornos_ativos     = []
ultimos_detectados   = {}
fps_atual = 0
ultimo_fps_tempo = time.time()
tempo_ocr = 0
regioes_detectadas = 0
deteccoes_cedulas   = []
fila_ocr = Queue(maxsize=OCR_QUEUE_SIZE)
fala_lock            = threading.Lock()
ultima_fala          = ""
valor_history        = []
fala_deteccao_tipo    = None
fala_deteccao_cancelamento = None
ultimo_qrcode_visto   = 0.0
qrcode_anunciado      = None
QRCODE_PERDA_GRACA    = 1.5

# -- Estado OCR --
ocr_rodando = False

# -- Estado do padrão do sistema --
modo_atual = MODOS['AUTO']
idioma_atual = IDIOMAS['PT_BR']

# -- Funções utilitárias para desenhos --
def cv2_para_pil(frame):
    # -- Compatibilidade com o módulo draw: converte BGR->RGB:
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

def pil_para_cv2(img):
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

# -- Carregamento do OCR --
def carregar_ocr():
    global reader
    global ocr_pronto
    try:
        logger.info("Carregando OCR...")
        reader = easyocr.Reader(
            ['pt', 'es'],
            gpu=OCR_USAR_GPU,
            download_enabled=True
        )
        ocr_pronto = True
        logger.info("OCR carregado (%s).", "GPU" if OCR_USAR_GPU else "CPU")

    except Exception as e:
        logger.error(f"Erro carregando OCR: {e}")
        print(e)

def carregar_yolo():
    global yolo_modelo, yolo_pronto
    if not os.path.exists(YOLO_MODELO):
        logger.warning("Modelo YOLO não encontrado: %s", YOLO_MODELO)
        return
    try:
        logger.info("Carregando modelo YOLO de cédulas...")
        yolo_modelo = YOLO(YOLO_MODELO)
        yolo_pronto = True
        logger.info("Modelo YOLO de cédulas pronto.")
    except Exception as erro:
        logger.error(f"Erro carregando modelo YOLO: {erro}")

def processar_cedulas(frame):
    global deteccoes_cedulas, contornos_ativos
    if not yolo_pronto or yolo_modelo is None:
        return
    try:
        resultado = yolo_modelo.predict(
            source=frame,
            conf=YOLO_CONFIANCA_MINIMA,
            verbose=False,
            device='cpu'
        )[0]
        deteccoes = []
        for caixa in resultado.boxes:
            confianca = float(caixa.conf[0])
            classe = int(caixa.cls[0])
            nome = resultado.names[classe]
            x1, y1, x2, y2 = caixa.xyxy[0].int().tolist()
            deteccoes.append((confianca, nome, (x1, y1), (x2, y2)))

        deteccoes_cedulas = deteccoes
        contornos_ativos = [
            item for item in contornos_ativos if item[3] != 'CEDULA'
        ]
        for confianca, nome, topo_esq, baixo_dir in deteccoes:
            contornos_ativos.append((
                (topo_esq, baixo_dir),
                f"Cedula R$ {nome} ({confianca:.0%})",
                time.time(),
                'CEDULA'
            ))
    except Exception as erro:
        logger.error(f"Erro na detecção YOLO: {erro}")

# -- Thread de OCR --
class OCRThread(threading.Thread):
    def __init__(self, fila, estat):
        super().__init__(daemon=True)
        self.fila = fila
        self.estat = estat
        self._parar = threading.Event()

    def run(self):
        while not self._parar.is_set():
            try:
                frame = self.fila.get(timeout=0.1)
                processar_valores(frame, self.estat)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Erro loop OCR: {e}")

    def stop(self):
        self._parar.set()

# -- Inicialização da câmera --
# A câmera será iniciada em thread para não bloquear a inicialização:
cap = None
camera_pronta = False

# Instancia a câmera e inicia a captura em thread separada:
_camera = Camera()
def _iniciar_camera():
    global cap, camera_pronta
    logger.info("Inicializando camera...")
    ok = _camera.start()
    if ok:
        cap = _camera.cap
        camera_pronta = True
        logger.info("Camera pronta.")
    else:
        logger.error("Erro ao acessar camera.")

# -- Funções de desenho e interface --
def rect_r(draw, x1, y1, x2, y2, r, fill=None, outline=None, width=1):
    if fill:
        draw.rounded_rectangle([x1, y1, x2, y2], radius=r, fill=fill)
    if outline:
        draw.rounded_rectangle([x1, y1, x2, y2], radius=r, outline=outline, width=width)

def texto_c(draw, texto, cx, y, fonte, cor):
    w = fonte.getlength(texto)
    draw.text((cx - w / 2, y), texto, font=fonte, fill=cor)

# -- Contornos ativos (valores e QR Codes):
def desenhar_contornos(draw, agora):
    for (top_left, bottom_right), texto, timestamp, tipo in contornos_ativos:
        alpha = 255 if tipo in ('VALOR', 'QRCODE') else 220
        cor      = CORES['ACENTO'] if tipo == 'QRCODE' else CORES['AMARELO']

        draw.rectangle([top_left, bottom_right],
                       outline=(*cor, alpha), width=2)
        tx = top_left[0]
        ty = max(top_left[1] - 22, 44)
        bw = int(FONTES['contorno'].getlength(texto)) + 12
        rect_r(draw, tx, ty, tx + bw, ty + 18, r=3,
               fill=(*cor, min(alpha, 210)))
        
        draw.text((tx + 6, ty + 3), texto,
                  font=FONTES['contorno'], fill=CORES['PRETO'])


# -- Desenho da interface principal:
def desenhar_interface(frame, estatisticas, agora):
    img  = cv2_para_pil(frame)
    draw = ImageDraw.Draw(img)
    W, H = img.size

    # -- Header:
    draw.rectangle([0, 0, W, 42], fill=CORES['BG'])
    draw.line(
        [(0, 42), (W, 42)], 
        fill=CORES['BORDA'],
        width=1
    )

    # -- Logo:
    lp = int(FONTES['logo_pay'].getlength("PAY"))
    draw.text((14, 11), "PAY", font=FONTES['logo_pay'], fill=CORES['ACENTO'])
    draw.text((14 + lp + 4, 11), "AI", font=FONTES['logo_ai'], fill=CORES['TEXTO_PRIM'])

    # -- Separador vertical:
    draw.line(
        [(14 + lp + 4 + 26, 13), (14 + lp + 4 + 26, 30)],
        fill=CORES['BORDA'],
        width=1
    )

    # -- Subtitulo:
    draw.text(
        (14 + lp + 4 + 33, 14),
        "Sistema Inteligente",
        font=FONTES['subtitulo'],
        fill=CORES['TEXTO_SEC']
    )

# -- Modo e idioma --
    modos_cfg = {
        0: ("AUTO",    CORES['ACENTO']),
        1: ("VALORES", CORES['AMARELO']),
        2: ("QR CODE", CORES['AZUL']),
    }

    # -- Obter rótulo e cor do modo atual --
    modo_label, cor_modo = modos_cfg.get(
        modo_atual,
        ("AUTO", CORES['ACENTO'])
    )

    # -- Obter rótulo do idioma atual --
    idioma_label = (
        'PT-BR'
        if idioma_atual == IDIOMAS['PT_BR']
        else 'ES-CO'
    )

    # -- Bagde Modo --
    modo_x1 = W - 235
    modo_y1 = 8
    modo_x2 = W - 145
    modo_y2 = 32

    # -- Desenhar retângulo arredondado para o modo --
    rect_r(
        draw,
        modo_x1,
        modo_y1,
        modo_x2,
        modo_y2,
        r=6,
        fill=CORES['CARD_BG'],
        outline=cor_modo,
        width=1
    )

    # -- Desenhar o texto do modo centralizado --
    texto_c(
        draw,
        modo_label,
        (modo_x1 + modo_x2) // 2,
        modo_y1 + 5,
        FONTES['modo'],
        cor_modo
    )

    # -- Bagde Idioma --
    idioma_x1 = W - 135
    idioma_y1 = 8
    idioma_x2 = W - 20
    idioma_y2 = 32

    # -- Desenhar retângulo arredondado para o idioma --
    rect_r(
        draw,
        idioma_x1,
        idioma_y1,
        idioma_x2,
        idioma_y2,
        r=6,
        fill=CORES['CARD_BG'],
        outline=CORES['AZUL'],
        width=1
    )

    # -- Desenhar o texto do idioma centralizado --
    texto_c(
        draw,
        idioma_label,
        (idioma_x1 + idioma_x2) // 2,
        idioma_y1 + 5,
        FONTES['badge'],
        CORES['TEXTO_PRIM']
    )

    # -- Estatísticas --
    if estatisticas:
        stats = estatisticas.obter_estatisticas()
        itens = [
            ("Valores",  str(stats['valores_detectados'])),
            ("QR Codes", str(stats['qrcodes_detectados'])),
            ("Taxa",     f"{stats['detectoes_por_minuto']:.1f}/min"),
            ("FPS",      f"{fps_atual:.1f}"),
            ("OCR",      f"{tempo_ocr:.0f}ms"),
            ("Regioes",  str(regioes_detectadas)),
        ]       
        sy = 50
        for label, valor in itens:

            # Desenhar rótulo à esquerda:
            draw.text(
                (14, sy),
                f"{label}:",
                font=FONTES['pequena'],
                fill=CORES['TEXTO_SEC']
            )
            lw = int(FONTES['pequena'].getlength(f"{label}:")) + 6

            # Desenhar valor à direita do rótulo:
            draw.text(
                (14 + lw, sy),
                valor,
                font=FONTES['corpo_b'],
                fill=CORES['TEXTO_PRIM']
            )
            sy += 16

    # -- Contornos ativos (valores e QR Codes) --
    desenhar_contornos(draw, agora)

    # -- Footer com botões de atalho --
    footer_y = H - 72

    # -- Desenhar retângulo de fundo do footer:
    draw.rectangle(
        [0, footer_y, W, H],
        fill=CORES['BG']
    )

    draw.line(
        [(0, footer_y), (W, footer_y)],
        fill=CORES['BORDA'],
        width=1
    )

    # -- Botões de atalho:
    botoes = [
        ("ESC", "SAIR"),
        ("V", "VALORES"),
        ("Q", "QR CODE"),
        ("A", "AUTO"),
        ("I", "IDIOMA"),
        ("R", "REPETIR"),
        ("S", "PRINT")
    ]

    # -- Calcular largura total dos botões e posição inicial para centralizar:
    card_w  = 72
    gap     = 4
    total_w = len(botoes) * card_w + (len(botoes) - 1) * gap
    bx_ini  = (W - total_w) // 2

    for i, (tecla, desc) in enumerate(botoes):

        # -- Calcular posição do botão:
        cx1 = bx_ini + i * (card_w + gap)
        cx2 = cx1 + card_w
        cy1 = footer_y + 8
        cy2 = H - 8

        # -- Determinar se o botão está ativo (modo atual):
        ativo = (
            (tecla == "A" and modo_atual == 0) or
            (tecla == "V" and modo_atual == 1) or
            (tecla == "Q" and modo_atual == 2)
        )

        cor_fill  = CORES['ACENTO_DIM'] if ativo else CORES['CARD_BG']
        cor_borda = CORES['ACENTO'] if ativo else CORES['BORDA']

        rect_r(
            draw,
            cx1,
            cy1,
            cx2,
            cy2,
            r=6,
            fill=cor_fill,
            outline=cor_borda,
            width=1
        )

        # -- Tecla:
        tw = FONTES['hotkey'].getlength(tecla)

        # -- Desenhar a tecla centralizada no botão:
        draw.text(
            (cx1 + (card_w - tw) / 2, cy1 + 5),
            tecla,
            font=FONTES['hotkey'],
            fill=CORES['ACENTO'] if ativo else CORES['TEXTO_PRIM']
        )

        # -- Label
        dw = FONTES['hotlabel'].getlength(desc)

        # -- Desenhar a descrição centralizada abaixo da tecla:
        draw.text(
            (cx1 + (card_w - dw) / 2, cy2 - 17),
            desc,
            font=FONTES['hotlabel'],
            fill=CORES['ACENTO'] if ativo else CORES['TEXTO_SEC']
        )

    # -- Retornar a imagem final como array OpenCV:
    return pil_para_cv2(img)

# -- Classe para estatísticas de detecção --
class Estatisticas:
    def __init__(self):
        self.valores_detectados = 0
        self.qrcodes_detectados = 0
        self.erros_ocr          = 0
        self.inicio             = time.time()

    def registrar_deteccao(self, tipo):
        if tipo == 'VALOR':    
            self.valores_detectados += 1
        elif tipo == 'QRCODE': 
            self.qrcodes_detectados += 1

    def registrar_erro(self):
        self.erros_ocr += 1

    def obter_estatisticas(self):
        t     = time.time() - self.inicio
        total = self.valores_detectados + self.qrcodes_detectados
        return {
            'tempo_execucao':       t,
            'valores_detectados':   self.valores_detectados,
            'qrcodes_detectados':   self.qrcodes_detectados,
            'erros_ocr':            self.erros_ocr,
            'detectoes_por_minuto': total / (t / 60) if t > 0 else 0,
        }

# -- Conversão de números para texto em português --
def _num_pt(n):
    if n == 0: 
        return "zero"
    if n <= 9:
        return ['','um','dois','tres','quatro','cinco','seis','sete','oito','nove'][n]
    if n <= 19:
        return ['dez','onze','doze','treze','quatorze','quinze',
                'dezesseis','dezessete','dezoito','dezenove'][n-10]
    if n <= 99:
        dez = ['','','vinte','trinta','quarenta','cinquenta',
               'sessenta','setenta','oitenta','noventa']
        d, u = n // 10, n % 10
        return dez[d] if u == 0 else f"{dez[d]} e {_num_pt(u)}"
    if n <= 999:
        if n == 100: 
            return "cem"
        c = ['','cento','duzentos','trezentos','quatrocentos','quinhentos',
             'seiscentos','setecentos','oitocentos','novecentos']
        cent, r = n // 100, n % 100
        return c[cent] + (" e " + _num_pt(r) if r else "")
    return f"{n:,}".replace(",", ".")

# -- Conversão para espanhol --
def numero_es(n):
    unidades = {
        0: 'cero',
        1: 'uno',
        2: 'dos',
        3: 'tres',
        4: 'cuatro',
        5: 'cinco',
        6: 'seis',
        7: 'siete',
        8: 'ocho',
        9: 'nueve'
    }
    especiais = {
        10: 'diez',
        11: 'once',
        12: 'doce',
        13: 'trece',
        14: 'catorce',
        15: 'quince'
    }
    dezenas = {
        20: 'veinte',
        30: 'treinta',
        40: 'cuarenta',
        50: 'cincuenta',
        60: 'sesenta',
        70: 'setenta',
        80: 'ochenta',
        90: 'noventa'
    }
    if n < 10:
        return unidades[n]
    if n in especiais:
        return especiais[n]
    if n < 20:
        return 'dieci' + unidades[n - 10]
    if n < 30:
        return 'veinti' + unidades[n - 20]
    if n < 100:
        d = (n // 10) * 10
        r = n % 10
        if r == 0:
            return dezenas[d]
        return f"{dezenas[d]} y {unidades[r]}"
    return str(n)

# -- Voz e fala --
async def falar_edge(texto, voz="es-CO-GonzaloNeural", cancelar_evento=None):
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        caminho = fp.name
    communicate = edge_tts.Communicate(texto, voz)
    try:
        await communicate.save(caminho)
        if cancelar_evento and cancelar_evento.is_set():
            return
        pygame.mixer.music.load(caminho)
        pygame.mixer.music.play()

        # -- Aguarda até que a reprodução termine ou seja cancelada:
        while pygame.mixer.music.get_busy():
            if cancelar_evento and cancelar_evento.is_set():
                pygame.mixer.music.stop()
                break
            await asyncio.sleep(0.05)
    finally:
        try:
            pygame.mixer.music.unload()
        except pygame.error:
            pass
        if os.path.exists(caminho):
            try:
                os.remove(caminho)
            except OSError as erro:
                logger.warning(f"Não foi possível remover áudio temporário: {erro}")

# -- Função de fala com controle de idioma e cancelamento:
def falar_texto(texto, idioma=None, ultima_fala_ref=None, cancelar_evento=None):
    global ultima_fala
    ultima_fala = texto
    if idioma is None:
        idioma = idioma_atual
    def _falar():
        with fala_lock:
            try:
                if cancelar_evento and cancelar_evento.is_set():
                    return
                tf = texto
                mr = re.search(r'(\d+)\s*reais', texto.lower())
                mc = re.search(r'(\d+)\s*centavos', texto.lower())
                # -- Português (Brasil):
                if idioma == IDIOMAS['PT_BR']:
                    if mr:
                        n = int(mr.group(1))
                        tf = f"{_num_pt(n)} reais"
                        if mc:
                            tf += f" e {_num_pt(int(mc.group(1)))} centavos"
                    elif mc:
                        tf = f"{_num_pt(int(mc.group(1)))} centavos"
                # -- Espanhol (Colômbia):
                elif idioma == IDIOMAS['ES_CO']:
                    if mr:
                        n = int(mr.group(1))
                        tf = f"{numero_es(n)} pesos colombianos"
                    elif mc:
                        tf = f"{numero_es(int(mc.group(1)))} centavos"
                    tf = tf.replace(
                        'QR Code detectado',
                        'Código QR detectado'
                    )
                    tf = tf.replace(
                        'Modo automatico ativado',
                        'Modo automático activado'
                    )
                    tf = tf.replace(
                        'Modo valores ativado',
                        'Modo valores activado'
                    )
                    tf = tf.replace(
                        'Modo QR Code ativado',
                        'Modo código QR activado'
                    )
                    tf = tf.replace(
                        'Screenshot salvo',
                        'Captura guardada'
                    )

                # -- Seleção de voz e execução do TTS:
                if idioma == IDIOMAS['ES_CO']:
                    asyncio.run(
                        falar_edge(
                            tf,
                            "es-CO-GonzaloNeural",
                            cancelar_evento
                        )
                    )
                else:
                    asyncio.run(
                        falar_edge(
                            tf,
                            "pt-BR-AntonioNeural",
                            cancelar_evento
                        )
                    )
            except Exception as e:
                logger.error(f"Erro na fala: {e}")

# -- Inicia a thread de fala como daemon para não bloquear o programa principal:
    threading.Thread(target=_falar, daemon=True).start()

# -- Formatação de valores monetários para fala --

# -- Formata o valor monetário para fala, considerando o idioma:
def formatar_fala(val, idioma=IDIOMAS['PT_BR']):
    p = val.strip().split(',')
    i = int(p[0].replace('.', '').strip())
    c = int(p[1].strip())
    if idioma == IDIOMAS['ES_CO']:
        if c == 0:
            return f"{i} pesos colombianos"
        if i == 0:
            return f"{c} centavos"
        return f"{i} pesos colombianos e {c} centavos"
    if c == 0:
        return f"{i} reais"
    if i == 0:
        return f"{c} centavos"
    return f"{i} reais e {c} centavos"

# -- Evita repetição de detecção de valores monetários em um curto período de tempo:
def evitar_repeticao(texto, minimo=5):
    global ultimo_tempo, texto_anterior, valor_history
    agora = time.time()

    # -- Verifica histórico recente (últimos 5 valores):
    valor_history.append((texto, agora))
    if len(valor_history) > VALOR_HISTORY_BUFFER:
        valor_history.pop(0)

    # -- Se o mesmo texto foi detecado nos últimos 'minimo' segundos, ignora:
    for hist_texto, hist_tempo in valor_history[:-1]:
        if hist_texto == texto and (agora - hist_tempo) < minimo:
            return False

    # -- Atualiza o último texto e tempo detectados:
    texto_anterior, ultimo_tempo = texto, agora
    return True

# -- Evita repetição de detecção de QR Codes em um curto período de tempo:
def pode_detectar(texto, cooldown=8):
    # -- Verifica se o texto pode ser detectado novamente (com cooldown):
    agora = time.time()

    # -- Evita crescimento contínuo quando aparecem muitos QR Codes diferentes:
    expirados = [chave for chave, instante in ultimos_detectados.items()
                 if agora - instante >= cooldown]
    for chave in expirados:
        del ultimos_detectados[chave]

    if texto in ultimos_detectados:
        if agora - ultimos_detectados[texto] < cooldown:
            return False

    ultimos_detectados[texto] = agora
    return True

# -- Contornos ativos (valores e QR Codes) --
def atualizar_contornos():
    global contornos_ativos
    agora = time.time()
    contornos_ativos = [
        item for item in contornos_ativos
        if item[3] in ('VALOR', 'QRCODE') or (agora - item[2]) < CONTORNO_TEMPO_VIDA
    ]

# -- Define um contorno ativo para exibição na interface:
def definir_contorno_ativo(tl, br, texto, tipo):
    # -- Mantém somente a detecção atual de cada tipo, sem rastros antigos:
    global contornos_ativos
    contornos_ativos = [item for item in contornos_ativos if item[3] != tipo]
    contornos_ativos.append(((tl, br), texto, time.time(), tipo))

# -- Remove contornos ativos de um tipo específico:
def remover_contorno(tipo):
    global contornos_ativos
    contornos_ativos = [item for item in contornos_ativos if item[3] != tipo]

# -- Processamento de QR Codes --
def processar_qrcode(frame, estat):
    global ultimo_qrcode_visto, qrcode_anunciado
    try:
        data, bbox, _ = detector.detectAndDecode(frame)
    except cv2.error as e:
        logger.warning(f"Erro QRCodeDetector: {e}")
        return
    if not data or not data.strip():
        # A decodificação pode falhar em alguns frames mesmo com o QR visível.
        # A fala não é cancelada: o Edge-TTS pode ainda estar gerando o áudio.
        if time.time() - ultimo_qrcode_visto > QRCODE_PERDA_GRACA:
            remover_contorno('QRCODE')
            qrcode_anunciado = None
        return

    # -- Atualiza o tempo do último QR Code visto:
    ultimo_qrcode_visto = time.time()

    # -- Evita repetição de detecção do mesmo QR Code em um curto período:
    if bbox is not None:
        pts = bbox.astype(int).reshape(-1, 2)
        tl = (int(pts[:, 0].min()), int(pts[:, 1].min()))
        br = (int(pts[:, 0].max()), int(pts[:, 1].max()))
        # -- O conteúdo pode incluir chave Pix ou URL de pagamento; não o exiba:
        definir_contorno_ativo(tl, br, "QR Code detectado", 'QRCODE')
    else:
        remover_contorno('QRCODE')

    # -- Anuncia somente ao encontrar um QR novo. Mantê-lo diante da câmera não
    # reinicia a fala repetidamente; após sumir, ele poderá ser anunciado outra vez:
    if data != qrcode_anunciado:
        qrcode_anunciado = data
        logger.info("QR Code detectado (%d caracteres).", len(data))
        estat.registrar_deteccao('QRCODE')
        iniciar_fala_deteccao("QR Code detectado", idioma_atual, 'QRCODE')

# -- Processamento de valores monetários com OCR --

# -- Lê o quadro inteiro e preserva a proporção da imagem, pois depender de
# contornos descartava com frequência o visor antes mesmo do OCR ser chamado:
def validar_valor(valor):
    try:
        valor = valor.strip().replace(' ', '')
        if ',' not in valor and valor.count('.') == 1:
            valor = valor.replace('.', ',')
        inteiro, centavos = valor.rsplit(',', 1)
        inteiro = inteiro.replace('.', '')
        if not inteiro.isdigit() or not centavos.isdigit() or len(centavos) != 2:
            return False
        return 0.01 <= float(f"{inteiro}.{centavos}") <= 10000
    except (ValueError, AttributeError):
        return False

# -- Filtra e valida valores monetários detectados pelo OCR:
def filtrar_valor_monetario(texto):
    if not texto:
        return None

    # O EasyOCR confunde O/0 com frequência em displays de sete segmentos.
    texto = texto.upper().replace('O', '0').replace(' ', '')
    padroes = (
        r'R\$?(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'(\d{1,3}(?:\.\d{3})*,\d{2})R\$?',
        r'(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'(\d{1,3}\.\d{2})',
    )
    for padrao in padroes:
        for encontrado in re.finditer(padrao, texto):
            valor = encontrado.group(1)
            if ',' not in valor and valor.count('.') == 1:
                valor = valor.replace('.', ',')
            if validar_valor(valor):
                return valor
    return None

# -- Busca o valor monetário global no quadro, retornando valor, confiança e contorno:
def buscar_valor_global(frame):
    if reader is None:
        return None

    # -- Redimensiona o quadro para acelerar o OCR, mantendo a proporção:
    altura, largura = frame.shape[:2]

    # -- 640px já é a resolução nativa da câmera. Ampliar todo quadro para 960px
    # aumentava muito o tempo de OCR em CPU sem melhorar proporcionalmente.
    escala = min(1.0, 640 / max(largura, 1))
    imagem = cv2.resize(frame, None, fx=escala, fy=escala,
                        interpolation=cv2.INTER_CUBIC) if escala != 1 else frame
    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    cinza = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(cinza)

    # -- Executa o OCR com configuração de allowlist para números e símbolos monetários:
    deteccoes = reader.readtext(
        cinza, detail=1, paragraph=False, batch_size=1,
        width_ths=1.5, height_ths=1.0,
        allowlist='0123456789R$,.', mag_ratio=1.5,
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
        topo_esq = (max(0, int(min(x)) - margem_x),
                    max(0, int(min(y)) - margem_y))
        baixo_dir = (min(largura - 1, int(max(x)) + margem_x),
                     min(altura - 1, int(max(y)) + margem_y))
        candidatos.append((confianca, area, valor,
                           topo_esq, baixo_dir))

    if not candidatos:
        return None
    confianca, _, valor, topo_esq, baixo_dir = max(candidatos, key=lambda item: (item[0], item[1]))
    return valor, confianca, topo_esq, baixo_dir

# -- Remove o contorno de valor ativo:
def remover_contorno_valor():
    remover_contorno('VALOR')

# -- Inicia a fala de detecção, cancelando qualquer fala anterior do mesmo tipo:
def parar_fala_deteccao(tipo):
    global fala_deteccao_tipo, fala_deteccao_cancelamento
    if fala_deteccao_tipo != tipo or fala_deteccao_cancelamento is None:
        return
    fala_deteccao_cancelamento.set()
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except pygame.error:
        pass
    fala_deteccao_tipo = None
    fala_deteccao_cancelamento = None

# -- Inicia a fala de detecção, cancelando qualquer fala anterior do mesmo tipo:
def iniciar_fala_deteccao(texto, idioma, tipo):
    global fala_deteccao_tipo, fala_deteccao_cancelamento
    parar_fala_deteccao(fala_deteccao_tipo)
    fala_deteccao_tipo = tipo
    fala_deteccao_cancelamento = threading.Event()
    falar_texto(texto, idioma, None, fala_deteccao_cancelamento)

# -- Processa os valores monetários detectados no quadro, atualizando contornos e estatísticas:
def processar_valores(frame, estat):
    global ocr_rodando, tempo_ocr, regioes_detectadas
    if reader is None:
        return
    ocr_rodando = True
    inicio = time.time()
    try:
        resultado = buscar_valor_global(frame)
        regioes_detectadas = 1 if resultado else 0
        if not resultado:
            remover_contorno_valor()
            parar_fala_deteccao('VALOR')
            return
        valor, confianca, topo_esq, baixo_dir = resultado
        if confianca < OCR_CONFIANCA_MINIMA:
            remover_contorno_valor()
            parar_fala_deteccao('VALOR')
            return
        texto_contorno = (f"COL$ {valor} pesos colombianos"
                           if idioma_atual == IDIOMAS['ES_CO']
                           else f"R$ {valor} reais")
        definir_contorno_ativo(topo_esq, baixo_dir, texto_contorno, 'VALOR')
        fala = formatar_fala(valor, idioma_atual)
        if evitar_repeticao(fala) and pode_detectar(fala):
            logger.info(f"Valor: {fala} (conf {confianca:.2f})")
            estat.registrar_deteccao('VALOR')
            iniciar_fala_deteccao(fala, idioma_atual, 'VALOR')
    except Exception as erro:
        logger.error(f"Erro OCR: {erro}")
        estat.registrar_erro()
    finally:
        tempo_ocr = (time.time() - inicio) * 1000
        ocr_rodando = False

# -- Inicializa a classe de estatísticas:
estatisticas = Estatisticas()

# -- Mensagem de inicialização e log:
print(f"[INFO] Aponte a camera para o visor da maquininha ou QR Code...")
logger.info(f"Sistema PayAI iniciado - {LARGURA}x{ALTURA}")

# -- Thread de carregamento OCR --
threading.Thread(
    target=carregar_ocr,
    daemon=True
).start()

threading.Thread(
    target=carregar_yolo,
    daemon=True
).start()

def _iniciar_camera_thread():
    global cap, camera_pronta
    ok = _camera.start()
    if ok:
        cap = _camera.cap
        camera_pronta = True

threading.Thread(
    target=_iniciar_camera_thread,
    daemon=True
).start()

# -- Loop principal --
_ocr_thread = OCRThread(fila_ocr, estatisticas)
_ocr_thread.start()

try:
    while True:
    # -- Splash screen --
        if not camera_pronta or not ocr_pronto:
            splash = np.zeros((ALTURA, LARGURA, 3), dtype=np.uint8)
            splash[:] = CORES['BG']
            img = cv2_para_pil(splash)
            draw = ImageDraw.Draw(img)
            texto_c(
                draw,
                "PAYAI",
                LARGURA // 2,
                165,
                FONTES['logo_pay'],
                CORES['ACENTO']
            )
            texto_c(
                draw,
                "Inicializando sistema...",
                LARGURA // 2,
                225,
                FONTES['corpo_b'],
                CORES['TEXTO_PRIM']
            )
            status = []
            if not camera_pronta:
                status.append("Camera")
            if not ocr_pronto:
                status.append("OCR")
            mensagens_loading = [
                "Inicializando componentes",
                "Preparando sistema",
                "Carregando interface",
                "Verificando modulos",
                "Inicializando camera",
                "Preparando reconhecimento",
                "Otimizando OCR",
                "Configurando acessibilidade",
                "Preparando sistema de voz",
                "Carregando deteccao inteligente",
                "Verificando desempenho",
                "Sincronizando componentes",
                "Iniciando visao computacional",
                "Configurando analise inteligente",
                "Inicializando assistente visual",
                "Preparando leitura automatica",
                "Sincronizando reconhecimento",
                "Aplicando melhorias de desempenho",
                "Verificando integridade do sistema",
                "Otimizando inicializacao",
                "Preparando captura de imagem",
                "Ativando componentes principais",
                "Preparando ambiente de execucao",
            ]
            indice_msg = int(
                time.time() * 0.45
            ) % len(mensagens_loading)

            texto_status = mensagens_loading[indice_msg]
            texto_status += f" | CAM:{camera_pronta} OCR:{ocr_pronto}"

            texto_c(
                draw,
                texto_status,
                LARGURA // 2,
                255,
                FONTES['pequena'],
                CORES['TEXTO_SEC']
            )
            # -- Desenha a barra simples:
            draw.rounded_rectangle(
                [170, 305, 470, 317],
                radius=5,
                fill=CORES['CARD_BG']
            )
            # -- Atualiza o progresso suavemente --
            alvo = 0.90

            if camera_pronta and ocr_pronto:
                alvo = 1.0
            if progresso_loading < alvo:
                progresso_loading += 0.025
            progresso_loading = min(
                progresso_loading,
                alvo
            )
            largura = int(300 * progresso_loading)
            draw.rounded_rectangle(
                [170, 305, 170 + largura, 317],
                radius=5,
                fill=CORES['ACENTO']
            )

            # -- Aplica brilho suave e contínuo --
            if largura > 80:
                barra_x1 = 170
                barra_x2 = 170 + largura
                brilho_total = largura
                brilho = (
                    time.time() * 70
                ) % brilho_total
                shine_x = barra_x1 + brilho
                brilho_largura = 28

                # -- Evita que o brilho ultrapasse a barra:
                if shine_x < barra_x2:
                    # -- Aplica fade perto da entrada:
                    entrada = min(
                        1.0,
                        max(
                            0,
                            (shine_x - barra_x1) / 25
                        )
                    )
                    # -- Aplica fade perto da saída:
                    saida = min(
                        1.0,
                        max(
                            0,
                            (barra_x2 - shine_x) / 25
                        )
                    )
                    intensidade = min(
                        entrada,
                        saida
                    )
                    branco = int(
                        140 + (115 * intensidade)
                    )
                    draw.rounded_rectangle(
                        [
                            shine_x - 2,
                            307,
                            shine_x + brilho_largura,
                            315
                        ],
                        radius=4,
                        fill=(branco, branco, branco)
                    )
            splash = pil_para_cv2(img)

            cv2.imshow(
                "PayAI - Sistema Inteligente",
                splash
            )

            if cv2.waitKey(1) & 0xFF == 27:
                logger.info("Encerrado pelo usuario durante a inicializacao")
                break
            continue
        # -- Câmera normal --
        ret, frame = cap.read()

        if not ret:
            break

        frame_count += 1

        if frame_count % 10 == 0:
            agora_fps = time.time()
            fps_atual = 10 / (
                agora_fps - ultimo_fps_tempo
            )
            ultimo_fps_tempo = agora_fps

        agora = time.time()
        atualizar_contornos()

        if modo_atual in (MODOS['AUTO'], MODOS['VALORES']):
            if (
                agora - ultimo_processamento > OCR_INTERVAL and
                frame_count % SKIP_FRAMES == 0
            ):
                ultimo_processamento = agora
                try:
                    fila_ocr.put_nowait(frame.copy())
                except Full:
                    pass

        if modo_atual in (MODOS['AUTO'], MODOS['QRCODE']):
            processar_qrcode(frame, estatisticas)

        if modo_atual in (MODOS['AUTO'], MODOS['VALORES']):
            if agora - ultimo_yolo_processamento > YOLO_INTERVAL:
                ultimo_yolo_processamento = agora
                processar_cedulas(frame)

        frame_final = desenhar_interface(frame, estatisticas, agora)
        cv2.imshow("PayAI - Sistema Inteligente", frame_final)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            logger.info("Encerrado pelo usuario")
            break
        elif key in (ord('v'), ord('V')):
            modo_atual = MODOS['VALORES']
            remover_contorno('QRCODE')
            parar_fala_deteccao('QRCODE')
            qrcode_anunciado = None
            falar_texto("Modo valores ativado", idioma_atual, None)
        elif key in (ord('q'), ord('Q')):
            modo_atual = MODOS['QRCODE']
            remover_contorno('VALOR')
            parar_fala_deteccao('VALOR')
            qrcode_anunciado = None
            falar_texto("Modo QR Code ativado", idioma_atual, None)
        elif key in (ord('a'), ord('A')):
            modo_atual = MODOS['AUTO']
            qrcode_anunciado = None
            falar_texto("Modo automatico ativado", idioma_atual, None)
        elif key in (ord('i'), ord('I')):
            if idioma_atual == IDIOMAS['PT_BR']:
                idioma_atual = IDIOMAS['ES_CO']
                falar_texto('Idioma español activado', idioma_atual, None)
            else:
                idioma_atual = IDIOMAS['PT_BR']
                falar_texto('Idioma portugues ativado', idioma_atual, None)
        elif key in (ord('s'), ord('S')):
            nome = f"screenshot_{time.strftime('%Y%m%d_%H%M%S')}.png"
            cv2.imwrite(nome, frame_final)
            logger.info(f"Screenshot: {nome}")
            falar_texto("Screenshot salvo", idioma_atual, None)
        elif key in (ord('r'), ord('R')):
            if ultima_fala:
                falar_texto(ultima_fala, idioma_atual, None)

except Exception as e:
    logger.error(f"Erro critico: {e}")
finally:
    try:
        parar_fala_deteccao('VALOR')
        parar_fala_deteccao('QRCODE')
    except Exception:
        pass
    if cap:
        try:
            cap.release()
        except Exception:
            pass
    else:
        # -- Libera a câmera gerenciada pela classe:
        try:
            _camera.release()
        except Exception:
            pass

    cv2.destroyAllWindows()
    logger.info(f"Estatisticas finais: {estatisticas.obter_estatisticas()}")
    logger.info("Sistema PayAI finalizado")
    
    # -- Para a thread OCR:
    try:
        _ocr_thread.stop()
    except Exception:
        pass