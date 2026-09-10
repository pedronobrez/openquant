---
title: Formatos de arquivo
---
Dois formatos são lidos: `.wiff` da SCIEX e mzML. Um é escrito: mzML.

## .wiff

Uma aquisição SCIEX são dois arquivos, `name.wiff` e `name.wiff.scan`, e os
dois são necessários — o primeiro guarda o método e o índice, o segundo os
espectros. O `.wiff` sozinho abre: a lista de amostras, o método, o
cromatograma de íons totais de cada canal e os parâmetros de aquisição estão
nele, e a árvore se preenche como se nada estivesse errado. O que não está
nele são os dados de scan, de modo que o primeiro espectro pedido falha — e
com ele todo cromatograma de íon extraído, o cromatograma de pico-base, o
contorno e a quantificação, que todos leem os scans. O OpenQuant tenta um
espectro quando o arquivo é aberto e, se falhar, diz isso de imediato: um
aviso quando o arquivo é acrescentado, um *⚠* diante da amostra na árvore,
com o motivo ao passar o cursor, o motivo no título do painel de espectro
onde estaria um espectro, e uma nota em qualquer linha de resultado que não
pôde ser extraída. A mensagem nomeia o arquivo que tem de estar ao lado do
`.wiff` e, quando a pasta contém um `.scan` que não pertence a nenhum
`.wiff` ali, nomeia também esse — um companheiro renomeado à mão
(`name.wiff_mix1.scan` ao lado de `name_mix1.wiff`) é a maneira habitual de
o par se desfazer, e renomeá-lo para `name_mix1.wiff.scan` é o reparo
inteiro — que [[checking-files]] encontra e oferece antes mesmo de o
arquivo ser aberto. Um `.wiff2` ao lado do par não é lido aqui, e nada se
perde com isso — veja a seção abaixo para o que foi medido.
Eles são lidos pelas próprias bibliotecas Clearcore2 da SCIEX, que
são o único software capaz de decodificar o formato e são redistribuídas
pelo pacote de código aberto alpharaw. Como elas são feitas funcionar fora
do Windows está descrito em [[how-wiff-is-read]].

Um `.wiff` pode conter várias amostras; cada uma é aberta como uma entrada
própria. Os arquivos são abertos em modo compartilhado somente leitura, de
modo que o Analyst ou uma segunda janela do OpenQuant podem abrir o mesmo
arquivo ao mesmo tempo.

Cada canal de aquisição — cada experimento do método — é listado com o seu
tipo, precursor, faixa de massas e energia de colisão, tal como o arquivo os
declara. Totais, tempos de retenção e áreas integradas que a biblioteca do
fabricante reporta são usados como reportados; nada é recalculado a partir
dos pontos armazenados onde existe o número do próprio instrumento, porque
somar os pontos armazenados em vez disso foi medido deslocando toda área
integrada em 2%.

## .wiff2

Um instrumento com SCIEX OS escreve um terceiro arquivo ao lado do par,
`name.wiff2`, e num ZenoTOF 7600 uma aquisição chega como um trio. Ele não
é aberto aqui, e o motivo é medido e não suposto.

Não é o mesmo tipo de arquivo. Um `.wiff` é um documento composto OLE; um
`.wiff2` é um banco de dados SQLite protegido por senha. Ao ser pedido para
abrir um, o Clearcore2 diz `Invalid OLE structured storage file`, e o seu
próprio `CheckDataFileIntegrity` chama-o de `NotWiffFile`. Isso valeu para
todos os nove `.wiff2` da pasta em que isto foi testado, com os
companheiros ao lado e com cada companheiro retirado por vez, e continuou
valendo quando o arquivo foi renomeado para `.wiff` — logo é o contêiner, e
não a extensão.

E, o que mais importa, não há nada nele para ler. A montagem do Clearcore2
que escreve um `.wiff2` declara o esquema inteiro, e são sete tabelas:
`header`, `sample`, `method`, `device_method`, `device_descriptor`,
`device_identifier` e `method_parameters_info`. Nenhuma coluna guarda um
espectro, um pico, uma intensidade ou um cromatograma. O que a tabela
`header` guarda é `wiff_hash`, `scan_hash` e `scan_size` — a identidade e o
tamanho dos dois arquivos ao lado dele. O `.wiff2` é o método da aquisição
e o seu registro dos companheiros, não os seus dados.

