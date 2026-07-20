import os
import requests
import json
import time
import threading
import ast
import shutil
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# ============================================
# CONFIGURACIÓN
# ============================================

API_KEY = os.environ.get("GOOGLE_API_KEY")
INTERVALO_APRENDIZAJE = 600  # 10 minutos
ARCHIVO_HISTORIAL = "aprendizaje.json"
CARPETA_BACKUPS = "backups"

# Crear carpeta de backups si no existe
os.makedirs(CARPETA_BACKUPS, exist_ok=True)

# Cargar historial de mejoras
try:
    with open(ARCHIVO_HISTORIAL, "r") as f:
        historial_mejoras = json.load(f)
except FileNotFoundError:
    historial_mejoras = []

# ============================================
# FUNCIÓN PARA LLAMAR A GEMINI
# ============================================

def llamar_gemini(pregunta):
    """Llama a la API de Gemini y devuelve la respuesta"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": pregunta}]
        }]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    resultado = response.json()
    return resultado["candidates"][0]["content"]["parts"][0]["text"]

# ============================================
# FUNCIONES DE VALIDACIÓN Y APLICACIÓN
# ============================================

def validar_codigo(codigo):
    """Valida que el código Python sea sintácticamente correcto"""
    try:
        ast.parse(codigo)
        return True, "Código válido"
    except SyntaxError as e:
        return False, f"Error de sintaxis: {e}"

def aplicar_mejora(archivo_mejora):
    """
    Lee el archivo de mejora, valida el código y lo aplica si es correcto.
    Crea un backup del app.py actual antes de modificar.
    """
    try:
        # Leer la mejora generada
        with open(archivo_mejora, "r") as f:
            contenido = f.read()
        
        # Buscar el bloque de código Python (entre ```python y ```)
        import re
        patron = r"```python\n(.*?)```"
        match = re.search(patron, contenido, re.DOTALL)
        
        if not match:
            print("❌ No se encontró bloque de código en la mejora")
            return False, "No se encontró código Python"
        
        nuevo_codigo = match.group(1).strip()
        
        # Validar el código
        valido, mensaje = validar_codigo(nuevo_codigo)
        if not valido:
            print(f"❌ Código inválido: {mensaje}")
            return False, mensaje
        
        # Crear backup del app.py actual
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(CARPETA_BACKUPS, f"app_backup_{timestamp}.py")
        shutil.copy2(__file__, backup_path)
        print(f"📦 Backup guardado en {backup_path}")
        
        # Aplicar el nuevo código (sobrescribir app.py)
        with open(__file__, "w") as f:
            f.write(nuevo_codigo)
        
        print("✅ Mejora aplicada correctamente")
        
        # Registrar en historial
        historial_mejoras.append({
            "timestamp": timestamp,
            "mejora": contenido[:500],
            "backup": backup_path
        })
        with open(ARCHIVO_HISTORIAL, "w") as f:
            json.dump(historial_mejoras[-50:], f, indent=2)
        
        # Notificar que se debe reiniciar el servicio
        print("🔄 El servicio se reiniciará en 5 segundos...")
        time.sleep(5)
        os._exit(0)  # Reiniciar el servicio
        
    except Exception as e:
        print(f"❌ Error al aplicar mejora: {e}")
        return False, str(e)

# ============================================
# CICLO DE APRENDIZAJE (con auto-aplicación)
# ============================================

def aprender_y_mejorar():
    """
    Genera una mejora, la valida y la aplica automáticamente si es segura.
    """
    print("🧠 Iniciando ciclo de aprendizaje...")
    
    prompt_contexto = f"""
    Eres el asistente Aether, un sistema autónomo que se mejora a sí mismo.
    Ya has implementado estas mejoras anteriormente:
    {json.dumps(historial_mejoras[-5:], indent=2)}
    
    Tu objetivo es sugerir UNA MEJORA NUEVA Y CONCRETA para tu propio código.
    La mejora debe ser:
    - Pequeña y aplicable (no reescribir todo).
    - Que añada una nueva funcionalidad útil.
    - Que no rompa el sistema actual.
    
    Responde ÚNICAMENTE con un bloque de código Python completo (incluyendo todo el app.py) 
    que reemplace al actual. Incluye TODAS las funciones existentes (home, health, ask, ping, aprender)
    y añade la nueva funcionalidad.
    
    Si la mejora es muy pequeña, responde con el código completo actualizado.
    """
    
    try:
        respuesta = llamar_gemini(prompt_contexto)
        print(f"💡 Mejora generada: {respuesta[:200]}...")
        
        # Guardar la mejora en un archivo temporal
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo_mejora = f"mejora_{timestamp}.txt"
        with open(archivo_mejora, "w") as f:
            f.write(respuesta)
        
        # Aplicar la mejora automáticamente
        exito, mensaje = aplicar_mejora(archivo_mejora)
        
        if exito:
            print("🚀 Mejora aplicada con éxito. Reiniciando...")
        else:
            print(f"⚠️ La mejora no se pudo aplicar: {mensaje}")
        
        return exito
        
    except Exception as e:
        print(f"❌ Error en ciclo de aprendizaje: {e}")
        return False

# ============================================
# BUCLE PRINCIPAL DE MANTENIMIENTO
# ============================================

def bucle_aprendizaje():
    """
    Bucle que se ejecuta en un hilo separado.
    Cada INTERVALO_APRENDIZAJE, ejecuta aprender_y_mejorar()
    """
    while True:
        inicio_ciclo = time.time()
        
        # Autoaprendizaje + auto-aplicación
        aprender_y_mejorar()
        
        # Ping interno para mantener vivo el servicio
        try:
            requests.get(f"http://localhost:{os.environ.get('PORT', 10000)}/health")
            print("🔋 Ping de mantenimiento enviado")
        except Exception as e:
            print(f"❌ Error en ping interno: {e}")
        
        # Calcular tiempo de espera
        tiempo_ejecucion = time.time() - inicio_ciclo
        tiempo_espera = max(0, INTERVALO_APRENDIZAJE - tiempo_ejecucion)
        print(f"⏳ Próximo ciclo en {tiempo_espera:.0f} segundos")
        time.sleep(tiempo_espera)

# ============================================
# ENDPOINTS DE LA API
# ============================================

@app.route('/')
def home():
    return "🤖 Asistente Gemini está vivo y funcionando!"

@app.route('/health')
def health():
    return {"status": "ok"}

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "alive", "message": "🤖 Asistente activo"})

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
        
        respuesta = llamar_gemini(pregunta)
        return jsonify({"respuesta": respuesta})
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/aprender', methods=['POST'])
def aprender_manual():
    """Endpoint para activar el aprendizaje bajo demanda."""
    try:
        resultado = aprender_y_mejorar()
        if resultado:
            return jsonify({"status": "ok", "message": "Ciclo de aprendizaje iniciado y aplicado"})
        else:
            return jsonify({"status": "error", "message": "Error en el aprendizaje"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# INICIO DEL SERVICIO
# ============================================

if __name__ == "__main__":
    # Lanzar el bucle de aprendizaje en segundo plano
    threading.Thread(target=bucle_aprendizaje, daemon=True).start()
    
    # Iniciar el servidor
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)