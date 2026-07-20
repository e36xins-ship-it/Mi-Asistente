import os
import requests
import json
from flask import Flask, request, jsonify, Response
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# Configuración - Lee desde variables de entorno
API_KEY = os.environ.get("GOOGLE_API_KEY")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

@app.route('/')
def home():
    return "🤖 Asistente Gemini está vivo y funcionando!"

@app.route('/health')
def health():
    return {"status": "ok"}

@app.route('/ask', methods=['POST'])
def ask():
    """Endpoint para preguntas por API (para pruebas)"""
    try:
        data = request.get_json()
        pregunta = data.get('pregunta')
        if not pregunta:
            return jsonify({"error": "Debes enviar una 'pregunta' en el JSON"}), 400
        
        respuesta = llamar_gemini(pregunta)
        return jsonify({"respuesta": respuesta})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/whatsapp', methods=['POST'])
def whatsapp():
    """Endpoint para recibir mensajes de WhatsApp"""
    try:
        # Obtener el mensaje y número de WhatsApp
        mensaje = request.form.get('Body', '').strip()
        numero = request.form.get('From', '').replace('whatsapp:', '')
        nombre = request.form.get('ProfileName', 'Usuario')
        
        print(f"Mensaje de {nombre} ({numero}): {mensaje}")
        
        # Llamar a Gemini
        respuesta = llamar_gemini(mensaje)
        
        # Crear respuesta en formato Twilio
        resp = MessagingResponse()
        resp.message(f"🤖 {respuesta}")
        
        return Response(str(resp), mimetype='text/xml')
    except Exception as e:
        print(f"Error: {e}")
        resp = MessagingResponse()
        resp.message("⚠️ Lo siento, hubo un error procesando tu mensaje.")
        return Response(str(resp), mimetype='text/xml')

def llamar_gemini(pregunta):
    """Función que llama a la API de Gemini"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": pregunta}]
        }]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    resultado = response.json()
    return resultado["candidates"][0]["content"]["parts"][0]["text"]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)