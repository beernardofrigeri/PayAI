import threading
import time
from queue import Empty, Full, Queue

import cv2
import numpy as np
import pygame
from PIL import ImageDraw

from payai.config import (
    ALTURA,
    CONTORNO_TEMPO_VIDA,
    CORES,
    IDIOMAS,
    LARGURA,
    MODOS,
    OCR_CONFIANCA_MINIMA,
    OCR_INTERVAL,
    OCR_QUEUE_SIZE,
    QRCODE_PERDA_GRACA,
    SKIP_FRAMES,
    VALOR_HISTORY_BUFFER,
    YOLO_INTERVAL,
    carregar_fontes,
    logger,
)
from payai.detectors import (
    Camera,
    buscar_valor_global as _buscar_valor_global_impl,
    carregar_ocr as _carregar_ocr_impl,
    carregar_yolo as _carregar_yolo_impl,
    detectar_cedulas,
    detectar_qrcode,
    filtrar_valor_monetario as _filtrar_valor_monetario_impl,
    validar_valor as _validar_valor_impl,
)
from payai.rendering import (
    cv2_para_pil,
    desenhar_interface as _desenhar_interface_impl,
    pil_para_cv2,
    rect_r,
    texto_c,
)
from payai.speech import (
    SpeechWorker as _SpeechWorkerBase,
    _num_pt,
    falar_edge as _falar_edge_impl,
    formatar_fala as _formatar_fala_impl,
    numero_es as _numero_es_impl,
    preparar_texto_fala as _preparar_texto_fala_impl,
)

numero_es = _numero_es_impl
preparar_texto_fala = _preparar_texto_fala_impl
falar_edge = _falar_edge_impl
formatar_fala = _formatar_fala_impl
validar_valor = _validar_valor_impl
filtrar_valor_monetario = _filtrar_valor_monetario_impl

FONTES = carregar_fontes()

# -- OCR / voz do sistema --
reader = None
ocr_pronto = False
yolo_modelo = None
yolo_pronto = False

# -- Câmera --
cap = None
camera_pronta = False

# -- Variáveis globais de estado --
progresso_loading = 0.0
detector = cv2.QRCodeDetector()
ultimo_tempo = time.time()
texto_anterior = ''
frame_count = 0
ultimo_processamento = 0
ultimo_yolo_processamento = 0
contornos_ativos = []
ultimos_detectados = {}
fps_atual = 0
ultimo_fps_tempo = time.time()
tempo_ocr = 0
regioes_detectadas = 0
deteccoes_cedulas = []
fila_ocr = Queue(maxsize=OCR_QUEUE_SIZE)
fala_lock = threading.Lock()
estado_lock = threading.RLock()
ultima_fala = ''
valor_history = []
fala_deteccao_tipo = None
fala_deteccao_cancelamento = None
ultimo_qrcode_visto = 0.0
qrcode_anunciado = None

# -- Estado OCR --
ocr_rodando = False

# -- Estado do padrão do sistema --
modo_atual = MODOS['AUTO']
idioma_atual = IDIOMAS['PT_BR']


def carregar_ocr():
    global reader, ocr_pronto
    reader = _carregar_ocr_impl()
    ocr_pronto = reader is not None


def carregar_yolo():
    global yolo_modelo, yolo_pronto
    yolo_modelo = _carregar_yolo_impl()
    yolo_pronto = yolo_modelo is not None


def processar_cedulas(frame):
    global deteccoes_cedulas, contornos_ativos
    if not yolo_pronto or yolo_modelo is None:
        return
    try:
        deteccoes = detectar_cedulas(frame, yolo_modelo)
        with estado_lock:
            deteccoes_cedulas = deteccoes
            contornos_ativos = [
                item for item in contornos_ativos if item[3] != 'CEDULA'
            ]
            for confianca, nome, topo_esq, baixo_dir in deteccoes:
                contornos_ativos.append((
                    (topo_esq, baixo_dir),
                    f'Cedula R$ {nome} ({confianca:.0%})',
                    time.time(),
                    'CEDULA',
                ))
    except Exception as erro:
        logger.error(f'Erro na detecção YOLO: {erro}')


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
                logger.error(f'Erro loop OCR: {e}')

    def stop(self):
        self._parar.set()


