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
- **"7 of the 97 ions predicted for … were found"** — o denominador é quantos
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

## Medido

Ácido cólico-d4 infundido num ZenoTOF 7600, o mesmo frasco sob duas
ativações, explicado a partir da fórmula `C24H40O5` como `[M+H]+` com quatro
deutérios não posicionados e buscado contra um registro feito da corrida CID:

| | CID, 45 eV, 473 scans | EAD, 22 eV, 146 scans |
|---|---|---|
| pico base | 359,2870 | 377,3015 |
| precursor 430,35 no espectro de íons produto | 84 contagens, 1,49% — pouco demais | 430,3489 a 9.415 contagens, **+20,7 ppm** |
| íons encontrados, de 97 previstos | 2 — 24,2% da intensidade | 7 — 41,9% |
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
2 de 97 íons é o que uma fórmula com três perdas neutras consegue dizer sobre
um espectro cujo pico base precisa de quatro. Nenhuma das duas é uma falha do
composto, e o relatório é construído de modo que a página diga qual é qual.
