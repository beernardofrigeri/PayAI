# Diário de bordo

Anotações elaboradas a partir dos commits do repositório no GitHub desde 18
de novembro de 2025 até 23 de outubro de 2026. As datas abaixo consideram o
horário local dos commits (UTC−03:00); os registros são agrupados em um
resumo geral de todo o período.

## Resumo geral do período (18 de novembro de 2025 a 23 de outubro de 2026)

Data: 18 de novembro de 2025 a 23 de outubro de 2026  
Local: Casa  
Intregrantes: Bernardo (só eu mexi nisso)

Atividades realizadas: Nesse período o PayAI saiu de um script único e meio
bagunçado até a versão usada na XV Mostra IFTec. Primeiro reestruturei o
código, publiquei a versão 1.0 com README e `.gitignore` organizados, e troquei
a síntese de voz para o Edge-TTS. Depois vieram a splash screen com
carregamento progressivo e a inicialização paralela do sistema, pra abrir
mais rápido.

A parte de leitura de valores por OCR e detecção de QR Code deu bastante
trabalho. Corrigi exceções que travavam a detecção de QR Code, melhorei a
validação dos valores lidos (priorizando formato monetário e usando o
histórico de detecções pra não oscilar tanto) e criei uma busca alternativa
para quando o OCR principal não achava nada. Corrigi também o feedback visual
dos pagamentos e vários bugs de áudio e de leitura de QR Code que foram
aparecendo com o uso.

A arquitetura mudou de ideia umas duas vezes: separei tudo em módulos
(câmera, OCR, voz, desenho, configuração, logging, utilitários), depois
voltei pra um arquivo único porque a modularização tava atrapalhando mais do
que ajudando, e no fim organizei de novo, dessa vez dentro do pacote `payai`.
Limpei o código com Ruff, tirei arquivos e testes que não usava mais e
escrevi testes automatizados pros pontos que mais quebravam (parser de
valores, formatação de fala, detecção de QR Code e leitura de QR Code Pix).

Nas últimas semanas, já perto do fechamento das notas da XV Mostra IFTec,
corrigi três bugs que apareceram em uso real: a voz cortando no meio da fala
(Edge-TTS desatualizado e cancelamento de fala antes da hora), a leitura de QR
Code falhando com código pequeno, longe da câmera ou desfocado (resolvido com
um segundo detector e nitidez de imagem) e a leitura de QR Code Pix, que agora
fala o valor cobrado e o nome de quem recebe, sem nunca revelar a chave Pix.

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