---
title: O relatório de infusão
---
**Process ▸ Report this infusion…** escreve um composto em duas a quatro
páginas: o documento que vai para o caderno quando um padrão é validado. Um
[[report]] responde o que um lote mediu; este responde algo menor e mais
antigo — *este frasco é o que o rótulo diz?* — e responde listando o que foi
verificado, não aprovando nem reprovando coisa alguma.

A ação só é oferecida enquanto a amostra ativa for uma [[direct-infusion]],
porque tudo o que está na página é a média de uma corrida inteira, o que é
uma mentira sobre uma amostra cromatográfica. **Process ▸ Report every
infusion…** faz o mesmo para todas as infusões abertas, uma seção por
composto num único documento, cada composto começando numa página nova.

## O que cada bloco carrega

**O cabeçalho** vem do arquivo e não do nome dele: a aquisição, a amostra, o
instrumento, a polaridade, o canal de íons produto com o precursor como o
método o escreveu, a energia de colisão, quantos scans foram promediados e
sobre que faixa de tempo — e o precursor acurado, com o seu erro em ppm e
onde ele foi medido. Quando a aquisição tem uma varredura de survey, a medida
é a do [[accurate-precursor]], com o espectro de íons produto como
verificação de que é o mesmo íon. Quando não tem nenhuma — o que é o caso de
todas as nove infusões reais contra as quais isto foi construído; cada uma
tem um único canal de íons produto e mais nada — o precursor é lido do
próprio espectro de íons produto promediado, e o relatório diz isso com todas
as letras.

**O espectro promediado**, desenhado para o papel no piso de rótulos em que o
painel foi deixado, de modo que as massas impressas são as massas que
estavam na tela — veja [[chromatograms-and-spectra]] para o piso e para como
os rótulos são posicionados. Abaixo dele, os vinte e cinco picos mais
intensos acima desse piso, com as suas intensidades e a sua fração do pico
base.

**A explicação estrutural**, quando alguma foi rodada na aba [[lipid-maps]] —
um registro curado, um desenho próprio, ou uma fórmula e as suas perdas. Cada
íon casado com a sua massa teórica, a massa medida, o erro em ppm e, para uma
marcação não posicionada, quantos deutérios o fragmento reteve. Depois, numa
tabela própria, **os picos que ela não explica**: a metade honesta da
resposta, e onde uma impureza co-infundida ou o composto errado aparece.

**A pureza isotópica**, quando o composto carrega marcações e um aduto foi
identificado — o número do certificado que ninguém mede. O bloco é o próprio
envelope: cada degrau de d0 a dn com a sua *m/z*, a sua intensidade, a sua
fração do íon totalmente marcado e a fração ajustada, depois o par de
espécies (`d4 96,2%, ≥d3 99,1%`) e o átomo por cento, que é a grandeza que o
certificado declara e é outro número. Quando o envelope não pode ser
resolvido, os degraus são impressos do mesmo jeito com a razão embaixo,
porque uma recusa é uma afirmação sobre aqueles números e quem não os vê não
pode conferi-la. Esse é o desfecho em todas as nove infusões reais, por uma
razão que o [[lipid-maps]] expõe: o precursor de um espectro de íons produto
passou pelo quadrupolo, e os satélites de carbono-13 de que a solução precisa
foram junto.

**O resultado da biblioteca**, quando uma busca foi feita na aba
[[spectral-library]]: o melhor registro, a sua pontuação e a pontuação
reversa, quantos dos seus picos casaram, a diferença de precursor em ppm, os
dois espectros cabeça contra cauda, e os campos do próprio registro como
foram escritos — o arquivo de onde ele veio, a energia de colisão e a data.
Um registro cuja procedência não está na página não pode ser conferido contra
a aquisição de onde saiu.

