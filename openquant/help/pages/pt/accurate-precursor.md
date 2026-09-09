---
title: Massa exata do precursor
---
A lista de precursores de um método é escrita à mão — `351.20`, `313.24` — e só
é boa até as casas decimais com que foi digitada. Consultar um lipídio a partir
disso é pedir ao banco de dados dígitos que o número não carrega: a ±0.005 Da
uma massa próxima de 350 é incerta em 14 ppm, e a janela de busca se enche do
que por acaso estiver por perto.

A varredura de survey (survey scan) contém o número real. Antes de uma busca de
lipídio em nome de um componente, o programa encontra o íon precursor no canal
de varredura completa (TOF MS) **no momento em que o canal de íons produto
efetivamente vê o pico**, e usa a massa que o instrumento mediu.

## Como é medida

1. A própria transição do componente é integrada para descobrir quando ele
   elui; esse tempo ancora a busca.
2. No canal de survey, o espectro naquele tempo é buscado dentro de ±0.25 Da do
   precursor escrito — amplo o bastante para absorver um valor arredondado à
   mão, bem dentro do cerca de 1 Da que o Q1 isola, de modo que uma massa
   nominal vizinha nunca pode ser capturada.
3. O pico encontrado é centroidizado; um pico mais fraco que 100 contagens não
   é confiado como medição de massa.
4. O mesmo é feito em cada amostra aberta. As amostras têm de concordar dentro
   de 25 ppm para estarem medindo o mesmo íon; o consenso é a mediana.
5. O **precursor sobrevivente** na varredura de íons produto — o íon não
   fragmentado que passou pelo Q1 — também é medido, e os dois têm de concordar
   dentro de 25 ppm.

Essa última verificação importa. O survey vê tudo o que elui naquele momento,
de modo que uma interferência forte dentro da janela de busca pode vencer; o
que quer que sobreviva à fragmentação teve de passar antes pela janela de
isolamento do Q1, o que é a confirmação de que o pico do survey é o precursor
da própria transição.

## Para que a massa é usada depois

Onde o survey consegue medir um precursor, uma busca de lipídio usa essa massa
a ±10 ppm. Onde não consegue, a janela recai sobre a precisão do próprio
precursor tal como escrito: uma massa escrita como `351.20` é conhecida a
±5 mDa, e pedir 10 ppm dela seria inventar dígitos.

Em dados reais a diferença decide a resposta. Uma transição escrita como
`325.20` corresponde a `FA 18:3;O3` em precisão nominal; a varredura de survey
coloca o íon em 325.1887 e a varredura de íons produto concorda dentro de
1 ppm, o que descarta essa espécie a 41 ppm.

## Onde aparece

- [[annotate-from-lipid-maps]] — cada proposta diz se sua massa veio do survey
  ou foi escrita, e que janela foi usada.
- o Explain da aba [[lipid-maps]] — o precursor ali digitado é aquilo pelo que
  os candidatos são consultados;
- [[mass-drift]] — a mesma medição feita em cada injeção, para ver se o eixo de
  massa se manteve ao longo da corrida;
- [[mass-recalibration]] — corrigir o eixo a partir dos padrões que carregam
  uma fórmula. Com ela ligada, esta medida é reportada crua e corrigida lado
  a lado: o valor medido nunca é sobrescrito, porque a correção foi ajustada
  a partir dele.
