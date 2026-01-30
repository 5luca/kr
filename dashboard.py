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

# =========================================
st.set_page_config(page_title="Moje Krypto Portfolio", page_icon="💰", layout="wide")

def clean_number(value):
    if pd.isna(value) or str(value).strip() == '': return 0.0
    text = str(value).replace(' ', '').replace('\xa0', '').replace(',', '.')
    try: return float(text)
    except: return 0.0

@st.cache_data(ttl=300)
def get_data():
    try:
        response = requests.get(SHEET_URL)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        
        # Očistíme názvy sloupců (odstraníme mezery)
        df.columns = [str(c).strip() for c in df.columns]
        
        data_rows = []
        for index, row in df.iterrows():
            if pd.isna(row.get('Symbol')): continue
            symbol = str(row['Symbol']).upper().strip()
            
            y_sym = f"{symbol}-USD"
            if symbol == 'DOT': y_sym = 'DOT-USD'
            
            # 1. Načteme množství
            mnozstvi = clean_number(row.get('Mnozstvi', 0))
            
            # 2. Načteme "V čem visím" přímo z Tabulky (sloupec 'Visim')
            v_tom_visim = clean_number(row.get('Visim', 0))
            
            data_rows.append({
                'Symbol': symbol,
                'Yahoo_Sym': y_sym,
                'Mnozstvi': mnozstvi,
                'Nakup_Strategie': clean_number(row.get('Nakup', 0)), # Pro info
                'V_tom_visim': v_tom_visim, 
                'Cil_Prodej': clean_number(row.get('Prodej', 0))
            })
            
        df_clean = pd.DataFrame(data_rows)
        
        # Ceny z Yahoo
        tickers = df_clean['Yahoo_Sym'].tolist()
        tickers.append("CZK=X")
        
        market_data = yf.download(tickers, period="1d", progress=False)['Close']
        
        if 'CZK=X' in market_data:
            usd_czk = float(market_data['CZK=X'].iloc[-1])
        else:
            usd_czk = 24.5
            
        def get_current_price(row):
            sym = row['Yahoo_Sym']
            if sym in market_data.columns:
                price_usd = float(market_data[sym].iloc[-1])
                return price_usd * usd_czk
            return 0.0

        df_clean['Cena_Ted'] = df_clean.apply(get_current_price, axis=1)
        df_clean['Hodnota_Ted'] = df_clean['Mnozstvi'] * df_clean['Cena_Ted']
        
        # Zisk = Hodnota teď - To v čem visím
        df_clean['Zisk_KC'] = df_clean['Hodnota_Ted'] - df_clean['V_tom_visim']
        
        return df_clean, usd_czk
        
    except Exception as e:
        st.error(f"Chyba při načítání dat: {e}")
        return None, 0

# --- START APLIKACE ---
st.title("💰 Krypto Dashboard")

if st.button('🔄 Aktualizovat'):
    st.cache_data.clear()

df, kurz = get_data()

if df is not None and not df.empty:
    # 1. HLAVNÍ METRIKY
    total_val = df['Hodnota_Ted'].sum()
    total_stuck = df['V_tom_visim'].sum() # Celkem "visím" (suma z Tabulky)
    total_profit = total_val - total_stuck
    
    col_main, col_chart = st.columns([1, 2])
    
    with col_main:
        st.markdown("### 🏦 Celková hodnota portfolia")
        st.markdown(f"<h1 style='color: #4CAF50; font-size: 48px;'>{total_val:,.0f} Kč</h1>", unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### 📊 Historická bilance")
        
        st.metric(
            label="Zůstatek vkladu (Kolik v tom visím)", 
            value=f"{total_stuck:,.0f} Kč",
            help="Částka načtená ze sloupce 'Visim' v Google Tabulce."
        )
        
        st.metric(
            label="Celkový čistý zisk", 
            value=f"{total_profit:,.0f} Kč",
            delta=f"{(total_profit/total_stuck*100):.1f} %" if total_stuck > 0 else "∞ %"
        )

    with col_chart:
        st.markdown("### 🏆 Kde je největší zisk?")
        df['Barva'] = df['Zisk_KC'].apply(lambda x: 'Zisk' if x>=0 else 'Ztráta')
        fig = px.bar(df.sort_values('Zisk_KC', ascending=False), 
                      x='Symbol', y='Zisk_KC', color='Barva',
                      text='Zisk_KC',
                      color_discrete_map={'Zisk': '#28a745', 'Ztráta': '#dc3545'})
        fig.update_traces(texttemplate='%{text:.0s}', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

    # 2. TABULKA
    st.markdown("---")
    st.subheader("📋 Detailní přehled")
    
    display = df.copy()
    display = display[['Symbol', 'Mnozstvi', 'Cena_Ted', 'V_tom_visim', 'Hodnota_Ted', 'Zisk_KC', 'Cil_Prodej']]
    display.columns = ['Mince', 'Držím', 'Cena (Kč)', 'Visím v tom (Kč)', 'Hodnota (Kč)', 'Zisk (Kč)', 'Cíl Prodej']
    
    def color_profit(val):
        color = '#28a745' if val > 0 else '#dc3545'
        return f'color: {color}; font-weight: bold;'

    st.dataframe(
        display.style.format({
            'Držím': '{:.4f}',
            'Cena (Kč)': '{:,.0f}',
            'Visím v tom (Kč)': '{:,.0f}',
            'Hodnota (Kč)': '{:,.0f}',
            'Zisk (Kč)': '{:+,.0f}',
            'Cíl Prodej': '{:,.0f}'
        }).applymap(color_profit, subset=['Zisk (Kč)']),
        use_container_width=True,
        height=500
    )
    
    st.caption(f"Aktualizováno přes Yahoo Finance. Kurz USD: {kurz:.2f} Kč")

else:
    st.warning("Načítám data... (Ujisti se, že jsi přidala sloupec 'Visim')")


