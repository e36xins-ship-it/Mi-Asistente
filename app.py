import os
import requests
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# Tu clave API se lee de las variables de entorno (más seguro)
API_KEY = os.environ.get("GOOGLE_API_KEY")

@app.route('/')
def home():
    return "🤖 Asistente Gemini está vivo y funcionando!"

@app.route('/ask', methods=['POST'])
def ask():
    """
    Esta es la función que recibe las preguntas.
    Debe recibir un JSON con el campo 'pregunta'.
    """
    try:
        data = request.get_json()
        pregunta = data.get('pregunta')
        if not pregunta:
            return jsonify({"error": "Debes enviar una 'pregunta' en el JSON"}), 400

        # Llamar a la API de Gemini
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={API_KEY}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": pregunta}]
            }]
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        resultado = response.json()
        respuesta = resultado["candidates"][0]["content"]["parts"][0]["text"]
        
        return jsonify({"respuesta": respuesta})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Render asigna el puerto automáticamente con la variable PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)