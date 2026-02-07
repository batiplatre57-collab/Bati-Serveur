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

# --- CONNEXION BDD (CORRIGÉE POUR RENDER) ---
def get_db_connection():
    try:
        # On récupère la variable d'environnement (méthode Render)
        url = os.environ.get("DATABASE_URL")
        
        # NETTOYAGE (Sécurité si l'URL contient encore 'psql' ou des guillemets)
        if url:
            url = url.replace("psql ", "").replace('"', "").replace("'", "").strip()
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
        
        return psycopg2.connect(url)
    except Exception as e:
        # On affiche l'erreur technique discrètement pour le debug
        st.error(f"⚠️ Erreur technique BDD : {e}")
        return None

# --- BARRE LATÉRALE (MENU) ---
with st.sidebar:
    st.title("🏗️ Bati-Plâtre 57")
    st.write("---")
    menu = st.radio("Navigation", ["📊 Tableau de Bord", "📞 Journal Chantiers", "📝 Devis & Factures", "⚙️ Clients"])
    st.write("---")
    
    # Indicateur d'état
    conn = get_db_connection()
    if conn:
        st.success("🟢 Base de Données Connectée")
        conn.close()
    else:
        st.error("🔴 Déconnecté")

# --- PAGE 1 : TABLEAU DE BORD (Accueil) ---
if menu == "📊 Tableau de Bord":
    st.markdown('<p class="main-header">Vue d\'ensemble</p>', unsafe_allow_html=True)
    
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            
            # Vérification si les tables existent (pour éviter le crash au premier lancement)
            cur.execute("CREATE TABLE IF NOT EXISTS chantiers (id SERIAL PRIMARY KEY, membre_id INTEGER, resume_texte TEXT, audio_url TEXT, date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            cur.execute("CREATE TABLE IF NOT EXISTS documents (id SERIAL PRIMARY KEY, membre_id INTEGER, type_doc TEXT, contenu_json TEXT, statut TEXT, date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            conn.commit()

            # Récupérer les stats
            cur.execute("SELECT COUNT(*) FROM chantiers")
            nb_chantiers = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM documents WHERE type_doc='DEVIS'")
            nb_devis = cur.fetchone()[0]
            
            conn.close()

            # Affichage des chiffres clés
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Rapports Chantiers", nb_chantiers)
            with col2:
                st.metric("Devis en Attente", nb_devis)
            with col3:
                st.metric("Appels Reçus", "En direct")

        except Exception as e:
            st.warning(f"Initialisation des tables... ({e})")
    
    st.write("### 📅 Activité Récente")
    st.info("Bienvenue Chef. L'application est prête à recevoir les données.")

# --- PAGE 2 : JOURNAL DE CHANTIER ---
elif menu == "📞 Journal Chantiers":
    st.markdown('<p class="main-header">👷 Suivi de Chantier</p>', unsafe_allow_html=True)
    
    conn = get_db_connection()
    if conn:
        try:
            df = pd.read_sql("SELECT * FROM chantiers ORDER BY date_creation DESC", conn)
            conn.close()

            if not df.empty:
                for index, row in df.iterrows():
                    with st.container():
                        st.write(f"**📅 Date :** {row['date_creation']}")
                        st.success(f"📝 **Résumé IA :** {row['resume_texte']}")
                        if row['audio_url']:
                            st.audio(row['audio_url'])
                        st.write("---")
            else:
                st.info("Aucun rapport de chantier pour le moment.")
        except:
            st.info("Table vide ou inexistante.")

# --- PAGE 3 : DEVIS & FACTURES ---
elif menu == "📝 Devis & Factures":
    st.markdown('<p class="main-header">💰 Gestion Commerciale</p>', unsafe_allow_html=True)
    
    conn = get_db_connection()
    if conn:
        try:
            df = pd.read_sql("SELECT * FROM documents WHERE type_doc='DEVIS' ORDER BY date_creation DESC", conn)
            conn.close()

            if not df.empty:
                st.dataframe(df[['date_creation', 'statut', 'contenu_json']])
                st.write("### 🔍 Détail du dernier devis")
                dernier_devis = df.iloc[0]
                st.json(dernier_devis['contenu_json'])
            else:
                st.info("Aucun devis généré pour le moment.")
        except:
             st.info("Table vide.")

# --- PAGE 4 : CLIENTS ---
elif menu == "⚙️ Clients":
    st.markdown('<p class="main-header">👥 Répertoire Clients</p>', unsafe_allow_html=True)
    conn = get_db_connection()
    if conn:
        try:
            df = pd.read_sql("SELECT nom_societe, telephone FROM membres", conn)
            st.table(df)
            conn.close()
        except:
            st.warning("Aucun client trouvé ou table manquante.")
