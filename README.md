# OpenPeakView

Visualizador de dados LC-MS da SCIEX (`.wiff` + `.wiff.scan`) escrito em Python,
com as funcionalidades de navegação do PeakView: TIC, BPC, canais individuais do
método, XIC e espectros de massa scan a scan ou como média de uma região do pico.

Roda em **macOS (incluindo Apple Silicon)**, Linux e Windows.

![tela](docs/screenshot.png)

## O que dá para fazer

### Navegação e visualização

| Recurso | Como |
|---|---|
| Abrir vários `.wiff` e sobrepor | `Arquivo ▸ Abrir .wiff` (aceita seleção múltipla) |
| TIC da amostra inteira | nó “TIC da amostra” na árvore |
| TIC ou BPC por canal | marque os canais e escolha `TIC`/`BPC` no combo |
| Canais individuais do método | cada experimento aparece na árvore com precursor, faixa de m/z e CE |
| Filtrar canais | caixa de busca (ex.: digite `313.2`) |
| Espectro de um scan | clique simples no cromatograma |
| Percorrer scan a scan | setas ← → ou os botões ◀ ▶ |
| Espectro médio de uma região | Shift + arrastar no cromatograma |
| Integração da região | área, altura, ápice e S/N na barra de status |
| Comparar em espelho | **Espelhar** inverte os traços pares (amostra × branco) |
| Normalizar, rótulos de m/z e de RT, legenda | botões da barra de ferramentas |
| Informações da amostra e do método | aba **Amostra** (vial, volume, método, lote, DP/CE do canal) |
| Preferências | tudo é lembrado entre sessões (janela, docas, opções, lista de compostos) |

### Extração e quantificação

| Recurso | Como |
|---|---|
| Lista de compostos alvo | aba **Compostos**: nome, precursor, fragmento, RT, janela, tolerância |
| Importar/exportar a lista | CSV, com cabeçalhos em português ou inglês |
| Extração em lote | **Extrair e integrar todos** roda a lista em todas as amostras marcadas |
| Ver um composto | duplo clique na linha mostra o XIC dele em todas as amostras |
| Tabela de resultados | RT, área, altura, largura, S/N e observação, ordenável e exportável |
| Detecção automática de picos | **Detectar picos** integra tudo que está no cromatograma |
| XIC manual | aba **XIC manual**: lista de m/z + tolerância em Da ou ppm |
| XIC a partir do espectro | Shift + arrastar no espectro → botão direito → *Extrair XIC* |
| XIC a partir da lista de picos | duplo clique na aba **Picos do espectro** |
| Exportar | `Arquivo ▸ Exportar cromatogramas / espectro (CSV)` |

### Processamento

| Recurso | Como |
|---|---|
| Suavização gaussiana | campo **Suavizar (σ, scans)**; 0 desliga |
| Subtração de linha de base | campo **Linha de base (min)**; use uma janela maior que o pico mais largo |
| Subtração de background nos espectros | selecione a faixa de branco → **Definir background** |

O que a suavização e a linha de base fazem vale tanto para o desenho quanto para a
integração e a exportação, então área e altura sempre correspondem ao que está na tela.

Atalhos do mouse nos dois painéis: arrastar = zoom por retângulo, duplo clique =
ajustar escala, botão direito = menu do pyqtgraph (exportar imagem, escalas etc.).

## Instalação

```bash
python3 -m pip install -r requirements.txt
python3 -m openpeakview.bootstrap --install   # baixa o runtime .NET (~30 MB) em ~/.dotnet
```

O segundo comando só é necessário uma vez, e apenas se você ainda não tiver um
runtime .NET 8 na máquina.

## Uso

```bash
python3 run.py
```

ou já abrindo arquivos:

```bash
python3 run.py 260903_Teste_Mix_EICs_DiHOME001.wiff 260903_Teste_Mix_EICs_S001.wiff
```

## Como o `.wiff` é lido

