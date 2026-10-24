# Diário de bordo

Anotações elaboradas a partir dos commits do repositório no GitHub desde 18
de novembro de 2025 até 23 de outubro de 2026. As datas abaixo consideram o
horário local dos commits (UTC−03:00); os registros são agrupados em um
resumo geral de todo o período.

## Resumo geral do período (18 de novembro de 2025 a 23 de outubro de 2026)

Data: 18 de novembro de 2025 a 23 de outubro de 2026  
Local: Casa  
Intregrantes: Bernardo (só eu mexi nisso)

Atividades realizadas: Ao longo desse período o PayAI nasceu e amadureceu até
a versão apresentada na XV Mostra IFTec. No começo, reestruturei o código
inicial, publiquei a versão 1.0 (com README e `.gitignore` organizados) e
implementei a síntese de voz com Edge-TTS, além de uma tela de abertura com
carregamento progressivo e, depois, uma inicialização paralela do sistema
para deixá-lo mais rápido.

O núcleo do projeto — leitura de valores monetários por OCR e detecção de QR
Codes — passou por várias rodadas de ajuste: corrigi exceções na detecção de
QR Codes, tornei a leitura de valores mais estável com validação robusta,
priorização de formatos monetários e histórico de detecções, além de criar
uma busca alternativa global para quando a detecção principal falhava.
Corrigi também o feedback visual dos pagamentos e problemas recorrentes de
áudio e de leitura de QR Code.

Em paralelo, reorganizei várias vezes a arquitetura do código: separei
responsabilidades em módulos (câmera, OCR, voz, desenho, configuração,
logging e utilitários), cheguei a reverter para uma versão monolítica mais
simples quando a modularização atrapalhou mais do que ajudou, e por fim
consolidei tudo em uma arquitetura modular definitiva dentro do pacote
`payai`. Também limpei o código com Ruff, removi arquivos e testes que não
eram mais usados, e escrevi testes automatizados para os pontos mais
críticos (parser de valores, formatação de fala, detecção de QR Code e
leitura de QR Codes Pix).

A reta final, às vésperas do fechamento das notas na XV Mostra IFTec, foi
dedicada a corrigir os três bugs mais críticos encontrados em uso real: o
corte de áudio na síntese de voz durante a apresentação ao vivo (biblioteca
desatualizada + cancelamento precoce da fala), a falha total na leitura de QR
Codes pequenos, distantes ou desfocados (resolvida com um segundo detector e
nitidez de imagem), e a leitura de QR Codes Pix, que agora anuncia por voz o
valor cobrado e o nome do recebedor sem nunca revelar a chave Pix.

Ass: Bernardo Girardi Frigeri

## 🏆 Conquistas em feiras científicas

> Registros bônus pra não esquecer das conquistas do projeto. Preencha as
> datas, a cidade e os nomes da equipe, e reposicione cada bloco na ordem
> cronológica certa ao passar a limpo no diário físico.

### FENECIT 2025

Data: [preencher]  
Local: [preencher cidade]  
Intregrantes: Bernardo e equipe ([preencher nomes dos colegas])

Atividades realizadas: Levamos o PayAI pra FENECIT 2025, onde fomos avaliados
por 3 avaliadores ao mesmo tempo (e, surpreendentemente, sobrevivemos 😄).
Resultado: 2° lugar na categoria Ciências Sociais e Aplicadas entre todos os
projetos da FENECIT, posição dividida com outros projetos — e de brinde ainda
garantimos credencial pra representar o Brasil na MILSET AMLAT 2026, em
Medellín, Colômbia. Bora empacotar as malas! 🇨🇴

Ass: Bernardo Girardi Frigeri

### II Mostra Científica — Senac São Leopoldo

Data: [preencher]  
Local: Senac São Leopoldo, RS  
Intregrantes: Bernardo e equipe ([preencher nomes dos colegas])

Atividades realizadas: Depois do tamanho da FENECIT, encaramos uma mostra
mais de bairro, mas igualmente importante: a II Mostra Científica do Senac
São Leopoldo. O PayAI brilhou de novo e trouxemos pra casa o 1° lugar em uma
das áreas de competência avaliadas — prova de que o projeto convence tanto em
palco grande quanto em feira local.

Ass: Bernardo Girardi Frigeri