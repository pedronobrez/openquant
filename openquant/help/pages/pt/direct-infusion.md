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

Esse máximo é o **scan do percentil 99, não o maior deles**, tomado sobre os
scans que sobram depois do **primeiro segundo de aquisição**. O maior é um
único scan, e um transiente de pulverização também é: três das nove infusões
reais medidas carregam um logo no início da aquisição, de duas a quatro vezes
a mediana da corrida, e metade desse pico fica acima de todos os outros scans
de uma corrida perfeitamente plana. Pôr de lado o um por cento mais alto dos
scans não custa nada numa corrida que tenha um pico de verdade — um pico são
muitos scans — e é a diferença entre ler essas três infusões em 0.002 e
lê-las em 1.00. O primeiro segundo sai porque um por cento de uma corrida
*curta* volta a ser um único scan; veja adiante. As medidas mostradas ao
pairar sobre a amostra dizem qual referência foi usada.

Ambas têm de ser de pelo menos **75%**. Um pico é, por definição, estreito
contra a corrida em que está, de modo que uma corrida com qualquer pico
dentro dela passa a maior parte dos seus scans bem abaixo da metade do ápice;
uma pulverização que apenas deriva fica acima dela do primeiro ao último
scan. As duas medidas são necessárias em vez de uma: um método agendado
adquire cada transição sobre a sua própria janela, e a soma de muitos picos
em tempos diferentes é mais plana que qualquer um deles, ao passo que uma
transição única de um branco é plana por estar vazia.

E uma corrida plana com menos de **120 scans** não é chamada de infusão de
jeito nenhum. Ela é relatada como **too short to tell** (curta demais para
dizer), com as duas medidas, e tratada como não sendo infusão. Por quê, e por
que 120, está na última seção desta página.

## Os números por trás dos limiares

Medido em todas as aquisições disponíveis — quarenta e oito delas, as duas
populações, corridas inteiras, **nenhuma das quarenta e oito classificada
errado**:

| conjunto de aquisições | n | TIC da amostra | canal mais forte |
|---|---|---|---|
| ZenoTOF 7600, 0.6 – 2.0 min, 146 – 473 scans, infusões de íons produto de padrões de ácidos biliares | 9 | 0.9936 – 1.0000 | 0.9936 – 1.0000 |
| TripleTOF 5600, 21.4 min, 577 scans, 81 canais, MRM-HR | 5 | 0.019 – 0.057 | 0.030 – 0.097 |
| TripleTOF 5600, 14.6 min, 61 scans, 144 canais | 26 | 0.033 – 0.433 | 0.017 – 0.383 |
| ZenoTOF 7600, 24.0 min, 482 – 490 scans, 25 canais, DIA | 8 | 0.031 – 0.364 | 0.015 – 0.060 |

Os casos cromatográficos mais difíceis são ambos apanhados pela segunda
medida. Uma equilibração de coluna sem injeção nenhuma — solvente
pulverizando por 24 minutos, o mais próximo de uma infusão em todo o conjunto
— mede 0.364 no total da amostra contra 0.060 no seu canal mais forte. Um
branco que mede 0.383 no seu canal mais forte mede 0.050 no total da amostra.
Nas trinta e nove corridas cromatográficas, a menor das duas medidas nunca
passa de **0.1167**, e nas nove infusões nunca cai abaixo de **0.9936**. O
limiar de 0.75 fica, portanto, 0.633 acima da pior corrida cromatográfica e
0.244 abaixo da pior infusão, dentro de uma folga de 0.877.

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

## Corridas curtas, e a resposta "too short to tell"

Um percentil põe de lado uma *fração* dos scans, e um por cento de uma
corrida curta é um scan. Cada uma das quarenta e oito aquisições foi truncada
aos seus primeiros 20, 30, 50, 75 e 100 scans e lida de novo. Só com o
percentil, a pior das nove infusões lê:

| primeiros N scans | pior infusão | pior corrida cromatográfica |
|---|---|---|
| 20 | **0.0500** | 0.9500 |
| 30 | **0.0333** | 0.9667 |
| 50 | **0.0200** | 0.6735 |
| 75 | **0.3333** | 0.8919 |
| 100 | 0.9900 | 0.9394 |
| a corrida inteira | 0.9937 | 0.1148 |

As três infusões com transiente ficam invertidas outra vez, até oitenta scans
e não até os cem que se supunha. Deixar o **primeiro segundo de aquisição**
fora tanto da referência quanto da contagem resolve isso por completo, porque
é ali que está o transiente — scan 1, meio segundo depois do início — e
depois disso o lado das infusões deixa de se mexer com o comprimento:
**1.0000 em cada uma dessas truncagens**, e 0.9936 na corrida inteira. Outras
duas regras foram medidas e são piores. Deixar o primeiro segundo fora e
voltar ao maior scan como referência falha na corrida inteira, onde um
arquivo tem mais duas rajadas um minuto adentro e lê 0.0043. Fazer a
referência ser a mediana dos poucos scans mais altos, com esse "poucos"
amarrado ao comprimento da corrida, sobrevive a um pico mas não a três, e lê
0.0100 nesse mesmo arquivo.

