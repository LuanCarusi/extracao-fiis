import pandas as pd
import requests
import argparse
import io
import os
from datetime import datetime

def fetch_ipca_12m_bcb():
    """Busca o IPCA acumulado dos últimos 12 meses via API do Banco Central (BCB série 13522)."""
    try:
        url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.13522/dados/ultimos/1?formato=json"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data:
            return float(data[-1]['valor'].replace(',', '.'))
        raise ValueError("Sem dados retornados pela API do BCB.")
    except Exception as e:
        raise RuntimeError(f"Falha ao buscar IPCA do BCB: {e}")

def parse_percentage(col):
    """Converts a percentage string like '12,34%' to a float 12.34.
    Compatible with both legacy object dtype and new pandas ArrowDtype strings."""
    try:
        cleaned = col.str.replace('%', '', regex=False).str.replace(',', '.', regex=False)
        return pd.to_numeric(cleaned, errors='coerce')
    except AttributeError:
        # Already numeric
        return pd.to_numeric(col, errors='coerce')

def get_fundamentus_data():
    """Fetches FII data from Fundamentus"""
    print("Extraindo dados do Fundamentus...")
    url = "https://www.fundamentus.com.br/fii_resultado.php"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    # Using ISO-8859-1 decoding to handle special characters correctly
    html_content = response.content.decode('iso-8859-1')
    
    # Read HTML table using pandas
    tables = pd.read_html(io.StringIO(html_content), decimal=',', thousands='.')
    df = tables[0]
    
    # Rename columns to standard pythonic names (removing special characters)
    df.columns = [
        'Papel', 'Segmento', 'Cotacao', 'FFO_Yield', 'Dividend_Yield', 'P_VP',
        'Valor_de_Mercado', 'Liquidez', 'Qtd_de_imoveis', 'Preco_do_m2',
        'Aluguel_por_m2', 'Cap_Rate', 'Vacancia_Media'
    ]
    
    # Convert percentage columns to float
    cols_to_convert = ['FFO_Yield', 'Dividend_Yield', 'Cap_Rate', 'Vacancia_Media']
    for col in cols_to_convert:
        df[col] = parse_percentage(df[col])
        
    return df

def apply_filters(df, min_liquidity, max_vacancy, min_pvp, min_dy):
    """Applies the screening filters to the DataFrame"""
    print("Aplicando filtros...")

    # Garante que as colunas numéricas estejam no tipo correto antes de filtrar
    for col in ['Liquidez', 'Vacancia_Media', 'P_VP', 'Dividend_Yield']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    initial_len = len(df)
    
    # Filter: Liquidez diária >= 500.000
    df = df[df['Liquidez'] >= min_liquidity]
    print(f" - Removidos ativos com Liquidez < {min_liquidity:,.0f} (Restam {len(df)})")
    
    # Filter: Vacância média <= max_vacancy (NaN = FII de papel/sem vacância → mantém)
    df = df[df['Vacancia_Media'].isna() | (df['Vacancia_Media'] <= max_vacancy)]
    print(f" - Removidos ativos com Vacância > {max_vacancy}% (Restam {len(df)})")
    
    # Filter: P/VP >= 0.7
    df = df[df['P_VP'] >= min_pvp]
    print(f" - Removidos ativos com P/VP < {min_pvp} (Restam {len(df)})")
    
    # Filter: Dividend Yield >= (IPCA+ rate + 1% Spread)
    df = df[df['Dividend_Yield'] >= min_dy]
    print(f" - Removidos ativos com Dividend Yield < {min_dy}% (Restam {len(df)})")
    
    print(f"Filtro concluído: {initial_len} -> {len(df)} ativos restantes.")
    
    return df.copy()

def apply_ranking(df):
    """Ranks the FIIs based on P/VP (lowest to highest) and Dividend Yield (highest to lowest)"""
    print("Calculando ranking dos ativos...")
    
    # Rank P/VP do menor para o maior (menor P/VP ganha 1º lugar)
    # Usamos method='min' para empates terem a mesma posição
    df['Rank_P_VP'] = df['P_VP'].rank(ascending=True, method='min')
    
    # Rank Dividend Yield do maior para o menor (maior DY ganha 1º lugar)
    df['Rank_DY'] = df['Dividend_Yield'].rank(ascending=False, method='min')
    
    # Soma dos rankings
    df['Rank_Final_Soma'] = df['Rank_P_VP'] + df['Rank_DY']
    
    # Ordena pela soma dos rankings (menores somas ficam em primeiro lugar)
    df = df.sort_values('Rank_Final_Soma', ascending=True).reset_index(drop=True)
    
    # Ranking visual final (1, 2, 3...)
    df.insert(0, 'Posicao_Geral', range(1, len(df) + 1))
    
    return df

