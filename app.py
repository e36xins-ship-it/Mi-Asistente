import os
import requests
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# La clave se lee de las variables de entorno
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
        
        if not API_KEY:
            print("❌ ERROR: La clave API no está configurada")
            return jsonify({"error": "Clave API no configurada"}), 500

        # ✅ NUEVA ESTRUCTURA DE PETICIÓN
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"
        headers = {"Content-Type": "application/json"}
        
        # ✅ FORMATO CORRECTO SEGÚN DOCUMENTACIÓN
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": pregunta}]
                }
            ]
        }
        
        print(f"📤 Enviando a Gemini...")
        response = requests.post(url, headers=headers, json=payload)
        print(f"📥 Código de respuesta: {response.status_code}")
        
        # ✅ MANEJO DE ERRORES MÁS DETALLADO
        if response.status_code != 200:
            print(f"❌ Error de Gemini: {response.text}")
            return jsonify({
                "error": "Error en la API de Gemini",
                "code": response.status_code,
                "details": response.json() if response.text else "Sin detalles"
            }), response.status_code
        
        resultado = response.json()
        print(f"📥 Respuesta completa: {json.dumps(resultado, indent=2)}")
        
        # ✅ ACCESO SEGURO A LA RESPUESTA
        if "candidates" in resultado and len(resultado["candidates"]) > 0:
            candidate = resultado["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                respuesta = candidate["content"]["parts"][0]["text"]
                return jsonify({"respuesta": respuesta})
        
        return jsonify({"error": "No se pudo obtener una respuesta válida"}), 500
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de red: {e}")
        return jsonify({"error": f"Error de conexión: {str(e)}"}), 500
    except json.JSONDecodeError as e:
        print(f"❌ Error al decodificar JSON: {e}")
        print(f"📥 Respuesta cruda: {response.text[:200]}")
        return jsonify({"error": "Error al procesar la respuesta de Gemini"}), 500
    except Exception as e:
        print(f"❌ ERROR INESPERADO: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
     