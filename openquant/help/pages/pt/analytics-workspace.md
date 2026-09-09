---
title: A área de trabalho Analytics
---
A área de trabalho Analytics (Ctrl+2) é o lote, quantitativamente: cada
componente em cada amostra, a integração de cada um, as curvas, as estatísticas
e a qualidade da corrida. É construída do modo como o MultiQuant é — um
componente escolhido à esquerda, um cromatograma por amostra para ele no meio, e
a tabela por baixo.

## Disposição

**Esquerda.** A árvore de componentes, agrupada pelos grupos do método, com
**All components** no topo; uma caixa de filtro acima dela; e dois painéis
dobráveis abaixo: **Integration** ([[integration-parameters]]) e **Acceptance**
([[acceptance-criteria]]). Os painéis começam dobrados, porque abertos deixam a
árvore com poucas linhas de altura, e se estavam abertos é lembrado.

**Centro.** A grade de [[peak-review]]: um painel por amostra para o componente
selecionado, com a área integrada sombreada.

**Base.** Seis abas: [[results-table|Results]], [[calibration|Calibration]],
[[statistics|Statistics]], [[metric-plot|Metric plot]], [[batch-qc|Batch QC]]
e [[mass-drift|Mass drift]].

## A barra de ferramentas

| Botão | Efeito |
|---|---|
| **Process batch** | extrai e integra cada componente válido em cada amostra aberta, depois ajusta as curvas, lê as concentrações e pontua os critérios de aceitação. Linhas integradas à mão em uma execução anterior são mantidas |
| **Recalibrate** | reajusta cada curva a partir das amostras marcadas como Standard e lê os desconhecidos de volta a partir delas, sem reintegrar |
| **Compare algorithms…** | integra o lote com todos os algoritmos e coloca as respostas lado a lado — veja [[compare-algorithms]] |
| **Compare batches…** | um projeto de referência contra este lote, componente a componente — veja [[compare-batches]] |
| **Magnify peak** | um painel preenchendo o painel principal; um duplo clique num painel faz o mesmo |

A linha de status à direita relata o que foi feito por último: quantas linhas em
quantas amostras, quantas integradas, qual padrão e qual qualificador o
componente selecionado tem.

## O que o "processamento" faz, em ordem

1. Para cada amostra e componente, o canal é correspondido e o XIC extraído e
   condicionado (suavização, linha de base) com as configurações de integração
   daquele componente.
2. O pico é encontrado e integrado pelo algoritmo do componente — veja
   [[integration-parameters]] e [[integration-algorithms]].
3. As razões de padrão interno e as razões iônicas de qualificador são
   calculadas — depois do lote inteiro, já que o próprio pico de um padrão tem
   de existir antes que algo possa ser dividido por ele.
4. As curvas são ajustadas a partir dos padrões, as concentrações lidas nelas e
   multiplicadas pela diluição de cada amostra, e as exatidões calculadas.
5. Cada linha é pontuada contra seus critérios de aceitação.

Uma mudança nas configurações de integração de um componente reprocessa apenas
aquele componente (ou seu grupo); tudo a jusante — razões, curvas,
concentrações, status — é recalculado a cada vez.

## Vinculação nos dois sentidos

Clicar em um painel da grade seleciona sua linha na tabela de resultados;
selecionar uma linha traz aquele componente na árvore e destaca seu painel;
clicar em um ponto do gráfico de métricas ou em uma linha do Batch QC faz o
mesmo. A tabela de resultados acompanha a árvore: com um componente selecionado
ela mostra as linhas daquele componente, com **All components** mostra tudo.

## Revisando um lote inteiro

**All components** na árvore coloca cada pico de cada componente na grade, uma
página por vez. Extrair todos eles — 141 componentes em 26 amostras — são cerca
de cem segundos de trabalho para pôr nove na tela, de modo que as páginas são
construídas conforme são viradas, em vez de todas de uma vez.
