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

@st.cache_data(ttl=300)
def get_data():
    try:
        response = requests.get(SHEET_URL)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        df.columns = [str(c).strip() for c in df.columns]
        
        data_rows = []
        for index, row in df.iterrows():
            if pd.isna(row.get('Symbol')): continue
            symbol = str(row['Symbol']).upper().strip()
            
            y_sym = f"{symbol}-USD"
            if symbol == 'DOT': y_sym = 'DOT-USD'
            
            # Načteme hodnoty
            mnozstvi = clean_number(row.get('Mnozstvi', 0))
            visim = clean_number(row.get('Visim', 0))   # Historická investice
            
            data_rows.append({
                'Symbol': symbol,
                'Yahoo_Sym': y_sym,
                'Mnozstvi': mnozstvi,
                'Visim': visim,
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
        
        # Výpočet historického zisku (Hodnota teď - Kolik v tom visím)
        # Pokud je 'Visim' záporné (BTC), přičte se to k hodnotě jako extra zisk
        df_clean['Zisk_KC'] = df_clean['Hodnota_Ted'] - df_clean['Visim']
        
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
    # Hlavní výpočty
    total_val = df['Hodnota_Ted'].sum()
    total_visim = df['Visim'].sum()
    total_profit = total_val - total_visim
    
    # 1. HLAVNÍ ČÍSLA (Jednoduchý přehled)
    st.markdown(f"### Celková hodnota: **{total_val:,.0f} Kč**")
    
    # Tady jsou ta čísla navíc, co jsi chtěla:
    col1, col2 = st.columns(2)
    col1.metric("V tom visím (Zbytek vkladu)", f"{total_visim:,.0f} Kč")
    col2.metric("Čistý historický zisk", f"{total_profit:,.0f} Kč", 
                delta=f"{(total_profit/total_visim*100):.1f} %" if total_visim > 0 else "∞ %")

    st.markdown("---")

    # 2. GRAFY (Volitelné)
    c_left, c_right = st.columns(2)
    with c_left:
        st.subheader("Kde leží peníze")
        fig1 = px.pie(df, values='Hodnota_Ted', names='Symbol', hole=0.4)
        st.plotly_chart(fig1, use_container_width=True)
    with c_right:
        st.subheader("Největší zisk (Kč)")
        df['Barva'] = df['Zisk_KC'].apply(lambda x: 'Zisk' if x>=0 else 'Ztráta')
        fig2 = px.bar(df.sort_values('Zisk_KC', ascending=False), 
                      x='Symbol', y='Zisk_KC', color='Barva',
                      color_discrete_map={'Zisk': '#28a745', 'Ztráta': '#dc3545'})
        st.plotly_chart(fig2, use_container_width=True)

    # 3. TABULKA
    st.subheader("📋 Přehled mincí")
    display = df[['Symbol', 'Mnozstvi', 'Cena_Ted', 'Visim', 'Hodnota_Ted', 'Zisk_KC', 'Cil_Prodej']].copy()
    display.columns = ['Mince', 'Množství', 'Cena (Kč)', 'Visím (Kč)', 'Hodnota (Kč)', 'Zisk (Kč)', 'Cíl Prodej']
    
    def color_profit(val):
        color = '#28a745' if val > 0 else '#dc3545'
        return f'color: {color}; font-weight: bold;'

    st.dataframe(
        display.style.format({
            'Množství': '{:.4f}',
            'Cena (Kč)': '{:,.0f}',
            'Visím (Kč)': '{:,.0f}',
            'Hodnota (Kč)': '{:,.0f}',
            'Zisk (Kč)': '{:+,.0f}',
            'Cíl Prodej': '{:,.0f}'
        }).applymap(color_profit, subset=['Zisk (Kč)']),
        use_container_width=True
    )

    st.caption(f"Kurz USD: {kurz:.2f} Kč")

else:
    st.warning("Data se nepodařilo načíst. Zkontroluj, jestli máš v tabulce sloupec 'Visim'.")

