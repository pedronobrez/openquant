---
title: Linha de comando
---
A aplicação instalada e a árvore de código respondem aos mesmos argumentos. A
partir da árvore de código o comando é `python3 run.py`; a partir de um
instalador é o executável dentro da aplicação — no macOS
`/Applications/OpenQuant.app/Contents/MacOS/OpenQuant`.

```
OpenQuant [files...] [--selftest] [--digest]
```

| Argumento | Efeito |
|---|---|
| `files` | arquivos de dados brutos a abrir — `.wiff`, `.mzML` — na janela, em lugar do prompt inicial |
| `--selftest` | abre os arquivos, relata o que foi lido, e sai sem janela |
| `--digest` | imprime uma impressão digital numérica de cada arquivo, para comparar uma build com outra, e sai |

## --selftest

Imprime a versão e a plataforma, se o índice do LIPID MAPS está instalado, se as
bibliotecas SCIEX estão prontas e onde o runtime .NET foi encontrado — ou por
que estão indisponíveis — e então, para cada arquivo, quantas amostras e canais
foram lidos, ou a exceção que o impediu. É o que os instaladores executam sobre
si mesmos antes de serem distribuídos, e a primeira coisa a executar quando um
arquivo não abre.

## --digest

Para cada arquivo, uma linha por canal com um hash curto de seu eixo de tempo e
de seu cromatograma total, uma por espectro amostrado, e uma por pico integrado
com sua área com nove casas decimais. Duas builds que leem o mesmo arquivo devem
imprimir uma saída idêntica byte a byte; o processo de lançamento compara a
build do macOS, a build do Windows e a árvore de código deste modo. A partir do
código no macOS, a partir da imagem de disco da CI e a partir do instalador do
Windows sob o CrossOver, cinco aquisições reais deram a mesma saída até o último
dígito. A build do Windows escreve terminações de linha CRLF, que é a única
diferença que o `diff` mostrará.

## O bootstrap

```
python3 -m openquant.bootstrap --install
```

instala um runtime .NET 8 em `~/.dotnet` quando a máquina não tem nenhum, e
busca os assemblies de compatibilidade de que o Clearcore2 precisa. É necessário
uma vez, a partir do código; os instaladores carregam o que precisam. Veja
[[installation]] e [[how-wiff-is-read]].

## Programando a camada de dados

O leitor e a numérica funcionam sem a interface:

```
from openquant import WiffFile

sample = WiffFile("run.wiff").sample(0)
channel = sample.channels[65]
rt, tic = channel.tic()
rt, xic = channel.xic(183.0137, tolerance=0.02)
mz, i = channel.spectrum(channel.scan_at_rt(13.14))
mz, i = channel.spectrum_rt_range(13.0, 13.3)
```

`openquant.raw.open_raw(path)` devolve o leitor certo para qualquer um dos
formatos com a mesma superfície. `openquant.quantify.process(entries, method)`
executa um método sobre um lote e devolve o conjunto de resultados;
`openquant.report` escreve um relatório a partir de uma sessão;
`openquant.compare.compare_algorithms` executa a comparação. A camada de química
— `openquant.chemistry` — analisa fórmulas, calcula massas e padrões isotópicos
e busca composições, e não depende nem da interface nem das bibliotecas do
fornecedor.

Esses são os módulos em si, e eles podem mudar de lugar. Para uma superfície
que não muda — um lote reprocessado e exportado, um espectro explicado, uma
biblioteca buscada, um relatório escrito, em dez linhas e com uma promessa
de estabilidade — use a [[python-api]].
