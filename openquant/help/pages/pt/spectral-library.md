---
title: Biblioteca espectral
---
A aba **Library** do [[explorer]] busca o espectro na tela contra uma
biblioteca espectral — registros do MassBank, do MoNA, do GNPS ou do NIST, ou a
biblioteca própria de um laboratório — e lista os registros que correspondem.

Ela fica ao lado de [[lipid-maps]] em vez de substituí-la. A aba *Explain* de
lá pergunta o que uma estrutura *poderia* produzir; uma biblioteca pergunta o
que alguém *registrou* do composto em um instrumento. As duas respondem
perguntas diferentes e discordam de maneiras úteis: uma estrutura explica um
espectro para cujo composto nunca se fez uma medida, e uma biblioteca carrega o
padrão de intensidades que nenhuma enumeração de ligações prevê.

## Carregar uma biblioteca

**Load library…** aceita um arquivo MSP — o formato que o NIST define e que
MassBank, MoNA e GNPS todos exportam — ou um MGF. O arquivo é lido uma vez, a
contagem de registros e quantos trazem um precursor é mostrada, e o caminho
fica guardado para que a biblioteca esteja lá na próxima inicialização. Os
nomes dos campos variam conforme o exportador (`PrecursorMZ`, `PRECURSORMZ`,
`Precursor_type`, `Formula`) e são lidos sem distinção de maiúsculas e
minúsculas; campos que o programa não conhece são mantidos e mostrados ao
passar o cursor.

## Buscar

**Search the spectrum on screen** toma o espectro que o Explorer está
mostrando — centroidado, se era perfil — e o precursor do canal ativo, e
pontua cada registro cujo precursor esteja dentro de **Precursor ±** dele. A
tolerância é no mínimo a precisão com que o precursor do canal foi escrito: um
valor de método `647.5` é conhecido a ±0.05, e um filtro de ±0.02 em torno dele
estaria pedindo dígitos que ele não tem. Registros sem precursor ficam fora de
uma busca filtrada a menos que **Also records with no precursor** esteja
marcado — medido no MassBank, 24,000 de 139,000 registros não trazem nenhum, e
um filtro que os admitisse todos tinha cada busca dominada por eles; marcados,
eles são pontuados com o Δ ppm mostrado como `—`, para que o leitor saiba que o
filtro não pôde se aplicar a eles. Picos medidos abaixo de um por cento do
pico-base não entram na correspondência; a linha de base de um espectro de íons
produto está cheia deles.

Um registro tem de alcançar pelo menos **Matched peaks ≥** dos seus picos para
ser listado, dois por padrão. Um pico em comum é uma coincidência: no mesmo
lote, um espectro que era quase todo o íon fosfocolina em 184.07 pontuou 83
contra um laxante cujo fragmento fica a 13 ppm de distância, e um registro de um
único pico correspondido nele era uma pontuação perfeita por nada.

Cada pico da biblioteca, do mais forte para o mais fraco, é emparelhado ao pico
medido livre mais próximo dentro de **Peaks ±** ppm, de modo que um íon forte da
biblioteca nunca é roubado da sua correspondência por um fraco listado antes.

## As duas pontuações

| Pontuação | O que ela pergunta |
|---|---|
| **Score** | o cosseno entre os dois espectros, sobre tudo o que ambos contêm, com as intensidades sob raiz quadrada para que um único pico-base não decida tudo |
| **Reverse** | o mesmo cosseno, mas apenas sobre os picos da biblioteca: se eles estão no espectro medido, ignorados os demais picos do espectro medido |

Um reverse alto com um score baixo é um composto presente acompanhado — uma
impureza coeluente, ou uma varredura de survey (survey scan) com mais de um íon
na janela de isolamento. Um score alto com tudo correspondido é o próprio
registro. Ambos são mostrados como porcentagens; **Matched** é quantos dos picos
do registro encontraram um par.

## Os picos correspondidos, e a sobreposição

Selecionar um registro lista os picos dele contra os medidos — massa, massa,
ppm e a fração do pico-base de cada espectro — e **Overlay on spectrum**
desenha os picos do registro sobre o painel do espectro, escalados ao pico-base
dele, do mesmo modo que a [[mass-calculator]] sobrepõe um padrão isotópico.
**Clear overlay** remove a sobreposição.

## Medido no MassBank

A exportação completa do MassBank em formato NIST — 139,006 registros, 137 MB —
é lida em cinco segundos e ocupa cerca de 1.3 GB de memória, já que os picos de
cada registro ficam guardados como arrays prontos para corresponder. Uma busca
filtrada responde em milissegundos; uma sem filtro de precursor, que tem de
considerar todo registro que compartilhe dois picos com a consulta, em dois a
sete segundos.

