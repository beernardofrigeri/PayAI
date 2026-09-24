import asyncio
import os
import re
import tempfile
import threading
from queue import Empty, Full, Queue

import edge_tts
import pygame

from payai.config import IDIOMAS, logger


def _num_pt(n):
    if n == 0:
        return 'zero'
    if n <= 9:
        return ['', 'um', 'dois', 'tres', 'quatro', 'cinco', 'seis', 'sete', 'oito', 'nove'][n]
    if n <= 19:
        return ['dez', 'onze', 'doze', 'treze', 'quatorze', 'quinze',
                'dezesseis', 'dezessete', 'dezoito', 'dezenove'][n - 10]
    if n <= 99:
        dez = ['', '', 'vinte', 'trinta', 'quarenta', 'cinquenta',
               'sessenta', 'setenta', 'oitenta', 'noventa']
        d, u = n // 10, n % 10
        return dez[d] if u == 0 else f'{dez[d]} e {_num_pt(u)}'
    if n <= 999:
        if n == 100:
            return 'cem'
        c = ['', 'cento', 'duzentos', 'trezentos', 'quatrocentos', 'quinhentos',
             'seiscentos', 'setecentos', 'oitocentos', 'novecentos']
        cent, r = n // 100, n % 100
        return c[cent] + (' e ' + _num_pt(r) if r else '')
    return f'{n:,}'.replace(',', '.')


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
        9: 'nueve',
    }
    especiais = {
        10: 'diez',
        11: 'once',
        12: 'doce',
        13: 'trece',
        14: 'catorce',
        15: 'quince',
    }
    dezenas = {
        20: 'veinte',
        30: 'treinta',
        40: 'cuarenta',
        50: 'cincuenta',
        60: 'sesenta',
        70: 'setenta',
        80: 'ochenta',
        90: 'noventa',
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
        return f'{dezenas[d]} y {unidades[r]}'
    return str(n)


def preparar_texto_fala(texto, idioma):
    tf = texto
    texto_base = texto.lower()
    mr = re.search(r'(\d+)\s*reais', texto_base)
    mc = re.search(r'(\d+)\s*centavos', texto_base)
    mp = re.search(r'(\d+)\s*pesos colombianos', texto_base)

    # -- Português (Brasil):
    if idioma == IDIOMAS['PT_BR']:
        if mr:
            n = int(mr.group(1))
            tf = f'{_num_pt(n)} reais'
            if mc:
                tf += f' e {_num_pt(int(mc.group(1)))} centavos'
        elif mc:
            tf = f'{_num_pt(int(mc.group(1)))} centavos'

    # -- Espanhol (Colômbia):
    elif idioma == IDIOMAS['ES_CO']:
        if mp:
            pesos = numero_es(int(mp.group(1)))
            if mc:
                centavos = numero_es(int(mc.group(1)))
                tf = f'{pesos} pesos colombianos y {centavos} centavos'
            else:
                tf = f'{pesos} pesos colombianos'
        elif mr:
            # Compatibilidade para textos em PT em contexto de voz ES.
            tf = f'{numero_es(int(mr.group(1)))} pesos colombianos'
        elif mc:
            tf = f'{numero_es(int(mc.group(1)))} centavos'

        tf = tf.replace(
            'QR Code detectado',
            'Código QR detectado',
        )
        tf = tf.replace(
            'Modo automatico ativado',
            'Modo automático activado',
        )
        tf = tf.replace(
            'Modo valores ativado',
            'Modo valores activado',
        )
        tf = tf.replace(
            'Modo QR Code ativado',
            'Modo código QR activado',
        )
        tf = tf.replace(
            'Screenshot salvo',
            'Captura guardada',
        )

    return tf


async def falar_edge(texto, voz='es-CO-GonzaloNeural', cancelar_evento=None):
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
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
                logger.warning(f'Não foi possível remover áudio temporário: {erro}')


def formatar_fala(val, idioma=IDIOMAS['PT_BR']):
    p = val.strip().split(',')
    i = int(p[0].replace('.', '').strip())
    c = int(p[1].strip())
    if idioma == IDIOMAS['ES_CO']:
        if c == 0:
            return f'{i} pesos colombianos'
        if i == 0:
            return f'{c} centavos'
        return f'{i} pesos colombianos e {c} centavos'
    if c == 0:
        return f'{i} reais'
    if i == 0:
        return f'{c} centavos'
    return f'{i} reais e {c} centavos'


class SpeechWorker:
    def __init__(
        self,
        tamanho_fila=8,
        fala_lock=None,
        logger_inst=None,
        preparar_texto_fala_fn=None,
        falar_edge_fn=None,
    ):
        self._fila = Queue(maxsize=tamanho_fila)
        self._parar = threading.Event()
        self._thread = None
        self._fala_lock = fala_lock or threading.Lock()
        self._logger = logger_inst or logger
        self._preparar_texto_fala_fn = preparar_texto_fala_fn or preparar_texto_fala
        self._falar_edge_fn = falar_edge_fn or falar_edge

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._parar.clear()
        self._thread = threading.Thread(target=self._loop, name='payai-speech-worker')
        self._thread.start()

    def enqueue(self, texto, idioma, cancelar_evento=None):
        self.start()
        if self._parar.is_set():
            return
        item = (texto, idioma, cancelar_evento)
        try:
            self._fila.put_nowait(item)
        except Full:
            try:
                self._fila.get_nowait()
            except Empty:
                pass
            try:
                self._fila.put_nowait(item)
            except Full:
                pass

    def _loop(self):
        while True:
            if self._parar.is_set() and self._fila.empty():
                break
            try:
                item = self._fila.get(timeout=0.1)
            except Empty:
                continue
            if item is None:
                continue
            texto, idioma, cancelar_evento = item
            if cancelar_evento and cancelar_evento.is_set():
                continue
            with self._fala_lock:
                try:
                    tf = self._preparar_texto_fala_fn(texto, idioma)
                    if idioma == IDIOMAS['ES_CO']:
                        asyncio.run(
                            self._falar_edge_fn(
                                tf,
                                'es-CO-GonzaloNeural',
                                cancelar_evento,
                            )
                        )
                    else:
                        asyncio.run(
                            self._falar_edge_fn(
                                tf,
                                'pt-BR-AntonioNeural',
                                cancelar_evento,
                            )
                        )
                except Exception as erro:
                    self._logger.error(f'Erro na fala: {erro}')

    def stop(self, timeout=3.0):
        self._parar.set()
        try:
            self._fila.put_nowait(None)
        except Full:
            pass
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        with self._fala_lock:
            try:
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
                    try:
                        pygame.mixer.music.unload()
                    except pygame.error:
                        pass
                    pygame.mixer.quit()
            except pygame.error:
                pass

