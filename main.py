import os
import json
import openai
import psycopg2
from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Dial

app = Flask(__name__)

# --- RECUPERATION DES CLES ---
openai.api_key = os.environ.get("OPENAI_API_KEY")
DB_URL = os.environ.get("DATABASE_URL")

SYSTEM_PROMPT = """
Tu es le secrétaire. Analyse la transcription.
Catégories : [PARTICULIER, RECRUTEMENT, PRO, COMPTABILITÉ, PUB, AUTRE].
Réponds en JSON : {"nom": "...", "prenom": "...", "objet": "...", "categorie": "..."}
"""

@app.route('/')
def home():
    return "Le serveur BATI-EURO est en ligne sur Render !"

@app.route('/webhook/incoming-call', methods=['POST'])
def incoming_call():
    resp = VoiceResponse()
    # Mettez votre portable ici pour tester le renvoi
    mobile_artisan = "+33600000000" 
    
    dial = Dial(timeout=10, action='/webhook/ai-takeover')
    dial.number(mobile_artisan)
    resp.append(dial)
    return str(resp)

@app.route('/webhook/ai-takeover', methods=['POST'])
def ai_takeover():
    if request.form.get('DialCallStatus') == 'completed':
        return "Terminé", 200
    resp = VoiceResponse()
    resp.say("Je suis l'assistant IA. Laissez votre message.", voice='alice', language='fr-FR')
    resp.record(maxLength=60, action='/webhook/process-recording')
    return str(resp)

@app.route('/webhook/process-recording', methods=['POST'])
def process_recording():
    print("Enregistrement reçu (Traitement simulé pour Render)")
    return "OK", 200

# Pas de app.run() ici, Render utilise Gunicorn !
