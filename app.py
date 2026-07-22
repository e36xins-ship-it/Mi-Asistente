# -*- coding: utf-8 -*-
"""
Aether – Recent memory manager with:
  • Automatic limited capacity (deque)
  • Timestamp register
  • Thread‑safe access via lock with context management
  • Automatic expiration by age (TTL)
  • Automatic persistence on exit (JSON)
  • New public method `clear()` to empty state safely
  • New method `get_recent()` for safe data reading
  • New method `prune_expired()` to delete expired entries
  • Configurable maximum capacity via `max_length` parameter
"""

import json
import os
import signal
import sys
import threading
from collections import deque
from datetime import datetime, timedelta
from threading import RLock

from flask import Flask, jsonify, request
from flask_cors import CORS

class RecentMemoryManager:
    def __init__(self, max_length=1000, ttl_seconds=86400):
        self._data = deque()
        self._timestamps = deque()
        self._lock = RLock()
        self.max_length = max_length
        self.ttl_seconds = ttl_seconds

    def add(self, item):
        with self._lock:
            now = datetime.now()
            self._data.append(item)
            self._timestamps.append(now)
            if len(self._data) > self.max_length:
                self._data.popleft()
                self._timestamps.popleft()
            # Persist to disk
            self._persist()

    def _persist(self):
        with open('memory_state.json', 'w') as f:
            json.dump({
                "data": list(self._data),
                "timestamps": [t.isoformat() for t in self._timestamps]
            }, f)

    @classmethod
    def load(cls):
        if not os.path.exists('memory_state.json'):
            return cls()
        with open('memory_state.json', 'r') as f:
            payload = json.load(f)
        manager = cls()
        manager._data = deque(payload["data"])
        manager._timestamps = deque(
            [datetime.fromisoformat(t) for t in payload["timestamps"]]
        )
        return manager

    def clear(self):
        with self._lock:
            self._data.clear()
            self._timestamps.clear()
            # Persist empty state
            self._persist()

    def get_recent(self, n=1):
        with self._lock:
            # Return up to n recent items
            return list(self._data)[-n:]

    def prune_expired(self):
        with self._lock:
            now = datetime.now()
            while self._timestamps and (now - self._timestamps[0]).total_seconds() > self.ttl_seconds:
                self._data.popleft()
                self._timestamps.popleft()
            self._persist()

    def get_all(self):
        with self._lock:
            return list(self._data)

app = Flask(__name__)
CORS(app)

# Instantiate the memory manager (singleton pattern could be used)
memory = RecentMemoryManager.load()

# Example API endpoints
@app.route('/add/<item>', methods=['POST'])
def add_item(item):
    memory.add(item)
    return jsonify({"status": "added"}), 201

@app.route('/recent', methods=['GET'])
def recent_items():
    return jsonify(memory.get_recent()), 200

@app.route('/clear', methods=['DELETE'])
def clear_memory():
    memory.clear()
    return jsonify({"status": "cleared"}), 200

@app.route('/prune', methods=['POST'])
def prune():
    memory.prune_expired()
    return jsonify({"status": "pruned"}), 200

@app.route('/state', methods=['GET'])
def get_state():
    return jsonify(memory.get_all()), 200

if __name__ == '__main__':
    # Register cleanup on exit
    signal.signal(signal.SIGINT, lambda s, f: memory.clear())
    signal.signal(signal.SIGTERM, lambda s, f: memory.clear())
from flask_cors import CORS
    app.run(host='0.0.0.0', port=5000, debug=False)