# Copilot Instructions — PayAI

## Propósito do projeto

O **PayAI** é um sistema de acessibilidade em Python para leitura assistida de maquininhas de cartão, combinando:
- captura de câmera (OpenCV),
- leitura de valores monetários por OCR (EasyOCR),
- detecção de QR Code (OpenCV QRCodeDetector),
- detecção de cédulas por YOLO (Ultralytics),
- feedback de voz (Edge TTS + pygame),
- interface visual em tempo real (OpenCV + PIL).

## Estado atual da arquitetura

- Arquivo principal único: `PayAI.py` (**arquitetura ainda monolítica**).
- Entrypoint atual:
  - `def main()` em `PayAI.py`
  - `if __name__ == "__main__": main()`
- Código de preparação de dataset/treino YOLO separado:
  - `prepare_yolo_dataset.py`
  - `train_banknotes.py`
- Testes adicionados em `tests/` para parser monetário, formatação de fala e ciclo de vida básico do worker de fala.

## Fluxo principal de execução (runtime)

1. `main()` inicia:
   - `speech_worker.start()`
   - thread daemon de `carregar_ocr`
   - thread daemon de `carregar_yolo`
   - thread daemon de inicialização de câmera
   - `OCRThread` dedicada para OCR de valores
2. Enquanto `camera_pronta` ou `ocr_pronto` não estiverem prontos, exibe splash de inicialização.
3. Loop principal:
   - lê frame da câmera;
   - agenda OCR (via `fila_ocr`) conforme `OCR_INTERVAL` + `SKIP_FRAMES`;
   - processa QR Code no thread principal;
   - processa YOLO no thread principal (sincrono);
   - desenha interface e contornos;
   - trata atalhos do teclado.
4. Encerramento (`finally`):
   - cancela falas de detecção;
   - `speech_worker.stop()`;
   - libera câmera;
   - `cv2.destroyAllWindows()`;
   - sinaliza parada do `OCRThread`.

## Estados e modos importantes

- Modos (`MODOS`):
  - `AUTO` (valores + QR + YOLO de cédulas)
  - `VALORES`
  - `QRCODE`
- Idiomas (`IDIOMAS`):
  - `PT_BR`
  - `ES_CO`
- Estados globais relevantes:
  - disponibilidade: `ocr_pronto`, `yolo_pronto`, `camera_pronta`
  - execução: `modo_atual`, `idioma_atual`, `frame_count`, `fps_atual`
  - OCR/QR: `tempo_ocr`, `regioes_detectadas`, `qrcode_anunciado`, `ultimo_qrcode_visto`
  - deduplicação/cooldown: `valor_history`, `ultimos_detectados`
  - overlays: `contornos_ativos`, `deteccoes_cedulas`
  - fala: `fala_deteccao_tipo`, `fala_deteccao_cancelamento`, `ultima_fala`

## Integração entre câmera, OCR, YOLO, QR Code, TTS e interface

- **Câmera**: classe `Camera` encapsula `cv2.VideoCapture`.
- **OCR de valores**:
  - loop principal envia `frame.copy()` para `fila_ocr` (`maxsize=1`);
  - `OCRThread` consome fila e chama `processar_valores`.
- **YOLO cédulas**:
  - carregado em `carregar_yolo`;
  - inferência em `processar_cedulas` no loop principal, com `YOLO_INTERVAL`.
- **QR Code**:
  - `processar_qrcode` chamado no loop principal (modo `AUTO`/`QRCODE`);
  - contorno/voz com anti-repetição por conteúdo e janela de perda (`QRCODE_PERDA_GRACA`).
- **TTS**:
  - `falar_texto` enfileira no `SpeechWorker`;
  - `SpeechWorker` usa `preparar_texto_fala` + `falar_edge`.
- **Interface**:
  - `desenhar_interface` compõe header, status, métricas, contornos e footer de atalhos.

## Concorrência, threads e estado compartilhado

Threads/processamento concorrente atual:
- thread principal: captura, UI, teclado, QR, YOLO.
- `OCRThread` (daemon): OCR de valores.
- thread de `SpeechWorker` (não-daemon): consumo serial da fila de fala.
- threads daemon de inicialização: OCR, YOLO, câmera.

Sincronização atual:
- `estado_lock = threading.RLock()` para estado compartilhado (contornos, idioma/modo, cooldowns, estado QR/fala e métricas OCR).
- `fala_lock = threading.Lock()` para operações de mixer/reprodução.
- `Estatisticas` possui lock interno (`self._lock`) para contadores.

Observações:
- A concorrência foi melhorada, mas o projeto ainda é global-state centric e monolítico.
- YOLO e QR ainda rodam no thread principal.

## SpeechWorker e ciclo de vida

