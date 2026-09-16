import unittest

import PayAI


class MoneyParserTests(unittest.TestCase):
    def test_accepts_large_values_without_thousand_separator(self):
        self.assertEqual(PayAI.filtrar_valor_monetario("1000,00"), "1000,00")
        self.assertEqual(PayAI.filtrar_valor_monetario("1234,56"), "1234,56")

    def test_accepts_currency_symbol_prefix_and_suffix(self):
        self.assertEqual(PayAI.filtrar_valor_monetario("R$1000,00"), "1000,00")
        self.assertEqual(PayAI.filtrar_valor_monetario("1000,00R$"), "1000,00")

    def test_preserves_existing_thousand_separator_format(self):
        self.assertEqual(PayAI.filtrar_valor_monetario("1.234,56"), "1.234,56")
        self.assertEqual(PayAI.filtrar_valor_monetario("R$1.234,56"), "1.234,56")

    def test_dot_decimal_format_remains_supported(self):
        self.assertEqual(PayAI.filtrar_valor_monetario("12.34"), "12,34")
        self.assertEqual(PayAI.filtrar_valor_monetario("999.99"), "999,99")

    def test_invalid_formats_return_none(self):
        self.assertIsNone(PayAI.filtrar_valor_monetario("12345,678"))
        self.assertIsNone(PayAI.filtrar_valor_monetario("valor: --"))
        self.assertIsNone(PayAI.filtrar_valor_monetario(""))

    def test_value_range_validation_is_preserved(self):
        self.assertTrue(PayAI.validar_valor("10000,00"))
        self.assertFalse(PayAI.validar_valor("10000,01"))


if __name__ == "__main__":
    unittest.main()