# -- Inicialização da câmera --
_camera = Camera(width=LARGURA, height=ALTURA)


def _iniciar_camera_thread():
    global cap, camera_pronta
    ok = _camera.start()
    if ok:
        cap = _camera.cap
        camera_pronta = True


def desenhar_interface(frame, estatisticas, agora):
    with estado_lock:
        modo_local = modo_atual
        idioma_local = idioma_atual
        tempo_ocr_local = tempo_ocr
        regioes_local = regioes_detectadas
        contornos_snapshot = list(contornos_ativos)

    return _desenhar_interface_impl(
        frame,
        estatisticas,
        agora,
        fontes=FONTES,
        cores=CORES,
        idiomas=IDIOMAS,
        fps_atual=fps_atual,
        modo_atual=modo_local,
        idioma_atual=idioma_local,
        tempo_ocr=tempo_ocr_local,
        regioes_detectadas=regioes_local,
        contornos_snapshot=contornos_snapshot,
    )


class Estatisticas:
    def __init__(self):
        self._lock = threading.Lock()
        self.valores_detectados = 0
        self.qrcodes_detectados = 0
        self.erros_ocr = 0
        self.inicio = time.time()

    def registrar_deteccao(self, tipo):
        with self._lock:
            if tipo == 'VALOR':
                self.valores_detectados += 1
            elif tipo == 'QRCODE':
                self.qrcodes_detectados += 1

    def registrar_erro(self):
        with self._lock:
            self.erros_ocr += 1

    def obter_estatisticas(self):
        with self._lock:
            valores_detectados = self.valores_detectados
            qrcodes_detectados = self.qrcodes_detectados
            erros_ocr = self.erros_ocr
            inicio = self.inicio
        t = time.time() - inicio
        total = valores_detectados + qrcodes_detectados
        return {
            'tempo_execucao': t,
            'valores_detectados': valores_detectados,
            'qrcodes_detectados': qrcodes_detectados,
            'erros_ocr': erros_ocr,
            'detectoes_por_minuto': total / (t / 60) if t > 0 else 0,
        }


class SpeechWorker(_SpeechWorkerBase):
    def __init__(self, tamanho_fila=8):
        super().__init__(
            tamanho_fila=tamanho_fila,
            fala_lock=fala_lock,
            logger_inst=logger,
            preparar_texto_fala_fn=lambda texto, idioma: preparar_texto_fala(texto, idioma),
            falar_edge_fn=lambda texto, voz='es-CO-GonzaloNeural', cancelar_evento=None: falar_edge(
                texto,
                voz,
                cancelar_evento,
            ),
        )


speech_worker = SpeechWorker()


def falar_texto(texto, idioma=None, ultima_fala_ref=None, cancelar_evento=None):
    global ultima_fala
    ultima_fala = texto
    if idioma is None:
        with estado_lock:
            idioma = idioma_atual
    speech_worker.enqueue(texto, idioma, cancelar_evento)


def evitar_repeticao(texto, minimo=5):
    global ultimo_tempo, texto_anterior, valor_history
    agora = time.time()
    with estado_lock:
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


def pode_detectar(texto, cooldown=8):
    # -- Verifica se o texto pode ser detectado novamente (com cooldown):
    agora = time.time()
    with estado_lock:
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


def atualizar_contornos():
    global contornos_ativos
    agora = time.time()
    with estado_lock:
        contornos_ativos = [
            item for item in contornos_ativos
            if item[3] in ('VALOR', 'QRCODE') or (agora - item[2]) < CONTORNO_TEMPO_VIDA
        ]


def definir_contorno_ativo(tl, br, texto, tipo):
    # -- Mantém somente a detecção atual de cada tipo, sem rastros antigos:
    global contornos_ativos
    with estado_lock:
        contornos_ativos = [item for item in contornos_ativos if item[3] != tipo]
        contornos_ativos.append(((tl, br), texto, time.time(), tipo))