**Outras infusões do mesmo composto**, quando houver alguma aberta: cada uma
promediada sobre a sua própria corrida inteira e desenhada cabeça contra
cauda contra esta, com o mesmo cosseno que uma busca em biblioteca usa. O
diálogo marca aquelas cujo nome de arquivo começa com o mesmo composto e
deixa marcar ou desmarcar qualquer uma, porque uma convenção de nomes não é
uma medida.

## O que o veredito afirma e o que não afirma

*What was measured* é uma frase por verificação, e uma verificação que não
foi feita não ganha frase nenhuma:

- **"Precursor confirmed at +20.7 ppm…"**, ou **"Precursor not confirmed:
  …"** com o motivo. Uma janela que contém menos de cem contagens não é uma
  massa: é reportada como pouco demais para medir, com a altura que foi
  encontrada, em vez de virar um centroide tirado sobre ruído.
- **"8 of the 56 ions predicted for … were found"** — o denominador é quantos
  íons a previsão ofereceu, para que o leitor veja do que a contagem é uma
  fração, e o pico não explicado mais intenso é nomeado ao lado.
- **"Best library record … at score 29, reverse 39"**, com a diferença entre
  os precursores em ppm.
- **"Collision energy differs from the record's (22 against 45 eV)"** — um
  espectro tirado em outra energia tem outros fragmentos, de modo que uma
  pontuação baixa ali é a energia e não necessariamente o composto.

Não há aprovação, não há reprovação e não há selo. Se o frasco contém o que
deveria conter é um juízo feito a partir de evidências por alguém que sabe o
que foi pesado nele, e um visto verde não convida ninguém a ler o resto da
página. Quando nada foi rodado, o veredito diz exatamente isso, e o documento
é um espectro e uma tabela de picos — o que é uma descrição justa dele.

Cada relatório escrito fica registrado no [[audit-trail]]: o que foi
relatado, em qual arquivo, e quais das três verificações estavam por trás.

## Todas as infusões de uma vez: a aba Infusions

Um relatório de um frasco responde uma pergunta. Uma pasta com nove faz outra
— quais delas mediram o seu precursor, quais acharam os seus fragmentos, quais
bateram com o registro feito do mesmo composto no mês passado — e essa é uma
tabela. A aba **Infusions** do [[analytics-workspace]] é ela: uma linha por
amostra infundida, agrupadas pelo composto com que o nome do arquivo começa.

Nada é medido antes de **Measure** ser pressionado: promediar uma corrida
inteira, centroidar um quarto de milhão de pontos, buscar numa biblioteca e
pontuar cada infusão de um composto contra as outras leva alguns segundos por
composto, e uma aba que fizesse isso a cada mudança nos resultados seria uma
aba que ninguém deixa aberta. A contagem de linhas aparece no próprio nome da
aba depois que ela mede.

Cada linha traz o composto e a amostra, o modo e a energia de colisão, quantos
scans foram promediados, o pico base, o precursor como o método o escreveu e
como foi medido de volta com o seu erro em ppm e a sua altura, os íons
encontrados dentre os previstos, o melhor registro da sua própria biblioteca
com as duas pontuações e a energia de colisão do registro contra a desta
aquisição, e as outras infusões do mesmo composto com o cosseno nos dois
sentidos.

Dois desses vêm de onde o relatório de um frasco os recebe de uma pessoa:

- **a explicação.** Quando a aba [[lipid-maps]] já explicou o espectro na
  tela, é essa explicação que é usada. Caso contrário o composto é procurado
  na tabela de componentes pelo nome e explicado a partir da sua fórmula — o
  caminho da fórmula do [[annotate-from-lipid-maps]], executado sem ninguém
  na aba. Duas coisas são lidas em vez de tomadas como escritas, pelo mesmo
  motivo: uma tabela de componentes não tem coluna para nenhuma das duas. As
  **marcações**: um componente chamado `CA-d4` cuja fórmula é a não marcada
  `C24H40O5` é explicado como `C24H36D4O5`, porque o nome diz quatro e a
  aritmética estaria fora por 4,025 Da. E o **aduto**: o do próprio
  componente é usado quando concorda com o precursor escrito do canal, e
  quando não concorda, o precursor vence e a linha de base diz isso — ver
  *Adutos* em [[lipid-maps]]. Um composto que o método não tem não é
  adivinhado, e um precursor que nenhum aduto da fórmula alcança não é
  explicado de modo algum: a célula diz qual dos dois.