O formato `.wiff`/`.wiff.scan` é proprietário e não tem especificação pública. As
únicas bibliotecas capazes de decodificá-lo são as **Clearcore2, da própria
SCIEX** — as mesmas usadas pelo ProteoWizard/msconvert. Elas são redistribuídas
pelo pacote open source [`alpharaw`](https://github.com/MannLabs/alpharaw) (MIT)
e são assemblies .NET gerenciados.

Fora do Windows elas normalmente não funcionam, porque `Clearcore2.StructuredStorage`
abre o arquivo pela API COM `StgOpenStorageEx`, exclusiva do Windows. O módulo
[`openpeakview/bootstrap.py`](openpeakview/bootstrap.py) contorna isso:

1. localiza (ou instala) um runtime .NET 8;
2. baixa do NuGet os assemblies de compatibilidade que o .NET Core não traz
   (`System.Configuration.ConfigurationManager` e dependências) e registra um
   resolvedor para eles;
3. troca, por reflexão, o campo estático `StgStorage.sWindows` para `False`,
   fazendo a Clearcore2 usar sua implementação gerenciada (OpenMcdf) em vez do
   caminho COM.

Com isso o `.wiff` é lido nativamente em Apple Silicon, sem Docker, sem Wine e
sem Analyst instalado.

**Sobre licenças:** o código deste projeto é MIT. As bibliotecas Clearcore2 são
da SCIEX e *não* são open source — são redistribuíveis, é o mesmo arranjo que o
ProteoWizard usa. Hoje não existe leitor de `.wiff` totalmente livre de código do
fabricante. Se isso for um problema no seu contexto, o caminho alternativo é
converter os arquivos para mzML com o `msconvert` e ler o mzML com
[`pyteomics`](https://github.com/levitsky/pyteomics).

## Lista de compostos

A aba **Compostos** aceita um CSV com estas colunas (só `nome` e `precursor` são
obrigatórias):

```csv
nome,precursor,fragmento,rt,janela,tolerancia,unidade
12,13-DiHOME,313.2384,183.1391,14.7,0.6,0.02,Da
9,10-DiHOME,313.2384,201.1496,14.2,0.6,20,ppm
```

Sem `fragmento`, o XIC usa o próprio precursor. Sem `rt`, a busca cobre a corrida
inteira. O canal do método é escolhido pelo precursor **e** pelo tempo de
retenção — necessário em métodos escalonados, onde o mesmo precursor aparece em
mais de um período. Quando o canal encontrado não cobre a janela de tempo pedida,
o resultado sai com área zero e uma observação, em vez de um pico de outro tempo.

## Estrutura

```
openpeakview/
  bootstrap.py           inicialização do runtime .NET + patch da Clearcore2
  wiff.py                WiffFile / Sample / Channel → arrays numpy
  compounds.py           lista de compostos alvo (CSV)
  processing.py          suavização, linha de base, detecção de picos, integração, S/N
  ui/plots.py            painéis de cromatograma e espectro (pyqtgraph)
  ui/compound_panel.py   gerenciador de compostos
  ui/results_panel.py    tabela de resultados
  ui/sample_info.py      informações da amostra
  ui/main_window.py      janela principal
  app.py                 ponto de entrada
tests/                   pytest (numérica e lista de compostos)
```

Rode os testes com `python3 -m pytest tests`.

A camada de dados funciona sozinha, sem interface:

```python
from openpeakview import WiffFile

sample = WiffFile("260903_Teste_Mix_EICs_DiHOME001.wiff").sample(0)
canal = sample.channels[80]                 # TOF PI, precursor 313.24
rt, tic = canal.tic()
rt, xic = canal.xic(183.1391, tolerance=0.02)        # fragmento do 12,13-DiHOME
mz, i = canal.spectrum(canal.scan_at_rt(14.66))      # espectro de um scan
mz, i = canal.spectrum_rt_range(14.5, 14.8)          # espectro médio da região
```

## Dados

Os arquivos `.wiff`/`.wiff.scan` não são versionados (veja `.gitignore`): são
binários grandes e mudam a cada corrida. Deixe-os onde preferir e abra pelo menu.

Os arquivos usados no desenvolvimento vêm de um TripleTOF 5600 em modo negativo,
método targeted MRM-HR com 81 experimentos em 2 períodos: `TOF MS` (100–2000)
mais 80 canais `TOF PI`, um por precursor.