def main():
    parser = argparse.ArgumentParser(description='Screening de Fundos Imobiliários (FIIs)')
    parser.add_argument('--ipca-plus-rate', type=float, required=True,
                        help='Spread do Tesouro IPCA+ de vencimento mais curto. Ex: 7.58 para IPCA+7.58')
    parser.add_argument('--ipca-12m', type=float, default=None,
                        help='IPCA acumulado nos ultimos 12 meses. Se omitido, busca automaticamente do BCB.')
    parser.add_argument('--liquidez', type=float, default=500000.0,
                        help='Liquidez diaria minima. Padrao: 500000')
    parser.add_argument('--vacancia', type=float, default=30.0,
                        help='Vacancia media maxima em percentual. Padrao: 30.0')
    parser.add_argument('--pvp', type=float, default=0.7,
                        help='P/VP minimo. Padrao: 0.7')
    parser.add_argument('--output', type=str, default='ranking_fiis.xlsx',
                        help='Nome do arquivo de saida Excel. Padrao: ranking_fiis.xlsx')
    
    args = parser.parse_args()

    # Resolve IPCA 12m: usa arg ou busca automaticamente no BCB
    if args.ipca_12m is not None:
        ipca_12m = args.ipca_12m
        print(f"IPCA 12m fornecido via argumento: {ipca_12m:.2f}%")
    else:
        try:
            ipca_12m = fetch_ipca_12m_bcb()
            print(f"IPCA 12m obtido automaticamente do BCB: {ipca_12m:.2f}%")
        except RuntimeError as e:
            print(f"ERRO: {e}")
            print("Informe o IPCA 12m manualmente com --ipca-12m.")
            return

    # Calcula DY mínimo: retorno real líquido do Tesouro IPCA+ após IR (15%) e inflação
    # Fórmula (tudo em fator):
    #   fator_bruto  = (1 + spread/100) * (1 + IPCA/100)       → rentabilidade nominal bruta
    #   fator_liq    = 1 + (fator_bruto - 1) * 0.85            → após IR de 15% sobre o ganho
    #   fator_real   = fator_liq / (1 + IPCA/100)              → deflaciona pela inflação (em fator)
    #   DY_mín       = (fator_real - 1) * 100                  → converte para %
    fator_bruto = (1 + args.ipca_plus_rate / 100) * (1 + ipca_12m / 100)
    fator_liquido = 1 + (fator_bruto - 1) * 0.85
    fator_real = fator_liquido / (1 + ipca_12m / 100)
    min_dy = (fator_real - 1) * 100

    print(f"--- Configuração do Screening ---")
    print(f"Tesouro IPCA+ spread: {args.ipca_plus_rate}% | IPCA 12m: {ipca_12m:.2f}%")
    print(f"Fator bruto: {fator_bruto:.6f} -> fator liquido (-IR 15%): {fator_liquido:.6f} -> fator real: {fator_real:.6f}")
    print(f"Corte de Dividend Yield Mínimo (real líquido): {min_dy:.2f}%")
    print(f"Liquidez Mínima: R$ {args.liquidez:,.2f}")
    print(f"Vacância Máxima: {args.vacancia}%")
    print(f"P/VP Mínimo: {args.pvp}")
    print(f"---------------------------------")
    
    # 1. Extração
    try:
        df_raw = get_fundamentus_data()
    except Exception as e:
        print(f"Erro ao extrair dados do Fundamentus: {e}")
        return
        
    # Colunas desejadas pelo usuário
    colunas_mantidas = ['Papel', 'Segmento', 'Cotacao', 'FFO_Yield', 'Dividend_Yield', 
                        'P_VP', 'Valor_de_Mercado', 'Liquidez', 'Qtd_de_imoveis', 'Vacancia_Media']
    df = df_raw[colunas_mantidas].copy()

    # Aplicar correção manual de segmentos APÓS seleção de colunas
    arquivo_correcao = 'segmentos_corrigidos.csv'
    if os.path.exists(arquivo_correcao):
        try:
            df_correcao = pd.read_csv(arquivo_correcao, sep=';', comment='#', usecols=['Ticker', 'Segmento'])
            if not df_correcao.empty:
                # Normalizar: remover espaços e padronizar caixa
                df_correcao['Ticker'] = df_correcao['Ticker'].astype(str).str.strip().str.upper()
                df_correcao['Segmento'] = df_correcao['Segmento'].astype(str).str.strip()
                # Remover linhas inválidas após limpeza
                df_correcao = df_correcao[df_correcao['Ticker'].str.match(r'^[A-Z]{4}\d{2}$')]

                # Criar dicionário de mapeamento {Ticker: Segmento}
                mapa_segmentos = dict(zip(df_correcao['Ticker'], df_correcao['Segmento']))

                # Normalizar a coluna Papel para garantir matching correto
                papel_normalizado = df['Papel'].astype(str).str.strip().str.upper()
                segmento_corrigido = papel_normalizado.map(mapa_segmentos)

                # Aplicar apenas onde há correção definida
                df['Segmento'] = segmento_corrigido.combine_first(df['Segmento'])
                print(f"Correção de segmentos aplicada: '{arquivo_correcao}' ({len(mapa_segmentos)} regras).")
        except Exception as e:
            print(f"Aviso: Não foi possível aplicar correções de segmento: {e}")
    
    # 2. Filtragem
    df_filtered = apply_filters(df, args.liquidez, args.vacancia, args.pvp, min_dy)
    
    # 3. Ranking
    df_ranked = apply_ranking(df_filtered)
    
    # 4. Salvar resultados
    output_path = args.output
    try:
        # Tenta salvar em Excel primeiro
        if output_path.endswith('.xlsx'):
            df_ranked.to_excel(output_path, index=False)
        else:
            df_ranked.to_csv(output_path, index=False, sep=';', decimal=',')
        print(f"\nSucesso! O ranking final foi salvo em: {os.path.abspath(output_path)}")
    except ImportError:
        # Se openpyxl não estiver instalado, salva como CSV
        fallback_path = output_path.replace('.xlsx', '.csv')
        df_ranked.to_csv(fallback_path, index=False, sep=';', decimal=',')
        print(f"\nSucesso! O ranking final foi salvo em CSV (openpyxl ausente): {os.path.abspath(fallback_path)}")
        
if __name__ == "__main__":
    main()