- **a biblioteca.** A biblioteca própria — o MSP a que *Add spectrum to
  library…* acrescenta, veja [[spectral-library]] — buscada na precisão do
  próprio precursor escrito. Um registro feito de uma destas mesmas infusões
  vai bater consigo mesmo em 100, o que diz que o arquivo foi escrito e lido
  de volta e mais nada; a linha que vale ler é a do mesmo composto sob outra
  ativação.

**Uma célula que não pôde ser preenchida diz por quê em vez de ficar em
branco.** *only 84 counts survive* não é a mesma resposta que *nothing within
±0.25 Da*, e nenhuma das duas é *CA-d4 is not a component of the method* —
uma tabela de travessões não distingue as três, e qual delas é decide o que
fazer em seguida. A frase inteira por trás de uma abreviada está na dica da
célula.

Os cabeçalhos ordenam pelos números onde os têm, então o precursor mais fraco
ou a pior pontuação está a um clique.

**Report…** escreve o documento por composto — o mesmo que *Process ▸ Report
this infusion…* escreve — para as linhas selecionadas, ou para todas quando
nenhuma está selecionada, uma seção por composto. Linhas do mesmo composto
escolhidas juntas são desenhadas cabeça-cauda umas contra as outras nele; uma
linha deixada de fora fica de fora também da comparação. **Export CSV…**
escreve a tabela inteira, todas as colunas, com ou sem seleção: um resumo com
linhas faltando não é a coisa que ele diz ser.

A linha de resumo sob a tabela é a única frase que a tabela soma — *3
compound(s) in 9 infusion(s); 4 of 9 precursor(s) confirmed within 25 ppm; 34
of 458 predicted ion(s) found across 7; 4 with an own record above 60 in
own-bileomics.msp* — apenas contagens, cada uma com aquilo contra o que foi
contada. O relatório do lote imprime a tabela e essa linha como a sua seção
*Infusions*, enquanto a medida valer: veja [[report]].

## Medido

Ácido cólico-d4 infundido num ZenoTOF 7600, o mesmo frasco sob duas
ativações, explicado a partir do `C24H40O5` da tabela de componentes — lido
como `C24H36D4O5` a partir das quatro marcações que o nome declara, e como
`[M+NH4]+` porque é isso que o 430,35 do canal é — e buscado contra um
registro feito da corrida CID:

| | CID, 45 eV, 473 scans | EAD, 22 eV, 146 scans |
|---|---|---|
| pico base | 359,2870 | 377,3015 |
| precursor 430,35 no espectro de íons produto | 84 contagens, 1,49% — pouco demais | 430,3489 a 9.415 contagens, **+20,7 ppm** |
| íons encontrados, de 56 previstos | 2 — 24,2% da intensidade | 8 — 63,6% |
| contra o registro CID | 100 / 100, o seu próprio registro | **29 / 39**, 22 de 200 picos |
| energia de colisão contra a do registro | igual | **22 contra 45 eV** |
| contra o mesmo composto a 12 eV | 7 / 29 | 67 / 81 |

Medido sobre a corrida EAD, acrescentando um bloco de cada vez: só o
espectro e os seus picos, **duas páginas**; com o precursor, duas; com a
explicação estrutural e os seus picos não explicados, duas; com o registro da
biblioteca e a sua figura cabeça contra cauda, **três**; com mais uma infusão
comparada, **quatro**. Cada um levou entre 0,3 e 1,0 s para diagramar e
imprimir. Dois compostos num só documento deram oito páginas em dois
segundos.

