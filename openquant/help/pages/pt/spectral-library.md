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

### Medido

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
