# Comparação entre a versão inicial e a atual

Este documento compara o primeiro commit disponível no histórico do GitHub com
a versão atual verificada neste repositório. A comparação é descritiva: não
altera nem substitui o código de nenhuma das versões.

## Referências

| Versão | Commit | Data do commit (UTC) | Mensagem |
|---|---|---|---|
| Inicial | [`5e0e461`](https://github.com/beernardofrigeri/PayAI/commit/5e0e4616eca453c2566c823f6c196efbe55417e6) | 2025-11-04 17:57:20 | `Versão inicial do PayAI` |
| Atual | [`8e8a48f`](https://github.com/beernardofrigeri/PayAI/commit/8e8a48fbb57cb58d2b4c5d4c7358c9bf63d6d225) | 2026-09-24 01:39:58 | `refactor: modularizar arquitetura do PayAI` |

## Resumo

A versão inicial era um protótipo funcional concentrado em `PayAI.py`, com
captura da câmera, leitura OCR, detecção de QR Code e anúncio por voz no mesmo
loop. A versão atual mantém esse objetivo, mas organiza o programa em módulos e
acrescenta tratamento específico de valores monetários, opções de operação e
idioma, processamento em segundo plano, interface visual e testes.

## Comparação por área

| Área | Versão inicial | Versão atual |
|---|---|---|
| Estrutura | Um único `PayAI.py` de 81 linhas, além de `.gitignore` e `requirements.txt`. | `PayAI.py` funciona como entrypoint; a lógica está em `payai/main.py`, `config.py`, `detectors.py`, `rendering.py` e `speech.py`. Há também testes automatizados. |
| OCR | EasyOCR em português e inglês, executado a cada quadro; considera texto com dígitos e confiança acima de 0,5. | OCR em português e espanhol, com filtragem e validação de formatos monetários, allowlist de caracteres e processamento em fila/thread. |
| Valores | Anuncia o texto detectado, sem validar se representa um valor monetário. | Procura valores monetários, valida faixa e centavos e formata o anúncio em reais ou pesos colombianos, conforme o idioma selecionado. |
| QR Code | Detecta e anuncia o QR Code quando seu conteúdo muda; mostra uma marcação simples no vídeo. | A detecção é integrada aos modos e à interface do sistema, com tratamento para manter o feedback visual e sonoro. |
| Voz | `pyttsx3`, inicializado diretamente no script; chamada síncrona no loop principal. | Worker e fila para fala, com suporte a Edge TTS e vozes para português brasileiro e espanhol colombiano. |
| Interface e controles | Janela de vídeo com caixas de texto/QR e saída por `ESC`. | Overlay com estatísticas e modos de leitura; atalhos para alternar modo e idioma, repetir leitura, salvar screenshot e sair. |
| Desempenho e organização | OCR e fala executados diretamente durante o loop da câmera. | Configurações centralizadas e tarefas assíncronas/em segundo plano para OCR e voz. |
| Testes | Nenhum teste aparece no commit inicial. | Há testes para parser de valores, formatação da fala e worker de voz. |

## Arquivos de referência

- **Versão inicial:** [PayAI.py no commit inicial](https://github.com/beernardofrigeri/PayAI/blob/5e0e4616eca453c2566c823f6c196efbe55417e6/PayAI.py)
- **Versão atual:** [`PayAI.py`](PayAI.py), [`payai/`](payai), [`tests/`](tests) e [`README.md`](README.md)

## Observações

- As datas da tabela são as datas dos commits em UTC; no horário de Brasília,
  correspondem a 2025-11-04 14:57:20 e 2026-09-23 22:39:58, respectivamente.
- A versão inicial foi identificada no histórico remoto do projeto PayAI; a
  cópia local deste workspace começa em um commit posterior. Por isso, a
  comparação usa o commit remoto inicial como referência, não presume que ele
  esteja presente no histórico Git local.
