import os
import requests
import json

# Configuración - PON AQUÍ TU CLAVE
API_KEY = os.environ.get("GOOGLE_API_KEY")  # <--- CAMBIA ESTO por tu clave real

def preguntar_a_gemini(pregunta):
    """Envía una pregunta a Gemini y devuelve la respuesta"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={API_KEY}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    data = {
        "contents": [{
            "parts": [{"text": pregunta}]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        resultado = response.json()
        respuesta = resultado["candidates"][0]["content"]["parts"][0]["text"]
        return respuesta
    except Exception as e:
        return f"❌ Error: {e}"

# Bucle principal
print("🤖 ASISTENTE GEMINI (escribe 'salir' para terminar)")
print("-" * 40)

while True:
    pregunta = input("\nTú: ")
    if pregunta.lower() in ["salir", "exit", "quit"]:
        print("👋 ¡Hasta luego!")
        break
    
    print("⏳ Pensando...")
    respuesta = preguntar_a_gemini(pregunta)
    print(f"\n🤖 Gemini: {respuesta}")