A coluna da direita da tabela acima é a parte que nenhuma referência conserta,
e é por isso que corridas curtas e planas são recusadas. Um gradiente cortado
antes de qualquer coisa eluir é plano, e "plano" é tudo o que essas duas
medidas medem. Uma corrida real do conjunto não carrega nada até 8.9 minutos:
**os seus primeiros cem scans leem 1.0000 no total da amostra e 0.9388 no seu
canal mais forte**, que é exatamente a assinatura de uma infusão. Nada num
cromatograma distingue as duas, porque não há nada ali para distinguir — as
duas são uma linha plana.

Assim, o limiar de 0.75 não separa as duas populações em comprimento nenhum
abaixo de 240 scans, que é mais do que tem a infusão real mais curta. O piso
vai para onde o resto da medição o sustenta: fora esse único arquivo, nenhuma
das trinta e nove corridas cromatográficas lê como plana depois de **35**
scans, e a infusão mais curta medida tem **146** — de modo que o piso é
**120**, entre os dois. Abaixo dele uma corrida plana é relatada como *too
short to tell* e tratada como não sendo infusão.

O piso vale só para a resposta "plana". Uma corrida que mostra estrutura é
cromatográfica em qualquer comprimento, e é por isso que as vinte e seis
corridas de 61 scans continuam lendo "chromatographic" com as suas medidas em
vez de "too short to tell". E a perda é real e está declarada: uma infusão
genuína com menos de 120 scans seria recusada, assim como aquele gradiente no
trecho entre 154 e 234 scans em que ele ainda é plano. Errar o veredito é
barato de propósito — ele só decide o que é mostrado primeiro.

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

## Uma infusão de outro instrumento

Tudo nesta página é lido de cromatogramas, de modo que nada disso depende de
onde o arquivo veio. Uma infusão convertida para mzML — um `.raw` da Thermo,
um `.d` da Agilent, um `.tdf` da Bruker pelo `msconvert` — passa pela mesma
detecção, pela mesma média, pela mesma explicação do [[lipid-maps]], pela
mesma busca na [[spectral-library]] e pelo mesmo [[infusion-report]]. Ver
[[formats]] para o que um arquivo convertido declara sobre cada scan e o que
ele não pode declarar.

Isso foi verificado, não suposto. Uma infusão real de ácido cólico-d4 num
ZenoTOF 7600 foi lida de três maneiras — do `.wiff`, do mzML exportado dele,
e desse mzML reescrito como o ProteoWizard escreve um arquivo Thermo, com
identificadores de scan Thermo, tempos em segundos, uma janela de
isolamento, um estado de carga, HCD nomeado em `activation`, e nada dizendo
a que experimento um scan pertence. As três leram **um canal de íons
produto**, precursor 430,34 a 22 eV, 146 scans ao longo de 0,61 minuto,
**1,0000 nas duas figuras**, e o mesmo espectro médio: pico base 377,3018 a
9.618,10 contagens, 424 centroides, 42 picos acima da fração de ruído, o
precursor sobrevivendo a 430,3489 com 9.415 contagens, e a fórmula
explicando 8 de 56 íons previstos e 63,63% do espectro. O arquivo no formato
Thermo nomeia além disso o seu instrumento, a sua carga e a sua ativação,
que um `.wiff` não carrega.

Duas infusões reais de Orbitrap da Thermo, de um repositório público, também
foram lidas, e nenhuma das duas é chamada de infusão. As duas recusas são a
aquisição e não o formato, e as duas vale conhecer:

- **Uma corrida curta demais para que a planura signifique algo.** Um LTQ
  Orbitrap Elite pulverizando por três minutos dá 108 scans de cerca de 1,7
  segundo cada, o que fica abaixo do piso de 120 scans acima. Ela também lê
  **0,5943** em vez de 1,0000, porque o spray decai ao longo dos primeiros
  dez segundos e só um segundo é posto de lado: a 1,7 segundo por scan, essa
  rampa são seis scans e a janela de acomodação alcança dois deles. Lida a
  mesma corrida com dez segundos postos de lado, dá 0,8812. A janela de
  acomodação é de um segundo porque foi medida em um ciclo de um quarto de
  segundo, onde o transiente é um único scan meio segundo adentro; num
  instrumento mais lento ela é curta.
- **Uma corrida que varre de propósito.** Uma infusão de precursor em passos
  — a janela de isolamento caminhada sobre o precursor em incrementos de
  0,02 Da enquanto a amostra é pulverizada — tem uma corrente iônica que
  sobe e desce com onde a janela está, e não com a eluição. Ela lê
  **0,0123** contra os 0,75 necessários, em toda janela de acomodação
  tentada, e as duas figuras não podem dizer outra coisa: elas perguntam se
  o sinal se mantém, e este não se mantém. Os seus 164 espectros também são
  inferidos como 82 canais de um ou dois scans cada, de modo que nenhum
  canal isolado tem cromatograma suficiente para julgar.

Nos dois casos **Average whole run** dá exatamente a visão que o caminho
automático teria dado, em qualquer canal que se queira; nada fica fora de
alcance.

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

## Colocando uma no papel

**Process ▸ Report this infusion…** escreve o espectro promediado, os seus
picos, o precursor acurado e o que quer que tenha sido rodado contra ele como
um documento de duas a quatro páginas — ver [[infusion-report]]. Só é
oferecido numa infusão, porque tudo nele é a média de uma corrida inteira.
