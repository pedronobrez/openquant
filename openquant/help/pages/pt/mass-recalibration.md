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

Uma lock mass aqui é um padrão interno que satisfaz três condições:

1. ele carrega uma **fórmula e um aduto** no [[method-workspace|method]], de
   modo que a sua massa verdadeira é conhecida;
2. o seu precursor fica dentro da faixa de massas da varredura de survey, de
   modo que pode ser medido — o [[check-method|Check method]] lista os que
   não ficam;
3. o íon medido se manteve o mesmo ao longo da corrida, que é o mesmo teste
   `same_ion` que a medida de [[mass-drift|drift]] aplica: injeções que
   discordam por mais de 25 ppm não estavam medindo um único íon, e
   promediá-las recalibraria o instrumento sobre o que por acaso estivesse
   mais perto.

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
cada 14.6 s):

| | |
|---|---|
| padrões internos no método | 11 |
| carregando uma fórmula, tal como o método foi escrito | **0** |
| lock masses, portanto | **nenhuma — nada corrigido** |

Essa é a resposta honesta para aquele lote como ele está: cada injeção voltou
como *no usable lock mass — left as measured*.

Dada uma fórmula — `SM(d18:1/12:0)`, C35H71N2O6P, [M+H]+ 647.5123 — o quadro
é:

| | |
|---|---|
| injeções corrigidas | 25 de 26 |
| lock masses em cada uma | 1 (somente offset) |
| offset mediano | **+4.8 ppm** (−4.4 a +11.7) |
| dispersão dos offsets | 16.1 ppm |

Os outros dez padrões não poderiam ser lock masses qualquer que fosse a
fórmula dada a eles: nove se dispersam entre 98 e 534 ppm ao longo da
corrida, e um não tem varredura de survey que o cubra.

O número que importa é o que acontece com *outros* componentes. Quinze
analitos dentro do survey têm uma massa derivável da notação abreviada de
lipídios dos seus próprios nomes. Sobre todas as 369 medidas deles o erro
mediano é −275 ppm antes e −270 ppm depois — essas são interferências e não o
composto, e nada na escala de ppm as toca. Sobre as 66 medidas que já estavam
dentro de 25 ppm para começar:

| | antes | depois |
|---|---|---|
| erro mediano | −8.7 ppm | **−3.3 ppm** |
| magnitude mediana | 9.9 ppm | **7.0 ppm** |
| menor depois | | 43 de 66 |

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