As duas linhas que vale reler são as duas últimas da coluna CID. A pontuação
de 100 na biblioteca é um registro casado contra o espectro do qual ele foi
feito, o que prova que o arquivo foi escrito e lido de volta e mais nada; e
2 de 56 íons é o que uma fórmula com três perdas neutras consegue dizer sobre
um espectro CID cuja escada já correu até o fim — os dois que ela acha são a
perda de três águas e o mesmo íon com uma marcação a menos. Nenhuma das duas
é uma falha do composto, e o relatório é construído de modo que a página diga
qual é qual.

### A aba, nos mesmos nove arquivos

Os nove abertos de uma vez — três compostos, cinco deles chamados `CA-d4` —
com as três corridas CID escritas numa biblioteca própria e as três fórmulas
na tabela de componentes. **Measure** levou **14,1 s**, 1,6 s por infusão; o
documento das nove deu 61 páginas em 18 s, a maior parte disso as vinte
figuras cabeça-cauda que cinco infusões de um composto produzem.

| | precursor encontrado | íons dentre os previstos | registro próprio |
|---|---|---|---|
| CA-d4 CID 45 eV | 84 contagens — pouco demais | 2 de 56 | 100, o dele mesmo |
| CA-d4 EAD 22 eV | 430,3489, **+20,7 ppm** | 8 de 56 | **29** a 45 eV |
| CA-d4 EAD 12 eV | 430,3488, +20,4 ppm | 3 de 56 | **6** a 45 eV |
| DCA-d4 CID 40 eV | 33 contagens — pouco demais | 3 de 41 | 99, o dele mesmo |
| DCA-d4 EAD 22 eV | 414,3525, +30,3 ppm | 8 de 41 | **33** a 40 eV |
| TDCA-d4 CID 30 eV | 504,3273, +14,6 ppm, 124 contagens | 5 de 104 | 100, o dele |
| TDCA-d4 EAD 22 eV | 504,3325, +24,9 ppm | 5 de 104 | **61** a 30 eV |

*3 compound(s) in 9 infusion(s); 4 of 9 precursor(s) confirmed within 25 ppm;
34 of 458 predicted ion(s) found across 7; 4 with an own record above 60.*

Quatro coisas nessa tabela merecem ser lidas em vez de puladas:

- **as duas linhas que não estão nela.**
  `CA-d4_TOFMSMS_EAD_12CE_…_TESTEARTIGO` e a sua gêmea de 22 eV carregam o
  nome CA-d4 e não são aquisições de CA-d4: o método delas mira **839,56**
  sobre 100–1000, o pico base é 839,23, nove e dezessete contagens ficam na
  janela do precursor, nenhum registro da biblioteca chega a ±0,02 Da de
  839,56. A célula de explicação delas agora diz a coisa abertamente —
  *839.56 is none of the adducts of C24H36D4O5 within ±0.05 Da — closest
  [M+K]+ at 451.2758* — em vez de reportar zero íons de trinta e um, o que
  era verdade e deixava o leitor descobrir por quê. O *across 7* na linha
  acima são essas duas linhas: uma infusão para a qual nada foi explicado não
  é contada como uma que não achou nada. Elas pontuam **73** uma
  contra a outra e **5 a 10** contra os três arquivos de CA-d4 de verdade. O
  prefixo do nome dizia um composto e o método dizia outro, e a linha é onde
  isso aparece — que é toda a razão de o composto nunca ser mais do que uma
  proposta.
- **o precursor sobrevive às ativações suaves e não às duras.** Todas as
  corridas EAD mediram o seu precursor; duas das três CID tinham pouco demais
  sobrando para chamar de massa. Isso é um achado comum sobre energia de
  colisão, e a célula diz *only 84 counts survive* em vez de reportar um
  centroide sobre ruído.
