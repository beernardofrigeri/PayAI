import re

import cv2
import easyocr

from payai.config import OCR_USAR_GPU, logger


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


def _ler_qrcode_seguro(detector, imagem):
    # O OpenCV lança cv2.error quando o quadrilatero do QR degenera (area 0),
    # algo comum com o código inclinado ou borrado — validamos antes de
    # decodificar para evitar o crash e aproveitar a chance de nova tentativa.
    # O 4o valor de retorno (achou_candidato) indica se um quadrilatero foi ao
    # menos localizado, mesmo que a decodificacao tenha falhado — usado para
    # decidir, de forma barata, se vale a pena investir em novas tentativas.
    try:
        ok, pontos = detector.detect(imagem)
    except cv2.error:
        return '', None, None, False
    if not ok or pontos is None:
        return '', None, None, False
    area = cv2.contourArea(pontos.reshape(-1, 1, 2).astype('float32'))
    if area <= 0:
        return '', None, None, True
    try:
        dados, pontos_retos = detector.decode(imagem, pontos)[:2]
    except cv2.error:
        return '', None, None, True
    return dados, pontos, pontos_retos, True


# -- QRCodeDetectorAruco localiza o QR usando deteccao de marcadores Aruco nos
# tres "olhos" do codigo, o que o torna bem mais tolerante a QR pequeno/distante
# na imagem do que o QRCodeDetector classico (confirmado em teste comparativo:
# o classico para de localizar o QR por volta de 100px, o Aruco continua
# localizando ate ~70px). Mantemos os dois: o classico decodifica mais rapido
# quando o QR esta bem posicionado, o Aruco cobre os casos em que ele falha:
_detector_aruco = cv2.QRCodeDetectorAruco()


def _nitidez_unsharp(imagem, forca=1.5, raio=3):
    # -- Mao-leve/desfoque de foco da camera (muito comum ao fotografar a tela
    # de um celular) foi, em testes, a causa mais frequente de falha na
    # decodificacao — mesmo um desfoque leve corrompe os modulos finos do QR.
    # Unsharp mask realca as bordas dos modulos e recupera a leitura:
    suavizada = cv2.GaussianBlur(imagem, (0, 0), raio)
    return cv2.addWeighted(imagem, 1 + forca, suavizada, -forca, 0)


def detectar_qrcode(frame, detector):
    # -- Passo 1 (caminho feliz): tenta decodificar direto no frame cru. Na
    # maioria dos casos com QR bem posicionado, resolve em uma unica chamada:
    dados, bbox, reto, achou = _ler_qrcode_seguro(detector, frame)
    if dados:
        return dados, bbox, reto

    # -- Passo 2 (gate barato): se nenhum candidato a QR foi localizado nem
    # pelo detector classico nem pelo Aruco (mais sensivel a QR pequeno), o
    # frame provavelmente nao contem QR algum. Evita pagar o custo das
    # tentativas seguintes (nitidez/contraste) no caso mais comum do uso
    # normal — frame sem nenhum QR na imagem:
    if not achou:
        _, _, _, achou = _ler_qrcode_seguro(_detector_aruco, frame)
        if not achou:
            return '', None, None

    # -- Ha um candidato (quadrilatero encontrado por algum detector), mas a
    # decodificacao falhou — provavelmente desfoque ou baixo contraste.
    # Tenta variantes mais robustas combinando os dois detectores:
    detectores = (detector, _detector_aruco)
    for imagem in (frame, _nitidez_unsharp(frame)):
        for tentativa_detector in detectores:
            dados, bbox, reto, _ = _ler_qrcode_seguro(tentativa_detector, imagem)
            if dados:
                return dados, bbox, reto

    # -- Reforça contraste (mesma técnica usada no OCR de valores): ajuda a
    # recuperar QR Codes sob reflexo/baixo contraste de telas:
    cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    cinza = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(cinza)
    for tentativa_detector in detectores:
        dados, bbox, reto, _ = _ler_qrcode_seguro(tentativa_detector, cinza)
        if dados:
            return dados, bbox, reto
    return '', None, None


def _ler_campos_tlv(payload):
    # Decodifica um payload EMV QR Code/BR Code (padrão Pix) em pares
    # (id, valor). Formato: ID (2 dígitos) + TAMANHO (2 dígitos) + VALOR.
    campos = []
    i, tamanho_total = 0, len(payload)
    while i + 4 <= tamanho_total:
        id_campo = payload[i:i + 2]
        try:
            tamanho = int(payload[i + 2:i + 4])
        except ValueError:
            break
        inicio = i + 4
        fim = inicio + tamanho
        if fim > tamanho_total:
            break
        campos.append((id_campo, payload[inicio:fim]))
        i = fim
    return campos


def _normalizar_valor_emv(valor_bruto):
    # Converte um valor EMV (ex.: '42.5') para o formato 'inteiro,centavos'
    # usado pelas funções de fala (ex.: '42,50'):
    inteiro, _, decimal = valor_bruto.partition('.')
    inteiro = inteiro.strip() or '0'
    decimal = (decimal.strip() + '00')[:2]
    if not inteiro.isdigit() or not decimal.isdigit():
        return None
    return f'{inteiro},{decimal}'


def interpretar_qrcode_pix(dados):
    """Interpreta um QR Code de cobrança Pix (padrão BR Code/EMV) e extrai
    somente o que é seguro anunciar: se é um Pix, o valor cobrado e o nome
    do recebedor. A chave Pix e demais dados sensíveis nunca são lidos.
    """
    resultado = {'eh_pix': False, 'valor': None, 'nome_recebedor': None}
    if not dados:
        return resultado

    campos_por_id = {}
    for id_campo, valor in _ler_campos_tlv(dados):
        campos_por_id.setdefault(id_campo, valor)

    # -- O GUI oficial do Pix é 'BR.GOV.BCB.PIX' (maiusculo, conforme o manual
    # do Bacen), mas comparamos sem diferenciar caixa por seguranca, ja que
    # cada instituicao pode gerar o payload de forma levemente diferente:
    if 'br.gov.bcb.pix' not in campos_por_id.get('26', '').lower():
        return resultado
    resultado['eh_pix'] = True

    valor_bruto = campos_por_id.get('54')
    if valor_bruto:
        resultado['valor'] = _normalizar_valor_emv(valor_bruto)

    nome = campos_por_id.get('59')
    if nome and nome.strip():
        resultado['nome_recebedor'] = nome.strip()

    return resultado


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
