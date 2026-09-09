---
title: Áreas de trabalho e a sessão
---
A janela é organizada do modo como o SCIEX OS é: as áreas de trabalho são abas,
e uma única sessão está por trás delas. Os arquivos abertos, a lista de
amostras, a tabela de componentes, os resultados e as curvas de calibração
existem uma vez só, de modo que uma amostra tipada como Standard em um lugar é
Standard em todos, e um componente editado na área de trabalho Method é o que a
área de trabalho Analytics integra.

| Área de trabalho | Atalho | Para que serve |
|---|---|---|
| **Explorer** | Ctrl+1 | revisão qualitativa dos dados brutos: cromatogramas, a [[contour-view]], espectros, íons extraídos, química — ver [[explorer]] |
| **Analytics** | Ctrl+2 | o lote, quantitativamente: um cromatograma por amostra para cada componente, a tabela de resultados, calibração, estatística e QC — ver [[analytics-workspace]] |
| **Method** | Ctrl+3 | a tabela de componentes — o que extrair, onde, e como o resultado é reportado — ver [[method-workspace]] |
| **Samples** | Ctrl+4 | o lote: tipo de amostra, grupo de estudo, concentração esperada, diluição — ver [[samples-workspace]] |

O menu `Workspace` lista as mesmas quatro. Todo atalho da aplicação está
reunido em [[keyboard-shortcuts]].

## Os menus

| Menu | Contém |
|---|---|
| File | New, Open e Save project; Add data files; Close all; Export report; as exportações do Explorer (cromatogramas e espectro como CSV, amostra como mzML); Quit |
| View | as chaves de exibição do Explorer: Fit, Normalise, Mirror, Stack, Overview, rótulos, legenda |
| Panels | uma entrada por painel lateral do Explorer, Ctrl+Shift+1 em diante |
| Process | Centroid, marcadores, background, Explain spectrum, Detect peaks |
| Workspace | as quatro abas |
| Help | este manual (F1, na página correspondente a onde está o foco), as dicas rápidas, e o manual como PDF |

## Tema

A aplicação acompanha o sistema ao entrar e sair do modo escuro enquanto está
em execução; os gráficos são recoloridos junto. A barra de status nomeia o tema
em uso quando ele muda.

## O que é lembrado entre sessões

A geometria da janela, a última pasta de onde um arquivo foi aberto ou para
onde foi salvo, se os painéis Integration e Acceptance da área de trabalho
Analytics estavam recolhidos, e se o aviso inicial foi dispensado de vez. Nada
sobre um lote é lembrado fora do arquivo de projeto dele.

## A barra de status

Toda área de trabalho reporta o que fez por último na barra de status ao pé da
janela — quantas linhas foram processadas, o que um clique integrou, por que
uma ação não fez nada. Quando algo parece não ter acontecido, a barra de status
costuma dizer por quê.
