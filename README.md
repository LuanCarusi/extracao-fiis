# Screening de Fundos Imobiliários (FIIs)

Este projeto realiza a extração, filtragem e rankeamento de todos os Fundos Imobiliários (FIIs) listados na B3, utilizando o site [Fundamentus](https://www.fundamentus.com.br/) como fonte primária de dados.

A estratégia implementada aqui aplica um modelo de screening semelhante à "Magic Formula", buscando fundos que estão baratos (menor P/VP) e pagando bons rendimentos (maior Dividend Yield), após passarem por filtros rigorosos de liquidez e vacância.

## 📋 Regras de Negócio e Filtros

1. **Liquidez Diária**: Remove fundos com liquidez menor que R$ 500.000,00.
2. **Vacância Média**: Remove fundos com vacância superior a 30%.
3. **P/VP**: Remove fundos com P/VP menor que 0,7 (evita fundos que podem estar com problemas estruturais ou em processo de liquidação).
4. **Dividend Yield**: Remove fundos cujo DY seja menor que a soma da **Taxa do Tesouro IPCA+ mais curto** + **1% de Spread**. (O valor da taxa IPCA+ deve ser fornecido na execução).

## 🏆 Critério de Rankeamento

Os fundos que sobrevivem aos filtros acima são rankeados da seguinte forma:
- **Rank P/VP**: Do menor (mais barato) para o maior.
- **Rank Dividend Yield**: Do maior (pagando mais) para o menor.

Ao final, os dois rankings são somados para cada ativo. A tabela é então ordenada por essa soma (do menor para o maior), revelando no topo da lista os FIIs que oferecem o melhor balanço entre preço descontado e alto retorno de dividendos.

## 🚀 Instalação e Configuração

Certifique-se de ter o Python 3 instalado.

1. Clone ou baixe este repositório.
2. Instale as dependências executando:

```bash
pip install -r requirements.txt
```

As dependências principais são:
- `pandas` (Manipulação e estruturação de dados)
- `requests` (Extração HTML web)
- `openpyxl` (Exportação do ranking para formato Excel `.xlsx`)

## 💻 Como Executar

O script foi desenvolvido com escalabilidade em mente e utiliza argumentos por linha de comando (`argparse`). Isso permite que você atualize os parâmetros (como a taxa IPCA+ atual) de maneira fácil, rápida e sem necessidade de editar o código fonte.

### Execução Padrão
Você **precisa** informar a taxa do Tesouro IPCA+ mais curto no momento da execução. Por exemplo, se hoje o Tesouro IPCA+ 2029 estiver pagando **IPCA + 7,58%**:

```bash
python screening_fiis.py --ipca-rate 7.58
```
*Isto irá gerar um arquivo `ranking_fiis.xlsx` no mesmo diretório.*

### Outros Parâmetros Customizáveis
Se quiser alterar o Spread, a Liquidez, a Vacância ou o arquivo de saída, você pode passar outros argumentos:

```bash
python screening_fiis.py --ipca-rate 7.58 --spread 1.5 --liquidez 1000000 --vacancia 25.0 --pvp 0.8 --output "meu_ranking.xlsx"
```

Para ver a lista completa de opções de uso, digite:
```bash
python screening_fiis.py --help
```

## 🛠 Colunas Mantidas no Relatório Final
- Papel (Ticker)
- Segmento
- Cotação
- FFO Yield
- Dividend Yield
- P/VP
- Valor de Mercado
- Liquidez
- Qtd de imóveis
- Vacância Média
- Rank_P_VP *(Cálculo interno)*
- Rank_DY *(Cálculo interno)*
- Rank_Final_Soma *(Cálculo interno)*
- Posicao_Geral *(Posição no Ranking)*

## 💡 Observações sobre Extração do Tesouro Direto
A taxa do Tesouro Direto é fornecida como argumento (`--ipca-rate`) em vez de ser feita extração automática (web scraping) pelo script. Isso ocorre pois os sites oficiais do governo e plataformas financeiras possuem proteção contra robôs que geram instabilidade constante (erros HTTP 403 e 410) ou mudam suas rotas frequentemente. Passar o valor como argumento torna o script muito mais robusto, determinístico e amigável para pipelines automatizados.
