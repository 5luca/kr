import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io

# --- KONFIGURACE ---
# Musíš mít v Google Sheets publikované oba listy jako CSV!
URL_BOT_DATA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRKIbg5LXy_GcU8iwXPxbskBL5dauZhrcmCqHJ8k9ijqi2p4rUyr8lHbEK5dZZMiRIEfvFnVyiw44r8/pub?gid=971190468&single=true&output=csv"
URL_TRANSAKCE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRKIbg5LXy_GcU8iwXPxbskBL5dauZhrcmCqHJ8k9ijqi2p4rUyr8lHbEK5dZZMiRIEfvFnVyiw44r8/pub?gid=681462677&single=true&output=csv"

st.set_page_config(page_title="Krypto Dashboard 3.0", layout="wide")

def load_data(url):
    res = requests.get(url)
    df = pd.read_csv(io.StringIO(res.text))
    df.columns = [c.strip() for c in df.columns]
    return df

try:
    df_bot = load_data(URL_BOT_DATA)
    df_trans = load_data(URL_TRANSAKCE)
    
    # Úprava dat transakcí (převod data)
    df_trans['Datum'] = pd.to_datetime(df_trans['Datum'], dayfirst=True)
    df_trans['Mesic'] = df_trans['Datum'].dt.strftime('%Y-%m')

    st.title("💰 Můj Krypto Inteligent")

    # --- SEKCE 1: HLAVNÍ METRIKY ---
    st.header("📍 Aktuální přehled")
    # Zde by byl výpočet zisku přes API (pro zjednodušení teď jen struktura)
    c1, c2, c3 = st.columns(3)
    c1.metric("Celková investice", f"{df_bot['Investovano'].sum():,.0f} Kč")
    c2.metric("Aktuálně visím", f"{df_bot['Visim (Dashboard)'].sum():,.0f} Kč")
    c3.metric("Počet mincí", len(df_bot))

    # --- SEKCE 2: GRAFY (Tvé nové "List 3") ---
    st.divider()
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📊 Rozložení portfolia")
        # Koláčový graf podle toho, kolik máš v čem zainvestováno
        fig_pie = px.pie(df_bot, values='Investovano', names='Symbol', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_right:
        st.subheader("📅 Měsíční aktivita (Cash-Flow)")
        # Seskupíme transakce podle měsíce a typu (Nákup/Prodej/Start)
        # Použijeme tvůj skrytý sloupec F (vypočítaná cena s +/-)
        # Pro dashboard to nasimulujeme z viditelné Ceny a Typu
        df_trans['Suma'] = df_trans.apply(lambda x: x['Cena (Kč)'] if x['Typ'] in ['Nákup', 'Start'] else -x['Cena (Kč)'], axis=1)
        
        monthly = df_trans.groupby(['Mesic', 'Typ'])['Suma'].sum().reset_index()
        fig_bar = px.bar(monthly, x='Mesic', y='Suma', color='Typ', 
                         title="Vklady (+) a Výběry (-)",
                         color_discrete_map={'Nákup': '#EF553B', 'Prodej': '#00CC96', 'Start': '#636EFA'})
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- SEKCE 3: TABULKA ÚSPĚŠNOSTI ---
    st.divider()
    st.subheader("🏆 Stav splácení mincí")
    # Vypočítáme % kolik už se vrátilo
    df_bot['Splaceno %'] = (1 - (df_bot['Visim (Dashboard)'] / df_bot['Investovano'])) * 100
    
    # Hezké zobrazení
    st.dataframe(df_bot[['Symbol', 'Investovano', 'Visim (Dashboard)', 'Splaceno %']].style.format({
        'Splaceno %': '{:.1f}%'
    }).background_gradient(subset=['Splaceno %'], cmap='RdYlGn'), use_container_width=True)

except Exception as e:
    st.error(f"Data se nepodařilo zpracovat: {e}")
