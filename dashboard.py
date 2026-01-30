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
        df.columns = [str(c).strip() for c in df.columns]
        
        data_rows = []
        for index, row in df.iterrows():
            if pd.isna(row.get('Symbol')): continue
            symbol = str(row['Symbol']).upper().strip()
            
            y_sym = f"{symbol}-USD"
            if symbol == 'DOT': y_sym = 'DOT-USD'
            
            # Načtení dat
            mnozstvi = clean_number(row.get('Mnozstvi', 0))
            nakup = clean_number(row.get('Nakup', 0))
            
            data_rows.append({
                'Symbol': symbol,
                'Yahoo_Sym': y_sym,
                'Mnozstvi': mnozstvi,
                'Nakup_Cena': nakup,
                'V_tom_visim': mnozstvi * nakup, # Tady počítáme "zůstatek vkladu"
                'Cil_Prodej': clean_number(row.get('Prodej', 0)),
                'Cil_Nakup': clean_number(row.get('Koupit', 0))
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
        
        df_clean['Zisk_PCT'] = df_clean.apply(
            lambda x: ((x['Cena_Ted'] - x['Nakup_Cena']) / x['Nakup_Cena'] * 100) if x['Nakup_Cena'] > 0 else 0, 
            axis=1
        )
        
        return df_clean, usd_czk
        
    except Exception as e:
        st.error(f"Chyba při načítání dat: {e}")
        return None, 0

st.title("💰 Krypto Přehled")

if st.button('🔄 Aktualizovat teď'):
    st.cache_data.clear()

df, kurz = get_data()

if df is not None and not df.empty:
    total_val = df['Hodnota_Ted'].sum()
    total_invested = df['V_tom_visim'].sum() # Celkem "visím"
    total_profit = total_val - total_invested
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Celková hodnota (Mám)", f"{total_val:,.0f} Kč")
    c2.metric("Zůstatek vkladu (Visím v tom)", f"{total_invested:,.0f} Kč")
    c3.metric("Čistý zisk", f"{total_profit:,.0f} Kč", 
              delta=f"{(total_profit/total_invested*100):.1f} %" if total_invested > 0 else None)

    st.markdown("---")
    st.subheader("📋 Detailní tabulka")
    
    # Výběr sloupců pro tabulku
    display = df.copy()
    display = display[['Symbol', 'Mnozstvi', 'Cena_Ted', 'V_tom_visim', 'Hodnota_Ted', 'Zisk_KC', 'Zisk_PCT', 'Cil_Prodej']]
    
    # Barvičky
    def color_text(val):
        color = '#28a745' if val > 0 else '#dc3545'
        return f'color: {color}; font-weight: bold;'

    st.dataframe(
        display.style.format({
            'Mnozstvi': '{:.4f}',
            'Cena_Ted': '{:,.0f} Kč',
            'V_tom_visim': '{:,.0f} Kč',    # Tady uvidíš "kolik v tom visíš"
            'Hodnota_Ted': '{:,.0f} Kč',    # Tady uvidíš "kolik to má cenu teď"
            'Zisk_KC': '{:+,.0f} Kč',       # Zisk v korunách
            'Zisk_PCT': '{:+.1f} %',        # Zisk v procentech
            'Cil_Prodej': '{:,.0f} Kč'
        }).applymap(color_text, subset=['Zisk_KC', 'Zisk_PCT']),
        use_container_width=True
    )

    c_left, c_right = st.columns(2)
    with c_left:
        st.subheader("Rozložení portfolia (Kde jsou peníze)")
        fig1 = px.pie(df, values='Hodnota_Ted', names='Symbol', hole=0.4)
        st.plotly_chart(fig1, use_container_width=True)
        
    with c_right:
        st.subheader("Zisk v korunách (Úspěšnost)")
        # Graf zisku v korunách je často přehlednější než v procentech
        df['Barva'] = df['Zisk_KC'].apply(lambda x: 'Zisk' if x>=0 else 'Ztráta')
        fig2 = px.bar(df.sort_values('Zisk_KC', ascending=False), 
                      x='Symbol', y='Zisk_KC', color='Barva',
                      title="Kolik mi která mince vydělala (Kč)",
                      color_discrete_map={'Zisk': '#28a745', 'Ztráta': '#dc3545'})
        st.plotly_chart(fig2, use_container_width=True)
        
    st.caption(f"Data: Yahoo Finance. Kurz USD: {kurz:.2f} Kč")
else:
    st.warning("Žádná data. Zkontroluj tabulku.")


