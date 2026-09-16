import asyncio
import time
import unittest
from unittest.mock import patch

import PayAI


class SpeechWorkerTests(unittest.TestCase):
    def test_worker_processes_queue_and_stops_cleanly(self):
        worker = PayAI.SpeechWorker(tamanho_fila=2)

        async def fake_falar_edge(texto, voz="pt-BR-AntonioNeural", cancelar_evento=None):
            await asyncio.sleep(0)
            return None

        with patch.object(PayAI, "falar_edge", side_effect=fake_falar_edge):
            worker.enqueue("Teste", PayAI.IDIOMAS['PT_BR'])
            time.sleep(0.05)
            worker.stop(timeout=1.0)

        self.assertIsNone(worker._thread)


if __name__ == "__main__":
    unittest.main()
