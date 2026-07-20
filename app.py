import os
import requests
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

API_KEY = os.environ.get("GOOGLE_API_KEY")

@app.route('/')
def home():
    return "🤖 Asistente Gemini está vivo y funcionando!"

@app.route('/health')
def health():
    return {"status": "ok"}

@app.route('/models', methods=['GET'])
def list_models():
    """Endpoint que lista los modelos disponibles en tu cuenta"""
    if not API_KEY:
        return jsonify({"error": "Clave API no configurada"}), 500
    
    try:
        # Consulta a la API de Google para listar modelos
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
        response = requests.get(url)
        
        if response.status_code != 200:
            return jsonify({
                "error": "Error al obtener modelos",
                "code": response.status_code,
                "details": response.json() if response.text else "Sin detalles"
            }), response.status_code
        
        data = response.json()
        modelos = []
        
        # Filtramos solo los que soportan generateContent
        for model in data.get('models', []):
            if 'generateContent' in model.get('supportedActions', []):
                modelos.append({
                    "name": model.get('name'),
                    "displayName": model.get('displayName'),
                    "description": model.get('description', '')[:100]
                })
        
        return jsonify({
            "total": len(modelos),
            "models": modelos
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.get_json()
        if not data or 'pregunta' not in data:
            return jsonify({"error": "Falta la pregunta"}), 400
        
        pregunta = data['pregunta']
        print(f"📩 Pregunta recibida: {pregunta}")
        
        if not API_KEY:
            return jsonify({"error": "Clave API no configurada"}), 500

        # ⚠️ IMPORTANTE: CAMBIA ESTE MODELO POR EL QUE TE APAREZCA EN /models
        # Por ahora usamos gemini-3.5-flash como ejemplo
        MODELO = "gemini-3.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent?key={API_KEY}"
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": pregunta}]
                }
            ]
        }
        
        headers = {"Content-Type": "application/json"}
        
        print(f"📤 Enviando a Gemini con modelo: {MODELO}")
        response = requests.post(url, headers=headers, json=payload)
        print(f"📥 Código de respuesta: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Error de Gemini: {response.text}")
            return jsonify({
                "error": "Error en la API de Gemini",
                "code": response.status_code,
                "details": response.json() if response.text else "Sin detalles"
            }), response.status_code
        
        resultado = response.json()
        
        if "candidates" in resultado and len(resultado["candidates"]) > 0:
            candidate = resultado["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                respuesta = candidate["content"]["parts"][0]["text"]
                return jsonify({"respuesta": respuesta})
        
        return jsonify({"error": "No se pudo obtener una respuesta válida"}), 500
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)