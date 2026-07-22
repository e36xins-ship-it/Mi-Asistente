#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aether — Asistente Autónomo con Auto-mejora Persistente
Versión: 5.1 (con gestor de memoria y modificación directa de archivos)
"""

import os
import sys
import json
import time
import ast
import re
import shutil
import subprocess
import threading
import tempfile
import traceback
import base64
import signal
import atexit
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import deque, Counter
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import psycopg2
from psycopg2.extras import RealDictCursor

# ============================================================
# CONFIGURACIÓN
# ============================================================

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no configurada.")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO_URL = os.environ.get("GITHUB_REPO_URL")

INTERVALO_APRENDIZAJE = 600
BACKUP_DIR = "backups"
REPO_DIR = "repo"

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(REPO_DIR, exist_ok=True)

# ============================================================
# APP Y CORS
# ============================================================

app = Flask(__name__)
CORS(app)  # Permite peticiones desde cualquier origen

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, RealDictCursor):
            return dict(obj)
        return super().default(obj)

app.json_encoder = CustomJSONEncoder

# ============================================================
# GESTOR DE MEMORIA (AETHER)
# ============================================================

class AetherMemory:
    """Gestor de memoria reciente con deque, TTL y persistencia JSON."""

    def __init__(self, maxlen: int = 100, ttl_seconds: int = 3600, filepath: str = "aether_memory.json"):
        self._deque = deque(maxlen=maxlen)
        self._ttl = timedelta(seconds=ttl_seconds)
        self._filepath = filepath
        self._lock = threading.RLock()
        self._load()
        atexit.register(self._save)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        self._save()
        sys.exit(0)

    def _load(self):
        if os.path.exists(self._filepath):
            try:
                with open(self._filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._deque = deque(data.get("entries", []), maxlen=self._deque.maxlen)
            except (json.JSONDecodeError, IOError):
                self._deque = deque(maxlen=self._deque.maxlen)

    def _save(self):
        with self._lock:
            now = datetime.now()
            valid_entries = [entry for entry in self._deque if now - datetime.fromisoformat(entry["timestamp"]) < self._ttl]
            data = {"entries": valid_entries, "saved_at": now.isoformat()}
            try:
                with open(self._filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except IOError:
                pass

    def add(self, content: str, metadata: dict = None):
        entry = {
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        with self._lock:
            self._deque.append(entry)
            self._cleanup_expired()

    def get(self, limit: int = None, since: datetime = None) -> list:
        with self._lock:
            self._cleanup_expired()
            entries = list(self._deque)
            if since:
                entries = [e for e in entries if datetime.fromisoformat(e["timestamp"]) >= since]
            if limit:
                entries = entries[-limit:]
            return entries

    def _cleanup_expired(self):
        now = datetime.now()
        while self._deque and (now - datetime.fromisoformat(self._deque[0]["timestamp"]) >= self._ttl):
            self._deque.popleft()

    def clear(self):
        with self._lock:
            self._deque.clear()
            self._save()

    def stats(self) -> dict:
        with self._lock:
            self._cleanup_expired()
            return {
                "count": len(self._deque),
                "capacity": self._deque.maxlen,
                "usage_percent": (len(self._deque) / self._deque.maxlen * 100) if self._deque.maxlen else 0,
                "oldest_entry": self._deque[0]["timestamp"] if self._deque else None,
                "newest_entry": self._deque[-1]["timestamp"] if self._deque else None
            }

aether = AetherMemory()

# ============================================================
# FUNCIONES DE MODIFICACIÓN DIRECTA DE ARCHIVOS (FUNCIONALES)
# ============================================================

def modificar_requirements(linea):
    """Añade una línea al final de requirements.txt en el directorio de trabajo."""
    path = os.path.join(os.getcwd(), "requirements.txt")
    try:
        with open(path, "a") as f:
            f.write(f"\n{linea}")
        print(f"✅ Línea '{linea}' añadida a requirements.txt", file=sys.stderr)
        return True
    except Exception as e:
        print(f"❌ Error al modificar requirements.txt: {e}", file=sys.stderr)
        return False

def modificar_app(linea):
    """Añade una línea al final de app.py (antes de la última línea) en el directorio de trabajo."""
    path = os.path.join(os.getcwd(), "app.py")
    try:
        with open(path, "r") as f:
            lineas = f.readlines()
        if len(lineas) > 1:
            lineas.insert(-1, f"{linea}\n")
        else:
            lineas.append(f"{linea}\n")
        with open(path, "w") as f:
            f.writelines(lineas)
        print(f"✅ Línea '{linea}' añadida a app.py", file=sys.stderr)
        return True
    except Exception as e:
        print(f"❌ Error al modificar app.py: {e}", file=sys.stderr)
        return False

def subir_app_por_api():
    """Sube app.py a GitHub usando la API, sin depender de git push."""
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN no configurado", file=sys.stderr)
        return False
    
    try:
        with open(os.path.join(os.getcwd(), "app.py"), "r") as f:
            contenido = f.read()
        contenido_b64 = base64.b64encode(contenido.encode()).decode()
        
        api_url = "https://api.github.com/repos/e36xins-ship-it/Mi-Asistente/contents/app.py"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.get(api_url, headers=headers)
        sha = None
        if response.status_code == 200:
            sha = response.json().get("sha")
        
        payload = {
            "message": "Actualización automática de app.py desde Aether",
            "content": contenido_b64,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha
        
        response = requests.put(api_url, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            print("✅ app.py actualizado en GitHub mediante API", file=sys.stderr)
            return True
        else:
            print(f"❌ API de GitHub falló: {response.status_code} - {response.text}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"❌ Error subiendo app.py por API: {e}", file=sys.stderr)
        return False

def subir_requirements_por_api():
    """Sube requirements.txt a GitHub usando la API."""
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN no configurado", file=sys.stderr)
        return False
    
    try:
        with open(os.path.join(os.getcwd(), "requirements.txt"), "r") as f:
            contenido = f.read()
        contenido_b64 = base64.b64encode(contenido.encode()).decode()
        
        api_url = "https://api.github.com/repos/e36xins-ship-it/Mi-Asistente/contents/requirements.txt"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.get(api_url, headers=headers)
        sha = None
        if response.status_code == 200:
            sha = response.json().get("sha")
        
        payload = {
            "message": "Actualización automática de requirements.txt desde Aether",
            "content": contenido_b64,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha
        
        response = requests.put(api_url, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            print("✅ requirements.txt actualizado en GitHub mediante API", file=sys.stderr)
            return True
        else:
            print(f"❌ API de GitHub falló: {response.status_code} - {response.text}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"❌ Error subiendo requirements.txt por API: {e}", file=sys.stderr)
        return False

# ============================================================
# CONEXIÓN A POSTGRESQL
# ============================================================

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    # (Tablas ya definidas en versiones anteriores)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tareas (
            id SERIAL PRIMARY KEY,
            descripcion TEXT NOT NULL,
            estado TEXT DEFAULT 'pendiente',
            prioridad INTEGER DEFAULT 0,
            creada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completada_en TIMESTAMP,
            intentos INTEGER DEFAULT 0,
            ultimo_error TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS historial (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            mejora TEXT,
            backup_path TEXT,
            estado TEXT DEFAULT 'aplicada'
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS memoria_episodica (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pregunta TEXT,
            respuesta TEXT,
            leccion TEXT,
            exito BOOLEAN DEFAULT TRUE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS memoria_semantica (
            key TEXT PRIMARY KEY,
            value TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            descripcion TEXT,
            codigo TEXT,
            activo BOOLEAN DEFAULT TRUE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fallos (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tarea_id INTEGER,
            error TEXT,
            stack_trace TEXT,
            resuelto BOOLEAN DEFAULT FALSE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS microtareas (
            id SERIAL PRIMARY KEY,
            descripcion TEXT NOT NULL,
            estimado_minutos INTEGER DEFAULT 5,
            estado TEXT DEFAULT 'pendiente',
            creada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            iniciada_en TIMESTAMP,
            completada_en TIMESTAMP,
            intentos INTEGER DEFAULT 0,
            ultimo_error TEXT,
            prioridad INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Base de datos inicializada", file=sys.stderr)

init_db()

# ============================================================
# FUNCIONES DE BASE DE DATOS
# ============================================================

def db_get_tareas(estado=None):
    conn = get_db_connection()
    cur = conn.cursor()
    if estado:
        cur.execute("SELECT * FROM tareas WHERE estado = %s ORDER BY prioridad DESC, creada_en", (estado,))
    else:
        cur.execute("SELECT * FROM tareas ORDER BY prioridad DESC, creada_en")
    result = cur.fetchall()
    cur.close()
    conn.close()
    return result

def db_add_tarea(descripcion, prioridad=0):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO tareas (descripcion, prioridad) VALUES (%s, %s) RETURNING id", (descripcion, prioridad))
    tarea_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return tarea_id

def db_marcar_completada(tarea_id, error=None):
    conn = get_db_connection()
    cur = conn.cursor()
    if error:
        cur.execute("UPDATE tareas SET estado = 'fallida', completada_en = CURRENT_TIMESTAMP, intentos = intentos + 1, ultimo_error = %s WHERE id = %s", (error, tarea_id))
    else:
        cur.execute("UPDATE tareas SET estado = 'completada', completada_en = CURRENT_TIMESTAMP WHERE id = %s", (tarea_id,))
    conn.commit()
    cur.close()
    conn.close()

def db_get_microtarea_pendiente():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM microtareas WHERE estado = 'pendiente' ORDER BY prioridad DESC, creada_en LIMIT 1")
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result

def db_add_microtarea(descripcion, estimado_minutos=5, prioridad=0):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO microtareas (descripcion, estimado_minutos, prioridad) VALUES (%s, %s, %s) RETURNING id", (descripcion, estimado_minutos, prioridad))
    microtarea_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return microtarea_id

def db_microtarea_iniciada(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE microtareas SET estado = 'en_progreso', iniciada_en = CURRENT_TIMESTAMP, intentos = intentos + 1 WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()

def db_microtarea_completada(id, exito=True, error=None):
    conn = get_db_connection()
    cur = conn.cursor()
    if exito:
        cur.execute("UPDATE microtareas SET estado = 'completada', completada_en = CURRENT_TIMESTAMP WHERE id = %s", (id,))
    else:
        cur.execute("UPDATE microtareas SET estado = 'fallida', completada_en = CURRENT_TIMESTAMP, ultimo_error = %s WHERE id = %s", (error, id))
    conn.commit()
    cur.close()
    conn.close()

def db_guardar_historial(mejora, backup_path, estado="aplicada"):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO historial (mejora, backup_path, estado) VALUES (%s, %s, %s) RETURNING id", (mejora[:500], backup_path, estado))
    historial_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return historial_id

def db_get_historial(limit=10):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM historial ORDER BY timestamp DESC LIMIT %s", (limit,))
    result = cur.fetchall()
    cur.close()
    conn.close()
    return result

def db_get_config(key):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM config WHERE key = %s", (key,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["value"] if row else None

def db_set_config(key, value):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (key, value))
    conn.commit()
    cur.close()
    conn.close()

def db_get_all_config():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM config")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

def db_guardar_checkpoint(descripcion, codigo):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE checkpoints SET activo = FALSE WHERE activo = TRUE")
    cur.execute("INSERT INTO checkpoints (descripcion, codigo, activo) VALUES (%s, %s, TRUE) RETURNING id", (descripcion, codigo))
    checkpoint_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return checkpoint_id

def db_get_checkpoint_activo():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM checkpoints WHERE activo = TRUE ORDER BY id DESC LIMIT 1")
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result

def db_rollback_checkpoint(checkpoint_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT codigo FROM checkpoints WHERE id = %s", (checkpoint_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return None
    codigo = row["codigo"]
    cur.execute("UPDATE checkpoints SET activo = FALSE WHERE id = %s", (checkpoint_id,))
    conn.commit()
    cur.close()
    conn.close()
    return codigo

def db_registrar_fallo(tarea_id, error, stack_trace):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO fallos (tarea_id, error, stack_trace) VALUES (%s, %s, %s)", (tarea_id, error[:500], stack_trace[:1000]))
    conn.commit()
    cur.close()
    conn.close()

def db_guardar_memoria_episodica(pregunta, respuesta, leccion, exito=True):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO memoria_episodica (pregunta, respuesta, leccion, exito) VALUES (%s, %s, %s, %s)", (pregunta, respuesta[:500], leccion[:500], exito))
    conn.commit()
    cur.close()
    conn.close()

def db_get_memoria_episodica(limit=10):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM memoria_episodica ORDER BY timestamp DESC LIMIT %s", (limit,))
    result = cur.fetchall()
    cur.close()
    conn.close()
    return result

# ============================================================
# GESTIÓN DE PROVEEDORES (MULTI-LLM)
# ============================================================

def get_provider_config():
    config = db_get_all_config()
    providers = {}
    env_mapping = {
        'openrouter': 'OPENROUTER_API_KEY',
        'gemini': 'GEMINI_API_KEY',
        'deepseek': 'DEEPSEEK_API_KEY',
        'openai': 'OPENAI_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
        'groq': 'GROQ_API_KEY'
    }
    for provider, env_var in env_mapping.items():
        api_key = config.get(f"{provider}_api_key")
        if not api_key:
            api_key = os.environ.get(env_var)
        if api_key:
            if provider == 'openrouter':
                providers[provider] = {
                    "type": "openrouter",
                    "api_key": api_key,
                    "base_url": "https://openrouter.ai/api/v1",
                    "model": config.get(f"{provider}_model", "openrouter/free"),
                    "priority": int(config.get(f"{provider}_priority", 1))
                }
            elif provider == 'gemini':
                providers[provider] = {"type": "gemini", "api_key": api_key, "model": config.get(f"{provider}_model", "gemini-3.5-flash"), "priority": int(config.get(f"{provider}_priority", 2))}
            elif provider == 'deepseek':
                providers[provider] = {"type": "openai_compatible", "api_key": api_key, "base_url": "https://api.deepseek.com", "model": config.get(f"{provider}_model", "deepseek-v4-flash"), "priority": int(config.get(f"{provider}_priority", 3))}
            elif provider == 'openai':
                providers[provider] = {"type": "openai_compatible", "api_key": api_key, "base_url": "https://api.openai.com/v1", "model": config.get(f"{provider}_model", "gpt-4o-mini"), "priority": int(config.get(f"{provider}_priority", 4))}
            elif provider == 'anthropic':
                providers[provider] = {"type": "anthropic", "api_key": api_key, "model": config.get(f"{provider}_model", "claude-3-5-haiku-20241022"), "priority": int(config.get(f"{provider}_priority", 5))}
            elif provider == 'groq':
                providers[provider] = {"type": "openai_compatible", "api_key": api_key, "base_url": "https://api.groq.com/openai/v1", "model": config.get(f"{provider}_model", "llama-3.3-70b-versatile"), "priority": int(config.get(f"{provider}_priority", 6))}
    return providers

# ============================================================
# LLAMADA A MODELOS
# ============================================================

def _llamar_openrouter(pregunta, provider):
    url = f"{provider['base_url']}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {provider['api_key']}"
    }
    payload = {
        "model": provider['model'],
        "messages": [{"role": "user", "content": pregunta}]
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def _llamar_gemini(pregunta, provider):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{provider['model']}:generateContent?key={provider['api_key']}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"role": "user", "parts": [{"text": pregunta}]}]}
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]

def _llamar_openai_compatible(pregunta, provider):
    from openai import OpenAI
    client = OpenAI(api_key=provider['api_key'], base_url=provider['base_url'])
    response = client.chat.completions.create(model=provider['model'], messages=[{"role": "user", "content": pregunta}])
    return response.choices[0].message.content

def _llamar_anthropic(pregunta, provider):
    from anthropic import Anthropic
    client = Anthropic(api_key=provider['api_key'])
    response = client.messages.create(model=provider['model'], max_tokens=1024, messages=[{"role": "user", "content": pregunta}])
    return response.content[0].text

def llamar_modelo(pregunta, proveedores_preferidos=None):
    providers = get_provider_config()
    if not providers:
        raise Exception("No hay proveedores configurados.")
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
            if provider['type'] == 'openrouter':
                respuesta = _llamar_openrouter(pregunta, provider)
            elif provider['type'] == 'gemini':
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

# ============================================================
# VALIDACIÓN DE CÓDIGO
# ============================================================

def validar_sintaxis(codigo: str) -> Tuple[bool, str]:
    try:
        ast.parse(codigo)
        return True, "Sintaxis válida"
    except SyntaxError as e:
        return False, f"Error de sintaxis: {e}"

def validar_semantica(codigo: str, timeout: int = 10) -> Tuple[bool, str]:
    try:
        compile(codigo, '<string>', 'exec')
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(codigo)
            temp_path = f.name
        try:
            result = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, '{os.path.dirname(temp_path)}'); import {os.path.splitext(os.path.basename(temp_path))[0]}"], capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                return False, f"Error de importación:\n{result.stderr}"
            return True, "Código semánticamente válido"
        finally:
            os.unlink(temp_path)
    except subprocess.TimeoutExpired:
        return False, f"Tiempo de ejecución excedido ({timeout}s)"
    except Exception as e:
        return False, f"Error en validación semántica: {e}"

def validar_codigo_completo(codigo: str) -> Tuple[bool, str, Optional[str]]:
    sintaxis_ok, sintaxis_msg = validar_sintaxis(codigo)
    if not sintaxis_ok:
        return False, sintaxis_msg, None
    semantica_ok, semantica_msg = validar_semantica(codigo)
    if not semantica_ok:
        return False, semantica_msg, None
    return True, "Código válido", None

# ============================================================
# CHECKPOINT Y ROLLBACK
# ============================================================

def guardar_checkpoint(descripcion: str = "") -> int:
    with open(__file__, 'r') as f:
        codigo = f.read()
    return db_guardar_checkpoint(descripcion or f"Checkpoint {datetime.now().isoformat()}", codigo)

def restaurar_checkpoint(checkpoint_id: int = None) -> bool:
    if checkpoint_id is None:
        checkpoint = db_get_checkpoint_activo()
        if not checkpoint:
            return False
        checkpoint_id = checkpoint["id"]
    codigo = db_rollback_checkpoint(checkpoint_id)
    if codigo is None:
        return False
    valido, msg, _ = validar_codigo_completo(codigo)
    if not valido:
        print(f"❌ Checkpoint {checkpoint_id} no válido: {msg}", file=sys.stderr)
        return False
    with open(__file__, 'w') as f:
        f.write(codigo)
    print(f"✅ Restaurado checkpoint {checkpoint_id}", file=sys.stderr)
    return True

# ============================================================
# AUTO-MEJORA (Ciclo de Aprendizaje)
# ============================================================

def generar_mejora(objetivo: str, historial: List[Dict]) -> Optional[str]:
    prompt = f"""
