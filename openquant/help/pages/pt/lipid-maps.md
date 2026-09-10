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
  certas por si sós. Hidrogênios escritos como átomos próprios são
  incorporados aos átomos que os carregam: o PubChem escreve todos os
  quarenta de um ácido biliar, e cortar quarenta ligações C–H só produz
  quarenta pedaços que diferem da molécula inteira por um hidrogênio — o que
  um deslocamento de hidrogênio já cobre. A fórmula não muda com isso, e o
  deutério que o desenho posiciona permanece no átomo em que foi desenhado.
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

**Limits** define até onde a enumeração vai e quão perto uma massa precisa
estar. Dois cortes, porque um esteroide cortado uma vez continua em uma só
peça; três perdas, porque um ácido biliar tri-hidroxilado perde três águas e
o íon de três águas é o seu pico base. A tolerância é de **± 5 ppm** em vez
dos 20 ppm com que um candidato do banco de dados é pontuado, e isso não é
questão de gosto — ver abaixo.

O resultado cai nas mesmas duas tabelas que um candidato do banco de dados —
a parcela do espectro explicada, os picos correspondidos com as suas rotas e
escadas — e os picos não explicados continuam sendo a metade honesta disso.

### Onde estão as marcações

Um pedaço que reteve duas de quatro marcações contém duas delas; um pedaço
que não reteve nenhuma não contém nenhuma. Todo íon correspondido é portanto
uma afirmação sobre *quais* hidrogênios são pesados, e não apenas sobre
quantos, e o bloco sob as tabelas reúne essas afirmações. Um posicionamento
é um conjunto de posições, uma por marcação; um posicionamento sobrevive a
um íon quando as marcações que ele coloca dentro daquele pedaço são o número
que o pedaço reteve. O que volta é quantos posicionamentos sobrevivem, em
quais posições todos os sobreviventes concordam, e quais posições nada
separa.

Posições que as observações não conseguem distinguir são agrupadas, porque
um empate entre dois hidrogênios que estão dentro exatamente dos mesmos
fragmentos não é um resultado. O ácido cólico oferece 21 posições ligadas a
carbono e **8.391** maneiras de colocar quatro marcações sobre elas.

Três regras decidem o que conta, e as três foram medidas, não supostas:

- **Um hidrogênio ligado a oxigênio ou nitrogênio não é oferecido.** Ele
  troca com o solvente muito antes de o espectro ser registrado. A caixa de
  seleção devolve essas posições para quem quiser ver o que o espectro diria
  se não trocasse.
- **Uma perda neutra pode levar uma marcação consigo.** Uma desidratação sai
  com o hidrogênio da própria hidroxila e mais um do carbono ao lado, de
  modo que um íon que perdeu água limita a contagem em vez de fixá-la; uma
  descarboxilação não leva hidrogênio ligado a carbono e por isso diz
  exatamente. Isso é medido: no espectro CID abaixo, o pico base em
  m/z 359,2870 é a perda de três águas retendo todas as quatro marcações, e
  358,2808 ao lado dele, a 12,5%, é o mesmo íon retendo três. Os dois estão a
  1,0062 de distância, que é o 1,00628 de um deutério contra um hidrogênio e
  não o 1,00783 de um hidrogênio contra nada.
- **Um hidrogênio que o pedaço perdeu na clivagem também pode ter sido uma
  marcação.** Supor o contrário é mais arrumado e é errado: com essa
  suposição, um íon escrito `-2H` não pode ter perdido uma marcação, e no
  espectro abaixo o posicionamento verdadeiro passava a satisfazer 43% das
  evidências em vez de 78% e era superado por 96% das possibilidades em vez
  de 79% — e o bloco apontava uma metila sem marcação alguma como posição em
  que todos os sobreviventes concordavam.

**Um pico só conta quando diz um número.** Um deutério é 1,55 mDa mais
pesado do que o hidrogênio que substituiu, de modo que o mesmo pedaço com
uma marcação a mais e um hidrogênio a menos fica a 1,55 mDa dali — em
m/z 359 isso são 4,3 ppm. Uma janela mais larga do que essa diferença contém
os dois, e a correspondência passa a ser decidida por qual está mais perto,
o que é cara ou coroa; esses íons são contados e deixados de fora. No
espectro do ácido cólico-d4, dos íons correspondidos deixados de fora por
esse motivo: 48 de 53 a 20 ppm, 24 de 47 a 10 ppm, 4 de 26 a 5 ppm, nenhum
de 19 a 3 ppm. É por isso que a tolerância aqui é de 5 ppm por padrão.

