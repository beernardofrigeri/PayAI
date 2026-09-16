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


if __name__ == "__main__":
    unittest.main()
