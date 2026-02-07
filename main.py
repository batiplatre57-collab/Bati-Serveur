import os
import json
import requests
import psycopg2
import google.generativeai as genai
from flask import Flask, request, Response
from signalwire.voice_response import VoiceResponse

app = Flask(__name__)

# --- CONFIGURATION ---
# Récupération des clés secrètes
try:
    DB_URL = os.environ['DATABASE_URL']
    GOOGLE_API_KEY = os.environ['GOOGLE_API_KEY']
except KeyError:
    print("ERREUR : Il manque des clés dans les Secrets Replit !")

# Configuration de Google Gemini
genai.configure(api_key=GOOGLE_API_KEY)

# --- LE CERVEAU (Prompt Système) ---
# On explique à Gemini comment analyser l'audio
SYSTEM_PROMPT = """
Tu es BATI-IA, l'assistant expert pour une entreprise de bâtiment.
Tu vas recevoir un FICHIER AUDIO d'un appel téléphonique.

TA MISSION :
1. Écoute l'audio.
2. Identifie l'intention de l'appelant.
3. Extrait les informations clés.

SI L'APPELANT EST UN CLIENT (Inconnu/Nouveau) :
- Ton but est de prendre un message clair.

SI L'APPELANT EST L'ARTISAN (Le patron) :
- Tu dois classer sa demande parmi :
  - [JOURNAL] : Compte-rendu de chantier.
  - [DEVIS] : Demande de création de devis.
  - [RELANCE] : Demande de relance factures.
  - [COMMANDE] : Commande de matériaux.

FORMAT DE RÉPONSE OBLIGATOIRE (JSON) :
{
  "categorie": "JOURNAL" | "DEVIS" | "RELANCE" | "COMMANDE" | "MESSAGE_CLIENT",
  "resume": "Résumé précis de ce qui a été dit",
  "data": {
      "nom_client": "Si mentionné",
      "details": "Détails techniques, adresse, prix, matériaux..."
  },
  "reponse_vocale": "La phrase exacte que le robot doit répondre à l'oral (sois bref et pro)."
}
"""

# --- CONNEXION BDD ---
def get_db_connection():
    return psycopg2.connect(DB_URL)

# --- ROUTES ---
@app.route('/')
def home():
    return "⚡ BATI-SERVEUR (Version Google Gemini 1.5 Flash) en ligne."

@app.route('/webhook/incoming', methods=['POST', 'GET'])
def incoming_call():
    resp = VoiceResponse()
    caller_phone = request.values.get('From')
    
    # Vérification BDD (Qui appelle ?)
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT nom_societe FROM membres WHERE telephone = %s", (caller_phone,))
        membre = cur.fetchone()
        cur.close()
        conn.close()
    except:
        membre = None

    if membre:
        resp.say(f"Bonjour Chef {membre[0]}. Je vous écoute.", voice='alice', language='fr-FR')
    else:
        resp.say("Bonjour, entreprise Bati-Plâtre. Je vous écoute.", voice='alice', language='fr-FR')

    # On enregistre et on envoie à l'IA
    resp.record(action='/webhook/process-audio', maxLength=120, playBeep=True)
    return Response(str(resp), mimetype='text/xml')

@app.route('/webhook/process-audio', methods=['POST', 'GET'])
def process_audio():
    recording_url = request.values.get('RecordingUrl')
    caller_phone = request.values.get('From')
    
    # 1. TÉLÉCHARGEMENT DE L'AUDIO (Requis pour Gemini)
    # On sauvegarde temporairement le fichier
    audio_filename = "temp_audio.wav"
    audio_data = requests.get(recording_url).content
    with open(audio_filename, "wb") as f:
        f.write(audio_data)

    try:
        # 2. INTELLIGENCE GEMINI (Mode Flash)
        # On charge le modèle
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # On envoie le fichier audio à Google
        audio_file = genai.upload_file(path=audio_filename)
        
        # On demande l'analyse
        response = model.generate_content([SYSTEM_PROMPT, audio_file])
        
        # 3. TRAITEMENT DE LA RÉPONSE
        # Nettoyage du JSON (Gemini est parfois bavard avec les balises ```)
        json_text = response.text.replace("```json", "").replace("```", "").strip()
        result = json.loads(json_text)
        
        # 4. SAUVEGARDE EN BDD
        conn = get_db_connection()
        cur = conn.cursor()
        
        # On retrouve l'ID membre
        cur.execute("SELECT id FROM membres WHERE telephone = %s", (caller_phone,))
        membre = cur.fetchone()
        
        if membre:
            membre_id = membre[0]
            cat = result.get('categorie')
            
            if cat == "JOURNAL":
                cur.execute("INSERT INTO chantiers (membre_id, resume_texte, audio_url) VALUES (%s, %s, %s)", 
                            (membre_id, result['resume'], recording_url))
            elif cat in ["DEVIS", "RELANCE", "COMMANDE"]:
                cur.execute("INSERT INTO documents (membre_id, type_doc, contenu_json, statut) VALUES (%s, %s, %s, 'BROUILLON')",
                            (membre_id, cat, json.dumps(result['data'])))
        
        conn.commit()
        cur.close()
        conn.close()

        reponse_vocale = result.get('reponse_vocale', "Bien reçu, c'est noté.")

    except Exception as e:
        print(f"ERREUR GEMINI: {e}")
        reponse_vocale = "J'ai eu un petit souci technique, mais l'audio est sauvegardé."

    # 5. NETTOYAGE
    # On supprime le fichier temporaire pour ne pas encombrer le serveur
    if os.path.exists(audio_filename):
        os.remove(audio_filename)

    # 6. RÉPONSE AU TÉLÉPHONE
    resp = VoiceResponse()
    resp.say(reponse_vocale, voice='alice', language='fr-FR')
    resp.hangup()
    
    return Response(str(resp), mimetype='text/xml')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
