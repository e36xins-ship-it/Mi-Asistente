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

# ============================================
# FALLBACK DE BASE DE DATOS
# ============================================

DB_TYPE = None  # 'postgres' o 'sqlite'
DB_CONN = None

# Intentar importar psycopg2 (versión 2)
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    DB_TYPE = 'postgres'
    print("✅ Usando psycopg2 (PostgreSQL)", file=sys.stderr)
except ImportError:
    try:
        # Intentar importar psycopg (versión 3)
        import psycopg
        from psycopg.rows import dict_row
        DB_TYPE = 'postgres'
        print("✅ Usando psycopg3 (PostgreSQL)", file=sys.stderr)
    except ImportError:
        # Si no hay PostgreSQL, usar SQLite (incluido en Python)
        import sqlite3
        DB_TYPE = 'sqlite'
        print("⚠️ No se encontró psycopg2. Usando SQLite como fallback.", file=sys.stderr)

# ============================================
# FUNCIONES DE BASE DE DATOS (adaptativas)
# ============================================

def get_db_connection():
    global DB_CONN
    if DB_TYPE == 'postgres':
        DATABASE_URL = os.environ.get("DATABASE_URL")
        if not DATABASE_URL:
            raise Exception("DATABASE_URL no configurada para PostgreSQL")
        if DB_CONN is None or DB_CONN.closed:
            if 'psycopg2' in sys.modules:
                DB_CONN = psycopg2.connect(DATABASE_URL)
            else:
                DB_CONN = psycopg.connect(DATABASE_URL)
        return DB_CONN
    else:
        # SQLite: crear archivo local
        if DB_CONN is None:
            DB_CONN = sqlite3.connect('data.db', check_same_thread=False)
            DB_CONN.row_factory = sqlite3.Row
        return DB_CONN

