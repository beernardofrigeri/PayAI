import unittest

import cv2
import numpy as np

from payai.detectors import detectar_qrcode


def _gerar_frame_com_qr(conteudo, tamanho=250, origem=(100, 180), fundo=255):
    encoder = cv2.QRCodeEncoder_create()
    qr_img = encoder.encode(conteudo)
    qr_bgr = cv2.cvtColor(qr_img, cv2.COLOR_GRAY2BGR)
    qr_redimensionado = cv2.resize(qr_bgr, (tamanho, tamanho), interpolation=cv2.INTER_NEAREST)
    frame = np.full((480, 640, 3), fundo, dtype=np.uint8)
    y, x = origem
    frame[y:y + tamanho, x:x + tamanho] = qr_redimensionado
    return frame


class QRCodeDetectionTests(unittest.TestCase):
    def test_decodifica_qrcode_bem_formado(self):
        detector = cv2.QRCodeDetector()
        frame = _gerar_frame_com_qr('https://pix.exemplo.com/chave-teste-12345')

        dados, bbox, _ = detectar_qrcode(frame, detector)

        self.assertEqual(dados, 'https://pix.exemplo.com/chave-teste-12345')
        self.assertIsNotNone(bbox)

    def test_decodifica_qrcode_com_desfoque_leve(self):
        # Reproduz o caso real relatado (Nubank, QR bem definido na tela mas
        # nao lido): desfoque leve de foco corrompe os modulos finos do QR e
        # impede a decodificacao direta. A nitidez (unsharp mask) deve
        # recuperar a leitura:
        detector = cv2.QRCodeDetector()
        conteudo = 'https://pix.exemplo.com/chave-teste-12345'
        frame = _gerar_frame_com_qr(conteudo)
        frame_desfocado = cv2.GaussianBlur(frame, (5, 5), 0)

        dados, bbox, _ = detectar_qrcode(frame_desfocado, detector)

        self.assertEqual(dados, conteudo)
        self.assertIsNotNone(bbox)

    def test_decodifica_qrcode_pequeno_com_desfoque_e_ruido(self):
        # QR pequeno no quadro (celular distante da camera) combinado com
        # desfoque e ruido leve — cenario tipico de uso real com webcam:
        detector = cv2.QRCodeDetector()
        conteudo = 'https://pix.exemplo.com/chave-teste-12345'
        frame = _gerar_frame_com_qr(conteudo, tamanho=130, origem=(175, 255))
        frame = cv2.GaussianBlur(frame, (3, 3), 0)
        ruido = np.random.RandomState(9).normal(0, 10, frame.shape).astype(np.float32)
        frame = np.clip(frame.astype(np.float32) + ruido, 0, 255).astype(np.uint8)

        dados, _, _ = detectar_qrcode(frame, detector)

        self.assertEqual(dados, conteudo)

    def test_nao_lanca_excecao_sem_qrcode_no_frame(self):
        detector = cv2.QRCodeDetector()
        # -- Seed fixa: ruido aleatorio sem semente pode, raramente, formar um
        # quadrilatero que o OpenCV interpreta como falso positivo, tornando
        # o teste instavel. Uma semente fixa mantem o teste determinístico:
        gerador = np.random.RandomState(42)
        frame = gerador.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        dados, bbox, _ = detectar_qrcode(frame, detector)

        self.assertEqual(dados, '')
        self.assertIsNone(bbox)

    def test_nao_chama_decode_quando_pontos_sao_degenerados(self):
        # Reproduz o erro visto em producao (qrcode.cpp:2961 -
        # "contourArea(src_points) is 0"): detect() retorna um quadrilatero
        # de area zero (QR muito inclinado/borrado). detectar_qrcode deve
        # descartar o frame sem sequer chamar decode(), evitando o crash.
        chamadas_decode = []

        class DetectorFake:
            def detect(self, _imagem):
                pontos_degenerados = np.array(
                    [[10, 10], [10, 10], [10, 10], [10, 10]],
                    dtype=np.float32,
                )
                return True, pontos_degenerados

            def decode(self, _imagem, pontos):
                chamadas_decode.append(pontos)
                raise AssertionError('decode nao deveria ser chamado')

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        dados, bbox, _ = detectar_qrcode(frame, DetectorFake())

        self.assertEqual(dados, '')
        self.assertIsNone(bbox)
        self.assertEqual(chamadas_decode, [])

    def test_nao_propaga_cv2_error_lancado_pelo_decode(self):
        # Mesmo com pontos de area valida, o OpenCV pode lancar cv2.error
        # dentro de decode() (ex.: convexHull em casos degenerados). O erro
        # nao pode propagar para quem chamou detectar_qrcode.
        class DetectorFake:
            def detect(self, _imagem):
                pontos_validos = np.array(
                    [[10, 10], [60, 10], [60, 60], [10, 60]],
                    dtype=np.float32,
                )
                return True, pontos_validos

            def decode(self, _imagem, _pontos):
                raise cv2.error('cv::convexHull assertion failed')

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        dados, bbox, _ = detectar_qrcode(frame, DetectorFake())

        self.assertEqual(dados, '')
        self.assertIsNone(bbox)


if __name__ == '__main__':
    unittest.main()
