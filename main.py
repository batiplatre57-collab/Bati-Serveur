import os
import json
import requests
import psycopg2
from flask import Flask, request, Response
from signalwire.voice_response import VoiceResponse
from openai import OpenAI

app = Flask(__name__)

# --- CONFIGURATION DES CLÉS (Secrets Render) ---
DB_URL = os.environ.get("DATABASE_URL")
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# --- LE CERVEAU INTELLIGENT (Prompt Système) ---
# C'est ici que l'IA décide quoi faire.
SYSTEM_PROMPT = """
Tu es BATI-IA, l'assistant expert pour artisans du bâtiment.

RÔLE :
Tu reçois une transcription vocale.
1. Si l'utilisateur est un ARTISAN (Reconnu) : Tu agis comme un gestionnaire.
2. Si l'utilisateur est un CLIENT (Inconnu) : Tu agis comme un secrétariat (Prise de message).

TES ACTIONS POSSIBLES (Pour l'Artisan) :
- [JOURNAL] : Compte-rendu de chantier. (Ex: "Fini le placo, manque 2 rails")
- [DEVIS] : Création de devis. (Ex: "Devis pour M. Durant. 10m2 carrelage à 50€")
- [RELANCE] : Gestion impayés. (Ex: "Relance les factures en retard")
- [COMMANDE] : Achat fournisseur. (Ex: "Commande le matériel chantier X chez Point P")
- [EXPERT] : Question technique. (Ex: "Quelle TVA pour rénovation ?")

FORMAT DE RÉPONSE OBLIGATOIRE (JSON) :
{
  "categorie": "JOURNAL" | "DEVIS" | "RELANCE" | "COMMANDE" | "EXPERT" | "MESSAGE_CLIENT",
  "resume_court": "Résumé de la demande",
  "data": {
      "client": "Nom du client si cité",
      "details": "Détails techniques complets"
  },
  "reponse_vocale": "Phrase courte que le robot dira à l'artisan pour confirmer."
}
"""

# --- FONCTION : CONNEXION BASE DE DONNÉES ---
def get_db_connection():
    return psycopg2.connect(DB_URL)

# --- ROUTE 1 : VÉRIFICATION (Ping) ---
@app.route('/')
def home():
    return "🏗️ BATI-SERVEUR est en ligne (Mode SignalWire)."

# --- ROUTE 2 : APPEL ENTRANT (SignalWire appelle ici) ---
@app.route('/webhook/incoming', methods=['POST', 'GET'])
def incoming_call():
    resp = VoiceResponse()
    
    # 1. Qui appelle ?
    caller_phone = request.values.get('From')
    
    # 2. Vérification dans Neon (Est-ce un Membre ?)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT nom_societe, id FROM membres WHERE telephone = %s", (caller_phone,))
    membre = cur.fetchone()
    cur.close()
    conn.close()

    # 3. Logique d'accueil
    if membre:
        # C'est l'Artisan -> Mode Gestion
        nom = membre[0]
        resp.say(f"Bonjour Chef {nom}. Je vous écoute pour le journal, un devis ou une commande.", voice='alice', language='fr-FR')
    else:
        # C'est un Client -> Mode Secrétariat
        resp.say("Bonjour, vous êtes bien sur le secrétariat Bati-Plâtre. Laissez votre message après le bip.", voice='alice', language='fr-FR')

    # 4. Enregistrement (Max 120 sec) -> Envoie l'audio vers l'étape suivante
    resp.record(action='/webhook/process-audio', maxLength=120, playBeep=True)
    
    return Response(str(resp), mimetype='text/xml')

# --- ROUTE 3 : TRAITEMENT DE L'AUDIO (Le Cœur du Système) ---
@app.route('/webhook/process-audio', methods=['POST', 'GET'])
def process_audio():
    # 1. Récupérer l'URL de l'enregistrement SignalWire
    recording_url = request.values.get('RecordingUrl')
    caller_phone = request.values.get('From')
    
    # 2. Télécharger l'audio temporairement pour l'envoyer à OpenAI
    # (Astuce : On utilise un fichier temporaire 'temp.wav')
    audio_data = requests.get(recording_url).content
    with open("temp.wav", "wb") as f:
        f.write(audio_data)
        
    # 3. TRANSCRIPTION (Whisper)
    audio_file = open("temp.wav", "rb")
    transcript = client.audio.transcriptions.create(
        model="whisper-1", 
        file=audio_file
    ).text
    
    # 4. INTELLIGENCE (GPT-4o-mini -> Rentabilité 4,99€)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Transcription : {transcript}"}
        ],
        temperature=0.3
    )
    
    # 5. Récupération du JSON de l'IA
    ai_content = response.choices[0].message.content
    # Nettoyage au cas où l'IA mettrait des balises ```json
    if "```" in ai_content:
        ai_content = ai_content.replace("```json", "").replace("```", "")
    
    result = json.loads(ai_content)
    categorie = result.get('categorie')
    
    # 6. ENREGISTREMENT DANS NEON (Base de Données)
    conn = get_db_connection()
    cur = conn.cursor()
    
    # On retrouve l'ID du membre
    cur.execute("SELECT id FROM membres WHERE telephone = %s", (caller_phone,))
    membre = cur.fetchone()
    
    if membre:
        membre_id = membre[0]
        
        if categorie == "JOURNAL":
            cur.execute("INSERT INTO chantiers (membre_id, resume_texte, audio_url) VALUES (%s, %s, %s)", 
                        (membre_id, result['resume_court'], recording_url))
            
        elif categorie in ["DEVIS", "RELANCE", "COMMANDE"]:
            # On stocke dans la table documents
            cur.execute("INSERT INTO documents (membre_id, type_doc, contenu_json, statut) VALUES (%s, %s, %s, 'BROUILLON')",
                        (membre_id, categorie, json.dumps(result['data'])))
            
    conn.commit()
    cur.close()
    conn.close()

    # 7. RÉPONSE VOCALE FINALE (SignalWire)
    resp = VoiceResponse()
    text_to_say = result.get('reponse_vocale', "Bien reçu, c'est traité.")
    resp.say(text_to_say, voice='alice', language='fr-FR')
    resp.hangup()
    
    return Response(str(resp), mimetype='text/xml')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
