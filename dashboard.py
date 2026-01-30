import streamlit as st
import pandas as pd
import requests
import io
import yfinance as yf
import plotly.express as px

# ==========================================
# ⚙️ NASTAVENÍ
# ==========================================
# Vlož sem ten stejný odkaz na Google Sheet (musí končit na output=csv)
SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRKIbg5LXy_GcU8iwXPxbskBL5dauZhrcmCqHJ8k9ijqi2p4rUyr8lHbEK5dZZMiRIEfvFnVyiw44r8/pub?output=csv"

# ==========================================

st.set_page_config(page_title="Moje Krypto Portfolio", page_icon="💰", layout="wide")

def clean_number(value):
    if pd.isna(value) or str(value).strip() == '': return 0.0
    text = str(value).replace(' ', '').replace('\xa0', '').replace(',', '.')
    try: return float(text)
    except: return 0.0

@st.cache_data(ttl=300) # Data se drží v paměti 5 minut
def get_data():
    try:
        # 1. Načíst Portfolio
        response = requests.get(SHEET_URL)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        
        # Očistit názvy sloupců
        df.columns = [str(c).strip() for c in df.columns]
        
        # Načítáme nové sloupce
        data_rows = []
        for index, row in df.iterrows():
            if pd.isna(row.get('Symbol')): continue
            symbol = str(row['Symbol']).upper().strip()
            
            # Yahoo Symbol
            y_sym = f"{symbol}-USD"
            if symbol == 'DOT': y_sym = 'DOT-USD'
            
            data_rows.append({
                'Symbol': symbol,
                'Yahoo_Sym': y_sym,
                'Mnozstvi': clean_number(row.get('Mnozstvi', 0)),
                'Nakup_Cena': clean_number(row.get('Nakup', 0)),
                'Cil_Prodej': clean_number(row.get('Prodej', 0)),
                'Cil_Nakup': clean_number(row.get('Koupit', 0))
            })
            
        df_clean = pd.DataFrame(data_rows)
        
        # 2. Stáhnout ceny (Yahoo Finance)
        tickers = df_clean['Yahoo_Sym'].tolist()
        tickers.append("CZK=X") # Kurz
        
        market_data = yf.download(tickers, period="1d", progress=False)['Close']
        
        # Kurz USD/CZK
        if 'CZK=X' in market_data:
            usd_czk = float(market_data['CZK=X'].iloc[-1])
        else:
            usd_czk = 24.5 # Fallback
            
        # Přiřadit ceny
        def get_current_price(row):
            sym = row['Yahoo_Sym']
            if sym in market_data.columns:
                price_usd = float(market_data[sym].iloc[-1])
                return price_usd * usd_czk
            return 0.0

        df_clean['Cena_Ted'] = df_clean.apply(get_current_price, axis=1)
        
        # Výpočty
        df_clean['Hodnota_Investice'] = df_clean['Mnozstvi'] * df_clean['Nakup_Cena']
        df_clean['Hodnota_Ted'] = df_clean['Mnozstvi'] * df_clean['Cena_Ted']
        df_clean['Zisk_KC'] = df_clean['Hodnota_Ted'] - df_clean['Hodnota_Investice']
        
        df_clean['Zisk_PCT'] = df_clean.apply(
            lambda x: ((x['Cena_Ted'] - x['Nakup_Cena']) / x['Nakup_Cena'] * 100) if x['Nakup_Cena'] > 0 else 0, 
            axis=1
        )
        
        return df_clean, usd_czk
        
    except Exception as e:
        st.error(f"Chyba při načítání dat: {e}")
        return None, 0

# --- VIZUÁL APLIKACE ---
st.title("💰 Krypto Přehled")

if st.button('🔄 Aktualizovat teď'):
    st.cache_data.clear()

df, kurz = get_data()

if df is not None and not df.empty:
    # 1. Horní statistiky
    total_val = df['Hodnota_Ted'].sum()
    total_inv = df['Hodnota_Investice'].sum()
    total_profit = total_val - total_inv
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Celková hodnota", f"{total_val:,.0f} Kč")
    c2.metric("Původní investice", f"{total_inv:,.0f} Kč")
    c3.metric("Zisk / Ztráta", f"{total_profit:,.0f} Kč", 
              delta=f"{(total_profit/total_inv*100):.1f} %" if total_inv > 0 else None)

    st.markdown("---")

    # 2. Hlavní tabulka s barvami
    st.subheader("📋 Detail mincí")
    
    # Úprava pro hezké zobrazení
    display = df.copy()
    display = display[['Symbol', 'Mnozstvi', 'Cena_Ted', 'Nakup_Cena', 'Zisk_PCT', 'Cil_Prodej', 'Cil_Nakup']]
    
    # Zvýraznění (Pandas Styler)
    def color_profit(val):
        color = '#d4edda' if val > 0 else '#f8d7da' # Zelená / Červená
        return f'background-color: {color}'

    st.dataframe(
        display.style.format({
            'Mnozstvi': '{:.4f}',
            'Cena_Ted': '{:,.0f} Kč',
            'Nakup_Cena': '{:,.0f} Kč',
            'Zisk_PCT': '{:+.1f} %',
            'Cil_Prodej': '{:,.0f} Kč',
            'Cil_Nakup': '{:,.0f} Kč'
        }).applymap(color_profit, subset=['Zisk_PCT']),
        use_container_width=True
    )

    # 3. Grafy
    c_left, c_right = st.columns(2)
    
    with c_left:
        st.subheader("Kde máš nejvíc peněz?")
        fig1 = px.pie(df, values='Hodnota_Ted', names='Symbol', hole=0.4)
        st.plotly_chart(fig1, use_container_width=True)
        
    with c_right:
        st.subheader("Kdo nejvíc vydělává (%)")
        df['Barva'] = df['Zisk_PCT'].apply(lambda x: 'Zisk' if x>=0 else 'Ztráta')
        fig2 = px.bar(df.sort_values('Zisk_PCT', ascending=False), 
                      x='Symbol', y='Zisk_PCT', color='Barva',
                      color_discrete_map={'Zisk': '#28a745', 'Ztráta': '#dc3545'})
        st.plotly_chart(fig2, use_container_width=True)
        
    st.caption(f"Data stažena z Yahoo Finance. Kurz USD: {kurz:.2f} Kč")

else:
    st.warning("Nepodařilo se načíst data. Zkontroluj tabulku.")
