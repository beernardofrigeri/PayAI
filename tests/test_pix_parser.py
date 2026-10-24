import unittest

from payai.detectors import interpretar_qrcode_pix


def _campo(id_campo, valor):
    return f'{id_campo}{len(valor):02d}{valor}'


def _montar_payload_pix(valor=None, nome=None, gui='BR.GOV.BCB.PIX'):
    # -- O GUI oficial (manual do Bacen) e maiusculo; o parser deve aceitar
    # tanto maiusculo quanto minusculo, dependendo de como cada instituicao
    # gera o payload:
    partes = [_campo('00', '01')]
    conta_pix = _campo('00', gui) + _campo('01', 'chave-pix-exemplo')
    partes.append(_campo('26', conta_pix))
    if valor is not None:
        partes.append(_campo('54', valor))
    if nome is not None:
        partes.append(_campo('59', nome))
    partes.append(_campo('63', 'ABCD'))
    return ''.join(partes)


class PixParserTests(unittest.TestCase):
    def test_qrcode_pix_com_valor_e_nome(self):
        payload = _montar_payload_pix(valor='42.50', nome='Padaria do Ze')

        info = interpretar_qrcode_pix(payload)

        self.assertTrue(info['eh_pix'])
        self.assertEqual(info['valor'], '42,50')
        self.assertEqual(info['nome_recebedor'], 'Padaria do Ze')

    def test_qrcode_pix_com_gui_minusculo_tambem_e_reconhecido(self):
        payload = _montar_payload_pix(valor='25.00', nome='Fulano', gui='br.gov.bcb.pix')

        info = interpretar_qrcode_pix(payload)

        self.assertTrue(info['eh_pix'])
        self.assertEqual(info['valor'], '25,00')

    def test_qrcode_pix_real_nubank_estilo_bacen_e_reconhecido(self):
        # Payload no formato exato do exemplo do manual do Bacen (GUI
        # maiusculo, cidade sem acento) - reproduz o caso real que falhou:
        payload = (
            '000201'
            '26360014BR.GOV.BCB.PIX0114+5511912345678'
            '52040000'
            '5303986'
            '5802BR'
            '540525.00'
            '5913Fulano de Tal'
            '6009Sao Paulo'
            '62070503***'
            '6304A13F'
        )

        info = interpretar_qrcode_pix(payload)

        self.assertTrue(info['eh_pix'])
        self.assertEqual(info['valor'], '25,00')
        self.assertEqual(info['nome_recebedor'], 'Fulano de Tal')
        self.assertNotIn('5511912345678', str(info))

    def test_qrcode_pix_estatico_sem_valor(self):
        payload = _montar_payload_pix(valor=None, nome='Padaria do Ze')

        info = interpretar_qrcode_pix(payload)

        self.assertTrue(info['eh_pix'])
        self.assertIsNone(info['valor'])
        self.assertEqual(info['nome_recebedor'], 'Padaria do Ze')

    def test_qrcode_pix_nao_expoe_chave_pix(self):
        payload = _montar_payload_pix(valor='10.00', nome='Fulano')

        info = interpretar_qrcode_pix(payload)

        self.assertNotIn('chave-pix-exemplo', str(info))

    def test_valor_com_uma_casa_decimal_e_normalizado(self):
        payload = _montar_payload_pix(valor='9.5')

        info = interpretar_qrcode_pix(payload)

        self.assertEqual(info['valor'], '9,50')

    def test_qrcode_generico_nao_e_tratado_como_pix(self):
        info = interpretar_qrcode_pix('https://exemplo.com/pagina')

        self.assertFalse(info['eh_pix'])
        self.assertIsNone(info['valor'])
        self.assertIsNone(info['nome_recebedor'])

    def test_dados_vazios_nao_lancam_excecao(self):
        info = interpretar_qrcode_pix('')

        self.assertFalse(info['eh_pix'])


if __name__ == '__main__':
    unittest.main()