### O que ele fez com um padrão real

Ácido cólico-d4 infundido em um ZenoTOF 7600 — o canal de íons-produto do
aduto de amônio em m/z 430,35, CE 45, com toda a corrida de 1,98 min
promediada (473 scans, plana do início ao fim, uma infusão pelo teste em
[[direct-infusion]]) e centroidada: 811 centroides, 60 picos acima de 1% do
pico base. A estrutura é o ácido cólico do PubChem (CID 221493) com quatro
marcações não posicionadas; a resposta é conhecida, porque o PubChem também
tem o padrão marcado (CID 16217616), cujo bloco `M  ISO` coloca as quatro em
C2 e C4 — de cada lado da hidroxila em C3, no anel A.

| | CID, CE 45 | EAD, 22 eV |
|---|---|---|
| picos explicados | 59,0% | 60,7% |
| íons correspondidos | 26 | 24 |
| destes, dizendo uma contagem | 22 | 15 |
| deixados de fora como indecisos | 4 | 9 |
| posicionamentos empatados no topo | 580 | 2.625 |
| de 8.391, com | 93% das evidências | 100% |
| posições em que todos concordam | nenhuma | nenhuma |
| o posicionamento do fabricante | 78% das evidências | 92% |
| posicionamentos que o superam | 6.589 (79%) | 6.224 (74%) |

A coluna EAD é uma segunda infusão do mesmo padrão, a 22 eV, lida do mesmo
modo: 146 scans em 0,61 min, 424 centroides, 42 picos.

**Ele não recupera a resposta.** Sob CID os melhores posicionamentos colocam
duas marcações em uma metila e uma em um carbono ao lado de outra hidroxila;
sob EAD elas se espalham por quatro posições no meio do sistema de anéis.
Nenhum dos dois é o anel A, e o 2,2,4,4 do fabricante é superado por três
quartos das possibilidades nas duas ativações. Leia o empate — 580 e 2.625 posicionamentos — como o
espectro limitando as marcações em vez de posicioná-las, que é o que o bloco
diz quando reporta que nenhuma posição está em todos eles. A razão é que uma
massa correspondida não é uma atribuição resolvida: um pedaço alcançado por
dois cortes e três perdas é uma entre milhares de possibilidades
aritméticas, e o posicionamento que melhor se ajusta é aquele que
racionaliza as que o correspondedor escolheu.

Recebendo em vez disso o desenho marcado, sem nada a inferir, os mesmos
espectros concordam com ele: todo íon que o posicionamento prevê está onde
deveria estar, 100% das evidências nos dois arquivos. O que isso custa é
alcance — o desenho marcado explica 35,5% do espectro CID contra os 59,0% da
versão não posicionada, porque a versão não posicionada recebe cinco vezes
mais massas para corresponder. E a discordância é reportada em vez de
escondida: três picos no espectro CID e dois no de EAD correspondem a um
pedaço que o posicionamento prevê *carregando um número diferente de
marcações*, um deles o 358,2836 já citado acima.

O que o espectro diz com clareza é que uma desidratação leva uma marcação.
Sob EAD a escada está completa, e a parcela de cada degrau que perdeu uma
cresce à medida que as hidroxilas saem: 5,2% no precursor, 5,0% após uma
água, 8,0% após duas e 104% após três — o íon que perdeu uma marcação é
então maior do que o que reteve todas. Qual hidroxila saiu em qual degrau
posicionaria as marcações; a enumeração ainda não acompanha isso.

## Contra uma biblioteca

A aba **Library** ao lado desta faz a outra pergunta — o que alguém
registrou a partir do composto, em vez do que a sua estrutura poderia
produzir — e vale a pena ler as duas juntas: [[spectral-library]].

## Anotar um método inteiro

**Annotate from LIPID MAPS…** na área de trabalho Method propõe uma espécie
para todo componente ainda nomeado a partir do seu precursor, usando a massa
medida na varredura de survey onde puder. Ver [[annotate-from-lipid-maps]] e
[[accurate-precursor]].
