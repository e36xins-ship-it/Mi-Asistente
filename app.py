import os
import requests
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# ✅ La clave se lee de las variables de entorno (SEGURO)
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
        # Obtener la pregunta
        data = request.get_json()
        if not data or 'pregunta' not in data:
            return jsonify({"error": "Falta la pregunta"}), 400
        
        pregunta = data['pregunta']
        print(f"📩 Pregunta recibida: {pregunta}")
        
        # Verificar que la clave existe
        if not API_KEY:
            print("❌ ERROR: La clave API no está configurada en las variables de entorno")
            return jsonify({"error": "La clave API no está configurada"}), 500
        
        # Llamar a Gemini
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={API_KEY}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": pregunta}]
            }]
        }
        
        print(f"📤 Enviando a Gemini...")
        response = requests.post(url, headers=headers, json=payload)
        print(f"📥 Código de respuesta: {response.status_code}")
        print(f"📥 Respuesta de Gemini: {response.text[:200]}")
        
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