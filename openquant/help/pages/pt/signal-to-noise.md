---
title: Sinal/ruído
---
O sinal/ruído aparece em quatro lugares — o portão do detector, os
[[acceptance-criteria]], as cartas de [[batch-qc]] e a [[results-table]] — e em
todos eles é a altura do pico dividida por uma medida do ruído. O que é o
ruído, e quando ele não pode ser medido, é o assunto inteiro desta página.

## Onde o ruído é medido

**Sobre o cromatograma inteiro**, quando nenhuma região de ruído está
definida. Ele deliberadamente *não* é medido dentro da janela de tempo de
retenção: aquele trecho é quase todo pico, de modo que a sua dispersão de
ponto a ponto reporta a própria inclinação do pico. Em dados reais isso leu
16,944 onde o ruído verdadeiro do traço era 505, e o mesmo pico saiu em S/N 19
automaticamente contra 531 à mão.

**Sobre uma região de ruído**, quando há uma definida a partir da grade de
[[peak-review]]: clique com o botão direito em um painel com um trecho de linha
de base sombreado e escolha *Set noise region from the shaded range*. **Noise
as** no painel Integration escolhe a medida: *peak-to-peak* toma a excursão
completa da região e é a leitura mais estrita e conservadora; *standard
deviation* é a mais branda. Ambas estão em uso em laboratórios, de modo que de
qual delas veio um número tem de ser declarado ao lado dele, e o painel o faz.

## Como funciona a estimativa automática

O ruído é o desvio absoluto mediano das diferenças de ponto a ponto, escalado
para um desvio padrão — um estimador robusto que um pico não consegue inflar.
Em um XIC de baixa contagem, mais da metade das diferenças é exatamente zero, o
que zera a mediana; o recurso alternativo é o desvio padrão da metade inferior
dos pontos, que raramente contém um pico.

## Quando não pode ser medido

**A estimativa fica "não medida" quando não há nada a medir**, e esse é o caso
ordinário em uma aquisição agendada, não a exceção. Ao longo de 846 traços
reais, o traço mediano tinha três pontos não nulos em sessenta e um, e apenas
9% tinham uma linha de base que variasse de algum modo. Um traço que o
instrumento reporta como zeros exatos tem uma linha de base abaixo do seu
limiar de reporte; não há ruído ali para medir, e um número inventado para isso
não seria razão com coisa alguma.

Assim, o sinal/ruído de uma linha fica vazio, mostrado como `—`, quando a linha
de base não pôde ser medida. No lote em que isso foi medido, ele pôde sê-lo
para 23% dos picos encontrados.

## O que os portões fazem sem ele

O detector ainda precisa de um piso para rejeitar os menores picos, de modo que
onde o ruído não pode ser medido ele usa uma contagem como ruído. Isso mantém o
portão — um pico de uma única contagem em um traço de outro modo nulo continua
rejeitado — mas significa que **Min. S/N** passa a ser um limiar de intensidade
absoluta vestindo um nome de sinal/ruído: um pico de 30 contagens em um traço
de zeros passa por S/N 3 com "S/N 30". Medido em um lote real, um padrão
interno de 30 contagens e outro de 42,400 contagens teriam reportado S/N 30 e
42,400 sob essa regra. O portão é mantido; o número sobre o qual ele rejeita
não é reportado como uma razão.

O mesmo vale para o S/N mínimo dos critérios de aceitação e para o limiar de
quantificável das cartas de QC: ambos ficam condicionados à altura absoluta com
uma constante arbitrária quando a linha de base é zero. O que essa questão de
fato exige é um piso sobre a resposta absoluta do padrão interno, e um lote do
tipo em que isto foi desenvolvido não fornece um — a precisão dele não acompanha
a sua resposta. Por isso o método o declara: **Min. response** no padrão, lido
pelas cartas, pela aceitação e pela verificação do método. Ver
[[internal-standards-and-qualifiers]] e [[batch-qc]].

## Aceitação

Um critério de aceitação sobre S/N que não pode ser avaliado marca a linha com
**S/N not measured** em vez de aprová-la em silêncio: um critério que não pôde
ser verificado não é um critério que passou, e não dizer nada permitiria que
fosse lido como tal.
