---
title: LIPID MAPS
---
A aba **LIPID MAPS** do [[explorer]] trabalha contra uma cópia local do LIPID
MAPS Structure Database (LMSD), de modo que uma massa possa ser transformada
em lipídios candidatos, um nome de lipídio nos seus íons, e uma estrutura
nos fragmentos que ela poderia produzir — nada disso precisando de rede uma
vez construído o índice.

## O banco de dados

O primeiro uso oferece **Download the database**. Um arquivo de 21 MB de
lipidmaps.org vira um índice de 1.3 MB com 49,969 estruturas curadas,
guardado sob `~/.openquant/lipidmaps/`. As consultas levam menos de um
milissegundo. O LMSD é redistribuído pelo LIPID MAPS sob CC BY 4.0 e é
baixado sob demanda, não distribuído junto.

As buscas são restritas a estruturas construídas a partir de C, H, N, O, P, S
e Se. O LMSD contém lipídios organoarsênicos e fluorados; são registros
válidos e candidatos absurdos para um painel de plasma, e uma massa de
precursor arredondada casa com um deles com toda a boa vontade.

## Massa → lipídio

Digite um m/z, escolha o aduto, defina uma tolerância em ppm ou Da e
**Search LIPID MAPS**. Os resultados são agrupados **por espécie, depois por
estrutura**: uma espécie — `PC 34:1`, digamos — com os isômeros que
compartilham a sua fórmula listados abaixo, porque uma massa não consegue
separá-los e uma lista que fingisse o contrário estaria afirmando mais do
que foi medido. Cada linha carrega a fórmula, o erro em mDa e em ppm e o
LM_ID; a dica de contexto dá o nome sistemático.

Clicar com o botão direito em um pico do espectro e escolher **Find formula
for this peak** manda a sua massa para cá tanto quanto para o
[[formula-finder]].

## Lipídio → massa

Digite um nome (`SM(d18:1/16:0)`, `Cer(d18:1/16:0)`) ou um LM_ID
(`LMSP03010003`) e **Find the precursor**: os registros correspondentes são
listados com fórmula e massa neutra, e selecionar um lista os seus íons —
cada aduto, o seu m/z e a sua carga. Duplo clique em um íon para usar o seu
m/z como precursor em outra parte do painel.

## Fragmentos

Dado um lipídio e uma polaridade, **Predict fragments** enumera o que a
clivagem das suas ligações deixaria. A estrutura vem do molfile do banco de
dados — uma simples tabela de conexões com coordenadas 2D, que é tudo o que
é preciso para enumerar clivagens e para desenhar uma, de modo que nenhum
toolkit de química está envolvido. Os hidrogênios, implícitos no arquivo,
são contados a partir da valência que resta em cada átomo e conferidos
contra a fórmula publicada: uma estrutura cujos hidrogênios não fecham a
conta é marcada como não confiável em vez de deixada produzir massas de
fragmento que parecem exatas e estão erradas.

Até duas ligações são cortadas de uma vez — o que um anel precisa para se
desfazer; três é uma explosão combinatória que ninguém procuraria — e cada
pedaço pode perder os pequenos neutros que a opção **losses** lista (água,
amônia e assim por diante). A tabela dá o m/z de cada fragmento, o pedaço, a
rota que o produziu, quantos cortes foram precisos e quantas outras rotas
chegam à mesma massa (**Rivals**). Um m/z **target** filtra para as rotas
que caem sobre ele.

O que isto *não* faz é dizer que clivagens de fato acontecem. Enumerar
ligações é aritmética; prever um espectro não é. A lista é o conjunto de
massas que vale a pena procurar.

## Explain

**Explain this spectrum** toma o espectro em tela e o precursor (preenchido
a partir do canal ativo, ou digitado), procura o precursor no LIPID MAPS,
prevê os fragmentos de cada estrutura candidata e pontua cada uma por **a
parcela da intensidade do espectro que ela explica**. Contar picos
correspondidos em vez disso premiaria um candidato que explica quarenta
pontinhos de ruído em detrimento de um que explica o pico-base, o que é o
contrário do certo: um espectro de produtos é, na maior parte, um punhado de
íons que importam.

Picos abaixo de 1% do pico-base não contam contra um candidato — a linha de
base de um espectro de produtos está cheia deles e nada os explica — e uma
massa prevista corresponde a uma medida dentro de 20 ppm. Os candidatos são
listados com o que cada um explica; selecionar um lista os picos
correspondidos com a sua massa medida, o erro, a rota e, onde várias perdas
formam uma escada, a escada. Os picos não explicados também são reportados:
vários candidatos costumam explicar os mesmos picos, porque isômeros
fragmentam de modo parecido, e os não explicados são a parte honesta da
resposta.

**Explain spectrum** na barra de ferramentas Processing faz o mesmo a partir
do cromatograma: toma o espectro do scan atual e o precursor do seu canal.

### Uma estrutura ou fórmula de sua autoria

O banco de dados não contém tudo — não um ácido biliar deuterado comprado
como padrão interno, não um composto desenhado na semana passada. O grupo
sob o botão Explain aceita uma de duas coisas:

- **Uma estrutura**, de um arquivo `.mol` ou `.sdf` (o download do PubChem, o
  arquivo salvo de um programa de desenho; MDL V2000). Ela recebe o
  tratamento completo: as clivagens e as perdas do desenho, pontuadas contra
  o espectro exatamente como um registro do banco de dados é. Um desenho que
  posiciona as suas marcações — um bloco `M  ISO`, ou átomos D explícitos,
  que é como a estrutura de um padrão d4 fornecida por um fabricante é
  escrita — não precisa de mais nada; os seus fragmentos saem nas massas
  certas por si sós.
- **Uma fórmula**, quando não há desenho. Uma fórmula não tem ligações a
  cortar, de modo que o que se pode dizer é o íon precursor e a escada de
  pequenas perdas neutras que ele poderia sofrer — água, amônia, monóxido e
  dióxido de carbono, ácido fórmico, até três de uma vez, cada uma apenas
  onde a fórmula tem os átomos para ela. Menos do que uma estrutura dá, e
  dito que é.

**Deuterium, unplaced** (deutério, não posicionado) serve para um desenho ou
fórmula do composto *não marcado* e um padrão cujas marcações estão em algum
lugar desconhecido. Cada fragmento é então oferecido carregando de nenhuma a
todas as marcações, e o espectro diz quantas ele reteve: uma correspondência
em +2.0126 é um pedaço que reteve duas, escrito `+2D` na sua rota. Enumerar
cada posicionamento seria honesto e inútil; enumerar a contagem é o que o
espectro pode confirmar. Um pedaço nunca recebe mais marcações do que
hidrogênios que tem.

O resultado cai nas mesmas duas tabelas que um candidato do banco de dados —
a parcela do espectro explicada, os picos correspondidos com as suas rotas e
escadas — e os picos não explicados continuam sendo a metade honesta disso.

## Contra uma biblioteca

A aba **Library** ao lado desta faz a outra pergunta — o que alguém
registrou a partir do composto, em vez do que a sua estrutura poderia
produzir — e vale a pena ler as duas juntas: [[spectral-library]].

## Anotar um método inteiro

**Annotate from LIPID MAPS…** na área de trabalho Method propõe uma espécie
para todo componente ainda nomeado a partir do seu precursor, usando a massa
medida na varredura de survey onde puder. Ver [[annotate-from-lipid-maps]] e
[[accurate-precursor]].