def remover_contorno(tipo):
    global contornos_ativos
    with estado_lock:
        contornos_ativos = [item for item in contornos_ativos if item[3] != tipo]


def processar_qrcode(frame, estat):
    global ultimo_qrcode_visto, qrcode_anunciado
    try:
        data, bbox, _ = detectar_qrcode(frame, detector)
    except cv2.error as erro:
        logger.warning(f'Erro QRCodeDetector: {erro}')
        return
    if not data or not data.strip():
        # A decodificação pode falhar em alguns frames mesmo com o QR visível.
        # A fala não é cancelada: o Edge-TTS pode ainda estar gerando o áudio.
        with estado_lock:
            apagar_qrcode = (time.time() - ultimo_qrcode_visto) > QRCODE_PERDA_GRACA
            if apagar_qrcode:
                qrcode_anunciado = None
        if apagar_qrcode:
            remover_contorno('QRCODE')
        return

    # -- Atualiza o tempo do último QR Code visto:
    with estado_lock:
        ultimo_qrcode_visto = time.time()

    # -- Evita repetição de detecção do mesmo QR Code em um curto período:
    if bbox is not None:
        pts = bbox.astype(int).reshape(-1, 2)
        tl = (int(pts[:, 0].min()), int(pts[:, 1].min()))
        br = (int(pts[:, 0].max()), int(pts[:, 1].max()))
        # -- O conteúdo pode incluir chave Pix ou URL de pagamento; não o exiba:
        definir_contorno_ativo(tl, br, 'QR Code detectado', 'QRCODE')
    else:
        remover_contorno('QRCODE')

    # -- Anuncia somente ao encontrar um QR novo. Mantê-lo diante da câmera não
    # reinicia a fala repetidamente; após sumir, ele poderá ser anunciado outra vez:
    with estado_lock:
        anunciar = data != qrcode_anunciado
        if anunciar:
            qrcode_anunciado = data
    if anunciar:
        logger.info('QR Code detectado (%d caracteres).', len(data))
        estat.registrar_deteccao('QRCODE')
        with estado_lock:
            idioma = idioma_atual
        iniciar_fala_deteccao('QR Code detectado', idioma, 'QRCODE')


def buscar_valor_global(frame):
    return _buscar_valor_global_impl(frame, reader)


def remover_contorno_valor():
    remover_contorno('VALOR')


def parar_fala_deteccao(tipo):
    global fala_deteccao_tipo, fala_deteccao_cancelamento
    with estado_lock:
        if fala_deteccao_tipo != tipo or fala_deteccao_cancelamento is None:
            return
        cancelar_evento = fala_deteccao_cancelamento
        fala_deteccao_tipo = None
        fala_deteccao_cancelamento = None
    cancelar_evento.set()
    with fala_lock:
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except pygame.error:
            pass


def iniciar_fala_deteccao(texto, idioma, tipo):
    global fala_deteccao_tipo, fala_deteccao_cancelamento
    with estado_lock:
        tipo_ativo = fala_deteccao_tipo
    parar_fala_deteccao(tipo_ativo)
    with estado_lock:
        fala_deteccao_tipo = tipo
        fala_deteccao_cancelamento = threading.Event()
        cancelar_evento = fala_deteccao_cancelamento
    falar_texto(texto, idioma, None, cancelar_evento)


