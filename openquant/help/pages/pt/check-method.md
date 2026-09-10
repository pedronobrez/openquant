---
title: Verificar o método
---
**Check method** no [[method-workspace]] lê o método contra si mesmo e contra os
arquivos abertos, e diz em que ele vai falhar antes que um lote seja processado.
Tudo o que ele reporta seria de outro modo aprendido a partir dos resultados, o
que é mais tarde e mais difícil.

## O que é verificado

| Achado | Severidade | Significado |
|---|---|---|
| shared transition | serious | dois componentes declaram o mesmo precursor e o mesmo fragmento e não têm nada — nenhum tempo de retenção, ou o mesmo — que os separe; a integração devolverá o mesmo pico sob os dois nomes |
| missing internal standard | serious | um componente nomeia um padrão que nenhum componente carrega, ou um que não está marcado como IS |
| internal standard without a time | serious | um padrão sem tempo de retenção é buscado ao longo de toda a corrida, e toma o maior pico em qualquer lugar dela; cada componente que ele normaliza herda isso. A contagem de componentes que ele carrega é dada |
| internal standard without a response floor | warning | um padrão que serve componentes não declara nenhuma **Min. response**, de modo que as cartas de qualidade e a aceitação recaem sobre um sinal/ruído de dez — o que, numa aquisição agendada, é uma altura absoluta contra uma constante arbitrária. Veja [[internal-standards-and-qualifiers]] |
| formula against precursor | serious | a **Formula** de um componente e o seu **Precursor** estão mais distantes do que a última casa decimal escrita desse precursor permite. Um dos dois está errado, e eles fazem trabalhos diferentes: o precursor constrói a janela de extração, a fórmula é a massa verdadeira em direção à qual a [[mass-recalibration|recalibração]] corrige |
| internal standard without a formula | warning | o padrão não pode ser uma lock mass. Sem uma fórmula e um aduto nada diz onde a massa dele deveria estar, e o precursor escrito não pode substituí-la — um digitado com uma única casa decimal é bom até algumas centenas de partes por milhão, cem vezes o erro que está sendo corrigido. O *Fill formulas from names* no [[method-workspace]] deriva uma onde quer que o nome seja notação abreviada de lipídios |
| no retention time | warning | a janela do componente é a corrida inteira, de modo que o maior pico da corrida é o componente, seja ele qual for |
| precursor outside the survey scan | warning | com arquivos abertos: componentes cujo precursor nenhuma varredura de survey cobre, e as faixas que os surveys de fato cobrem. A massa exata, a anotação do LIPID MAPS e a [[mass-drift]] não podem ser medidas para eles; a transição em si não é afetada. Uma aquisição sem nenhuma varredura de survey é reportada sob as verificações puladas |
| window too narrow | warning | no intervalo de amostragem medido a partir dos arquivos abertos, a janela ± contém menos de oito pontos; abaixo de cinco o detector recusa de saída |

Severidades: um achado **serious** produzirá números errados; um **warning**
produzirá números mais difíceis de defender.

## O que é pulado, e dito

Verificações que precisam dos arquivos — o intervalo de amostragem, e portanto a
verificação de janela — são puladas quando nenhuma amostra está aberta, e o
diálogo lista o que não pôde verificar em vez de silenciar sobre isso. Um método
que "passa" com metade das verificações não executadas não passou.

## Agindo sobre os achados

- Uma transição compartilhada precisa de um tempo de retenção em cada
  componente, e de tempos diferentes.
- Um padrão sem tempo precisa de um: [[suggest-from-data]] estima tempos a
  partir das injeções abertas e diz o quanto cada estimativa pode ser confiada.
- Uma janela estreita demais para a amostragem pode ser alargada pelo mesmo
  diálogo, que calcula a meia-largura que dá oito pontos.
- Um padrão ausente é um erro de grafia ou uma marcação faltando, corrigido na
  tabela.
- Um padrão sem fórmula ganha uma do *Fill formulas from names* onde o nome
  dele diz do que ele é feito; os demais são digitados.
- Uma fórmula que discorda do seu precursor é uma pergunta que só quem
  escreveu o método pode responder — qual dos dois está certo. No lote contra
  o qual isto foi desenvolvido era o precursor: o `dHCer(d18:0/12:0)`
  carregava 484.465 contra os 484.4724 da sua própria fórmula, 15 ppm fora.

A verificação corre sobre o método tal como está, de modo que pode ser executada
de novo após cada correção. Os mesmos achados aparecem no início da seção de
método do [[report]], de modo que um relatório carrega seus próprios avisos.
