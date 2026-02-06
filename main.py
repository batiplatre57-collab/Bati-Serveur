import os
import json
import openai
import psycopg2
from flask import Flask, request, Response
from signalwire.voice_response import VoiceResponse, Dial

app = Flask(__name__)

# --- CONFIGURATION ---
openai.api_key = os.environ.get("OPENAI_API_KEY")
DB_URL = os.environ.get("DATABASE_URL")

# Le Prompt défini plus haut
SYSTEM_PROMPT = "..." # (Copier le texte du point 5 ici)

# --- FONCTION BDD ---
def get_db_connection():
    return psycopg2.connect(DB_URL)

@app.route('/')
def home():
    return "🚀 BATI-SERVEUR (SaaS SignalWire) en ligne."

# --- ÉTAPE 1 : RÉCEPTION APPEL (Webhook SignalWire) ---
@app.route('/webhook/incoming', methods=['POST', 'GET'])
def incoming_call():
    resp = VoiceResponse()
    caller = request.values.get('From') # Numéro de celui qui appelle
    
    # Vérifier si c'est un MEMBRE (Artisan)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT nom_societe FROM membres WHERE telephone = %s", (caller,))
    membre = cur.fetchone()
    cur.close()
    conn.close()

    if membre:
        # C'est l'Artisan -> Mode Gestion
        resp.say(f"Bonjour Chef {membre[0]}. Je vous écoute pour devis, journal ou commandes.", voice='alice', language='fr-FR')
    else:
        # C'est un Client -> Mode Secrétariat
        resp.say("Bonjour, vous êtes bien sur le secrétariat Bati-Plâtre. Laissez un message.", voice='alice', language='fr-FR')

    # Enregistrement de la demande (Max 120s pour éviter les abus)
    resp.record(action='/webhook/process-audio', maxLength=120, playBeep=True)
    
    return Response(str(resp), mimetype='text/xml')

# --- ÉTAPE 2 : TRAITEMENT INTELLIGENT ---
@app.route('/webhook/process-audio', methods=['POST', 'GET'])
def process_audio():
    recording_url = request.values.get('RecordingUrl')
    
    # 1. Transcription (Whisper)
    # (Note: Code simplifié, en prod il faut télécharger le fichier audio avant)
    transcript = "Simulation: Transcription du fichier audio" 
    
    # 2. Analyse GPT-4o-mini (Économique)
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",  # <--- LE SECRET DE LA RENTABILITÉ
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Voici la transcription : {transcript}"}
        ],
        temperature=0.3
    )
    
    ai_content = response.choices[0].message.content
    result = json.loads(ai_content)
    
    # 3. Exécution des Tâches
    action = result.get('intent')
    data = result.get('data')
    
    conn = get_db_connection()
    cur = conn.cursor()

    if action == "JOURNAL":
        # Sauvegarde en BDD
        cur.execute("INSERT INTO chantiers (resume_texte, audio_url) VALUES (%s, %s)", (result['reponse_vocale'], recording_url))
        
    elif action == "DEVIS":
        # Création entrée BDD (Génération PDF à faire plus tard)
        cur.execute("INSERT INTO documents (type_doc, contenu_json, statut) VALUES ('DEVIS', %s, 'BROUILLON')", (json.dumps(data),))
        
    elif action == "RELANCE":
        # Logique Chien de Garde
        pass 

    conn.commit()
    cur.close()
    conn.close()

    # 4. Réponse Vocale de confirmation
    resp = VoiceResponse()
    resp.say(result.get('reponse_vocale', "C'est noté."), voice='alice', language='fr-FR')
    resp.hangup()
    
    return Response(str(resp), mimetype='text/xml')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
