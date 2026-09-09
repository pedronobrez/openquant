---
title: Projetos e arquivos
---
## O arquivo de projeto

Um projeto é um único arquivo, `name.oqproj`, JSON, legível por qualquer
coisa. Ele contém:

| Chave | Conteúdo |
|---|---|
| `version` | a versão do formato do arquivo, atualmente 3 |
| `method` | a tabela de componentes, os padrões de integração e de aceitação, a tolerância e as unidades, as faixas de razão iônica — tudo o que está na [[method-workspace]] |
| `samples` | uma entrada por injeção: o caminho do arquivo bruto e o índice da amostra, o nome exibido, o tipo, o grupo, a concentração esperada, a diluição e o comentário — tudo o que está na [[samples-workspace]] |
| `results` | cada linha da [[results-table]], incluindo integrações manuais, notas, o algoritmo que produziu cada área, os pontos sobre o pico e, para um pico ajustado, o modelo |
| `calibrations` | cada curva: regressão, ponderação, coeficientes, r² e cada padrão com a indicação de se é usado |

Ele **não** contém os dados brutos — o projeto aponta para os arquivos por
caminho — nem a última comparação de algoritmos, que é derivada e refeita sob
demanda. Um arquivo que mudou de lugar é reportado pelo nome quando o projeto
abre, e o projeto abre sem ele; ver [[starting-a-project]].

Projetos escritos pelo programa sob o nome anterior, `.opvproj`, são abertos;
nada novo é escrito com esse sufixo. Um projeto escrito por uma versão mais
antiga abre em uma mais nova: os campos que a mais nova acrescentou assumem
seus padrões — um método salvo antes de existirem algoritmos de integração é
lido de volta como *valley*, que foi o que ele executou.

## Dados brutos

`.wiff` com seu `.wiff.scan`, e mzML. Nunca modificados. Ver [[formats]].
O que uma pasta contém e o que daria errado nela — um companheiro que não
está lá, um `.scan` com o nome errado, arquivos que nenhum leitor daqui
abre — é respondido antes de qualquer coisa ser aberta por *File ▸ Check a
folder…*; ver [[checking-files]], que é também onde o único reparo,
renomear um `.scan` órfão, é oferecido.

## Arquivos CSV

**A tabela de componentes** — `Import CSV…` e `Export CSV…` na área de
trabalho Method; o layout e os cabeçalhos aceitos estão em
[[method-workspace]].

**Resultados** — `Export CSV…` abaixo da tabela de resultados escreve as
colunas visíveis das linhas visíveis; na aba Statistics, o resumo como
mostrado; no Explorer, as linhas da aba Results.

**Cromatogramas e espectros** — `File ▸ Export chromatograms (CSV)…` escreve
cada traço do cromatograma do Explorer como colunas de tempo e intensidade;
`Export spectrum (CSV)…` escreve o espectro na tela como m/z e intensidade.

## mzML

`File ▸ Export sample as mzML…` escreve a amostra selecionada espectro por
espectro; o que sobrevive à viagem está em [[formats]].

## O relatório e o manual

`File ▸ Export report…` escreve PDF ou HTML — ver [[report]]. `Help ▸ Export
manual as PDF…` escreve este manual.

## Onde a aplicação guarda os próprios arquivos

| O quê | Onde |
|---|---|
| preferências | o repositório de configurações da plataforma, organização `OpenQuant`, aplicação `OpenQuant`: geometria da janela, última pasta, painéis recolhidos, o aviso inicial |
| o runtime .NET, quando instalado pelo bootstrap | `~/.dotnet` |
| assemblies NuGet baixados, o índice do LIPID MAPS | `~/.openquant`, ou o diretório indicado pela variável de ambiente `OPENPEAKVIEW_HOME` |

Apagar `~/.openquant` custa um download dos assemblies e do índice de lipídios
na próxima vez que cada um for necessário; nada sobre qualquer lote está lá
dentro.
