import os
import requests
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# La clave se lee de las variables de entorno (SEGURO)
API_KEY = os.environ.get("GOOGLE_API_KEY")

@app.route('/')
def home():
    return "🤖 Asistente Gemini está vivo y funcionando!"

@app.route('/health')
def health():
    return {"status": "ok"}

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.get_json()
        if not data or 'pregunta' not in data:
            return jsonify({"error": "Falta la pregunta"}), 400
        
        pregunta = data['pregunta']
        print(f"📩 Pregunta recibida: {pregunta}")
        
        if not API_KEY:
            print("❌ ERROR: La clave API no está configurada")
            return jsonify({"error": "Clave API no configurada"}), 500

        # ✅ Usamos el modelo que SÍ funciona: gemini-2.0-flash
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": pregunta}]
            }]
        }
        
        print(f"📤 Enviando a Gemini...")
        response = requests.post(url, headers=headers, json=payload)
        print(f"📥 Código de respuesta: {response.status_code}")
        
        response.raise_for_status()
        resultado = response.json()
        respuesta = resultado["candidates"][0]["content"]["parts"][0]["text"]
        
        return jsonify({"respuesta": respuesta})
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)