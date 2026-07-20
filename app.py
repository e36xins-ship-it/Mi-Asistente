import os
import sys
import requests
import json
import time
import threading
import ast
import shutil
import re
import subprocess
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# ============================================
# CONFIGURACIÓN
# ============================================

API_KEY = os.environ.get("GOOGLE_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO_URL = os.environ.get("GITHUB_REPO_URL")

INTERVALO_APRENDIZAJE = 600  # 10 minutos
ARCHIVO_HISTORIAL = "aprendizaje.json"
ARCHIVO_TAREAS = "tareas.json"
CARPETA_BACKUPS = "backups"
CARPETA_REPO = "repo"

os.makedirs(CARPETA_BACKUPS, exist_ok=True)
os.makedirs(CARPETA_REPO, exist_ok=True)

# Cargar historial
try:
    with open(ARCHIVO_HISTORIAL, "r") as f:
        historial_mejoras = json.load(f)
except FileNotFoundError:
    historial_mejoras = []

# Cargar tareas
try:
    with open(ARCHIVO_TAREAS, "r") as f:
        tareas = json.load(f)
except FileNotFoundError:
    tareas = []

id_counter = max([t["id"] for t in tareas]) + 1 if tareas else 1

def guardar_tareas():
    with open(ARCHIVO_TAREAS, "w") as f:
        json.dump(tareas, f, indent=2)

def guardar_historial():
    with open(ARCHIVO_HISTORIAL, "w") as f:
        json.dump(historial_mejoras[-50:], f, indent=2)

# ============================================
# FUNCIONES DE GIT
# ============================================

def git_inicializar():
    if not GITHUB_TOKEN or not GITHUB_REPO_URL:
        print("⚠️ GitHub no configurado", file=sys.stderr)
        return False
    repo_path = os.path.join(os.getcwd(), CARPETA_REPO)
    if not os.path.exists(os.path.join(repo_path, ".git")):
        print("📦 Clonando repositorio...", file=sys.stderr)
        sys.stderr.flush()
        url_con_token = GITHUB_REPO_URL.replace("https://", f"https://{GITHUB_TOKEN}@")
        try:
            subprocess.run(["git", "clone", url_con_token, repo_path], check=True, capture_output=True)
            print("✅ Repositorio clonado", file=sys.stderr)
            sys.stderr.flush()
            return True
        except Exception as e:
            print(f"❌ Error clonando: {e}", file=sys.stderr)
            return False
    else:
        print("📂 Repositorio ya existe. Haciendo pull...", file=sys.stderr)
        try:
            subprocess.run(["git", "-C", repo_path, "pull"], check=True, capture_output=True)
            return True
        except Exception as e:
            print(f"❌ Error pull: {e}", file=sys.stderr)
            return False

def git_commit_and_push():
    if not GITHUB_TOKEN or not GITHUB_REPO_URL:
        print("⚠️ GitHub no configurado", file=sys.stderr)
        return False
    repo_path = os.path.join(os.getcwd(), CARPETA_REPO)
    if not os.path.exists(os.path.join(repo_path, ".git")):
        print("❌ Repositorio no inicializado", file=sys.stderr)
        return False
    shutil.copy2(__file__, os.path.join(repo_path, "app.py"))
    try:
        subprocess.run(["git", "-C", repo_path, "add", "app.py"], check=True, capture_output=True)
        mensaje = f"Auto-mejora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(["git", "-C", repo_path, "commit", "-m", mensaje], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo_path, "push"], check=True, capture_output=True)
        print(f"✅ Commit y push: {mensaje}", file=sys.stderr)
        sys.stderr.flush()
        return True
    except Exception as e:
        print(f"❌ Error git: {e}", file=sys.stderr)
        return False

# ============================================
# FUNCIÓN GEMINI
# ============================================

def llamar_gemini(pregunta):
    print(f"📤 Llamando a Gemini...", file=sys.stderr)
    sys.stderr.flush()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"role": "user", "parts": [{"text": pregunta}]}]}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        resultado = response.json()
        return resultado["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"❌ Error Gemini: {e}", file=sys.stderr)
        raise

# ============================================
# VALIDACIÓN Y APLICACIÓN DE MEJORAS
# ============================================

def validar_codigo(codigo):
    try:
        ast.parse(codigo)
        return True, "Código válido"
    except SyntaxError as e:
        return False, f"Error sintaxis: {e}"

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
        historial_mejoras.append({"timestamp": timestamp, "mejora": contenido[:500], "backup": backup_path})
        guardar_historial()
        print("📤 Subiendo mejora a GitHub...", file=sys.stderr)
        sys.stderr.flush()
        if git_commit_and_push():
            print("✅ Mejora subida a GitHub", file=sys.stderr)
        else:
            print("⚠️ No se pudo subir a GitHub", file=sys.stderr)
        sys.stderr.flush()
        print("🔄 Reiniciando en 5s...", file=sys.stderr)
        time.sleep(5)
        os._exit(0)
    except Exception as e:
        return False, str(e)

# ============================================
# GESTIÓN DE TAREAS
# ============================================

def obtener_siguiente_tarea():
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
    tarea = {"id": id_counter, "descripcion": descripcion, "estado": "pendiente", "fecha_creacion": datetime.now().isoformat()}
    tareas.append(tarea)
    id_counter += 1
    guardar_tareas()
    return tarea

def eliminar_tarea(tarea_id):
    global tareas
    tareas = [t for t in tareas if t["id"] != tarea_id]
    guardar_tareas()

# ============================================
# CICLO DE APRENDIZAJE
# ============================================

def aprender_y_mejorar():
    print("🧠 Iniciando ciclo de aprendizaje...", file=sys.stderr)
    sys.stderr.flush()
    tarea_actual = obtener_siguiente_tarea()
    if tarea_actual:
        objetivo = f"Resolver la tarea: '{tarea_actual['descripcion']}'"
        print(f"📋 Tarea en curso: {tarea_actual['descripcion']}", file=sys.stderr)
    else:
        objetivo = "Mejorar el sistema en general. Aprende algo nuevo."
        print("🧠 No hay tareas pendientes. Aprendizaje libre.", file=sys.stderr)
    sys.stderr.flush()
    prompt_contexto = f"""
    Eres el asistente Aether, un sistema autónomo que se mejora a sí mismo.
    OBJETIVO ACTUAL: {objetivo}
    Ya has implementado estas mejoras: {json.dumps(historial_mejoras[-5:], indent=2)}
    Responde ÚNICAMENTE con un bloque de código Python completo (todo el app.py) que reemplace al actual.
    Incluye TODAS las funciones existentes y añade la nueva funcionalidad.
    """
    try:
        respuesta = llamar_gemini(prompt_contexto)
        print(f"💡 Mejora generada", file=sys.stderr)
        sys.stderr.flush()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo_mejora = f"mejora_{timestamp}.txt"
        with open(archivo_mejora, "w") as f:
            f.write(respuesta)
        exito, mensaje = aplicar_mejora(archivo_mejora)
        if exito:
            if tarea_actual:
                marcar_tarea_completada(tarea_actual["id"])
                print(f"✅ Tarea completada", file=sys.stderr)
            print("🚀 Mejora aplicada. Reiniciando...", file=sys.stderr)
        else:
            print(f"⚠️ No se pudo aplicar: {mensaje}", file=sys.stderr)
        sys.stderr.flush()
        return exito
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.stderr.flush()
        return False

# ============================================
# BUCLE DE MANTENIMIENTO
# ============================================

def bucle_aprendizaje():
    print("🔄 Bucle iniciado. Esperando primer ciclo...", file=sys.stderr)
    sys.stderr.flush()
    while True:
        try:
            inicio = time.time()
            aprender_y_mejorar()
            try:
                requests.get(f"http://localhost:{os.environ.get('PORT', 10000)}/health", timeout=5)
                print("🔋 Ping enviado", file=sys.stderr)
            except Exception as e:
                print(f"❌ Ping error: {e}", file=sys.stderr)
            sys.stderr.flush()
            espera = max(0, INTERVALO_APRENDIZAJE - (time.time() - inicio))
            print(f"⏳ Próximo ciclo en {espera:.0f}s", file=sys.stderr)
            time.sleep(espera)
        except Exception as e:
            print(f"❌ Error crítico: {e}", file=sys.stderr)
            time.sleep(60)

# ============================================
# ENDPOINTS DE LA API
# ============================================

@app.route('/')
def home():
    return "🤖 Asistente Gemini vivo y funcionando"

@app.route('/health')
def health():
    return {"status": "ok"}

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.get_json()
        if not data or 'pregunta' not in data:
            return jsonify({"error": "Falta pregunta"}), 400
        pregunta = data['pregunta']
        respuesta = llamar_gemini(pregunta)
        return jsonify({"respuesta": respuesta})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/aprender', methods=['POST'])
def aprender_manual():
    print("🔧 /aprender llamado", file=sys.stderr)
    sys.stderr.flush()
    def wrapper():
        try:
            aprender_y_mejorar()
        except Exception as e:
            print(f"❌ Error en hilo: {e}", file=sys.stderr)
            sys.stderr.flush()
    threading.Thread(target=wrapper, daemon=True).start()
    return jsonify({"status": "ok", "message": "Ciclo iniciado"})

@app.route('/tareas', methods=['GET'])
def listar_tareas():
    return jsonify({
        "pendientes": [t for t in tareas if t["estado"] == "pendiente"],
        "completadas": [t for t in tareas if t["estado"] == "completada"],
        "total": len(tareas)
    })

@app.route('/tareas', methods=['POST'])
def crear_tarea():
    data = request.get_json()
    if not data or 'descripcion' not in data:
        return jsonify({"error": "Falta descripción"}), 400
    tarea = anadir_tarea(data['descripcion'])
    return jsonify({"status": "ok", "tarea": tarea}), 201

@app.route('/estado', methods=['GET'])
def estado_sistema():
    tarea_actual = obtener_siguiente_tarea()
    return jsonify({
        "tarea_actual": tarea_actual,
        "pendientes": len([t for t in tareas if t["estado"] == "pendiente"]),
        "completadas": len([t for t in tareas if t["estado"] == "completada"]),
        "total_mejoras": len(historial_mejoras),
        "ultima_mejora": historial_mejoras[-1] if historial_mejoras else None
    })

# ============================================
# INICIO
# ============================================

if __name__ == "__main__":
    print("🚀 Iniciando asistente...", file=sys.stderr)
    sys.stderr.flush()
    if GITHUB_TOKEN and GITHUB_REPO_URL:
        git_inicializar()
    else:
        print("⚠️ GitHub no configurado. No se podrá subir código.", file=sys.stderr)
    threading.Thread(target=bucle_aprendizaje, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)