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

Esse máximo é o **scan do percentil 99, não o maior deles**. O maior é um
único scan, e um transiente de pulverização também é: três das nove infusões
reais medidas carregam um logo no início da aquisição, de duas a quatro vezes
a mediana da corrida, e metade desse pico fica acima de todos os outros scans
de uma corrida perfeitamente plana. Pôr de lado o um por cento mais alto dos
scans não custa nada numa corrida que tenha um pico de verdade — um pico são
muitos scans — e é a diferença entre ler essas três infusões em 0.002 e
lê-las em 1.00. As medidas mostradas ao pairar sobre a amostra dizem qual
referência foi usada.

Ambas têm de ser de pelo menos **75%**. Um pico é, por definição, estreito
contra a corrida em que está, de modo que uma corrida com qualquer pico
dentro dela passa a maior parte dos seus scans bem abaixo da metade do ápice;
uma pulverização que apenas deriva fica acima dela do primeiro ao último
scan. As duas medidas são necessárias em vez de uma: um método agendado
adquire cada transição sobre a sua própria janela, e a soma de muitos picos
em tempos diferentes é mais plana que qualquer um deles, ao passo que uma
transição única de um branco é plana por estar vazia.

## Os números por trás dos limiares

Medido em todas as aquisições disponíveis — quarenta e oito delas, as duas
populações, **nenhuma das quarenta e oito classificada errado**:

| conjunto de aquisições | n | TIC da amostra | canal mais forte |
|---|---|---|---|
| ZenoTOF 7600, 0.6 – 2.0 min, infusões de íons produto de padrões de ácidos biliares | 9 | 0.9937 – 1.0000 | 0.9937 – 1.0000 |
| TripleTOF 5600, 21.4 min, 81 canais, MRM-HR | 5 | 0.019 – 0.057 | 0.029 – 0.097 |
| TripleTOF 5600, 14.6 min, 144 canais | 26 | 0.033 – 0.426 | 0.016 – 0.377 |
| ZenoTOF 7600, 24.0 min, 25 canais, DIA | 8 | 0.031 – 0.361 | 0.014 – 0.059 |

Os casos cromatográficos mais difíceis são ambos apanhados pela segunda
medida. Uma equilibração de coluna sem injeção nenhuma — solvente
pulverizando por 24 minutos, o mais próximo de uma infusão em todo o conjunto
— mede 0.361 no total da amostra contra 0.059 no seu canal mais forte. Um
branco que mede 0.377 no seu canal mais forte mede 0.049 no total da amostra.
Nas trinta e nove corridas cromatográficas, a menor das duas medidas nunca
passa de **0.1148**, e nas nove infusões nunca cai abaixo de **0.9937**. O
limiar de 0.75 fica, portanto, 0.635 acima da pior corrida cromatográfica e
0.244 abaixo da pior infusão, dentro de uma folga de 0.879.

Essa folga não existia antes de a referência mudar. Lidas contra o maior
scan, três das nove infusões mediram 0.0021, 0.0039 e 0.0063 — **abaixo de
todas as trinta e nove corridas cromatográficas**. As duas populações não
estavam apenas sobrepostas, estavam invertidas, e nenhum limiar as teria
separado. Um único scan fez isso: um transiente em 0.008 min, de 2.8 a 4.4
vezes a mediana da corrida, e num dos arquivos mais duas rajadas no meio
dela. A estatística estava errada, não o limiar — e é por isso que a
referência agora é o scan do percentil 99.

O percentil 99 está onde está porque foi medido. O 99.5 não basta — os três
scans com pico de um dos arquivos são 0.63% dos seus 473, de modo que
sobrevivem a ele, que lê 0.639 — enquanto o 95 e o 90 levantam as medidas
cromatográficas para 0.262 e 0.410 ao pôr de lado ápices de picos reais. A
maior margem medida é 0.895 no percentil 99.2 e 0.879 no 99.

Abaixo de uns cem scans o percentil 99 volta a ser o maior scan, de modo que
um pico isolado ainda poderia chamar de cromatográfica uma infusão muito
curta. Isso é uma lacuna declarada e não uma lacuna corrigida; a infusão mais
curta medida tem 146 scans, e errar o veredito é barato de propósito — ele só
decide o que é mostrado primeiro.

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
