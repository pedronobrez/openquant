---
title: A área de trabalho Method
---
A área de trabalho Method (Ctrl+3) é a tabela de componentes — o equivalente
da tabela de componentes do MultiQuant. Um componente diz o que extrair
(precursor, fragmento, tolerância), onde o pico é esperado (tempo de
retenção e meia janela) e como o seu resultado é reportado (área, razão a um
padrão interno, ou concentração).

## Colunas

| Coluna | Significado |
|---|---|
| Name | o nome do componente; como ele é referido em todo o resto |
| Group | um agrupamento em texto livre — ceramidas, esfingomielinas — que dobra a árvore de componentes em Analytics e permite aplicar parâmetros de integração a um grupo de uma vez |
| Precursor | o m/z do precursor; o canal é associado por ele |
| Fragment | o íon produto extraído; vazio significa que o próprio precursor é extraído |
| RT | o tempo de retenção esperado em minutos; vazio significa que a corrida inteira é pesquisada |
| ± RT | a meia janela: o ápice tem de cair dentro de RT ± isto. O padrão é 0.5 min |
| Tol. e Unit | a meia largura da janela de massa, em Da ou ppm; o padrão do método quando deixado em branco |
| Formula e Adduct | opcionais; com os dois e sem precursor, o precursor é calculado — `C18H30D4O4` com [M−H]⁻ é como um padrão marcado é inserido |
| IS | marcado quando o componente **é** um padrão interno |
| Internal standard | o nome do padrão interno contra o qual este componente é reportado |
| Response | o que a tabela de resultados reporta: `area`, `ratio` ao padrão interno, ou `concentration` |
| Conc. unit | a unidade de concentração mostrada para este componente, quando difere da do método |
| Qualifier of | o quantificador que esta transição confirma, quando ela é um qualificador |
| Ion ratio % e ± ratio % | a razão de áreas qualificador/quantificador esperada, e a tolerância que sobrepõe a do método |
| Min. response | para um padrão interno: a menor área que ele tem de dar em uma injeção antes que uma razão a ele signifique alguma coisa — ver [[internal-standards-and-qualifiers]] |

As colunas de padrão interno e de qualificador são explicadas em
[[internal-standards-and-qualifiers]].

## Construir a tabela

- **Add** e **Remove** editam linhas à mão.
- **Generate from acquisition method** lê o método da primeira amostra aberta
  e faz um componente por canal de íons produto, nomeado a partir do seu
  precursor, com o precursor e a faixa de massas que o canal declara. Um
  método de oitenta transições chega em um clique; nomeá-lo é para o que
  serve [[annotate-from-lipid-maps]].
- **Import CSV…** e **Export CSV…** leem e escrevem a tabela como uma
  planilha, ver abaixo.
- **Export for Skyline…** escreve o método como uma lista de transições de
  moléculas pequenas, ver [[export]].
- **Suggest from data…** propõe tempos de retenção e larguras de janela a
  partir das injeções abertas, ver [[suggest-from-data]].
- **Check method** lê o método contra si mesmo e contra os arquivos abertos,
  ver [[check-method]].
- **Annotate from LIPID MAPS…** propõe nomes de espécie, ver
  [[annotate-from-lipid-maps]].
- **Export schedule…** escreve a aquisição agendada que o método implica, com
  o dwell time que um ciclo alvo deixa a cada transição, ver
  [[acquisition-schedule]].

## Padrões do método

Abaixo da tabela: a **default tolerance** (tolerância padrão) e a sua
unidade, que todo componente sem a sua própria usa; a **concentration unit**
do lote; e a tolerância de **ion ratio** que aprova e a faixa mais larga que
é *marginal* em vez de reprovação (20% e 30% para começar). Os padrões de
integração que todo componente herda — suavização, linha de base, critérios,
o algoritmo — são editados no painel Integration da [[analytics-workspace]]
com **Back to method defaults**, e os [[acceptance-criteria]] da mesma
maneira.

## A disposição do CSV

Apenas `name` e `precursor` são obrigatórios. Os cabeçalhos são reconhecidos
em inglês ou em português, de modo que uma lista escrita por uma versão
anterior continua funcionando.

```
name,precursor,fragment,rt,window,tolerance,unit
12,13-DiHOME,313.2384,183.1391,14.7,0.6,0.02,Da
9,10-DiHOME,313.2384,201.1496,14.2,0.6,20,ppm
```

| Campo | Cabeçalhos aceitos |
|---|---|
| name | name, compound, component, analyte, nome, composto, analito |
| group | group, grupo |
| precursor | precursor, q1, precursor_mz, parent, precursormz |
| fragment | fragment, q3, product, fragment_mz, productmz, fragmento, produto |
| rt | rt, retention_time, rt_min, tr, tempo |
| rt_halfwidth | window, rt_window, rt_halfwidth, half_window, janela, meia_janela, tolerancia_rt |
| tolerance, unit | tolerance, tol, mz_tolerance, tolerancia; unit, tol_unit, unidade |
| formula, adduct | formula, chemical_formula, molecular_formula; adduct, aduto, ion |
| is_internal_standard | is, is_internal_standard, internal_standard?, istd, is_istd, e_padrao_interno — verdadeiro para 1, true, yes, y, sim, is, istd, x |
| internal_standard | internal_standard, is_name, istd_name, padrao_interno |
| response | response, response_type, resposta |
| concentration_unit | concentration_unit, conc_unit, units, unidade_concentracao |
| qualifier_of, ion_ratio, ion_ratio_tolerance | qualifier_of, qualifier, qualificador_de, quantifier; ion_ratio, expected_ion_ratio, razao_ionica; ion_ratio_tolerance, ion_ratio_tol |
| regression, weighting | regression, curve, fit, regressao; weighting, weight, ponderacao, peso |
| lm_id | lm_id, lipidmaps, lipidmaps_id, lmid |
| min_response | min_response, response_floor, min_area, floor, piso_resposta, resposta_minima, area_minima |

Os parâmetros de integração próprios de um componente e os seus critérios de
aceitação não estão no CSV; eles são salvos no projeto.

## Como um componente encontra o seu canal

Para cada amostra, o canal que carrega um componente é escolhido por três
condições: o seu precursor está dentro de 0.7 Da do precursor do componente;
a sua faixa de massas contém o alvo (o fragmento, ou o precursor quando não
há fragmento); e, quando o componente declara um tempo de retenção, o canal
foi adquirido naquele tempo. A última condição é por que o tempo faz parte do
método: um método agendado repete o mesmo precursor em períodos diferentes —
313.24 em um experimento cobrindo 0–13 min e outro cobrindo 13–21.5 — e
associar apenas pelo precursor escolhe um canal que nem sequer estava sendo
adquirido quando o composto elui. Falhando tudo isso, um canal de varredura
completa cuja faixa contenha o alvo é usado; falhando isso, a linha diz
*no matching channel*. Quando o canal associado não cobre a janela pedida, a
linha diz isso em vez de reportar um pico de algum outro tempo.
