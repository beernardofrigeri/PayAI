import unittest

import PayAI


class SpeechFormattingTests(unittest.TestCase):
    def test_spanish_money_with_pesos_and_centavos(self):
        saida = PayAI.preparar_texto_fala(
            "15 pesos colombianos e 30 centavos",
            PayAI.IDIOMAS['ES_CO'],
        )
        self.assertEqual(saida, "quince pesos colombianos y treinta centavos")

    def test_spanish_money_only_pesos(self):
        saida = PayAI.preparar_texto_fala(
            "15 pesos colombianos",
            PayAI.IDIOMAS['ES_CO'],
        )
        self.assertEqual(saida, "quince pesos colombianos")

    def test_spanish_money_only_centavos(self):
        saida = PayAI.preparar_texto_fala(
            "30 centavos",
            PayAI.IDIOMAS['ES_CO'],
        )
        self.assertEqual(saida, "treinta centavos")

    def test_spanish_interface_translation_is_preserved(self):
        saida = PayAI.preparar_texto_fala(
            "Modo QR Code ativado",
            PayAI.IDIOMAS['ES_CO'],
        )
        self.assertEqual(saida, "Modo código QR activado")

    def test_portuguese_money_spelling_is_preserved(self):
        saida = PayAI.preparar_texto_fala(
            "15 reais e 30 centavos",
            PayAI.IDIOMAS['PT_BR'],
        )
        self.assertEqual(saida, "quinze reais e trinta centavos")

    def test_portuguese_composed_sentence_keeps_surrounding_text(self):
        saida = PayAI.preparar_texto_fala(
            "QR Code Pix detectado. Para Padaria do Ze. Cobranca de 42 reais e 50 centavos.",
            PayAI.IDIOMAS['PT_BR'],
        )
        self.assertEqual(
            saida,
            "QR Code Pix detectado. Para Padaria do Ze. "
            "Cobranca de quarenta e dois reais e cinquenta centavos.",
        )

    def test_spanish_composed_sentence_translates_prefix_and_keeps_name(self):
        saida = PayAI.preparar_texto_fala(
            "QR Code Pix detectado. Para Padaria do Ze. Cobranca de 42 reais e 50 centavos.",
            PayAI.IDIOMAS['ES_CO'],
        )
        self.assertEqual(
            saida,
            "Código QR Pix detectado. Para Padaria do Ze. "
            "Cobro de cuarenta y dos pesos colombianos y cincuenta centavos.",
        )

    def test_spanish_pix_without_value_is_translated(self):
        saida = PayAI.preparar_texto_fala(
            "QR Code Pix detectado. Sem valor definido.",
            PayAI.IDIOMAS['ES_CO'],
        )
        self.assertEqual(saida, "Código QR Pix detectado. Sin valor definido.")


if __name__ == "__main__":
    unittest.main()