Implementação atual (`class SpeechWorker` em `PayAI.py`):
- fila interna `Queue(maxsize=8)`;
- `enqueue()` inicia worker sob demanda e tenta enfileirar sem bloqueio;
- se fila cheia, remove um item antigo e tenta inserir o novo;
- `_loop()` processa eventos serialmente;
- `stop(timeout=3.0)`:
  - seta evento de parada,
  - injeta sentinela,
  - faz `join`,
  - para/unload/quit do `pygame.mixer` sob `fala_lock`.

Integração:
- `main()` chama `speech_worker.start()` no boot.
- `finally` chama `speech_worker.stop()` no encerramento.

## Parser e formatação monetária

Funções principais:
- `validar_valor(valor)`: valida formato e faixa `0.01` a `10000`.
- `filtrar_valor_monetario(texto)`: extrai valor monetário com regex e normalizações (`O`->`0`, espaços).
- `formatar_fala(val, idioma)`: gera frase monetária base.
- `preparar_texto_fala(texto, idioma)`: normaliza frase final para TTS em PT/ES.

Regex atual cobre:
- `1000,00`, `1234,56`, `1.234,56`, prefixo/sufixo `R$`, e formato com ponto decimal (`12.34` -> `12,34`).

## Idiomas e regras de fala

- Idioma padrão: `PT_BR`.
- Alternância por tecla `I`.
- PT-BR:
  - números em palavras via `_num_pt`.
- ES-CO:
  - números em palavras via `numero_es`;
  - frases monetárias com pesos/centavos (ex.: `"quince pesos colombianos y treinta centavos"`);
  - tradução de frases de interface (QR detectado, modos, screenshot).

## Estrutura de testes atual

Pasta `tests/`:
- `test_money_parser.py`
  - cobre parser monetário e faixa de valor.
- `test_speech_formatting.py`
  - cobre formatação de fala PT/ES e traduções-chave.
- `test_speech_worker.py`
  - cobre ciclo básico de enfileiramento e `stop()` do worker com mock de TTS.

## Comandos de validação usados no projeto

- Compilação sintática:
  - `python -m py_compile PayAI.py tests\test_money_parser.py tests\test_speech_formatting.py tests\test_speech_worker.py`
- Testes:
  - `python -m unittest discover -s tests -p "test_*.py" -v`
- Verificação de import sem side effects:
  - `python -c "import PayAI; print('import-ok')"`
- Execução manual:
  - `python PayAI.py`

## Decisões arquiteturais já tomadas (implementadas)

1. **Entrypoint explícito (C2)**: bootstrap movido para `main()` com guard `__main__`.
2. **Correção de parser monetário (A3)**: regex ajustada para valores de 4+ dígitos sem truncamento parcial.
3. **Correção de fala ES (A2)**: normalização de fala centralizada em `preparar_texto_fala`.
4. **Lifecycle de áudio (C4)**: adoção de `SpeechWorker` com start/stop explícitos.
5. **Sincronização de estado (C3)**: introdução de lock de estado compartilhado + lock em `Estatisticas`.

## Roadmap (fonte: plan.md da sessão) e status

Fonte de planejamento ativa:
- `C:\Users\GAMER\.copilot\session-state\4dfde080-6c8e-47c3-9d36-582b9b92b5b9\plan.md`

Status registrado:
- **Concluídas**: `C2`, `A3`, `A2`, `C4`, `C3`
- **Pendentes**: `A4`, `A1` (profiling + migração assíncrona), `A5` (profiling + otimizações OCR)
- Próxima etapa pronta para execução (ready): `A4` (modularização inicial)

## Restrições importantes para futuras refatorações

- Preservar atalhos e UX principal (`A`, `V`, `Q`, `I`, `R`, `S`, `ESC`).
- Evitar mudança de comportamento em etapas estruturais (modularização).
- Em bugfixes, explicitar mudanças funcionais esperadas.
- Manter `import PayAI` sem side effects.
- Preservar contratos dos testes atuais e expandir cobertura antes de grandes mudanças.
- Alterações em concorrência devem manter shutdown limpo (sem erros tardios de áudio/câmera).

## NÃO CONFIRMADO

- Presença de `plan.md` **na raiz do repositório**: **NÃO CONFIRMADO** (não existe atualmente no root; o plano ativo está no diretório de sessão).
- Ganho real de performance de mover YOLO para worker assíncrono: **NÃO CONFIRMADO** (falta profiling comparativo no estado atual).
- Ganho real de otimizações OCR (ROI/cadência/histerese): **NÃO CONFIRMADO** (falta baseline de métricas e teste em hardware real).
- Comportamento com falhas prolongadas de câmera/OCR no boot (timeout/fallback): **NÃO CONFIRMADO** (fluxo de splash indefinido ainda depende de validação funcional em campo).
