---
title: Cromatogramas e espectros
---
## O painel do cromatograma

Cada canal marcado é um traço. O nó *Sample TIC* desenha o cromatograma de íons
totais (TIC) da corrida, que é somado **por ciclo, não por tempo**: os
experimentos de um ciclo são medidos um após o outro, de modo que a união de
seus tempos é um ponto por espectro — 23,722 onde o instrumento reporta 577 — e
o programa reporta os 577 do instrumento. Um canal desenhado como **TIC** é a
soma de cada um de seus scans; como **BPC**, o pico mais alto de cada scan.

| Gesto | Efeito |
|---|---|
| clique simples | espectro do scan sob o cursor |
| arrastar | zoom por faixa elástica |
| duplo clique | ajustar o traço |
| Shift + arrastar, ou arrastar com *Select range* ligado | selecionar um intervalo: o painel de espectro mostra a média sobre ele, ao vivo, enquanto a seleção é arrastada ou redimensionada, e a barra de status relata a integração do intervalo — área, altura, ápice e S/N |
| ← → | scan anterior e seguinte |
| clique com o botão direito | o menu do gráfico: exportar como imagem, eixos, grade |

**Stack** dá a cada traço um painel próprio, com os eixos de tempo travados, de
modo que um zoom em um é um zoom em todos. **Overview** acrescenta um navegador
ao longo da base: a faixa completa, com o zoom atual desenhado como uma janela
que pode ser arrastada. **Mirror** desenha um traço a cada dois para baixo, que
é como uma amostra é comparada contra seu branco. **Cascade** desloca traços
sobrepostos em x (minutos) e em y (por cento da altura) de modo que oito corridas
quase idênticas possam ser distinguidas.

**RT labels** põe o tempo do ápice em cada pico. Com um marcador presente,
**Relative labels** rotula novamente os picos pela distância até ele.

## O painel do espectro

O espectro de um scan do canal ativo, ou a média sobre um intervalo selecionado.
Canais de íons produto mostram o que sobreviveu à fragmentação de seu precursor;
o canal de survey (TOF MS) mostra tudo o que elui naquele momento.

| Gesto | Efeito |
|---|---|
| Shift + arrastar | selecionar um intervalo de m/z |
| clique com o botão direito | *Extract XIC from selection*, *Find formula for this peak*, *Add marker here*, *Clear markers*, *Clear theoretical overlay* |
| arrastar / duplo clique | zoom / ajustar |

**Marcadores.** Solte um marcador sobre um pico e os demais picos são rotulados
com sua distância até ele em daltons, que é como perdas neutras (18.011 para
água, 44.026 para CO₂, 87.032 para uma serina) e espaçamentos isotópicos são
lidos em um espectro. Vários marcadores podem ser colocados; *Clear markers* os
remove.

Aba **Spectrum peaks**. Os picos do espectro na tela — m/z, intensidade e por
cento do pico-base — encontrados por máximo local, centroidizados em dados de
perfil, e fundidos quando mais próximos que 0.03 Da, de modo que o topo ondulado
de um perfil não apareça como cinco massas. Dê duplo clique numa linha para
extrair aquela massa como um XIC.

*Average whole run*, na barra de ferramentas Processing, promedia todos os
scans do canal ativo — que é como uma [[direct-infusion]] é aberta.

## Comparando espectros entre amostras

O painel do cromatograma sobrepõe tantos traços quantos estiverem marcados; o
painel do espectro mostra um espectro por vez, porque um espectro pertence a um
scan de um canal de uma amostra. **Pin spectrum** (a barra de ferramentas
Processing, ou o menu de contexto do espectro) mantém o espectro na tela de modo
que o próximo desenhe sobre ele: mude para outra amostra na árvore, outro scan
ou outro canal, e o novo espectro é desenhado em azul sobre os fixados, cada um
em sua própria cor e nomeado na legenda pela amostra, pelo canal e pelo scan de
onde veio. Vários podem ser fixados; **Unpin spectra** os limpa.

Dois interruptores tornam a comparação legível. **Normalise** põe cada espectro
sobre seu próprio pico-base, que é o que duas amostras em concentrações
diferentes precisam. **Mirror** desenha um espectro a cada dois para baixo, de
modo que um espectro fixado e o ao vivo tornam-se um gráfico cabeça-cauda — o
modo como uma correspondência de biblioteca é usualmente mostrada, e a maneira
mais rápida de ver um pico presente em um e ausente no outro. Com mais de um
fixado, as cores fazem a separação e o Mirror alterna.

Todo o resto lê o espectro ao vivo: a tabela de picos, o [[formula-finder]], o
Explain do [[lipid-maps]], a [[spectral-library]]. As cópias fixadas são
figuras, e são perdidas quando os arquivos são fechados.

## Espectros de perfil e seus zeros

Um espectro de perfil de um `.wiff` e o mesmo espectro de um mzML não têm o
mesmo número de pontos. A SCIEX retira os pontos de intensidade zero ao
armazenar e os repõe ao desenhar; um mzML carrega o que foi armazenado.
Desenhado como vem, uma linha vai direto do último ponto de um pico ao primeiro
ponto do seguinte e o trecho vazio entre eles parece uma linha de base
inclinada — sinal onde não há nenhum. Pior, um rótulo de pico tomado através da
lacuna estava errado: um leu 184.8466 para um pico em 185.0077.

Então o programa restaura os zeros para qualquer formato que não os tenha,
medindo o intervalo de amostragem a partir do próprio arquivo: o menor quarto
das lacunas entre pontos são as que estão dentro dos picos, e interpolá-las ao
longo do eixo de massa dá o intervalo em qualquer massa — nenhuma física de
instrumento é presumida, o que cobre igualmente um tempo de voo e um Orbitrap.
Cada ponto acrescentado é um zero, em uma massa onde o instrumento não reportou
nada; nenhuma intensidade muda. Um espectro que já carrega seus zeros não tem
lacuna larga o bastante para acioná-lo e volta intocado.

## Centroide

*Centroid* na barra de ferramentas Processing converte um espectro de perfil em
bastões: um por pico, no centro de massa ponderado pela intensidade, tão alto
quanto o ápice do perfil. Um espectro centroidizado tem menos pontos que seu
perfil, razão pela qual a sobreposição de padrão isotópico teórico e o
localizador de fórmula trabalham sobre o que estiver sendo mostrado.

## Suavização e linha de base

**Smooth (σ, scans)** aplica um filtro gaussiano dessa largura a cada
cromatograma; 0 o desliga. Uma gaussiana é o filtro certo para cromatografia
porque, ao contrário de uma média móvel, preserva a posição e a área do pico.
**Baseline (min)** estima um envelope inferior sobre uma janela dessa largura —
mínimos por bloco, interpolados e suavizados — e o subtrai; a janela tem de ser
mais larga que o pico mais largo que valha a pena manter, ou o pico é tomado
como linha de base. Ambos se aplicam ao desenho, à integração e à exportação, de
modo que um número na aba Results é o número na tela.

## Subtração de fundo

Selecione um trecho de cromatograma que não contenha pico e use **Set
background**: o espectro médio sobre aquele intervalo é subtraído de cada
espectro mostrado até **Clear background**. O intervalo em uso é nomeado ao lado
dos controles de scan.