Eres Aether, un asistente autónomo que se mejora a sí mismo editando su propio código.

OBJETIVO ACTUAL: {objetivo}

INSTRUCCIONES ESTRICTAS:
1. Responde ÚNICAMENTE con el código Python completo del archivo app.py.
2. El código debe ser la versión completa y funcional del archivo, con la mejora solicitada aplicada.
3. NO incluyas explicaciones, introducciones, ni texto fuera del código.
4. NO uses comillas triples para otro fin que no sea el bloque de código.
5. El bloque de código debe estar encerrado entre ```python y ```.

Mejoras anteriores (para contexto): {json.dumps(historial[-5:], indent=2, default=str)}

Genera el código completo de app.py con la mejora solicitada.
"""
    try:
        respuesta = llamar_modelo(prompt)
        return respuesta
    except Exception as e:
        print(f"❌ Error generando mejora: {e}", file=sys.stderr)
        return None

def extraer_codigo(respuesta: str) -> Optional[str]:
    patron = r"```python\n(.*?)```"
    match = re.search(patron, respuesta, re.DOTALL)
    if match:
        return match.group(1).strip()
    if "import" in respuesta and "def " in respuesta:
        return respuesta.strip()
    return None

def aplicar_mejora(codigo: str) -> Tuple[bool, str]:
    valido, msg, _ = validar_codigo_completo(codigo)
    if not valido:
        return False, f"Validación fallida: {msg}"
    checkpoint_id = guardar_checkpoint("Antes de mejora")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"app_backup_{timestamp}.py")
    with open(__file__, 'r') as f_orig:
        with open(backup_path, 'w') as f_backup:
            f_backup.write(f_orig.read())
    try:
        with open(__file__, 'w') as f:
            f.write(codigo)
        db_guardar_historial(codigo[:500], backup_path, "aplicada")
        return True, f"Mejora aplicada. Checkpoint: {checkpoint_id}"
    except Exception as e:
        restaurar_checkpoint(checkpoint_id)
        return False, f"Error aplicando mejora: {e}"

def ejecutar_microtarea(microtarea: Dict) -> bool:
    tarea_id = microtarea["id"]
    descripcion = microtarea["descripcion"]
    print(f"🔧 Ejecutando microtarea {tarea_id}: {descripcion}", file=sys.stderr)
    db_microtarea_iniciada(tarea_id)
    try:
        # Si la tarea es añadir una línea a requirements.txt
        if "requirements.txt" in descripcion and ("añade" in descripcion.lower() or "agrega" in descripcion.lower()):
            match = re.search(r"['\"](.*?)['\"]", descripcion)
            if match:
                linea = match.group(1)
            else:
                palabras = descripcion.split()
                for palabra in reversed(palabras):
                    if '-' in palabra or '_' in palabra or palabra.isalnum():
                        linea = palabra
                        break
                else:
                    linea = "nueva_libreria"
            if modificar_requirements(linea):
                if subir_requirements_por_api():
                    db_microtarea_completada(tarea_id, exito=True)
                    print(f"✅ Microtarea {tarea_id} completada con éxito (requirements)", file=sys.stderr)
                    return True
                else:
                    raise Exception("Error al subir requirements.txt a GitHub")
            else:
                raise Exception("Error al modificar requirements.txt")

        # Si la tarea es añadir algo a app.py
        if "app.py" in descripcion and ("añade" in descripcion.lower() or "agrega" in descripcion.lower()):
            match = re.search(r"['\"](.*?)['\"]", descripcion)
            if match:
                linea = match.group(1)
            else:
                linea = "# Comentario añadido por Aether"
            if modificar_app(linea):
                if subir_app_por_api():
                    db_microtarea_completada(tarea_id, exito=True)
                    print(f"✅ Microtarea {tarea_id} completada con éxito (app.py)", file=sys.stderr)
                    return True
                else:
                    raise Exception("Error al subir app.py a GitHub")
            else:
                raise Exception("Error al modificar app.py")

        # Si no es de requirements ni app.py, seguir con el flujo normal de generación de código
        historial = db_get_historial(5)
        respuesta = generar_mejora(descripcion, historial)
        if not respuesta:
            raise Exception("No se pudo generar una mejora")
        codigo = extraer_codigo(respuesta)
        if not codigo:
            raise Exception("No se pudo extraer código de la respuesta")
        exito, mensaje = aplicar_mejora(codigo)
        if not exito:
            raise Exception(mensaje)
        db_microtarea_completada(tarea_id, exito=True)
        print(f"✅ Microtarea {tarea_id} completada con éxito", file=sys.stderr)
        return True
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Microtarea {tarea_id} falló: {error_msg}", file=sys.stderr)
        db_registrar_fallo(tarea_id, error_msg, traceback.format_exc())
        db_microtarea_completada(tarea_id, exito=False, error=error_msg[:500])
        checkpoint = db_get_checkpoint_activo()
        if checkpoint:
            restaurar_checkpoint(checkpoint["id"])
        return False

def ciclo_aprendizaje():
    print("🧠 Iniciando ciclo de aprendizaje...", file=sys.stderr)
    microtarea = db_get_microtarea_pendiente()
    if microtarea:
        print(f"📋 Microtarea pendiente: {microtarea['descripcion']}", file=sys.stderr)
        ejecutar_microtarea(microtarea)
        return
    tareas = db_get_tareas("pendiente")
    if tareas:
        tarea = tareas[0]
        print(f"📋 Tarea pendiente: {tarea['descripcion']}", file=sys.stderr)
        db_add_microtarea(tarea["descripcion"], prioridad=tarea["prioridad"])
        db_marcar_completada(tarea["id"])
        return
    print("🧠 No hay tareas pendientes. Aprendizaje libre controlado.", file=sys.stderr)
    memoria = db_get_memoria_episodica(5)
    historial = db_get_historial(5)
    prompt_libre = f"""
