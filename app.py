import os
import requests
import json
import time
import threading
import ast
import shutil
import re
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# ============================================
# CONFIGURACIÓN
# ============================================

API_KEY = os.environ.get("GOOGLE_API_KEY")
INTERVALO_APRENDIZAJE = 600  # 10 minutos
ARCHIVO_HISTORIAL = "aprendizaje.json"
ARCHIVO_TAREAS = "tareas.json"
CARPETA_BACKUPS = "backups"

# Crear carpetas necesarias
os.makedirs(CARPETA_BACKUPS, exist_ok=True)

# ============================================
# CARGA DE ESTADO PERSISTENTE
# ============================================

# Cargar historial de mejoras
try:
    with open(ARCHIVO_HISTORIAL, "r") as f:
        historial_mejoras = json.load(f)
except FileNotFoundError:
    historial_mejoras = []

# Cargar lista de tareas
try:
    with open(ARCHIVO_TAREAS, "r") as f:
        tareas = json.load(f)
except FileNotFoundError:
    tareas = []  # Lista de diccionarios: {"id": 1, "descripcion": "...", "estado": "pendiente"}

# Contador para IDs de tareas
id_counter = max([t["id"] for t in tareas]) + 1 if tareas else 1

# ============================================
# FUNCIONES DE PERSISTENCIA
# ============================================

def guardar_tareas():
    with open(ARCHIVO_TAREAS, "w") as f:
        json.dump(tareas, f, indent=2)

def guardar_historial():
    with open(ARCHIVO_HISTORIAL, "w") as f:
        json.dump(historial_mejoras[-50:], f, indent=2)  # Guardar últimas 50

# ============================================
# FUNCIÓN PARA LLAMAR A GEMINI
# ============================================

def llamar_gemini(pregunta):
    """Llama a la API de Gemini y devuelve la respuesta"""
    print(f"📤 Llamando a Gemini con: {pregunta[:50]}...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": pregunta}]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        resultado = response.json()
        respuesta = resultado["candidates"][0]["content"]["parts"][0]["text"]
        print(f"✅ Gemini respondió: {respuesta[:50]}...")
        return respuesta
    except Exception as e:
        print(f"❌ Error al llamar a Gemini: {e}")
        raise

# ============================================
# VALIDACIÓN Y APLICACIÓN DE MEJORAS
# ============================================

def validar_codigo(codigo):
    try:
        ast.parse(codigo)
        return True, "Código válido"
    except SyntaxError as e:
        return False, f"Error de sintaxis: {e}"

def aplicar_mejora(archivo_mejora):
    try:
        with open(archivo_mejora, "r") as f:
            contenido = f.read()
        
        patron = r"```python\n(.*?)```"
        match = re.search(patron, contenido, re.DOTALL)
        if not match:
            return False, "No se encontró código Python"
        
        nuevo_codigo = match.group(1).strip()
        valido, mensaje = validar_codigo(nuevo_codigo)
        if not valido:
            return False, mensaje
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(CARPETA_BACKUPS, f"app_backup_{timestamp}.py")
        with open(__file__, "r") as f_actual:
            with open(backup_path, "w") as f_backup:
                f_backup.write(f_actual.read())
        
        with open(__file__, "w") as f:
            f.write(nuevo_codigo)
        
        historial_mejoras.append({
            "timestamp": timestamp,
            "mejora": contenido[:500],
            "backup": backup_path
        })
        guardar_historial()
        
        print("🔄 El servicio se reiniciará en 5 segundos...")
        time.sleep(5)
        os._exit(0)
        
    except Exception as e:
        return False, str(e)

# ============================================
# FUNCIONES DE GESTIÓN DE TAREAS
# ============================================

def obtener_siguiente_tarea():
    """Devuelve la primera tarea pendiente o None si no hay"""
    for tarea in tareas:
        if tarea["estado"] == "pendiente":
            return tarea
    return None

