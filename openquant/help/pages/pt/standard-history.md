---
title: Histórico do padrão
---
Um registro escrito na sua própria biblioteca é uma verificação que já
aconteceu. Toda vez que o padrão é infundido para conferir o frasco, mais um
registro do mesmo composto entra no mesmo MSP — e depois de alguns meses
esse arquivo guarda a única medida daquele padrão ao longo do tempo que
existe.

**History…**, ao lado da contagem de registros na aba
[[spectral-library]], lê tudo de volta. É o [[batch-qc]] perguntado a uma
biblioteca em vez de a um lote: o mesmo centro robusto, as mesmas duas
condições que um ponto precisa cumprir antes de ser chamado de fora do
limite, a mesma tendência que exige tamanho e direção — com os registros na
ordem em que foram **adquiridos**, e não na ordem em que foram digitados.

## O que é agrupado com o quê

Os registros de um composto são cortados em **séries** por energia de
colisão e ativação, e nada é comparado através dessa fronteira. Um espectro
medido em outra energia tem outros fragmentos e muitas vezes outro pico
base, de modo que um cosseno contra ele mede o método e não o padrão; e uma
intensidade absoluta só é comparável dentro de um mesmo método. Medido em um
padrão infundido real, o ácido cólico-d4, o mesmo composto no mesmo frasco
obteve **67 em EAD 12 eV contra EAD 22 eV, 29 em EAD 22 eV contra CID 45 eV
e 6 em EAD 12 eV contra CID 45 eV** — três números que não dizem nada sobre
o frasco e tudo sobre a cela de colisão.

O composto é a parte do nome do registro antes do primeiro separador, como
no [[infusion-report]]. A ativação é lida de um campo `Activation` onde
algum exportador escreveu um, e do nome do registro caso contrário —
`..._EAD_22CE_...` — porque nenhum campo que este programa lê de um `.wiff`
a carrega: as nove infusões do ZenoTOF disponíveis dizem todas `TOF PI` e
`Product`, e a energia dos elétrons aparece apenas no nome do arquivo. Um
registro cujo nome não diz é agrupado como *não declarado*, nunca como CID.

### A fronteira da série não é o fim da história

Esses três números — 67, 29 e 6 — são a razão de uma série nunca cruzar uma
energia, e são também três medidas desperdiçadas. Os mesmos registros que não
podem ser postos em gráfico uns contra os outros *podem* ser lidos como uma
curva: como a fração de intensidade de cada fragmento se move conforme a
energia sobe. Isso é o perfil de energia, é calculado a partir dos registros de
um composto sem cruzar série alguma, e é o que permite à aba
[[spectral-library]] dizer **compatible with CA-d4 EAD at ~18 eV** em vez de
listar três registros que parecem todos errados.

O do ácido cólico-d4, em frações do total do próprio perfil — as mesmas nove
infusões de onde vêm os números desta página:

| Íon | m/z | EAD 12 eV | EAD 22 eV | 45 eV, não declarada |
|---|---|---|---|---|
| `[M+NH4]+ +4D` | 430,3465 | 83,5% | 24,6% | 0,0% |
| `[M+H]+ (-NH3) +4D` | 413,3200 | 0,0% | 0,9% | 0,0% |
| `[M+H-H2O]+ +4D` | 395,3094 | 0,0% | 6,5% | 0,0% |
| `[M+H-H2O]+ +3D` | 394,3031 | 0,0% | 0,3% | 0,0% |
| `[M+H-2H2O]+ +4D` | 377,2988 | 1,5% | 25,2% | 1,7% |
| `[M+H-2H2O]+ +3D` | 376,2926 | 1,3% | 2,0% | 0,0% |
| `[M+H-3H2O]+ +4D` | 359,2883 | 0,0% | 6,2% | 54,2% |
| `[M+H-3H2O]+ +3D` | 358,2820 | 0,0% | 6,5% | 6,8% |
| doze fragmentos compartilhados abaixo de m/z 150, juntos | | 13,7% | 27,8% | 37,2% |

O pico-base é um íon diferente em cada um dos três arquivos — o precursor,
depois `[M+H-2H2O]+`, depois `[M+H-3H2O]+` — que é por que o perfil é mantido
em frações do próprio total, e não em relação a um pico-base que se muda. É
também por que o gráfico de *intensidade do pico-base* abaixo é traçado dentro
de uma série e nunca através de uma.

O perfil é calculado a partir dos registros presentes e nunca é escrito neles,
de modo que acrescentar mais uma verificação o altera sem deixar nada
desatualizado. Veja [[spectral-library]] para a interpolação, as duas recusas —
nada extrapolado além da faixa medida, nenhuma ativação cruzada com outra — e o
que duas energias por ativação permitem e não permitem.

## Os três gráficos

O primeiro registro de uma série é a **referência**, e tudo é medido contra
ele.

| Gráfico | O que pergunta | Sinalizado além de |
|---|---|---|
| Escore contra o primeiro registro | ainda se parece consigo mesmo | 20% do centro e 3σ, ou 50% de imediato |
| Pico base, ppm do primeiro registro | o pico base ainda é o mesmo íon, no mesmo lugar | 20 ppm e 3σ, ou 40 ppm de imediato |
| Intensidade do pico base | ainda está dando o que dava | 20% e 3σ, ou 50% de imediato |

