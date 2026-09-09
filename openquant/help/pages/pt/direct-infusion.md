---
title: Infusão direta
---
Numa infusão direta não há coluna. A amostra é pulverizada na fonte por um
minuto ou dois e cada scan é o mesmo espectro mais ruído, de modo que o
cromatograma não carrega informação e o que vale olhar é a média da corrida
inteira. Aberta como se fosse uma corrida cromatográfica, uma infusão pede ao
leitor que escolha o canal de íons produto na árvore, arraste com Shift uma
faixa sobre uma linha plana e só então obtenha um espectro que valha mandar
para o [[lipid-maps]] ou para a [[spectral-library]].

O [[explorer]] reconhece uma infusão quando uma amostra é aberta e começa
pela média em vez disso.

## Como ela é detectada

Duas medidas, ambas de cromatogramas — nenhum espectro é lido, de modo que o
veredito não custa nada a mais e vale tanto num `.wiff` cujo `.wiff.scan`
está faltando quanto na mesma aquisição convertida para mzML:

- a fração do **cromatograma de íons totais da amostra** que fica em ou acima
  da metade do seu próprio máximo;
- a mesma medida sobre **o canal mais forte** — o canal de íons produto que
  carrega mais sinal, ou o survey se o método não tiver varredura de íons
  produto.

Ambas têm de ser de pelo menos **75%**. Um pico é, por definição, estreito
contra a corrida em que está, de modo que uma corrida com qualquer pico
dentro dela passa a maior parte dos seus scans bem abaixo da metade do ápice;
uma pulverização que apenas deriva fica acima dela do primeiro ao último
scan. As duas medidas são necessárias em vez de uma: um método agendado
adquire cada transição sobre a sua própria janela, e a soma de muitos picos
em tempos diferentes é mais plana que qualquer um deles, ao passo que uma
transição única de um branco é plana por estar vazia.

## Os números por trás dos limiares

Medido em todas as aquisições cromatográficas disponíveis — trinta e nove
delas, nenhuma marcada:

| conjunto de aquisições | n | TIC da amostra | canal mais forte |
|---|---|---|---|
| TripleTOF 5600, 21.4 min, 81 canais, MRM-HR | 5 | 0.016 – 0.043 | 0.025 – 0.088 |
| TripleTOF 5600, 14.6 min, 144 canais | 26 | 0.033 – 0.213 | 0.016 – 0.295 |
| ZenoTOF 7600, 24.0 min, 25 canais, DIA | 8 | 0.012 – 0.267 | 0.004 – 0.010 |

Os dois casos mais difíceis são ambos apanhados pela segunda medida. Uma
equilibração de coluna sem injeção nenhuma — solvente pulverizando por 24
minutos, o mais próximo de uma infusão em todo o conjunto — mede 0.267 no
total da amostra contra 0.006 no seu canal mais forte. Um branco que mede
0.295 no seu canal mais forte mede 0.049 no total da amostra. Nas trinta e
nove, a menor das duas medidas nunca passa de **0.098**, contra um limiar de
0.75; de uma infusão espera-se 0.95 – 1.00 nas duas.

O lado da infusão dessa comparação não foi medido em arquivos reais, e o
módulo diz isso com todas as letras. Os limiares são, portanto, postos onde a
margem cromatográfica é maior, em vez de na metade do caminho entre duas
populações medidas — que é também por que errar o veredito é feito barato:
ele só decide o que é mostrado primeiro.

Três outras regras foram tentadas e rejeitadas, com números, em
`openquant/infusion.py`: a correlação espectral de scan a scan (0.85 – 0.99
nos canais de íons produto de corridas em gradiente comuns, que é o canal que
importa), o coeficiente de variação do cromatograma de íons totais (sem
margem contra um branco, e que pune a deriva da pulverização) e a ausência de
um pico detectado (um traço plano com 3% de ruído ainda rende três).

## O que muda

Para uma amostra lida como infusão:

- a árvore escreve **infusion** ao lado do nome do instrumento, e passar o
  cursor sobre a amostra dá as medidas que a decidiram;
- o seu canal de íons produto mais forte vem marcado e torna-se o **active
  channel** (canal ativo), em vez do survey em que o Explorer aterrissaria;
- o painel do espectro abre na média de todos os scans, intitulado *average
  of N scans (infusion)*, e **infusion** aparece ao lado do tempo de
  retenção;
- tudo a jusante vê essa média, porque ela é o espectro ao vivo: a subtração
  de fundo, o *Explain spectrum*, a busca na biblioteca, a tabela de picos, o
  *Pin spectrum* e a exportação CSV.

Nada mais muda. O painel do cromatograma continua desenhando a corrente
iônica total ao longo do tempo, os controles de scan continuam avançando scan
a scan, e o [[contour-view]] continua sendo construído.

## Fazer à mão, e sobrepor a escolha

**Average whole run** (promediar a corrida inteira), na barra de ferramentas
Processing, faz o mesmo em qualquer amostra e em qualquer canal, infusão ou
não — útil para um canal que não seja o escolhido, e para uma corrida que a
regra não chamou de infusão.

Para sobrepor a escolha, trabalhe como de costume: escolha outro canal na
árvore ou no seletor **Active channel**, e avance scans ou arraste com Shift
uma faixa no cromatograma, como em [[chromatograms-and-spectra]]. Qualquer
uma dessas coisas substitui a média pelo que foi pedido; nada fica travado.

## O precursor acurado

O [[accurate-precursor]] ancora a sua medida na varredura de survey sobre um
pico no canal de íons produto, ou sobre o tempo de retenção de um componente.
Uma infusão não tem nem um nem outro: não há pico, e um tempo de retenção
copiado de um método cromatográfico aponta para fora de uma corrida que dura
um minuto. Numa infusão a medida toma o meio da corrida como âncora e
promedia a corrida inteira tanto para o survey quanto para o espectro de íons
produto, que é o máximo de sinal que a aquisição pode lhe dar.
