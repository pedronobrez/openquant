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

## O que a biblioteca não sabe

Um registro é o espectro de um instrumento em uma energia de colisão. Uma
correspondência é evidência de que o espectro medido se parece com aquele
registro; quanta semelhança basta é decisão do analista, e o
[[accurate-precursor]] e o [[formula-finder]] são as verificações independentes
sobre o precursor que uma correspondência de biblioteca não faz.
