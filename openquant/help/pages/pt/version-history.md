---
title: Histórico de versões
---
O repositório público começa na 0.6.1, depois de ter sido recriado para
descartar um histórico cujas capturas de tela mostravam o nome de uma pessoa e
resultados não publicados; as versões anteriores existem apenas como
instaladores. Cada versão abaixo traz os três instaladores descritos em
[[installation]].

| Versão | Data | O que entrou |
|---|---|---|
| 0.8.1 | 2026-09-10 | o aduto que o precursor de fato é — lido do precursor escrito e da fórmula em todas as vias de explicação, com a razão impressa; um aduto lábil entrega o seu próton aos fragmentos e a escada de perdas pendura-se de `[M+H]+`; nomes de padrões de ácidos biliares resolvidos com a sua contagem de marcações — [[lipid-maps]]; o piso de etiquetas, os espectros fixados e o estado do painel salvos com o projeto como receitas — [[projects-and-files]] |
| 0.8.0 | 2026-09-10 | o piso de etiquetas — o triângulo do PeakView ao lado do eixo Y do espectro, **Label floor (%)**, levado à impressão — ver [[chromatograms-and-spectra]]; etiquetas impressas nunca sobre um traço; o [[infusion-report]] por composto com o seu veredito de verificações somadas, a aba *Infusions* da [[analytics-workspace]] e a sua seção no relatório; [[standard-history]], a biblioteca própria lida de volta como carta de controle; **Repair precursors…** com o nome sugerido onde a massa está certa — [[method-workspace]]; a porta de lock mass a 50 ppm e o precursor do registro medido contra a sua fórmula — [[mass-recalibration]], [[spectral-library]]; onde está o deutério, inferido dos fragmentos — [[lipid-maps]]; a regra de [[direct-infusion]] após o primeiro segundo e o veredito *too short to tell*; a pasta de trabalho aberta no Excel — [[export]] |
| 0.7.9 | 2026-09-10 | o Dock mostra o ícone em camadas enquanto a aplicação corre (o bundle já não define ícone de janela); a regra de [[direct-infusion]] medida nas infusões de ácidos biliares e corrigida — o scan do percentil 99 como referência, 48 de 48 classificados; a biblioteca própria medida nos mesmos padrões — [[spectral-library]]; **Fill formulas from names** na [[method-workspace]] com a verificação do precursor, e o [[check-method]] nomeando um padrão sem lock mass; a [[mass-recalibration]] medida com fórmulas em dez padrões; o `.wiff2` medido como não contendo dados de scan — [[formats]]; etiquetas de picos com orçamento por região — [[chromatograms-and-spectra]]; a [[audit-trail]] salva com o projeto, em aba própria, no [[report]] e em CSV |
| 0.7.8 | 2026-09-10 | o ícone Liquid Glass para o macOS 26 — um documento do Icon Composer em camadas compilado na máquina de build, o `.icns` mantido para sistemas anteriores — e o ícone no atalho e na lista de programas do instalador do Windows, ver [[installation]] |
| 0.7.7 | 2026-09-09 | o manual em português do Brasil, comutado na sua barra de ferramentas, com busca e PDF por idioma; **Add spectrum to library…** — o espectro em tela escrito num MSP próprio e pesquisável de imediato — ver [[spectral-library]]; **Export comparison…** e a seção *Compared spectra* do [[report]], desenhada para papel — ver [[chromatograms-and-spectra]]; uma [[direct-infusion]] reconhecida ao abrir e mostrada como a média de todos os scans, e **Average whole run** em qualquer canal; **Check a folder…** antes de os arquivos serem abertos, com o rename de um `.scan` órfão oferecido — [[checking-files]]; **Export workbook (Excel)…** e **Export for Skyline…** — [[export]]; [[mass-recalibration]] a partir dos padrões que carregam uma fórmula, desligada por padrão e medida no lote; o ícone na entrada do menu Iniciar e na lista de programas do Windows, e uma entrada de lançador no Linux com `install.sh` — [[installation]] |
| 0.7.6 | 2026-09-09 | um `.wiff` sem o seu `.wiff.scan` avisa em vez de deixar o painel do espectro vazio — um aviso quando o arquivo é adicionado, a amostra marcada com *⚠* na árvore, o motivo escrito onde estaria o espectro, e uma nota na linha em vez de um lote interrompido; a mensagem nomeia o `.scan` de que o arquivo precisa e qualquer um perdido na pasta — ver [[formats]] e [[troubleshooting]]; o ícone da aplicação no bundle, no executável de Windows e na janela; a suíte de testes guarda as configurações em um arquivo próprio, em vez de nas preferências reais |
| 0.7.5 | 2026-09-08 | Explain com uma estrutura ou fórmula própria — um molfile do PubChem pontuado como um registro, o precursor e as perdas de uma fórmula, e deutério não posicionado enumerado por contagem — ver [[lipid-maps]]; **Pin spectrum** para desenhar o espectro de uma amostra sobre o de outra, com Normalise e Mirror para a comparação cabeça-cauda — ver [[chromatograms-and-spectra]] |
| 0.7.4 | 2026-09-08 | a [[spectral-library]] medida sobre os 139,006 registros do MassBank — mínimo de dois picos correspondidos, registros sem precursor deixados fora de uma busca filtrada a menos que se peça, a tolerância de precursor no mínimo igual à precisão escrita, e um índice que responde em milissegundos; o resultado de [[compare-batches]] impresso no [[report]] enquanto ele valer |
| 0.7.3 | 2026-09-08 | a aba [[spectral-library]] do Explorer — bibliotecas MSP e MGF buscadas com o espectro na tela, pontuações simples e reversa, o registro sobreposto; [[compare-batches]] — um projeto de referência contra o lote aberto, componente por componente, a referência lida sem abrir um arquivo bruto |
| 0.7.2 | 2026-09-08 | **Export schedule…** na [[method-workspace]]: a aquisição agendada que o método implica, com o dwell time que um ciclo alvo deixa a cada transição no momento mais congestionado — [[acquisition-schedule]]; [[check-method]] nomeia os precursores que nenhuma varredura de survey (survey scan) cobre |
| 0.7.1 | 2026-09-08 | **Suggest floors…** em [[batch-qc]]: uma Min. response proposta por padrão interno a partir das injeções que não foram falhas, com a sua base; a aba e a seção de relatório de [[mass-drift]] — o precursor de cada padrão lido do survey em cada injeção, a mudança ao longo da corrida, e a regra de que uma dispersão acima de 25 ppm não é duas vezes o mesmo íon |
| 0.7.0 | 2026-09-08 | F1 abre a página do painel que está com o foco, e todo diálogo tem um botão Help; a aba *Sampling* de [[batch-qc]] e a sua seção de relatório — pontos por pico contados na integração, os tempos de ciclo de que os picos precisariam, um ponto por pico no lote para o qual isto foi escrito; o piso de resposta que um padrão interno declara (**Min. response**), lido pela carta de controle, pela aceitação e por [[check-method]] — ver [[internal-standards-and-qualifiers]] |
| 0.6.9 | 2026-09-08 | este manual: quarenta e quatro páginas ligadas como um cofre, com busca, backlinks e uma cópia impressa a partir de **Help ▸ Export manual as PDF…**; a regra de títulos órfãos do [[report]] corrigida para um título cujo bloco seguinte era ele próprio empurrado para uma nova página |
| 0.6.8 | 2026-09-07 | três [[integration-algorithms]] — valley, summation, ajuste gaussiano — com cada linha dizendo qual produziu o seu número; [[compare-algorithms]] com a visão de traço único, a adoção e uma seção de relatório; a regra dos três pontos nos flancos do ajuste, medida em um padrão real |
| 0.6.7 | 2026-09-07 | [[suggest-from-data]]: tempos de retenção calibrados por faixa de altura, janelas a partir da amostragem; **Exclude failed injections** no Batch QC; o diálogo [[check-method]]; S/N reportado como não medido em vez de como uma constante — [[signal-to-noise]] |
| 0.6.6 | 2026-09-07 | o índice de resposta da injeção e o veredito de carta inutilizável em [[batch-qc]]; uma condição de sinal/ruído nas cartas; a margem dada ao detector de cada lado da janela, que levou um lote real de 1,771 a 2,665 picos — [[integration-parameters]] |
| 0.6.5 | 2026-09-07 | a [[contour-view]]; a regra de pico *nearest the expected RT* |
| 0.6.4 | 2026-09-07 | [[batch-qc]]: cartas de controle contra a ordem de injeção com limites robustos, deriva e precisão dos QCs |
| 0.6.3 | 2026-09-07 | o [[report]] corrigido e redesenhado — A4 retrato, sumário com números de página, elementos correntes; [[detection-limits-and-carryover]] |
| 0.6.2 | 2026-09-07 | o relatório do lote, PDF e HTML; as capturas de tela a partir de um lote sintético |
| 0.6.1 | 2026-09-06 | o repositório público recriado; um único sistema de design no azul do projeto; grupos de amostra e estatística por grupo; o gráfico de métricas colorido por grupo; o assistente New Project; renomeado para OpenQuant a partir de OpenPeakView |
| 0.6.0 | 2026-09-06 | os instaladores de Windows e de Linux ao lado da imagem de disco de macOS; o shim ICU para Wine documentado |
| 0.5.x | 2026-09-06 | a área de trabalho Analytics — revisão de picos, resultados, calibração, aceitação, estatística; as áreas de trabalho Method e Samples; projetos; anotação pelo LIPID MAPS, explicação de estruturas e a medição de precursor exato; leitura e escrita de mzML com as medições de fidelidade em [[measured-facts]] |

