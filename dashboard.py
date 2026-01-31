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

# --- POMOCNÉ FUNKCE ---
def load_data(url):
    try:
        res = requests.get(url)
        res.raise_for_status()
        df = pd.read_csv(io.StringIO(res.text))
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Chyba při stahování dat: {e}")
        return None

def find_column(df, keywords):
    """Najde sloupec, který obsahuje některé z klíčových slov."""
    for col in df.columns:
        for key in keywords:
            if key.lower() in col.lower():
                return col
    return None

# --- HLAVNÍ APLIKACE ---
st.title("💰 Můj Krypto Inteligent")

df_bot = load_data(URL_BOT_DATA)
df_trans = load_data(URL_TRANSAKCE)

if df_bot is not None and df_trans is not None:
    # --- PŘÍPRAVA DAT TRANSAKCÍ ---
    # Najdeme sloupce dynamicky, abychom předešli chybám v názvech
    date_col = find_column(df_trans, ['datum'])
    price_col = find_column(df_trans, ['cena'])
    type_col = find_column(df_trans, ['typ'])
    symbol_col = find_column(df_trans, ['symbol'])

    if not all([date_col, price_col, type_col]):
        st.warning(f"V listu Transakce chybí sloupce. Nalezeno: {list(df_trans.columns)}")
    else:
        # Čištění dat a převod na čísla
        df_trans[date_col] = pd.to_datetime(df_trans[date_col], dayfirst=True, errors='coerce')
        df_trans = df_trans.dropna(subset=[date_col])
        df_trans['Mesic'] = df_trans[date_col].dt.strftime('%Y-%m')

        def to_num(x):
            try: return float(str(x).replace(' ', '').replace('\xa0', '').replace(',', '.'))
            except: return 0.0

        df_trans['Cena_Num'] = df_trans[price_col].apply(to_num)
        # Nákup/Start je plus (peníze jdou do krypta), Prodej je mínus (peníze jdou ke mně)
        df_trans['Suma'] = df_trans.apply(lambda x: x['Cena_Num'] if str(x[type_col]).strip() in ['Nákup', 'Start'] else -x['Cena_Num'], axis=1)

        # --- SEKCE 1: HLAVNÍ METRIKY ---
        st.header("📍 Aktuální přehled")
        c1, c2, c3 = st.columns(3)
        
        # Součty z Bot_Data
        total_invested = df_bot['Investovano'].sum() if 'Investovano' in df_bot.columns else 0
        total_visim = df_bot['Visim (Dashboard)'].sum() if 'Visim (Dashboard)' in df_bot.columns else 0
        
        c1.metric("Celková investice (Hrubá)", f"{total_invested:,.0f} Kč")
        c2.metric("Aktuálně 'visím'", f"{total_visim:,.0f} Kč", help="Kolik peněz zbývá vybrat, abych byla na nule.")
        c3.metric("Počet mincí", len(df_bot))

        # --- SEKCE 2: GRAFY (Tvé nové "List 3") ---
        st.divider()
        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("📊 Rozložení investic")
            # Koláčový graf podle hrubé investice
            fig_pie = px.pie(df_bot, values='Investovano', names='Symbol', hole=0.4, 
                             color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_right:
            st.subheader("📅 Měsíční Cash-Flow")
            # Seskupení transakcí podle měsíce pro bar graf
            monthly = df_trans.groupby(['Mesic', type_col])['Cena_Num'].sum().reset_index()
            fig_bar = px.bar(monthly, x='Mesic', y='Cena_Num', color=type_col, 
                             barmode='group',
                             title="Měsíční aktivita (Kč)",
                             labels={'Cena_Num': 'Částka (Kč)', 'Mesic': 'Měsíc'},
                             color_discrete_map={'Nákup': '#EF553B', 'Prodej': '#00CC96', 'Start': '#636EFA'})
            st.plotly_chart(fig_bar, use_container_width=True)

        # --- SEKCE 3: TABULKA ÚSPĚŠNOSTI ---
        st.divider()
        st.subheader("🏆 Stav splácení a cíle")
        
        # Funkce pro výpočet procenta splacení
        def calc_repaid(row):
            try:
                inv = to_num(row['Investovano'])
                vis = to_num(row['Visim (Dashboard)'])
                if inv <= 0: return 100.0
                return (1 - (vis / inv)) * 100
            except:
                return 100.0

        df_bot['Splaceno %'] = df_bot.apply(calc_repaid, axis=1)
        
        # Převedeme sloupce na čísla, aby formátování nepadalo (pokud je tam "Máš Zisk", zůstane jako text)
        cols_to_format = ['Investovano', 'Visim (Dashboard)', 'Prodej (CÍL)', 'Koupit (SLEVA)']
        for col in cols_to_format:
            if col in df_bot.columns:
                df_bot[col] = pd.to_numeric(df_bot[col], errors='coerce')

        # Výběr sloupců pro zobrazení
        cols_to_show = ['Symbol', 'Investovano', 'Splaceno %', 'Prodej (CÍL)']
        available_cols = [c for c in cols_to_show if c in df_bot.columns]
        
        # Formátování tabulky - ošetřeno proti textu
        st.dataframe(
            df_bot[available_cols].style.format({
                'Investovano': '{:,.0f} Kč',
                'Splaceno %': '{:.1f} %',
                'Prodej (CÍL)': '{:,.2f} Kč', # Pokud je zde NaN (kvůli textu), vypíše prázdno
            }, na_rep="-").background_gradient(subset=['Splaceno %'], cmap='RdYlGn'),
            use_container_width=True
        )

else:
    st.info("💡 Čekám na data z Google Sheets. Zkontroluj, zda jsou odkazy správné a listy jsou publikovány jako CSV.")