def init_db():
    """Crea las tablas si no existen (adaptado a SQLite o PostgreSQL)."""
    conn = get_db_connection()
    
    if DB_TYPE == 'sqlite':
        # SQLite: usa executescript() para múltiples sentencias
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tareas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descripcion TEXT NOT NULL,
                estado TEXT DEFAULT 'pendiente',
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_completada TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                mejora TEXT,
                backup_path TEXT
            );
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS memoria_episodica (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pregunta TEXT,
                respuesta TEXT,
                leccion TEXT
            );
            CREATE TABLE IF NOT EXISTS memoria_semantica (
                key TEXT PRIMARY KEY,
                value TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    else:
        # PostgreSQL
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tareas (
                id SERIAL PRIMARY KEY,
                descripcion TEXT NOT NULL,
                estado TEXT DEFAULT 'pendiente',
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_completada TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS historial (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                mejora TEXT,
                backup_path TEXT
            );
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS memoria_episodica (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pregunta TEXT,
                respuesta TEXT,
                leccion TEXT
            );
            CREATE TABLE IF NOT EXISTS memoria_semantica (
                key TEXT PRIMARY KEY,
                value TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
    
    conn.close()

# Inicializar DB al arrancar
init_db()

# ============================================
# FUNCIONES DE ACCESO A DATOS (adaptativas)
# ============================================

def db_get_tareas():
    conn = get_db_connection()
    if DB_TYPE == 'postgres':
        if 'psycopg2' in sys.modules:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM tareas ORDER BY id")
            tareas = cur.fetchall()
        else:
            cur = conn.cursor(row_factory=dict_row)
            cur.execute("SELECT * FROM tareas ORDER BY id")
            tareas = cur.fetchall()
    else:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tareas ORDER BY id")
        tareas = [dict(row) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return tareas

def db_add_tarea(descripcion):
    conn = get_db_connection()
    cur = conn.cursor()
    if DB_TYPE == 'postgres':
        cur.execute(
            "INSERT INTO tareas (descripcion) VALUES (%s) RETURNING id",
            (descripcion,)
        )
        tarea_id = cur.fetchone()[0]
    else:
        cur.execute(
            "INSERT INTO tareas (descripcion) VALUES (?)",
            (descripcion,)
        )
        tarea_id = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return tarea_id

def db_marcar_completada(tarea_id):
    conn = get_db_connection()
    cur = conn.cursor()
    if DB_TYPE == 'postgres':
        cur.execute(
            "UPDATE tareas SET estado = 'completada', fecha_completada = CURRENT_TIMESTAMP WHERE id = %s",
            (tarea_id,)
        )
    else:
        cur.execute(
            "UPDATE tareas SET estado = 'completada', fecha_completada = CURRENT_TIMESTAMP WHERE id = ?",
            (tarea_id,)
        )
    conn.commit()
    cur.close()
    conn.close()

def db_guardar_historial(mejora, backup_path):
    conn = get_db_connection()
    cur = conn.cursor()
    if DB_TYPE == 'postgres':
        cur.execute(
            "INSERT INTO historial (mejora, backup_path) VALUES (%s, %s)",
            (mejora[:500], backup_path)
        )
    else:
        cur.execute(
            "INSERT INTO historial (mejora, backup_path) VALUES (?, ?)",
            (mejora[:500], backup_path)
        )
    conn.commit()
    cur.close()
    conn.close()

def db_get_historial(limit=5):
    conn = get_db_connection()
    cur = conn.cursor()
    if DB_TYPE == 'postgres':
        if 'psycopg2' in sys.modules:
            cur.execute("SELECT * FROM historial ORDER BY timestamp DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
            historial = [dict(row) for row in rows]
        else:
            cur.execute("SELECT * FROM historial ORDER BY timestamp DESC LIMIT %s", (limit,))
            rows = cur.fetchall()
            historial = [dict(row) for row in rows]
    else:
        cur.execute("SELECT * FROM historial ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        historial = [dict(row) for row in rows]
    cur.close()
    conn.close()
    return historial

def db_get_config(key):
    conn = get_db_connection()
    cur = conn.cursor()
    if DB_TYPE == 'postgres':
        cur.execute("SELECT value FROM config WHERE key = %s", (key,))
    else:
        cur.execute("SELECT value FROM config WHERE key = ?", (key,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

def db_set_config(key, value):
    conn = get_db_connection()
    cur = conn.cursor()
    if DB_TYPE == 'postgres':
        cur.execute(
            "INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (key, value)
        )
    else:
        cur.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            (key, value)
        )
    conn.commit()
    cur.close()
    conn.close()

def db_get_all_config():
    conn = get_db_connection()
    cur = conn.cursor()
    if DB_TYPE == 'postgres':
        cur.execute("SELECT key, value FROM config")
        rows = cur.fetchall()
        if 'psycopg2' in sys.modules:
            config = {row['key']: row['value'] for row in rows}
        else:
            config = {row['key']: row['value'] for row in rows}
    else:
        cur.execute("SELECT key, value FROM config")
        rows = cur.fetchall()
        config = {row[0]: row[1] for row in rows}
    cur.close()
    conn.close()
    return config

# ============================================
# CONFIGURACIÓN DE ENTORNO
# ============================================

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO_URL = os.environ.get("GITHUB_REPO_URL")

INTERVALO_APRENDIZAJE = 600  # 10 minutos
CARPETA_BACKUPS = "backups"
CARPETA_REPO = "repo"
os.makedirs(CARPETA_BACKUPS, exist_ok=True)
os.makedirs(CARPETA_REPO, exist_ok=True)

# ============================================
# GESTIÓN DE PROVEEDORES (desde DB)
# ============================================

def get_provider_config():
    """Carga la configuración de proveedores desde la base de datos."""
    config = db_get_all_config()
    providers = {}
    for provider in ['gemini', 'deepseek', 'openai', 'anthropic']:
        api_key = config.get(f"{provider}_api_key")
        if api_key:
            if provider == 'gemini':
                providers[provider] = {
                    "type": "gemini",
                    "api_key": api_key,
                    "model": config.get(f"{provider}_model", "gemini-3.5-flash"),
                    "priority": int(config.get(f"{provider}_priority", 1))
                }
            elif provider == 'deepseek':
                providers[provider] = {
                    "type": "openai_compatible",
                    "api_key": api_key,
                    "base_url": "https://api.deepseek.com",
                    "model": config.get(f"{provider}_model", "deepseek-v4-flash"),
                    "priority": int(config.get(f"{provider}_priority", 2))
                }
            elif provider == 'openai':
                providers[provider] = {
                    "type": "openai_compatible",
                    "api_key": api_key,
                    "base_url": "https://api.openai.com/v1",
                    "model": config.get(f"{provider}_model", "gpt-4o-mini"),
                    "priority": int(config.get(f"{provider}_priority", 3))
                }
            elif provider == 'anthropic':
                providers[provider] = {
                    "type": "anthropic",
                    "api_key": api_key,
                    "model": config.get(f"{provider}_model", "claude-3-5-haiku-20241022"),
                    "priority": int(config.get(f"{provider}_priority", 4))
                }
    return providers

# ============================================
# FUNCIONES DE LLAMADA A MODELOS (con fallback)
# ============================================

def _llamar_gemini(pregunta, provider):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{provider['model']}:generateContent?key={provider['api_key']}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": pregunta}]
        }]
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]

def _llamar_openai_compatible(pregunta, provider):
    from openai import OpenAI
    client = OpenAI(api_key=provider['api_key'], base_url=provider['base_url'])
    response = client.chat.completions.create(
        model=provider['model'],
        messages=[{"role": "user", "content": pregunta}]
    )
    return response.choices[0].message.content

def _llamar_anthropic(pregunta, provider):
    from anthropic import Anthropic
    client = Anthropic(api_key=provider['api_key'])
    response = client.messages.create(
        model=provider['model'],
        max_tokens=1024,
        messages=[{"role": "user", "content": pregunta}]
    )
    return response.content[0].text

def llamar_modelo(pregunta, proveedores_preferidos=None):
    """
    Llama al primer proveedor disponible con fallback automático.
    """
    providers = get_provider_config()
    if not providers:
        raise Exception("No hay proveedores configurados. Usa /config para añadir claves.")

    if proveedores_preferidos is None:
        proveedores_preferidos = sorted(providers.keys(), key=lambda p: providers[p]['priority'])

    ultimo_error = None
    for provider_name in proveedores_preferidos:
        if provider_name not in providers:
            continue
        provider = providers[provider_name]
        try:
            print(f"📤 Intentando con {provider_name}...", file=sys.stderr)
            sys.stderr.flush()
            if provider['type'] == 'gemini':
                respuesta = _llamar_gemini(pregunta, provider)
            elif provider['type'] == 'openai_compatible':
                respuesta = _llamar_openai_compatible(pregunta, provider)
            elif provider['type'] == 'anthropic':
                respuesta = _llamar_anthropic(pregunta, provider)
            else:
                continue
            print(f"✅ {provider_name} respondió con éxito", file=sys.stderr)
            sys.stderr.flush()
            return respuesta
        except Exception as e:
            print(f"❌ {provider_name} falló: {e}", file=sys.stderr)
            ultimo_error = e
            sys.stderr.flush()
            continue

    raise Exception(f"Todos los proveedores fallaron. Último error: {ultimo_error}")

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
        db_guardar_historial(contenido[:500], backup_path)
        print("📤 Subiendo mejora a GitHub...", file=sys.stderr)
        sys.stderr.flush()
        if GITHUB_TOKEN and GITHUB_REPO_URL:
            git_commit_and_push()
        else:
            print("⚠️ GitHub no configurado. Mejora guardada en DB.", file=sys.stderr)
        sys.stderr.flush()
        print("🔄 Reiniciando en 5s...", file=sys.stderr)
        time.sleep(5)
        os._exit(0)
    except Exception as e:
        return False, str(e)

# ============================================
# GIT AUTOMÁTICO
# ============================================

def git_inicializar():
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
# CICLO DE APRENDIZAJE
# ============================================

def aprender_y_mejorar():
    print("🧠 Iniciando ciclo de aprendizaje...", file=sys.stderr)
    sys.stderr.flush()

    # Obtener tareas pendientes desde DB
    tareas = db_get_tareas()
    tarea_actual = None
    for t in tareas:
        if t['estado'] == 'pendiente':
            tarea_actual = t
            break

    if tarea_actual:
        objetivo = f"Resolver la tarea: '{tarea_actual['descripcion']}'"
        print(f"📋 Tarea en curso: {tarea_actual['descripcion']}", file=sys.stderr)
    else:
        objetivo = "Mejorar el sistema en general. Aprende algo nuevo."
        print("🧠 No hay tareas pendientes. Aprendizaje libre.", file=sys.stderr)
    sys.stderr.flush()

    historial = db_get_historial(5)
    prompt_contexto = f"""
    Eres el asistente Aether, un sistema autónomo que se mejora a sí mismo.
    OBJETIVO ACTUAL: {objetivo}
    Mejoras anteriores: {json.dumps(historial, indent=2)}
    Responde ÚNICAMENTE con un bloque de código Python completo (todo el app.py) que reemplace al actual.
    Incluye TODAS las funciones existentes y añade la nueva funcionalidad.
    """

    try:
        respuesta = llamar_modelo(prompt_contexto)
        print(f"💡 Mejora generada", file=sys.stderr)
        sys.stderr.flush()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo_mejora = f"mejora_{timestamp}.txt"
        with open(archivo_mejora, "w") as f:
            f.write(respuesta)
        exito, mensaje = aplicar_mejora(archivo_mejora)
        if exito:
            if tarea_actual:
                db_marcar_completada(tarea_actual['id'])
                print(f"✅ Tarea '{tarea_actual['descripcion']}' completada.", file=sys.stderr)
            print("🚀 Mejora aplicada. Reiniciando...", file=sys.stderr)
        else:
            print(f"⚠️ No se pudo aplicar: {mensaje}", file=sys.stderr)
        sys.stderr.flush()
        return exito
    except Exception as e:
        print(f"❌ Error en ciclo: {e}", file=sys.stderr)
        sys.stderr.flush()
        return False

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

app = Flask(__name__)

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
        respuesta = llamar_modelo(pregunta)
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
    tareas = db_get_tareas()
    return jsonify({
        "pendientes": [t for t in tareas if t['estado'] == 'pendiente'],
        "completadas": [t for t in tareas if t['estado'] == 'completada'],
        "total": len(tareas)
    })

@app.route('/tareas', methods=['POST'])
def crear_tarea():
    data = request.get_json()
    if not data or 'descripcion' not in data:
        return jsonify({"error": "Falta descripción"}), 400
    tarea_id = db_add_tarea(data['descripcion'])
    return jsonify({"status": "ok", "id": tarea_id}), 201

@app.route('/estado', methods=['GET'])
def estado_sistema():
    tareas = db_get_tareas()
    pendientes = [t for t in tareas if t['estado'] == 'pendiente']
    completadas = [t for t in tareas if t['estado'] == 'completada']
    historial = db_get_historial(1)
    return jsonify({
        "tarea_actual": pendientes[0] if pendientes else None,
        "pendientes": len(pendientes),
        "completadas": len(completadas),
        "total_mejoras": len(db_get_historial(100)),
        "ultima_mejora": historial[0] if historial else None
    })

@app.route('/config', methods=['POST'])
def configurar_proveedor():
    """Configura una clave API para un proveedor."""
    data = request.get_json()
    if not data or 'provider' not in data or 'api_key' not in data:
        return jsonify({"error": "Falta provider o api_key"}), 400
    provider = data['provider']
    api_key = data['api_key']
    if provider not in ['gemini', 'deepseek', 'openai', 'anthropic']:
        return jsonify({"error": "Provider no soportado"}), 400
    db_set_config(f"{provider}_api_key", api_key)
    if 'model' in data:
        db_set_config(f"{provider}_model", data['model'])
    if 'priority' in data:
        db_set_config(f"{provider}_priority", str(data['priority']))
    return jsonify({"status": "ok", "message": f"Clave para {provider} guardada"})

@app.route('/orden', methods=['POST'])
def recibir_orden():
    """Recibe órdenes desde PowerShell u otros."""
    data = request.get_json()
    if not data or 'orden' not in data:
        return jsonify({"error": "Falta la orden"}), 400
    orden = data['orden']
    print(f"📨 Orden recibida: {orden}", file=sys.stderr)
    sys.stderr.flush()
    if orden.startswith("/tarea"):
        descripcion = orden[7:].strip()
        if descripcion:
            tarea_id = db_add_tarea(descripcion)
            return jsonify({"status": "ok", "message": f"Tarea añadida (ID {tarea_id})"})
        else:
            return jsonify({"error": "Falta descripción"}), 400
    elif orden.startswith("/aprender"):
        threading.Thread(target=aprender_y_mejorar, daemon=True).start()
        return jsonify({"status": "ok", "message": "Aprendizaje iniciado"})
    elif orden.startswith("/config"):
        parts = orden.split()
        if len(parts) >= 3:
            provider = parts[1]
            api_key = parts[2]
            db_set_config(f"{provider}_api_key", api_key)
            return jsonify({"status": "ok", "message": f"Clave para {provider} guardada"})
        else:
            return jsonify({"error": "Formato: /config <provider> <api_key>"}), 400
    else:
        return jsonify({"error": "Orden no reconocida"}), 400

# ============================================
# INICIO DEL SERVICIO
# ============================================

if __name__ == "__main__":
    print(f"🚀 Iniciando asistente con base de datos: {DB_TYPE}", file=sys.stderr)
    sys.stderr.flush()
    if GITHUB_TOKEN and GITHUB_REPO_URL:
        git_inicializar()
    else:
        print("⚠️ GitHub no configurado. No se podrá subir código.", file=sys.stderr)
    threading.Thread(target=bucle_aprendizaje, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)