Eres Aether, un asistente autónomo.
No hay tareas específicas. Sugiere UNA mejora pequeña y segura.
Contexto de memoria reciente: {json.dumps(memoria, indent=2, default=str)}
Mejoras anteriores: {json.dumps(historial, indent=2, default=str)}
La mejora debe ser incremental, segura y útil.
Responde con el código Python completo modificado.
"""
    try:
        respuesta = llamar_modelo(prompt_libre)
        codigo = extraer_codigo(respuesta)
        if codigo:
            exito, mensaje = aplicar_mejora(codigo)
            if exito:
                db_guardar_memoria_episodica("Aprendizaje libre", respuesta[:500], f"Mejora aplicada: {mensaje}", exito=True)
                print(f"✅ Mejora libre aplicada: {mensaje}", file=sys.stderr)
            else:
                db_guardar_memoria_episodica("Aprendizaje libre fallido", respuesta[:500], f"Error: {mensaje}", exito=False)
                print(f"❌ Mejora libre falló: {mensaje}", file=sys.stderr)
    except Exception as e:
        print(f"❌ Error en aprendizaje libre: {e}", file=sys.stderr)

def bucle_aprendizaje():
    print("🔄 Bucle de aprendizaje iniciado.", file=sys.stderr)
    while True:
        try:
            inicio = time.time()
            ciclo_aprendizaje()
            try:
                requests.get(f"http://localhost:{os.environ.get('PORT', 10000)}/health", timeout=5)
                print("🔋 Ping de mantenimiento enviado", file=sys.stderr)
            except Exception as e:
                print(f"❌ Error en ping interno: {e}", file=sys.stderr)
            tiempo_espera = max(0, INTERVALO_APRENDIZAJE - (time.time() - inicio))
            print(f"⏳ Próximo ciclo en {tiempo_espera:.0f}s", file=sys.stderr)
            time.sleep(tiempo_espera)
        except Exception as e:
            print(f"❌ Error crítico en bucle: {e}", file=sys.stderr)
            time.sleep(60)

# ============================================================
# AUTO-PING
# ============================================================

def self_ping():
    while True:
        time.sleep(840)
        try:
            requests.get(f"http://localhost:{os.environ.get('PORT', 10000)}/health", timeout=5)
            print("🔋 Auto-ping: servicio mantenido activo", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ Auto-ping falló: {e}", file=sys.stderr)

# ============================================================
# GIT AUTOMÁTICO (CON FALLBACK API)
# ============================================================

def git_inicializar():
    if not GITHUB_TOKEN or not GITHUB_REPO_URL:
        print("⚠️ GitHub no configurado", file=sys.stderr)
        return False
    repo_path = os.path.join(os.getcwd(), REPO_DIR)
    if not os.path.exists(os.path.join(repo_path, ".git")):
        print("📦 Clonando repositorio...", file=sys.stderr)
        url_con_token = GITHUB_REPO_URL.replace("https://", f"https://{GITHUB_TOKEN}@")
        try:
            subprocess.run(["git", "clone", url_con_token, repo_path], check=True, capture_output=True)
            print("✅ Repositorio clonado", file=sys.stderr)
            return True
        except Exception as e:
            print(f"❌ Error clonando: {e}", file=sys.stderr)
            return False
    else:
        try:
            subprocess.run(["git", "-C", repo_path, "pull"], check=True, capture_output=True)
            return True
        except Exception as e:
            print(f"❌ Error pull: {e}", file=sys.stderr)
            return False

def git_commit_and_push():
    # Si la API funciona, usarla directamente
    if subir_app_por_api():
        return True
    # Si falla, intentar con git push (legado)
    if not GITHUB_TOKEN or not GITHUB_REPO_URL:
        print("⚠️ GitHub no configurado", file=sys.stderr)
        return False

    repo_path = os.path.join(os.getcwd(), REPO_DIR)
    if not os.path.exists(os.path.join(repo_path, ".git")):
        print("❌ Repositorio no inicializado", file=sys.stderr)
        return False

    try:
        subprocess.run(["git", "-C", repo_path, "config", "user.email", "aether@asistente.local"], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo_path, "config", "user.name", "Aether Asistente"], check=True, capture_output=True)
        shutil.copy2(__file__, os.path.join(repo_path, "app.py"))
        subprocess.run(["git", "-C", repo_path, "add", "."], check=True, capture_output=True)
        result = subprocess.run(["git", "-C", repo_path, "status", "--porcelain"], check=True, capture_output=True, text=True)
        if not result.stdout.strip():
            print("ℹ️ No hay cambios para commitear", file=sys.stderr)
            return True
        mensaje = f"Auto-mejora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        subprocess.run(["git", "-C", repo_path, "commit", "-m", mensaje], check=True, capture_output=True)
        subprocess.run(["git", "-C", repo_path, "push"], check=True, capture_output=True)
        print("✅ git push exitoso", file=sys.stderr)
        return True
    except Exception as e:
        print(f"❌ Error en git push: {e}", file=sys.stderr)
        return False

# ============================================================
# ENDPOINTS DE LA API
# ============================================================

@app.route('/')
def home():
    return "🤖 Aether — Asistente Autónomo v5.1"

@app.route('/health')
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.get_json()
        if not data or 'pregunta' not in data:
            return jsonify({'error': 'Falta pregunta'}), 400

        pregunta = data['pregunta']

        # Obtener memoria reciente
        memoria = aether.get(limit=5)
        contexto = ''
        if memoria:
            contexto = 'Contexto de memoria reciente:\n' + '\n'.join([m['content'] for m in memoria])

        prompt_completo = pregunta
        if contexto:
            prompt_completo = f'{contexto}\n\nPregunta: {pregunta}'

        respuesta = llamar_modelo(prompt_completo)

        aether.add(f'Pregunta: {pregunta}\nRespuesta: {respuesta}')

        return jsonify({'respuesta': respuesta})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/aprender', methods=['POST'])
def aprender_manual():
    threading.Thread(target=ciclo_aprendizaje, daemon=True).start()
    return jsonify({"status": "ok", "message": "Ciclo de aprendizaje iniciado"})

@app.route('/tareas', methods=['GET'])
def listar_tareas():
    tareas = db_get_tareas()
    return jsonify({
        "pendientes": [t for t in tareas if t['estado'] == 'pendiente'],
        "completadas": [t for t in tareas if t['estado'] == 'completada'],
        "fallidas": [t for t in tareas if t['estado'] == 'fallida'],
        "total": len(tareas)
    })

@app.route('/tareas', methods=['POST'])
def crear_tarea():
    data = request.get_json()
    if not data or 'descripcion' not in data:
        return jsonify({"error": "Falta descripción"}), 400
    tarea_id = db_add_tarea(data['descripcion'], data.get('prioridad', 0))
    return jsonify({"status": "ok", "id": tarea_id}), 201

@app.route('/microtareas', methods=['GET'])
def listar_microtareas():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM microtareas ORDER BY prioridad DESC, creada_en")
    microtareas = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(microtareas)

@app.route('/microtareas', methods=['POST'])
def crear_microtarea():
    data = request.get_json()
    if not data or 'descripcion' not in data:
        return jsonify({"error": "Falta descripción"}), 400
    microtarea_id = db_add_microtarea(data['descripcion'], data.get('estimado_minutos', 5), data.get('prioridad', 0))
    return jsonify({"status": "ok", "id": microtarea_id}), 201

@app.route('/estado', methods=['GET'])
def estado_sistema():
    tareas = db_get_tareas()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM microtareas")
    microtareas = cur.fetchall()
    cur.close()
    conn.close()
    historial = db_get_historial(5)
    checkpoint = db_get_checkpoint_activo()
    memoria = db_get_memoria_episodica(5)
    return jsonify({
        "tareas": {
            "pendientes": len([t for t in tareas if t['estado'] == 'pendiente']),
            "completadas": len([t for t in tareas if t['estado'] == 'completada']),
            "fallidas": len([t for t in tareas if t['estado'] == 'fallida'])
        },
        "microtareas": {
            "pendientes": len([m for m in microtareas if m['estado'] == 'pendiente']),
            "en_progreso": len([m for m in microtareas if m['estado'] == 'en_progreso']),
            "completadas": len([m for m in microtareas if m['estado'] == 'completada']),
            "fallidas": len([m for m in microtareas if m['estado'] == 'fallida'])
        },
        "checkpoint_activo": checkpoint["id"] if checkpoint else None,
        "ultimas_mejoras": historial,
        "memoria_reciente": memoria
    })

@app.route('/config', methods=['POST'])
def configurar_proveedor():
    data = request.get_json()
    if not data or 'provider' not in data or 'api_key' not in data:
        return jsonify({"error": "Falta provider o api_key"}), 400
    provider = data['provider']
    api_key = data['api_key']
    if provider not in ['gemini', 'deepseek', 'openai', 'anthropic', 'groq', 'openrouter']:
        return jsonify({"error": "Provider no soportado"}), 400
    db_set_config(f"{provider}_api_key", api_key)
    if 'model' in data:
        db_set_config(f"{provider}_model", data['model'])
    if 'priority' in data:
        db_set_config(f"{provider}_priority", str(data['priority']))
    return jsonify({"status": "ok", "message": f"Clave para {provider} guardada"})

@app.route('/orden', methods=['POST'])
def recibir_orden():
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({"error": f"Error al leer JSON: {str(e)}"}), 400
    if not data or 'orden' not in data:
        return jsonify({"error": "Falta la orden"}), 400
    orden = data['orden']
    print(f"📨 Orden recibida: {orden}", file=sys.stderr)

    if orden.startswith("/tarea"):
        descripcion = orden[7:].strip()
        if descripcion:
            tarea_id = db_add_tarea(descripcion)
            return jsonify({"status": "ok", "message": f"Tarea añadida (ID {tarea_id})"})
        return jsonify({"error": "Falta descripción"}), 400

    elif orden.startswith("/microtarea"):
        descripcion = orden[12:].strip()
        if descripcion:
            microtarea_id = db_add_microtarea(descripcion)
            return jsonify({"status": "ok", "message": f"Microtarea añadida (ID {microtarea_id})"})
        return jsonify({"error": "Falta descripción"}), 400

    elif orden.startswith("/aprender"):
        threading.Thread(target=ciclo_aprendizaje, daemon=True).start()
        return jsonify({"status": "ok", "message": "Ciclo de aprendizaje iniciado"})

    elif orden.startswith("/rollback"):
        checkpoint = db_get_checkpoint_activo()
        if checkpoint:
            if restaurar_checkpoint(checkpoint["id"]):
                return jsonify({"status": "ok", "message": f"Rollback al checkpoint {checkpoint['id']}"})
        return jsonify({"error": "No hay checkpoint disponible"}), 400

    elif orden.startswith("/config"):
        parts = orden.split()
        if len(parts) >= 3:
            provider = parts[1]
            api_key = parts[2]
            db_set_config(f"{provider}_api_key", api_key)
            if len(parts) >= 4:
                db_set_config(f"{provider}_model", parts[3])
            return jsonify({"status": "ok", "message": f"Clave para {provider} guardada"})
        return jsonify({"error": "Formato: /config <provider> <api_key> [modelo]"}), 400

    elif orden.startswith("/estado"):
        return estado_sistema()

    elif orden.startswith("/git"):
        if git_commit_and_push():
            return jsonify({"status": "ok", "message": "Git push ejecutado con éxito"})
        return jsonify({"error": "Git push falló"}), 500

    else:
        return jsonify({"error": "Orden no reconocida"}), 400

@app.route('/rollback', methods=['POST'])
def rollback_manual():
    checkpoint = db_get_checkpoint_activo()
    if not checkpoint:
        return jsonify({"error": "No hay checkpoint disponible"}), 400
    if restaurar_checkpoint(checkpoint["id"]):
        return jsonify({"status": "ok", "message": f"Rollback al checkpoint {checkpoint['id']}"})
    return jsonify({"error": "Error al restaurar checkpoint"}), 500

@app.route('/git', methods=['POST'])
def git_manual():
    if git_commit_and_push():
        return jsonify({"status": "ok", "message": "Git push ejecutado con éxito"})
    return jsonify({"error": "Git push falló"}), 500

@app.route('/memory', methods=["POST"])
def add_memory():
    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"error": "Se requiere 'content'"}), 400
    aether.add(data["content"], data.get("metadata"))
    return jsonify({"status": "ok"}), 201

@app.route('/memory', methods=["GET"])
def get_memory():
    limit = request.args.get("limit", type=int)
    since_str = request.args.get("since")
    since = datetime.fromisoformat(since_str) if since_str else None
    entries = aether.get(limit=limit, since=since)
    return jsonify(entries)

@app.route('/memory/stats', methods=["GET"])
def memory_stats():
    return jsonify(aether.stats())

@app.route('/memory/clear', methods=["POST"])
def clear_memory():
    aether.clear()
    return jsonify({"status": "cleared"})

# ============================================================
# INICIO DEL SERVICIO
# ============================================================

if __name__ == "__main__":
    print("🚀 Iniciando Aether v5.1", file=sys.stderr)
    if GITHUB_TOKEN and GITHUB_REPO_URL:
        git_inicializar()
    else:
        print("⚠️ GitHub no configurado", file=sys.stderr)
    threading.Thread(target=self_ping, daemon=True).start()
    threading.Thread(target=bucle_aprendizaje, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)