Os tamanhos dos arquivos dizem o mesmo. Nessas nove aquisições o
`.wiff.scan` — que realmente contém os espectros — vai de 1.67 a 9.88 MB,
um fator de 5.9, enquanto o `.wiff2` vai de 303 a 406 kB, um fator de 1.34,
em cinco valores distintos. O `.wiff2` acompanha o `.wiff` (correlação
0.989), não os dados de scan (0.748).

Portanto o `.wiff` de mesmo nome contém a aquisição, e abri-lo não perde
nada: lido com o `.wiff2` ao lado e com o `.wiff2` apagado, o mesmo arquivo
deu a mesma amostra, o mesmo experimento único, o mesmo cromatograma de
íons totais de 473 pontos e o mesmo primeiro espectro de 13.705 pontos. Um
`.wiff2` sem nenhum `.wiff` ao lado é uma aquisição que não pode ser aberta
aqui de modo algum, e nenhum leitor poderia ser escrito para ele a partir
deste contêiner — os espectros não estão nele. [[checking-files]] diz em
qual dos dois casos uma pasta está antes de qualquer coisa ser aberta.

## mzML

mzML é o formato aberto que o `msconvert` do ProteoWizard escreve a partir
dos arquivos de qualquer fabricante, de modo que um `.raw` da Thermo, um
`.d` da Agilent ou um `.tdf` da Bruker entram sendo convertidos primeiro.
Espectros em perfil e em centroide são ambos lidos, e os pontos de
intensidade zero que um fabricante removeu de um perfil são restaurados —
ver [[chromatograms-and-spectra]] para por que isso importa.

mzML não tem noção de *canal* de aquisição. Os canais são inferidos, e
inferidos a partir da ordem de aquisição em vez de apenas das propriedades
dos scans: um método pode ter dois experimentos que concordam em nível de
MS, precursor, energia de colisão e faixa de massas, e agrupar só pelas
propriedades deu 69 canais onde a aquisição tinha 81. Um método agendado
repete os seus experimentos em um ciclo fixo, de modo que a posição no ciclo
é o experimento. O arquivo contra o qual isto foi desenvolvido é um ciclo de
44 executado 339 vezes seguido de um ciclo de 37 executado 238 vezes —
44 + 37 = 81 canais, 44 × 339 + 37 × 238 = 23,722 espectros. Um ciclo tem de
se repetir pelo menos quatro vezes para ser acreditado; a aquisição
dependente de dados não tem ciclo e recai sobre as propriedades dos scans.

## Escrever mzML

`File ▸ Export sample as mzML…` no Explorer escreve a amostra selecionada
espectro por espectro, com a corrente iônica total que o instrumento
reportou em vez de uma recalculada aqui. O que sobrevive à viagem foi medido
em cinco aquisições reais de 81 canais lidas de volta por este programa, e
verificado contra o ProteoWizard nos dois sentidos:

| | |
|---|---|
| espectros | idênticos, em todos os canais, até o último dígito |
| cromatogramas de canal | idênticos, em todos os canais |
| o cromatograma de íons totais da corrida | idêntico, 577 pontos |
| áreas de pico integradas | idênticas |
| cromatogramas de íon extraído | **diferem**, ver abaixo |

## A única diferença: cromatogramas de íon extraído

A extração da própria SCIEX conta parte de um pico cujos pontos medidos caem
logo fora da janela de massas; este programa soma os pontos dentro dela.
Naquela aquisição a diferença é, na mediana, 0.58% da altura do pico, no
máximo 12%, e sempre menor aqui. De ponta a ponta, quantificar um componente
a partir do `.wiff` e a partir do seu mzML dá o mesmo tempo de retenção e a
mesma largura do pico e uma área com 0.54% de diferença.

Foram feitas duas tentativas de reproduzir a regra de borda do fabricante.
Ambas erradas: a segunda parecia certa nas janelas das quais foi derivada e,
em outras janelas, foi melhor em 41 canais e pior em 38 — cara ou coroa.
Portanto a regra simples é a que é distribuída e este parágrafo é o aviso.
**Quantifique uma série em um só formato.** Ver [[measured-facts]].

## Qual formato para quê

| Tarefa | Usar |
|---|---|
| revisar e quantificar dados SCIEX | `.wiff` diretamente |
| dados de outro fabricante | msconvert para mzML, depois abrir o mzML |
| uma série que precisa ser comparada ao longo do tempo | um só formato para a série inteira |
| entregar dados a software que não lê `.wiff` | exportar como mzML |

Os arquivos brutos nunca são modificados. Tudo o que o programa acrescenta —
tipos de amostra, concentrações, o método, os resultados — vive no arquivo
de projeto, ver [[projects-and-files]].
