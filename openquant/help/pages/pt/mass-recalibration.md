---
title: Recalibração de massa
---
A [[mass-drift|Mass drift]] pergunta se o eixo de massa do instrumento *se
moveu* durante a corrida, e responde contra a mediana do próprio lote porque
essa é a única referência que uma corrida pode fornecer a si mesma. A
recalibração pergunta a outra metade da questão — **o eixo está no lugar
certo, afinal** — e o corrige se não estiver.

O interruptor é *Recalibrate m/z from the internal standards*, na aba **Mass
drift** da área de trabalho Analytics. Ele vem desligado e é salvo com o
projeto.

## O que conta como lock mass

Uma lock mass aqui é um padrão interno que satisfaz quatro condições:

1. ele carrega uma **fórmula e um aduto** no [[method-workspace|method]], de
   modo que a sua massa verdadeira é conhecida. O *Fill formulas from names*
   preenche as células Formula vazias a partir da notação abreviada de
   lipídios dos próprios nomes — `SM(d18:1/12:0)`, `C16:0-Ceramide`,
   `PC 34:1` — e guarda cada uma somente onde ela concorda com o precursor já
   escrito;
2. o seu precursor fica dentro da faixa de massas da varredura de survey, de
   modo que pode ser medido — o [[check-method|Check method]] lista os que
   não ficam;
3. o íon medido se manteve o mesmo ao longo da corrida, que é o mesmo teste
   `same_ion` que a medida de [[mass-drift|drift]] aplica: injeções que
   discordam por mais de 25 ppm não estavam medindo um único íon, e
   promediá-las recalibraria o instrumento sobre o que por acaso estivesse
   mais perto;
4. ele mediu esse íon **perto de onde a fórmula o coloca** — dentro de
   **50 ppm**, na maioria das suas injeções. A condição 3 pergunta às injeções
   se elas concordam *entre si*; ela não consegue perguntar se elas concordam
   com o composto, e um padrão cuja janela de ±0.25 Da contém o mesmo íon
   *errado* em toda injeção concorda consigo mesmo perfeitamente. Um padrão
   além do limite é nomeado na tabela — *measures 237 ppm from its formula:
   not the ion the formula names* — e não é usado, por mais firme que tenha
   sido a medida. Onde um padrão está dentro do limite na maioria das injeções
   e além dele em uma, apenas aquela injeção o perde, e a linha daquela
   injeção diz isso.

**De onde vêm os 50 ppm.** Medido sobre as 1,439 medidas de survey que o lote
real fornece — todos os 60 componentes com fórmula dentro do survey, em cada
injeção — a distância até a fórmula é bimodal: 19.5% delas abaixo de 20 ppm,
53.5% além de 200 ppm, e o fundo do vale entre os dois lóbulos em 30–50 ppm,
onde um intervalo de 10 ppm contém 1.0–1.4%. Cinquenta é a borda distante
desse vale, e é o dobro dos 25 ppm que a condição 3 já tolera: um íon ao qual
se permite vagar o equivalente a uma dispersão pode ficar o equivalente a uma
dispersão longe da verdade, e não mais. As margens de cada lado são ambas de
cerca de um fator de cinco — 11.7 ppm na pior injeção da lock mass honesta,
237 ppm no impostor.

O **precursor escrito é deliberadamente recusado**. Um método que diz `647.5`
é bom até cerca de 800 ppm naquela massa; corrigir um eixo de massa em
direção ao arredondamento de alguém é pior do que não corrigi-lo. Digite a
fórmula.

## O que é ajustado

Uma correção por injeção:

- um **offset** em ppm — a mediana dos erros das lock masses daquela injeção,
  com o sinal invertido;
- um **termo linear** em ppm por dalton, mas apenas onde **quatro ou mais**
  lock masses cobrem pelo menos 100 Da *e* um teste de deixar-uma-de-fora diz
  que a reta prevê uma lock mass retida melhor do que o offset simples
  prevê. Uma reta traçada pelos pontos sobre os quais ela é então pontuada é
  exata e não diz nada, que é o mesmo aviso que o
  [[integration-algorithms|Gaussian fit]] carrega; quatro em vez de três,
  porque reter uma de três deixa uma reta por dois pontos, o que é exato de
  novo.

Uma correção a partir de **uma** lock mass é um offset e a tabela diz isso:
não sobra uma segunda medida contra a qual conferi-la, e o seu resíduo vai a
zero por construção e não por concordância.

## Onde ela se aplica

Enquanto o interruptor está ligado:

- o eixo de m/z dos espectros no [[explorer|Explorer]], cujo título passa a
  dizer `· recalibrated +3.2 ppm`;
- a medida do [[accurate-precursor|accurate precursor]], que reporta a massa
  crua e a corrigida lado a lado — o valor medido nunca é sobrescrito, porque
  a correção foi ajustada a partir dele;
- a janela de extração de todo [[manual-xic|XIC]] e de todo pico integrado. A
  janela se move; a aritmética do leitor, não. As linhas carregam a correção
  que lhes foi aplicada.

Com o interruptor desligado nada muda em absoluto, e um projeto salvo antes
de isto existir reabre com ele desligado.

## O que o lote real disse

Medido no lote de esfingolipídios de 26 injeções contra o qual isto foi
escrito (TripleTOF 5600, uma única varredura de survey de 50–700, um scan a
cada 14.6 s).

