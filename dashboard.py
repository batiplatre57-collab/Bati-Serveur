import streamlit as st
import psycopg2
import pandas as pd
import os
import json

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Bati-Plâtre | Gestion",
    page_icon="🏗️",
    layout="wide"
)

# --- STYLE (CSS) ---
st.markdown("""
<style>
    .main-header {font-size: 2.5rem; color: #1E3A8A; font-weight: bold;}
    .sub-header {font-size: 1.5rem; color: #F59E0B;}
    .card {background-color: #f0f2f6; padding: 20px; border-radius: 10px; margin-bottom: 20px;}
</style>
""", unsafe_allow_html=True)

# --- CONNEXION BDD ---
# On utilise la même base de données que le téléphone
def get_db_connection():
    try:
        url = st.secrets["DATABASE_URL"]
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url)
    except:
        st.error("⚠️ Erreur de connexion à la Base de Données.")
        return None

# --- BARRE LATÉRALE (MENU) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2942/2942544.png", width=100)
    st.title("Bati-Plâtre 57")
    st.write("---")
    menu = st.radio("Navigation", ["📊 Tableau de Bord", "📞 Journal Chantiers", "📝 Devis & Factures", "⚙️ Clients"])
    st.write("---")
    st.info("🟢 IA Connectée")

# --- PAGE 1 : TABLEAU DE BORD (Accueil) ---
if menu == "📊 Tableau de Bord":
    st.markdown('<p class="main-header">Vue d\'ensemble</p>', unsafe_allow_html=True)
    
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        
        # Récupérer les stats
        cur.execute("SELECT COUNT(*) FROM chantiers")
        nb_chantiers = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM documents WHERE type_doc='DEVIS'")
        nb_devis = cur.fetchone()[0]
        
        conn.close()

        # Affichage des chiffres clés
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Rapports Chantiers", nb_chantiers, "+2 ajd")
        with col2:
            st.metric("Devis en Attente", nb_devis, "Urgent")
        with col3:
            st.metric("Appels Reçus", "12", "-1")

    st.write("### 📅 Activité Récente")
    st.info("Bienvenue Chef. L'IA a détecté 2 nouvelles demandes de devis ce matin.")

# --- PAGE 2 : JOURNAL DE CHANTIER ---
elif menu == "📞 Journal Chantiers":
    st.markdown('<p class="main-header">👷 Suivi de Chantier</p>', unsafe_allow_html=True)
    
    conn = get_db_connection()
    if conn:
        # On récupère les rapports
        df = pd.read_sql("SELECT * FROM chantiers ORDER BY date_creation DESC", conn)
        conn.close()

        for index, row in df.iterrows():
            with st.container():
                st.write(f"**📅 Date :** {row['date_creation']}")
                st.success(f"📝 **Résumé IA :** {row['resume_texte']}")
                if row['audio_url']:
                    st.audio(row['audio_url'])
                st.write("---")
    else:
        st.write("Aucune donnée.")

# --- PAGE 3 : DEVIS & FACTURES ---
elif menu == "📝 Devis & Factures":
    st.markdown('<p class="main-header">💰 Gestion Commerciale</p>', unsafe_allow_html=True)
    
    conn = get_db_connection()
    if conn:
        df = pd.read_sql("SELECT * FROM documents WHERE type_doc='DEVIS' ORDER BY date_creation DESC", conn)
        conn.close()

        st.dataframe(df[['date_creation', 'statut', 'contenu_json']])
        
        st.write("### 🔍 Détail du dernier devis")
        if not df.empty:
            dernier_devis = df.iloc[0]
            st.json(dernier_devis['contenu_json'])
            st.button("🖨️ Générer le PDF (Prochainement)")

# --- PAGE 4 : CLIENTS ---
elif menu == "⚙️ Clients":
    st.markdown('<p class="main-header">👥 Répertoire Clients</p>', unsafe_allow_html=True)
    conn = get_db_connection()
    if conn:
        df = pd.read_sql("SELECT nom_societe, telephone, email FROM membres", conn)
        st.table(df)
        conn.close()