Contra os espectros de íons produto de um lote real, a busca filtrada retornou
o composto onde a biblioteca o tinha — uma esfingomielina C16 com score 46 e
reverse 79, uma ceramida C16 com 32 e 94, uma ceramida C24:1 com 11 e 90, uma
esfingomielina C18 com 48 e 96 — e nada para os padrões internos C17, que não
estão no MassBank. As pontuações são baixas e as reversas altas porque uma
varredura de íons produto num TOF carrega o precursor, os isótopos dele e toda a
região de baixa massa, além dos fragmentos que o registro lista: em espectros
assim, o reverse é o que se deve ler, e o score simples diz quanta outra coisa
havia ali.

## Sua própria biblioteca

Um padrão interno deuterado infundido de propósito não está em biblioteca
pública nenhuma. O espectro na tela é o único registro dele que algum dia
existirá, de modo que **Add spectrum to library…** o escreve numa biblioteca
sua: um arquivo MSP que você escolhe uma vez, ao qual se acrescenta, e que é
legível por qualquer coisa que leia MSP — inclusive este programa, o MS-DIAL
e o MSPepSearch.

Na primeira vez, um arquivo é pedido; depois disso o painel diz quantos
registros ele contém. O diálogo pergunta apenas o que a aquisição não pode
fornecer e preenche de antemão tudo o que pode:

| Campo | De onde vem |
|---|---|
| **Name** | seu. É o que uma busca mostrará, e um registro sem ele não é sequer lido de volta |
| **Precursor m/z** | o canal ativo, ou o que estiver digitado em **Precursor** acima |
| **Adduct** | a polaridade que foi executada — `[M-H]-` para um método negativo, `[M+H]+` para um positivo — e qualquer outro aduto pode ser digitado |
| **Formula** | sua, se for conhecida; um registro não precisa de uma |
| **Collision energy** | a informação do canal, onde o instrumento registrou alguma |
| **Comment** | o próprio título do painel do espectro — amostra, canal e os scans sobre os quais a média foi tomada — com o arquivo e a data de hoje |

O espectro é escrito como **centroides**: bastões, um por íon, não os pontos
de perfil. Se o painel de [[chromatograms-and-spectra]] estiver mostrando um
espectro de perfil, ele é centroidado na saída, do mesmo modo que para uma
busca. Picos abaixo de um por cento do pico-base são descartados — a linha de
base de uma varredura de íons produto são milhares deles, e um registro que
os carregasse corresponderia a qualquer coisa — e no máximo duzentos do que
sobra são mantidos, do mais forte para o mais fraco. As intensidades são
guardadas em relação ao pico-base, como porcentagem, que é como todo formato
de biblioteca as contém.

O registro entra no arquivo como MSP no estilo NIST: `Name`, `PrecursorMZ`,
`Precursor_type`, `Formula`, `Collision_energy`, `Comment`, `Num Peaks`, e
então a lista de picos. Se a biblioteca carregada for o arquivo que acabou de
ser escrito, ela é lida de novo em seguida, de modo que o registro novo pode
ser buscado imediatamente — o que é também a verificação de que ele foi
escrito numa forma que o analisador lê de volta.

### Medido em três padrões infundidos

As aquisições para as quais isto foi escrito: ácido cólico-d4, ácido
desoxicólico-d4 e ácido taurodesoxicólico-d4, infundidos um de cada vez num
ZenoTOF 7600 em modo negativo, varreduras de íons produto, um canal cada e
sem coluna. O veredito de [[direct-infusion]] chama todos eles de infusões,
de modo que cada registro é a média de **todos os scans da corrida** — 473,
473 e 257 deles, ao longo de 1.98, 1.98 e 1.07 minutos — centroidada:

| | CA-d4 | DCA-d4 | TDCA-d4 |
|---|---|---|---|
| pontos de perfil na média | 255,113 | 242,308 | 192,688 |
| centroides | 811 | 1,059 | 455 |
| em ou acima de 1% do pico base | 204 | 226 | 25 |
| picos no registro | 200 | 200 | 25 |
| o que limitou | o teto de 200 | o teto de 200 | o piso de 1% |
| pico base | 359.2870 | 361.3017 | 468.3072 |

Buscar um espectro contra um registro do mesmo composto é uma das três
verificações que um [[infusion-report]] soma, e a sua pontuação, a pontuação
reversa e a procedência do registro são impressas ali ao lado da figura
cabeça contra cauda.

Três registros, 8,144 bytes, escritos em menos de um segundo. Lidos de volta,
todos os três voltaram com cada campo com que foram escritos, as massas
dentro de 5·10⁻⁶ Da e as intensidades relativas dentro de 5·10⁻⁷ — o
arredondamento do texto, e nada mais.

Depois, cada composto foi **readquirido com dissociação ativada por elétrons
a 22 eV** e essa média buscada contra os três registros, que foram escritos a
partir de dissociação induzida por colisão a 45, 40 e 30 eV. Essa é uma
pergunta mais difícil que o mesmo canal de uma injeção diferente: o registro
e a consulta não são apenas duas medições, são duas maneiras de quebrar a
molécula.