O escore é o mesmo cosseno que a busca em biblioteca usa, para que "quão
parecidos são estes dois espectros" tenha uma resposta só neste programa; o
cosseno reverso fica ao lado dele, porque um padrão que ganhou uma impureza
manteve tudo o que tinha e ganhou algo. A tabela traz também o escore contra
o registro **anterior**, que é o que diz se a mudança aconteceu em uma
verificação ou foi se acumulando.

O gráfico de massa é a única métrica que não pode ser uma porcentagem do
próprio centro — uma mediana de zero ppm não tem porcentagem de si mesma —
então seus limites são escritos em ppm e sua tendência é uma diferença
simples. Um pico base a mais de 50 ppm do da referência não é traçado: isso
é outro íon, não um erro de massa, e a linha diz `not the same ion` com as
duas massas ao lado. É a lição do [[mass-drift]] em outro lugar — uma medida
que não pode ser mostrada como sendo do mesmo íon não é julgada.

## Três registros, não dois

Nenhum limite é traçado com menos de três registros. Abaixo disso todos os
gráficos dizem **too few to chart** e os registros continuam listados,
porque uma mediana e uma dispersão tiradas de dois pontos são uma reta por
dois pontos, e quem vê limites desenhados vai lê-los. Um lote ganha seis, e
pode: ele é adquirido em uma tarde. Um histórico acumula um registro por
verificação, e seis deles são um ano.

## O que um registro precisa carregar

Dois campos são escritos em todo registro feito a partir desta versão, e
nenhum dos dois pode ser recuperado depois:

- **Acquired** — o dia em que o instrumento mediu, lido do arquivo, e não o
  dia em que o registro foi digitado. Uma pasta adquirida ao longo de três
  meses e escrita em uma biblioteca numa tarde é três meses de histórico, e
  `added 2026-09-10` não diz nada sobre o padrão. Ele aparece, somente para
  leitura, no diálogo *Add spectrum to library*.
- **Base peak intensity** — a altura do pico base em contagens. Todo formato
  de biblioteca guarda os picos como fração do pico base, então o tamanho do
  espectro se perde no instante em que o registro é escrito, a menos que
  seja escrito junto.

Um registro feito antes desses campos existirem continua sendo lido: ele é
ordenado pela ordem em que o arquivo o guarda, sua intensidade fica fora
daquele gráfico, e as duas coisas são ditas no gráfico em vez de passarem em
silêncio.

## O que foi medido

Nove infusões de ácidos biliares no ZenoTOF, escritas em uma biblioteca
própria e lidas de volta: nove registros, sete séries, todas adquiridas em um
único dia. **Dois registros em uma energia é o que a pasta tem** — esperava-se
que as aquisições `_TESTEARTIGO` fossem repetições das `_mix1` nas mesmas
energias, e não são. Elas isolaram m/z 839,56 numa faixa de 100–1000, onde as
infusões `_mix1` isolaram 430,34 em 50–500, e o histórico diz isso sem que
ninguém o avise: em EAD 22 eV o segundo registro obteve escore **8** com pico
base em 839,2343 contra 377,3015 — *não é o mesmo íon* — a 2,4% da altura do
primeiro registro; em 12 eV obteve **0**, a 0,9% dela.

Como nenhuma série real chega a três registros, os limites foram exercitados
cortando seis das infusões em três terços consecutivos cada — dezoito
registros, seis séries, um padrão em uma energia por série, nada mudando
entre eles. Esse é o piso da medida: o escore contra o primeiro terço ficou
entre **98,7 e 100,0**, o pico base se manteve em **0,4 ppm**, e a altura do
pico base variou **até 4,5%**, o que deixou um dos seis gráficos de
intensidade com um ponto além de dois sigmas. Um dos terços da infusão de
ácido cólico-d4 em EAD 22 eV teve o pico base trocado do fragmento em
377,3014 para o precursor em 430,3489 — dois picos de altura quase igual, e
qual deles é o maior muda ao longo da corrida. Esse registro saiu do gráfico
de massa como *not the same ion*, que é a resposta pretendida.

Ler uma biblioteca de nove registros como histórico completo leva cerca de
3 ms.

## O que ele não é

É um gráfico de controle de um padrão contra si mesmo, e tem o mesmo limite
que o [[batch-qc]] declara: não distingue um instrumento que mudou de um
frasco que mudou. Vários padrões caindo juntos em uma verificação é o que
diz qual dos dois, e esse julgamento é do analista — isto desenha os
gráficos que o tornam possível. **Export CSV…** escreve todos os registros
com o que cada gráfico disse acima das linhas.

Ele também precisa de registros, o que significa que alguém tem de os ter
escrito. As mesmas duas regras — cinquenta ppm para *o mesmo íon*, vinte por
cento para *a mesma resposta* — são aplicadas a uma bandeja inteira de uma
vez pelo [[compare-infusions]], que lê um dia de referência do arquivo de
projeto em vez de uma biblioteca, e não precisa que nada tenha sido
acrescentado a uma.
