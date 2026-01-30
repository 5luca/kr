import streamlit as st
import pandas as pd
import requests
import io
import plotly.express as px

# ==========================================
# ⚙️ NASTAVENÍ
# ==========================================
# Vlož sem ten stejný odkaz na Google Sheet (musí končit na output=csv)
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRKIbg5LXy_GcU8iwXPxbskBL5dauZhrcmCqHJ8k9ijqi2p4rUyr8lHbEK5dZZMiRIEfvFnVyiw44r8/pub?output=csv"

# ==========================================

st.set_page_config(page_title="Moje Krypto Portfolio", page_icon="💰", layout="centered")

# Funkce pro načtení dat
def clean_number(value):
    if pd.isna(value): return 0.0
    text = str(value).replace(' ', '').replace('\xa0', '').replace(',', '.')
    try: return float(text)
    except: return 0.0

@st.cache_data(ttl=300) # Data se aktualizují každých 5 minut
def get_data():
    try:
        # 1. Načíst Portfolio z Google Sheetu
        response = requests.get(SHEET_URL)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        
        # Vyčistit data
        df['Mnozstvi'] = df['Mnozstvi'].apply(clean_number)
        df['Cena_Nakup'] = df['Cena_Nakup'].apply(clean_number)
        
        # 2. Získat aktuální ceny z CoinGecko
        # Mapování symbolů
        id_map = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'DOT': 'polkadot', 
            'DOGE': 'dogecoin', 'LTC': 'litecoin', 'XTZ': 'tezos', 
            'SOL': 'solana', 'UNI': 'uniswap', 'OMG': 'omg',
            'MKR': 'maker', 'NMR': 'numeraire', 'TRUMP': 'official-trump'
        }
        
        ids = []
        df['Coin_ID'] = df['Symbol'].str.upper().str.strip().map(id_map)
        valid_coins = df.dropna(subset=['Coin_ID'])
        ids_list = valid_coins['Coin_ID'].unique().tolist()
        
        if not ids_list: return None
        
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(ids_list)}&vs_currencies=czk"
        price_response = requests.get(url, timeout=10)
        prices = price_response.json()
        
        # 3. Spojit to dohromady
        def get_current_price(row):
            coin_id = row['Coin_ID']
            if coin_id in prices:
                return prices[coin_id]['czk']
            return 0.0

        df['Cena_Ted'] = df.apply(get_current_price, axis=1)
        
        # Výpočty
        df['Hodnota_Investice'] = df['Mnozstvi'] * df['Cena_Nakup']
        df['Hodnota_Ted'] = df['Mnozstvi'] * df['Cena_Ted']
        
        # Ošetření nulové nákupky (DOGE/BTC)
        df['Zisk_KC'] = df['Hodnota_Ted'] - df['Hodnota_Investice']
        df['Zisk_PCT'] = df.apply(
            lambda x: ((x['Cena_Ted'] - x['Cena_Nakup']) / x['Cena_Nakup'] * 100) if x['Cena_Nakup'] > 0 else 100, 
            axis=1
        )
        
        return df
        
    except Exception as e:
        st.error(f"Chyba: {e}")
        return None

# --- APLIKACE ---
st.title("💰 Moje Krypto Nástěnka")
st.caption("Data čerpám z tvé Google Tabulky")

if st.button('🔄 Aktualizovat data'):
    st.cache_data.clear()

df = get_data()

if df is not None and not df.empty:
    # 1. Hlavní metriky
    total_value = df['Hodnota_Ted'].sum()
    total_invested = df['Hodnota_Investice'].sum()
    total_profit = total_value - total_invested
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Celková hodnota", f"{total_value:,.0f} Kč")
    col2.metric("Celkový zisk/ztráta", f"{total_profit:,.0f} Kč", delta_color="normal" if total_profit > 0 else "inverse")
    
    # Zobrazení jen pro info (Investováno)
    # col3.metric("Původní investice", f"{total_invested:,.0f} Kč")

    st.divider()

    # 2. Grafy
    st.subheader("📊 Rozložení portfolia")
    
    # Koláčový graf (Kde máš nejvíc peněz)
    fig_pie = px.pie(df, values='Hodnota_Ted', names='Symbol', title='V čem máš uložené peníze')
    st.plotly_chart(fig_pie, use_container_width=True)
    
    st.subheader("🚀 Ziskovost mincí (%)")
    # Barva sloupců podle toho, jestli jsou v plusu nebo mínusu
    df['Barva'] = df['Zisk_PCT'].apply(lambda x: 'Zisk' if x > 0 else 'Ztráta')
    
    fig_bar = px.bar(
        df.sort_values('Zisk_PCT', ascending=False), 
        x='Symbol', 
        y='Zisk_PCT',
        color='Barva',
        color_discrete_map={'Zisk': '#2ecc71', 'Ztráta': '#e74c3c'},
        title='Které mince vydělávají nejvíc (%)'
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # 3. Detailní tabulka
    st.subheader("📝 Detailní přehled")
    
    # Formátování tabulky pro hezké zobrazení
    display_df = df[['Symbol', 'Mnozstvi', 'Cena_Nakup', 'Cena_Ted', 'Zisk_PCT', 'Hodnota_Ted']].copy()
    display_df.columns = ['Mince', 'Množství', 'Nákupka (Kč)', 'Cena Teď (Kč)', 'Zisk %', 'Hodnota (Kč)']
    
    st.dataframe(display_df.style.format({
        'Množství': '{:.4f}',
        'Nákupka (Kč)': '{:.2f}',
        'Cena Teď (Kč)': '{:.2f}',
        'Zisk %': '{:+.1f} %',
        'Hodnota (Kč)': '{:,.0f}'
    }))

else:
    st.warning("Zatím se nepodařilo načíst data. Zkontroluj odkaz na Google Sheet.")