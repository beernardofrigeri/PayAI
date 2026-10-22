import asyncio
import unittest
from unittest.mock import Mock, patch

from payai.speech import falar_edge


class SpeechFallbackTests(unittest.TestCase):
    def test_uses_local_voice_when_edge_tts_fails(self):
        async def fail_to_save(_path):
            raise RuntimeError('403 Invalid response status')

        engine = Mock()
        communicate = Mock()
        communicate.save.side_effect = fail_to_save

        with (
            patch('payai.speech.edge_tts.Communicate', return_value=communicate),
            patch('payai.speech.pygame.mixer.get_init', return_value=None),
            patch('payai.speech.pyttsx3.init', return_value=engine),
        ):
            asyncio.run(falar_edge('Valor quinze reais'))

        engine.say.assert_called_once_with('Valor quinze reais')
        engine.runAndWait.assert_called_once_with()
        engine.stop.assert_called_once_with()

    def test_does_not_use_local_voice_after_cancellation(self):
        async def fail_to_save(_path):
            raise RuntimeError('connection closed')

        cancellation = asyncio.Event()
        cancellation.set()
        communicate = Mock()
        communicate.save.side_effect = fail_to_save

        with (
            patch('payai.speech.edge_tts.Communicate', return_value=communicate),
            patch('payai.speech.pygame.mixer.get_init', return_value=None),
            patch('payai.speech.pyttsx3.init') as local_tts,
        ):
            asyncio.run(falar_edge('Leitura cancelada', cancelar_evento=cancellation))

        local_tts.assert_not_called()


if __name__ == '__main__':
    unittest.main()