| | CA-d4 | DCA-d4 | TDCA-d4 |
|---|---|---|---|
| o próprio registro veio primeiro | sim | sim | sim |
| o score dele | 29.2 | 33.3 | 61.5 |
| o reverse dele | 38.8 | 43.8 | 68.7 |
| picos correspondidos | 22 de 200 | 19 de 200 | 8 de 25 |
| o melhor registro *errado* | 14.1 | 14.0 | 10.3 |
| Δ ppm ao precursor registrado | −23.2 | +0.0 | +0.0 |

**Um composto diferente não corresponde.** Buscados contra os outros dois
registros sem filtro de precursor, o melhor score errado em qualquer lugar é
14.1 com um reverse de 31.2 — da metade a um sexto do que o registro do
próprio composto dá — e o espectro do CA-d4 não retorna **correspondência
alguma** contra o registro do TDCA-d4, menos de dois picos em comum. Com o
filtro de precursor que o painel aplica por padrão havia exatamente um
registro na janela de ±0.02 Da a cada vez e era o certo; o filtro não muda
nenhum score nem a ordem aqui, apenas quais registros foram pontuados. Uma
busca leva de 0.1 a 1.6 ms.

O Δ de −23.2 ppm do CA-d4 é a regra sobre a precisão escrita fazendo o seu
trabalho: o registro diz `430.35`, que é bom até ±0.005 Da, e o canal que o
consultou diz `430.34`. Os dois são o mesmo íon escrito com duas casas.

**Um registro é uma energia, e uma maneira de quebrar a molécula.** O mesmo
espectro do CA-d4 readquirido a 12 eV em vez de 22, contra o mesmo registro
de CID, pontua **6.4 com um reverse de 21.3 sobre 8 picos correspondidos** —
contra 29.2, 38.8 e 22 a 22 eV. Separando as duas causas: um registro escrito
a partir da própria média de EAD a 22 eV do CA-d4 pontua 100.0 contra si
mesmo (que é a ida e volta, exata), **67.4** contra a média dele a 12 eV, e
29.1 com um reverse de 55.7 contra a média de CID a 45 eV. Ou seja, a mudança
de energia custa cerca de um terço do score e a mudança de ativação custa
quase todo o resto. A ordenação sobrevive a tudo isso — o registro certo veio
primeiro todas as vezes — mas o número ao lado dele não viaja entre métodos,
e um limiar escolhido num não é um limiar noutro.

### Medido num lote de esfingolipídios

Num lote real de aquisições de íons produto — 26 injeções de um método cujos
144 canais são um composto cada, na sua própria energia de colisão, que é o
mesmo formato de uma infusão de um padrão:

Catorze registros foram escritos a partir da primeira injeção, cada um a
média de todos os 61 scans de um canal, centroidada. De onze mil a vinte e um
mil pontos de perfil viraram de 84 a 3,650 centroides e de 7 a 82 picos no
registro; o arquivo são catorze registros em 13.9 kB, construído em menos de
dois segundos. Lidos de volta, todos os catorze voltaram com cada campo com
que foram escritos, as massas dentro de 5·10⁻⁶ Da e as intensidades relativas
dentro de 5·10⁻⁷ — o arredondamento do texto, e nada mais.

Depois, os **mesmos canais de uma injeção diferente** foram buscados contra
aquela biblioteca, sem filtro de precursor, de modo que a correspondência é
espectral apenas:

| | Injeção 02 | Injeção 13 |
|---|---|---|
| o registro certo veio primeiro | 14 de 14 | 14 de 14 |
| o score dele | 13–95, mediana 60 | 33–95, mediana 63 |
| o reverse dele | 45–96, mediana 87 | 61–99, mediana 83 |
| o melhor registro *errado* | 42 | 42 |

Um composto diferente não corresponde. O registro feito a partir do padrão em
354.3 foi buscado contra cada um dos outros treze canais da segunda injeção:
nove deles não retornaram **correspondência alguma** — menos de dois picos em
comum — e o melhor dos demais pontuou 19 com um reverse de 67, contra 95 e 96
para o seu próprio canal. Com o filtro de precursor que o painel aplica por
padrão, cada busca teve exatamente um registro na janela e o encontrou.

As pontuações se leem baixas pelo mesmo motivo que os números do MassBank
acima: uma varredura de íons produto num TOF carrega o precursor, os isótopos
dele e toda a região de baixa massa, além dos fragmentos, e nada disso está
num registro construído a partir de uma média mais limpa. O reverse é o que
se deve ler.

## O que a biblioteca não sabe

Um registro é o espectro de um instrumento em uma energia de colisão. Uma
correspondência é evidência de que o espectro medido se parece com aquele
registro; quanta semelhança basta é decisão do analista, e o
[[accurate-precursor]] e o [[formula-finder]] são as verificações independentes
sobre o precursor que uma correspondência de biblioteca não faz.

## Ler de volta a sua própria biblioteca

Uma biblioteca própria acumula um registro por verificação do mesmo padrão.
**History…**, ao lado da contagem de registros, lê esses registros de volta
como um gráfico de controle do padrão ao longo do tempo — veja
[[standard-history]].
