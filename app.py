# -*- coding: utf-8 -*-
"""
Aether – Gestor de memoria reciente con:
  • Capacidad limitada automática (deque)
  • Registro de marca de tiempo
  • Acceso thread‐safe mediante lock
  • Eliminación automática por antigüedad (TTL)
  • Persistencia automática al salir (JSON)
  • Nuevo método público `clear()` para vaciar el estado de forma segura
"""

import json
import signal
import sys
import threading
import os
import atexit
from datetime import datetime, timedelta
from collections import deque, Counter
from flask import Flask, request, jsonify

app = Flask(__name__)

class Aether:
    """Gestor de memoria reciente con:
    • Capacidad limitada automática (deque)
    • Registro de marca de tiempo
    • Acceso thread-safe mediante lock con gestión de contexto
    • Eliminación automática por antigüedad (TTL)
    • Persistencia automática al salir (JSON seguro)
    • Método clear() para reinicio seguro
    """

    def __init__(self, maxlen: int = 1000, ttl_seconds: int = 3600, filepath: str = "aether_memory.json"):
        self._deque = deque(maxlen=maxlen)
        self._ttl = timedelta(seconds=ttl_seconds)
        self._filepath = filepath
        self._lock = threading.RLock()
        self._load()
        # Registrar handlers de salida para persistencia
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
                    # Restaurar deque con maxlen
                    self._deque = deque(data.get("entries", []), maxlen=self._deque.maxlen)
            except (json.JSONDecodeError, IOError):
                # Si hay error, iniciar vacío
                self._deque = deque(maxlen=self._deque.maxlen)

    def _save(self):
        with self._lock:
            # Filtrar entradas expiradas antes de guardar
            now = datetime.now()
            valid_entries = [entry for entry in self._deque if now - datetime.fromisoformat(entry["timestamp"]) < self._ttl]
            data = {"entries": valid_entries, "saved_at": now.isoformat()}
            try:
                with open(self._filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except IOError:
                pass # Fallo silencioso en persistencia

    def add(self, content: str, metadata: dict = None):
        """Añade una entrada con timestamp y metadatos opcionales."""
        entry = {
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        with self._lock:
            self._deque.append(entry)
            self._cleanup_expired()

    def get(self, limit: int = None, since: datetime = None) -> list:
        """Recupera entradas, opcionalmente limitadas y filtradas por fecha."""
        with self._lock:
            self._cleanup_expired()
            entries = list(self._deque)
            if since:
                entries = [e for e in entries if datetime.fromisoformat(e["timestamp"]) >= since]
            if limit:
                entries = entries[-limit:]
            return entries

    def _cleanup_expired(self):
        """Elimina entradas más antiguas que TTL."""
        now = datetime.now()
        while self._deque and (now - datetime.fromisoformat(self._deque[0]["timestamp"]) >= self._ttl):
            self._deque.popleft()

    def clear(self):
        """Vacía la memoria de forma thread-safe y persiste el estado vacío."""
        with self._lock:
            self._deque.clear()
            self._save()

    def stats(self) -> dict:
        """Devuelve estadísticas de uso de memoria."""
        with self._lock:
            self._cleanup_expired()
            return {
                "count": len(self._deque),
                "capacity": self._deque.maxlen,
                "usage_percent": (len(self._deque) / self._deque.maxlen * 100) if self._deque.maxlen else 0,
                "oldest_entry": self._deque[0]["timestamp"] if self._deque else None,
                "newest_entry": self._deque[-1]["timestamp"] if self._deque else None
            }

# Instancia global para la API
aether = Aether()

@app.route("/memory", methods=["POST"])
def add_memory():
    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"error": "Se requiere 'content'"}), 400
    aether.add(data["content"], data.get("metadata"))
    return jsonify({"status": "ok"}), 201

@app.route("/memory", methods=["GET"])
def get_memory():
    limit = request.args.get("limit", type=int)
    since_str = request.args.get("since")
    since = datetime.fromisoformat(since_str) if since_str else None
    entries = aether.get(limit=limit, since=since)
    return jsonify(entries)

@app.route("/memory/stats", methods=["GET"])
def memory_stats():
    return jsonify(aether.stats())

@app.route("/memory/clear", methods=["POST"])
def clear_memory():
    aether.clear()
    return jsonify({"status": "cleared"})

if __name__ == "__main__":
from collections import deque
from collections import Counter
    app.run(host="0.0.0.0", port=5000, threaded=True)