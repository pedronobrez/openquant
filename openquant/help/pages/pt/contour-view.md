---
title: Vista de contorno
---
**View ▸ Contour** no topo do [[explorer]] desenha o canal ativo como uma
superfície: tempo de retenção na horizontal, m/z na vertical, intensidade como
cor. Um cromatograma soma e elimina o eixo de massa e um espectro soma e elimina
o eixo de tempo; o contorno são os mesmos dados sem nenhum dos dois somados, de
modo que uma interferência situada ao lado de um alvo, ou uma crista percorrendo
toda a corrida em uma massa, é visível em vez de inferida.

## O que é desenhado

Cada scan do canal é uma linha e cada bin de m/z uma coluna. O eixo de massa é
dividido em cerca de 1,400 bins — grosso modo um por pixel de tela ao longo de
uma faixa ampla; mais fino do que isso a figura é a mesma, apenas mais lenta.
Uma corrida longa tem mais scans do que uma tela tem linhas, e os scans acima do
limite de cerca de 900 linhas são **promediados em sua linha, não pulados**:
amostrar cada k-ésimo scan é mais rápido e perde inteiramente um pico de um
único scan, o que é o oposto daquilo para que serve uma figura dos dados. A
média em vez da soma, porque o último grupo em geral é curto e uma linha que
fica mais escura apenas por isso seria uma mentira sobre os dados.

Os espectros são tomados sem seus zeros restaurados: um histograma de
intensidades não pode ser alterado pelo acréscimo de pontos de intensidade zero,
e restaurá-los foi medido como triplicando o tempo para a mesma grade.

## Controles

| Controle | Efeito |
|---|---|
| **Intensity** | como as intensidades viram cor: *sqrt* (padrão), *log* ou *linear*. Uma rampa linear sobre quatro décadas mostra o pico-base e mais nada; a raiz quadrada traz os íons menores à vista sem o achatamento que faz um gráfico logarítmico parecer uniformemente cinza |
| **Colours** | a paleta: inferno, viridis, magma, turbo, CET-L9 |
| **Extract this view** | o cromatograma e o espectro do retângulo na tela — ambos tomados do leitor, não da grade |
| **Rebuild** | reconstruir a grade sobre a faixa atualmente na tela, em resolução plena para aquela faixa |
| clicar | o espectro do scan sob o cursor, no painel de espectro |
| leitura | o tempo de retenção, o m/z e a intensidade sob o cursor |

O topo da escala de cor é o percentil 99.7 das intensidades, não o máximo: um
único scan saturado ou com um pico espúrio de outro modo definiria a escala para
todo o resto e deixaria o restante da superfície preto.

## Nada é quantificado a partir do contorno

Seus bins de m/z são mais largos que os passos do instrumento e suas linhas
podem ser vários scans promediados, de modo que ele é uma figura,
deliberadamente. *Extract this view* volta ao leitor tanto para o XIC quanto
para o espectro, e são esses que o [[manual-xic]] e a aba Results utilizam.

A leitura sob o cursor busca as bordas dos bins para a direita, porque é ali que
um valor situado exatamente sobre uma borda é colocado pelo histograma; buscar
para a esquerda lê a célula ao lado e a leitura discorda da figura — apanhado
por um teste, não a olho nu.
