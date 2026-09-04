# OpenPeakView

Visualizador de dados LC-MS da SCIEX (`.wiff` + `.wiff.scan`) escrito em Python,
com as funcionalidades de navegação do PeakView: TIC, BPC, canais individuais do
método, XIC e espectros de massa scan a scan ou como média de uma região do pico.

Roda em **macOS (incluindo Apple Silicon)**, Linux e Windows.

![tela](docs/screenshot.png)

## O que dá para fazer

| Recurso | Como |
|---|---|
| Abrir vários `.wiff` e sobrepor | `Arquivo ▸ Abrir .wiff` (aceita seleção múltipla) |
| TIC da amostra inteira | nó “TIC da amostra” na árvore |
| TIC ou BPC por canal | marque os canais e escolha `TIC`/`BPC` no combo |
| Canais individuais do método | cada experimento aparece na árvore com precursor, faixa de m/z e CE |
| Filtrar canais | caixa de busca (ex.: digite `313.2`) |
| XIC | painel **XIC**: lista de m/z + tolerância em Da ou ppm |
| XIC a partir do espectro | Shift + arrastar no espectro → botão direito → *Extrair XIC* |
| XIC a partir da lista de picos | duplo clique na aba **Picos do espectro** |
| Espectro de um scan | clique simples no cromatograma |
| Percorrer scan a scan | setas ← → ou os botões ◀ ▶ |
| Espectro médio de uma região | Shift + arrastar no cromatograma |
| Integração da região | área, altura, ápice e S/N aparecem na barra de status |
| Exportar | `Arquivo ▸ Exportar cromatogramas / espectro (CSV)` |

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

## Estrutura

```
openpeakview/
  bootstrap.py     inicialização do runtime .NET + patch da Clearcore2
  wiff.py          WiffFile / Sample / Channel → arrays numpy
  processing.py    suavização, detecção de picos, integração, S/N
  ui/plots.py      painéis de cromatograma e espectro (pyqtgraph)
  ui/main_window.py janela principal
  app.py           ponto de entrada
```

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

## Os arquivos de exemplo

Os dois `.wiff` do diretório são de um TripleTOF 5600 em modo negativo, método
targeted MRM-HR com 81 experimentos: `TOF MS` (100–2000) mais 80 canais `TOF PI`,
um por precursor, em 2 períodos. O canal 80 (precursor 313.24) é o do
12,13-DiHOME; o fragmento em *m/z* 183.139 elui em ~14,7 min na injeção do padrão
e está ausente no branco de solvente.