def processar_valores(frame, estat):
    global ocr_rodando, tempo_ocr, regioes_detectadas
    if reader is None:
        return
    ocr_rodando = True
    inicio = time.time()
    try:
        resultado = buscar_valor_global(frame)
        with estado_lock:
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
        with estado_lock:
            idioma = idioma_atual
        texto_contorno = (f'COL$ {valor} pesos colombianos'
                          if idioma == IDIOMAS['ES_CO']
                          else f'R$ {valor} reais')
        definir_contorno_ativo(topo_esq, baixo_dir, texto_contorno, 'VALOR')
        fala = formatar_fala(valor, idioma)
        if evitar_repeticao(fala) and pode_detectar(fala):
            logger.info(f'Valor: {fala} (conf {confianca:.2f})')
            estat.registrar_deteccao('VALOR')
            iniciar_fala_deteccao(fala, idioma, 'VALOR')
    except Exception as erro:
        logger.error(f'Erro OCR: {erro}')
        estat.registrar_erro()
    finally:
        with estado_lock:
            tempo_ocr = (time.time() - inicio) * 1000
        ocr_rodando = False


def main():
    global frame_count
    global fps_atual
    global ultimo_fps_tempo
    global ultimo_processamento
    global ultimo_yolo_processamento
    global modo_atual
    global idioma_atual
    global qrcode_anunciado
    global progresso_loading

    estatisticas = Estatisticas()
    _ocr_thread = None

    # -- Mensagem de inicialização e log:
    print('[INFO] Aponte a camera para o visor da maquininha ou QR Code...')
    logger.info(f'Sistema PayAI iniciado - {LARGURA}x{ALTURA}')
    speech_worker.start()

    # -- Thread de carregamento OCR --
    threading.Thread(
        target=carregar_ocr,
        daemon=True,
    ).start()

    threading.Thread(
        target=carregar_yolo,
        daemon=True,
    ).start()

    threading.Thread(
        target=_iniciar_camera_thread,
        daemon=True,
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
                    'PAYAI',
                    LARGURA // 2,
                    165,
                    FONTES['logo_pay'],
                    CORES['ACENTO'],
                )
                texto_c(
                    draw,
                    'Inicializando sistema...',
                    LARGURA // 2,
                    225,
                    FONTES['corpo_b'],
                    CORES['TEXTO_PRIM'],
                )
                mensagens_loading = [
                    'Inicializando componentes',
                    'Preparando sistema',
                    'Carregando interface',
                    'Verificando modulos',
                    'Inicializando camera',
                    'Preparando reconhecimento',
                    'Otimizando OCR',
                    'Configurando acessibilidade',
                    'Preparando sistema de voz',
                    'Carregando deteccao inteligente',
                    'Verificando desempenho',
                    'Sincronizando componentes',
                    'Iniciando visao computacional',
                    'Configurando analise inteligente',
                    'Inicializando assistente visual',
                    'Preparando leitura automatica',
                    'Sincronizando reconhecimento',
                    'Aplicando melhorias de desempenho',
                    'Verificando integridade do sistema',
                    'Otimizando inicializacao',
                    'Preparando captura de imagem',
                    'Ativando componentes principais',
                    'Preparando ambiente de execucao',
                ]
                indice_msg = int(
                    time.time() * 0.45
                ) % len(mensagens_loading)

                texto_status = mensagens_loading[indice_msg]
                texto_status += f' | CAM:{camera_pronta} OCR:{ocr_pronto}'

                texto_c(
                    draw,
                    texto_status,
                    LARGURA // 2,
                    255,
                    FONTES['pequena'],
                    CORES['TEXTO_SEC'],
                )
                # -- Desenha a barra simples:
                draw.rounded_rectangle(
                    [170, 305, 470, 317],
                    radius=5,
                    fill=CORES['CARD_BG'],
                )
                # -- Atualiza o progresso suavemente --
                alvo = 0.90

                if camera_pronta and ocr_pronto:
                    alvo = 1.0
                if progresso_loading < alvo:
                    progresso_loading += 0.025
                progresso_loading = min(
                    progresso_loading,
                    alvo,
                )
                largura = int(300 * progresso_loading)
                draw.rounded_rectangle(
                    [170, 305, 170 + largura, 317],
                    radius=5,
                    fill=CORES['ACENTO'],
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
                                (shine_x - barra_x1) / 25,
                            ),
                        )
                        # -- Aplica fade perto da saída:
                        saida = min(
                            1.0,
                            max(
                                0,
                                (barra_x2 - shine_x) / 25,
                            ),
                        )
                        intensidade = min(
                            entrada,
                            saida,
                        )
                        branco = int(
                            140 + (115 * intensidade)
                        )
                        draw.rounded_rectangle(
                            [
                                shine_x - 2,
                                307,
                                shine_x + brilho_largura,
                                315,
                            ],
                            radius=4,
                            fill=(branco, branco, branco),
                        )
                splash = pil_para_cv2(img)

                cv2.imshow(
                    'PayAI - Sistema Inteligente',
                    splash,
                )

                if cv2.waitKey(1) & 0xFF == 27:
                    logger.info('Encerrado pelo usuario durante a inicializacao')
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
            with estado_lock:
                modo_loop = modo_atual
                idioma_loop = idioma_atual

            if modo_loop in (MODOS['AUTO'], MODOS['VALORES']):
                if (
                    agora - ultimo_processamento > OCR_INTERVAL and
                    frame_count % SKIP_FRAMES == 0
                ):
                    ultimo_processamento = agora
                    try:
                        fila_ocr.put_nowait(frame.copy())
                    except Full:
                        pass

            if modo_loop in (MODOS['AUTO'], MODOS['QRCODE']):
                processar_qrcode(frame, estatisticas)

            if modo_loop in (MODOS['AUTO'], MODOS['VALORES']):
                if agora - ultimo_yolo_processamento > YOLO_INTERVAL:
                    ultimo_yolo_processamento = agora
                    processar_cedulas(frame)

            frame_final = desenhar_interface(frame, estatisticas, agora)
            cv2.imshow('PayAI - Sistema Inteligente', frame_final)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                logger.info('Encerrado pelo usuario')
                break
            elif key in (ord('v'), ord('V')):
                with estado_lock:
                    modo_atual = MODOS['VALORES']
                    qrcode_anunciado = None
                remover_contorno('QRCODE')
                parar_fala_deteccao('QRCODE')
                falar_texto('Modo valores ativado', idioma_loop, None)
            elif key in (ord('q'), ord('Q')):
                with estado_lock:
                    modo_atual = MODOS['QRCODE']
                    qrcode_anunciado = None
                remover_contorno('VALOR')
                parar_fala_deteccao('VALOR')
                falar_texto('Modo QR Code ativado', idioma_loop, None)
            elif key in (ord('a'), ord('A')):
                with estado_lock:
                    modo_atual = MODOS['AUTO']
                    qrcode_anunciado = None
                falar_texto('Modo automatico ativado', idioma_loop, None)
            elif key in (ord('i'), ord('I')):
                with estado_lock:
                    if idioma_atual == IDIOMAS['PT_BR']:
                        idioma_atual = IDIOMAS['ES_CO']
                        idioma_novo = idioma_atual
                        mensagem = 'Idioma español activado'
                    else:
                        idioma_atual = IDIOMAS['PT_BR']
                        idioma_novo = idioma_atual
                        mensagem = 'Idioma portugues ativado'
                falar_texto(mensagem, idioma_novo, None)
            elif key in (ord('s'), ord('S')):
                nome = f"screenshot_{time.strftime('%Y%m%d_%H%M%S')}.png"
                cv2.imwrite(nome, frame_final)
                logger.info(f'Screenshot: {nome}')
                falar_texto('Screenshot salvo', idioma_loop, None)
            elif key in (ord('r'), ord('R')):
                if ultima_fala:
                    falar_texto(ultima_fala, idioma_loop, None)

    except Exception as e:
        logger.error(f'Erro critico: {e}')
    finally:
        try:
            parar_fala_deteccao('VALOR')
            parar_fala_deteccao('QRCODE')
        except Exception:
            pass
        speech_worker.stop()
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
        logger.info(f'Estatisticas finais: {estatisticas.obter_estatisticas()}')
        logger.info('Sistema PayAI finalizado')

        # -- Para a thread OCR:
        if _ocr_thread is not None:
            try:
                _ocr_thread.stop()
            except Exception:
                pass


if __name__ == '__main__':
    main()
