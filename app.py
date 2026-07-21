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
        # Usar DATABASE_URL de entorno
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
            DB_CONN = sqlite3.connect('data.db')
            DB_CONN.row_factory = sqlite3.Row
        return DB_CONN

def init_db():
    """Crea las tablas si no existen (adaptado a SQLite o PostgreSQL)."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    if DB_TYPE == 'sqlite':
        # SQLite usa AUTOINCREMENT y TEXT para fechas
        cur.execute("""
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
        # PostgreSQL (sintaxis ya existente)
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
        cur.execute("SELECT * FROM historial ORDER BY timestamp DESC LIMIT %s", (limit,))
    else:
        cur.execute("SELECT * FROM historial ORDER BY timestamp DESC LIMIT ?", (limit,))
    if DB_TYPE == 'postgres':
        if 'psycopg2' in sys.modules:
            rows = cur.fetchall()
        else:
            rows = cur.fetchall()
        historial = [dict(row) for row in rows] if not isinstance(rows[0], dict) else rows
    else:
        historial = [dict(row) for row in cur.fetchall()]
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
    else:
        cur.execute("SELECT key, value FROM config")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    if DB_TYPE == 'postgres' and 'psycopg2' in sys.modules:
        return {row['key']: row['value'] for row in rows}
    else:
        return {row[0]: row[1] for row in rows}

# ============================================
# EL RESTO DEL CÓDIGO (idéntico al anterior)
# ============================================

# ... (aquí va el resto de tu código: config, llamar_modelo, endpoints, etc.)
# Para no repetir, usa el código que ya tenías, pero asegúrate de que todas las funciones de DB usen las nuevas definiciones.

# ============================================
# INICIO DEL SERVICIO
# ============================================

if __name__ == "__main__":
    print(f"🚀 Iniciando asistente con base de datos: {DB_TYPE}", file=sys.stderr)
    sys.stderr.flush()
    # ... resto del código de inicio