- **os erros têm todos o mesmo sinal**, de +14,6 a +30,3 ppm. Um deles, o
  DCA-d4 a +30,3, passa dos 25 ppm que a linha conta e está na página do
  mesmo jeito: a contagem é uma frase, não um veredito.
- **uma fórmula acha de dois a oito íons, e quais depende da ativação.** Uma
  fórmula oferece o precursor, a forma que os seus fragmentos carregam e as
  perdas neutras dela, e mais nada; o resto destes espectros são clivagens de
  anel. É para isso que serve o denominador. Nas sete aquisições reais:
  **34 de 458** íons previstos encontrados, 2 de 56 no CA-d4 sob CID contra 8
  de 56 sob EAD a 22 eV, 3 de 41 e 8 de 41 no DCA-d4, 5 de 104 dos dois lados
  no TDCA-d4 — as ativações suaves guardam a escada e as duras já a
  terminaram. A linha com que comparar é a da aba [[lipid-maps]], onde o
  mesmo composto como *desenho* é pontuado contra milhares de massas em vez
  de dezenas.

A coluna da biblioteca é a que diz algo que o resto não diz. Um registro feito
de uma corrida bate com essa corrida em 100, o que prova que o arquivo foi
escrito e lido de volta; os números que significam alguma coisa são 6, 29, 33
e 61 — o mesmo composto, o mesmo frasco, sob outra ativação, e um registro não
viaja entre elas.

### Pureza isotópica, nos mesmos nove arquivos

Todos eles voltaram como *não medida*, e o bloco diz isso com os seus próprios
números na página. O satélite de carbono-13 do íon totalmente marcado, que a
fórmula coloca em 26,5 – 30,0% dele, mede 0,006 – 0,206%:

| infusão | degrau d4 | M+1 medido | razão para a fórmula | leitura |
|---|---|---|---|---|
| CA-d4 EAD 12 eV | 83.712 | 0,006% | 0,0002 | não medida |
| CA-d4 EAD 22 eV | 66.655 | 0,028% | 0,0010 | não medida |
| CA-d4 CID 45 eV | 607 | 0,095% | 0,0036 | não medida |
| DCA-d4 EAD 22 eV | 38.178 | 0,015% | 0,0006 | não medida |
| DCA-d4 CID 40 eV | 296 | 0,150% | 0,0057 | não medida |
| TDCA-d4 EAD 22 eV | 36.447 | 0,020% | 0,0007 | não medida |
| TDCA-d4 CID 30 eV | 2.272 | 0,206% | 0,0069 | não medida |

As duas linhas `TESTEARTIGO` não têm bloco nenhum: nada identificou um íon
para elas, pela razão que a lista acima dá, e não há envelope para imprimir.

O número que o envelope *teria* dado, com a verificação desligada, é
98,3 – 99,0% de d4 nos sete precursores — o que ficaria confortavelmente acima
de um `≥98 átomo % D` de certificado e não significaria nada, porque se move
com a energia de colisão: 98,32%, 98,77% e 98,98% em três aquisições do mesmo
frasco de ácido cólico-d4 a 12, 22 e 45 eV. A escada, tentada do mesmo modo,
dá 36,7%, 90,1% e 85,0% para essas mesmas três. **O que os dados dizem é que
estes arquivos não conseguem responder à pergunta**, e um relato honesto da
pureza de um padrão d4 neste instrumento precisa de um minuto de TOF MS ao
lado do canal de íons produto. O [[lipid-maps]] tem a aritmética e o resto das
evidências.

## O mesmo padrão, no mês que vem

Este relatório é uma verificação. O registro que ele nomeia é escrito na sua
própria biblioteca, e o [[standard-history]] lê os registros acumulados de
um composto como um gráfico de controle: o cosseno contra o primeiro
registro, o pico base em ppm a partir dele, e a altura do pico base, ao
longo dos dias em que foram adquiridos.