def marcar_tarea_completada(tarea_id):
    for tarea in tareas:
        if tarea["id"] == tarea_id:
            tarea["estado"] = "completada"
            tarea["fecha_completada"] = datetime.now().isoformat()
            guardar_tareas()
            return True
    return False

def anadir_tarea(descripcion):
    global id_counter
    tarea = {
        "id": id_counter,
        "descripcion": descripcion,
        "estado": "pendiente",
        "fecha_creacion": datetime.now().isoformat()
    }
    tareas.append(tarea)
    id_counter += 1
    guardar_tareas()
    return tarea

def eliminar_tarea(tarea_id):
    global tareas
    tareas = [t for t in tareas if t["id"] != tarea_id]
    guardar_tareas()

# ============================================
# CICLO DE APRENDIZAJE (CON TAREAS)
# ============================================

def aprender_y_mejorar():
    """
    Ejecuta el ciclo de aprendizaje.
    Si hay tareas pendientes, usa la primera como objetivo.
    Si no, aprende libremente.
    """
    print("🧠 Entrando en aprender_y_mejorar()...")
    print("🧠 Iniciando ciclo de aprendizaje...")
    
    # 1. Verificar si hay tareas pendientes
    tarea_actual = obtener_siguiente_tarea()
    
    if tarea_actual:
        objetivo = f"Resolver la tarea: '{tarea_actual['descripcion']}'"
        print(f"📋 Tarea en curso: {tarea_actual['descripcion']}")
    else:
        objetivo = "Mejorar el sistema en general. Aprende algo nuevo y útil."
        print("🧠 No hay tareas pendientes. Aprendizaje libre.")
    
    # 2. Construir el prompt
    prompt_contexto = f"""
    Eres el asistente Aether, un sistema autónomo que se mejora a sí mismo.
    
    OBJETIVO ACTUAL: {objetivo}
    
    Ya has implementado estas mejoras anteriormente:
    {json.dumps(historial_mejoras[-5:], indent=2)}
    
    Tu objetivo es sugerir UNA MEJORA NUEVA Y CONCRETA para tu propio código.
    La mejora debe:
    - Estar alineada con el objetivo actual.
    - Ser pequeña y aplicable.
    - No romper el sistema.
    
    Responde ÚNICAMENTE con un bloque de código Python completo (incluyendo todo el app.py)
    que reemplace al actual. Incluye TODAS las funciones existentes y añade la nueva funcionalidad.
    """
    
    try:
        respuesta = llamar_gemini(prompt_contexto)
        print(f"💡 Mejora generada: {respuesta[:200]}...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo_mejora = f"mejora_{timestamp}.txt"
        with open(archivo_mejora, "w") as f:
            f.write(respuesta)
        
        exito, mensaje = aplicar_mejora(archivo_mejora)
        
        if exito:
            # Marcar tarea como completada si existe
            if tarea_actual:
                marcar_tarea_completada(tarea_actual["id"])
                print(f"✅ Tarea '{tarea_actual['descripcion']}' completada.")
            print("🚀 Mejora aplicada con éxito. Reiniciando...")
        else:
            print(f"⚠️ La mejora no se pudo aplicar: {mensaje}")
            # Si la tarea falla, se queda pendiente para el próximo ciclo
        
        return exito
        
    except Exception as e:
        print(f"❌ Error en ciclo de aprendizaje: {e}")
        return False

# ============================================
# BUCLE DE MANTENIMIENTO (KEEP-ALIVE + APRENDIZAJE)
# ============================================

def bucle_aprendizaje():
    print("🔄 Bucle de aprendizaje iniciado. Esperando primer ciclo...")
    while True:
        try:
            inicio_ciclo = time.time()
            
            aprender_y_mejorar()
            
            # Ping interno
            try:
                requests.get(f"http://localhost:{os.environ.get('PORT', 10000)}/health", timeout=5)
                print("🔋 Ping de mantenimiento enviado")
            except Exception as e:
                print(f"❌ Error en ping interno: {e}")
            
            tiempo_ejecucion = time.time() - inicio_ciclo
            tiempo_espera = max(0, INTERVALO_APRENDIZAJE - tiempo_ejecucion)
            print(f"⏳ Próximo ciclo en {tiempo_espera:.0f} segundos")
            time.sleep(tiempo_espera)
        except Exception as e:
            print(f"❌ Error crítico en bucle_aprendizaje: {e}")
            time.sleep(60)  # Espera 1 minuto antes de reintentar

# ============================================
# ENDPOINTS DE LA API
# ============================================

@app.route('/')
def home():
    return "🤖 Asistente Gemini está vivo y funcionando!"

@app.route('/health')
def health():
    return {"status": "ok"}

@app.route('/ping')
def ping():
    return {"status": "alive", "message": "🤖 Asistente activo"}

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
        print(f"❌ ERROR en /ask: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/aprender', methods=['POST'])
def aprender_manual():
    """Inicia el ciclo de aprendizaje en segundo plano"""
    print("🔧 Endpoint /aprender llamado manualmente")
    thread = threading.Thread(target=aprender_y_mejorar)
    thread.daemon = True
    thread.start()
    return jsonify({
        "status": "ok",
        "message": "Ciclo de aprendizaje iniciado en segundo plano."
    })

# ============================================
# ENDPOINTS DE GESTIÓN DE TAREAS
# ============================================

@app.route('/tareas', methods=['GET'])
def listar_tareas():
    """Devuelve todas las tareas con su estado"""
    return jsonify({
        "pendientes": [t for t in tareas if t["estado"] == "pendiente"],
        "completadas": [t for t in tareas if t["estado"] == "completada"],
        "total": len(tareas)
    })

@app.route('/tareas', methods=['POST'])
def crear_tarea():
    """Añade una nueva tarea a la lista"""
    data = request.get_json()
    if not data or 'descripcion' not in data:
        return jsonify({"error": "Falta la descripción de la tarea"}), 400
    
    tarea = anadir_tarea(data['descripcion'])
    return jsonify({"status": "ok", "tarea": tarea}), 201

@app.route('/tareas/<int:tarea_id>', methods=['DELETE'])
def borrar_tarea(tarea_id):
    """Elimina una tarea (completada o pendiente)"""
    eliminar_tarea(tarea_id)
    return jsonify({"status": "ok", "message": f"Tarea {tarea_id} eliminada"})

@app.route('/tareas/<int:tarea_id>/completar', methods=['POST'])
def completar_tarea(tarea_id):
    """Marca una tarea como completada manualmente"""
    if marcar_tarea_completada(tarea_id):
        return jsonify({"status": "ok", "message": f"Tarea {tarea_id} completada"})
    else:
        return jsonify({"error": "Tarea no encontrada"}), 404

@app.route('/estado', methods=['GET'])
def estado_sistema():
    """Devuelve el estado completo del sistema"""
    tarea_actual = obtener_siguiente_tarea()
    return jsonify({
        "tarea_actual": tarea_actual,
        "pendientes": len([t for t in tareas if t["estado"] == "pendiente"]),
        "completadas": len([t for t in tareas if t["estado"] == "completada"]),
        "total_mejoras": len(historial_mejoras),
        "ultima_mejora": historial_mejoras[-1] if historial_mejoras else None
    })

# ============================================
# INICIO DEL SERVICIO
# ============================================

if __name__ == "__main__":
    print("🚀 Iniciando asistente con bucle de aprendizaje...")
    # Lanzar el bucle de aprendizaje en segundo plano
    thread_bucle = threading.Thread(target=bucle_aprendizaje, daemon=True)
    thread_bucle.start()
    print("✅ Bucle de aprendizaje lanzado en segundo plano.")
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)