**Fórmulas.** O método não carregava nenhuma. O *Fill formulas from names*
leu 125 dos seus 141 nomes de componente e 10 dos seus 11 padrões internos,
em milissegundos e sem abrir um arquivo:

| | |
|---|---|
| preenchidas a partir do nome | **125** de 141 |
| recusadas — a fórmula do nome não é o precursor escrito | 16 |
| nomes que não são notação abreviada de lipídios | 0 |
| padrões internos que ganharam uma fórmula | **10** de 11 |

As dezesseis recusas são todas o *precursor* estar errado, e não o nome:
`dHCer(d18:0/12:0)` está escrito 484.465 contra os 484.4724 da sua fórmula
(15 ppm), `LacCER(d18:1/18:1(9Z))` exatamente 2.0000 Da abaixo, e as treze
linhas de `HexCer_2OH` e de ceramidas de cadeia longa cerca de 0.13 Da. Cada
uma é listada com os dois números, e a célula fica vazia — veja o
[[check-method]].

**Lock masses.** Uma fórmula era a metade que faltava da questão, e não é a
metade que limita. Dos 60 componentes que agora carregam uma fórmula *e*
ficam dentro do survey, exatamente **um** mede o mesmo íon injeção após
injeção:

| | |
|---|---|
| injeções corrigidas | 25 de 26 |
| lock masses em cada uma | **1** (somente offset) |
| offset mediano | **+4.8 ppm** (−4.4 a +11.7) |
| dispersão dos offsets | 16.1 ppm |

**O que a barreira da fórmula recusa.** Cinco dos dez padrões que carregam
uma fórmula são nomeados como medindo um íon que a fórmula deles não nomeia:
`Sphingosine C17:0` a 383 ppm dela, `C17:0_Ceramide` a 237, `C12:0 _Ceramide`
a 204, `Cer1P (12:0)` a 91 e `Sphingosine-1-P C17:0` a 82 — este último
montado a cavalo sobre a sua fórmula, com um erro mediano de apenas −43 ppm e
a maioria das suas injeções além do limite de um lado ou do outro. Cada um
deles já havia falhado na condição 3 ou estava aquém das injeções que uma
tendência exige, de modo que o ajuste abaixo permanece inalterado até a última
casa decimal e nenhuma injeção perdeu uma medida: neste lote a barreira é uma
guarda e não um achado. O quase-acerto diz por que vale a pena tê-la. O
`Sphingosine C14:0`, um analito e não um padrão, mantém a sua medida dentro de
**52 ppm ao longo de 25 injeções** — o dobro do limite de mesmo-íon, e nada
mais — a uma mediana de **156 ppm** da sua fórmula. Isso é um íon, medido
firmemente, e não é o composto; nada além da fórmula consegue dizer isso.

Os outros dez padrões falham por um motivo que fórmula nenhuma resolve: o
sinal deles no survey é fraco demais, de modo que a janela de busca de
±0.25 Da pega um vizinho diferente em cada injeção e eles se dispersam entre
98 e 534 ppm ao longo da corrida — e um fica fora do survey por completo. O
`C17:0_Ceramide` foi encontrado em apenas cinco injeções e a sua mediana fica
237 ppm da sua própria fórmula, o que é um íon diferente e não um íon mal
medido. **Várias lock masses não estão disponíveis neste lote com nenhuma
cobertura de fórmulas**, de modo que o termo linear continua nunca tendo
disparado em dados reais.

O número que importa é o que acontece com *outros* componentes. Cinquenta e
um analitos dentro do survey carregam agora uma fórmula — contra quinze
quando isto foi medido pela primeira vez — e foram medidos em cada injeção:
1,228 medidas ao todo. Sobre todas elas o erro mediano é −247 ppm antes e
−241 ppm depois, porque a maioria é interferência e não o composto, e nada na
escala de ppm as toca. Sobre as 197 medidas que já estavam dentro de 25 ppm
para começar:

| | antes | depois |
|---|---|---|
| erro mediano | −7.0 ppm | **−1.4 ppm** |
| magnitude mediana | 8.6 ppm | **6.8 ppm** |
| menor depois | | 122 de 197 |

Ou seja, isso move o centro na direção certa, e não pode ser melhor que a
única lock mass de que veio — cuja própria dispersão de 16 ppm ao longo da
corrida é maior que os 4.8 ppm pelos quais ela corrige.

## Isso muda os números

Reprocessando o lote inteiro dos dois modos, sobre janelas de extração de
±20 ppm, um deslocamento mediano de 5 ppm moveu **1,769 das 2,593 áreas
integradas**: uma mudança absoluta mediana de 1.3%, 830 linhas além de 5%, e
dez linhas que deixaram de encontrar um pico. Um instrumento de tempo de voo
guarda poucos pontos ao longo de uma janela tão estreita, de modo que mover a
borda da janela leva pontos inteiros para dentro ou para fora.

Ligar isto é uma decisão quantitativa, não uma preferência de exibição.
Ajuste, leia a tabela por injeção, e ligue apenas quando as lock masses o
justificarem — e então processe o lote de novo para que os resultados
acompanhem.

## Ver também

- [[mass-drift]] — a medida a partir da qual isto é ajustado
- [[accurate-precursor]] — a medida da massa de um componente na varredura de
  survey
- [[check-method]] — quais precursores a varredura de survey consegue ver
- [[report]] — a tabela de correções é impressa sob a seção de massa