## Ainda não em uma versão publicada

Um manual lido da árvore de código descreve o que a árvore de código faz, e
ela corre à frente da última tag. Estas páginas descrevem trabalho que está
no ramo principal e ainda não entrou em uma versão: o caminho da infusão
direta de ponta a ponta — a máscara de pulverização da [[direct-infusion]] e
o seu filme na [[contour-view]], o [[infusion-report]] de uma pasta com a
sua capa, a [[infusion-quantitation]], a [[compare-infusions]], a
[[collision-energy]] e o [[new-standard]] —, o [[method-report]], a
[[python-api]], o piso de ruído medido numa infusão ([[signal-to-noise]]), a
margem e as hipóteses para picos não explicados do [[lipid-maps]], o eixo de
massa próprio do registro ([[spectral-library]]) e o processamento
incremental ([[analytics-workspace]]); e o *Measure* da aba Infusions com as
médias em cache no disco e o detector de picos já não quadrático — um
*Measure* morno de nove infusões de 7,7 – 8,5 s para 1,7 ([[infusion-report]]).
Cada uma será nomeada na linha da versão que a publicar.

O manual faz parte de cada versão: uma versão que muda o que o aplicativo faz
muda a página que a descreve, e a cópia impressa é regerada a partir das mesmas
páginas.
