# -*- coding: utf-8 -*-
"""
Aether – Recent memory manager with:
  • Automatic limited capacity (deque)
  • Timestamp recording
  • Element count retrieval
  • Search for elements containing a specific word
  • Eliminación de elementos
"""
from collections import deque
import time
import datetime
import flask
from flask import Flask, request, jsonify
import psycopg2
from psycopg2.extras import DictCursor
import os
import re

app = Flask(__name__)

# Conexión a la base de datos
def get_db_connection():
    return psycopg2.connect(os.environ['DATABASE_URL'], cursor_factory=DictCursor)

# Inicialización de la memoria reciente
memoria_reciente = deque(maxlen=100)

# Función para agregar elementos a la memoria reciente
def agregar_elemento(elemento):
    memoria_reciente.append({
        'timestamp': datetime.datetime.now(),
        'elemento': elemento
    })

# Función para obtener la cantidad de elementos en la memoria reciente que contienen una palabra específica
def contar_elementos_con_palabra(palabra):
    return sum(1 for elemento in memoria_reciente if palabra in elemento['elemento'])

# Función para eliminar elementos de la memoria reciente que contienen una palabra específica
def eliminar_elementos_con_palabra(palabra):
    memoria_reciente = deque([elemento for elemento in memoria_reciente if palabra not in elemento['elemento']], maxlen=100)
    return memoria_reciente

# Ruta para agregar elementos a la memoria reciente
@app.route('/agregar', methods=['POST'])
def agregar():
    elemento = request.json['elemento']
    agregar_elemento(elemento)
    return jsonify({'mensaje': 'Elemento agregado con éxito'})

# Ruta para obtener la cantidad de elementos en la memoria reciente que contienen una palabra específica
@app.route('/contar', methods=['GET'])
def contar():
    palabra = request.args.get('palabra')
    contador = contar_elementos_con_palabra(palabra)
    return jsonify({'contador': contador})

# Ruta para eliminar elementos de la memoria reciente que contienen una palabra específica
@app.route('/eliminar', methods=['GET'])
def eliminar():
    palabra = request.args.get('palabra')
    memoria_reciente = eliminar_elementos_con_palabra(palabra)
    return jsonify({'mensaje': 'Elementos eliminados con éxito'})

if __name__ == '__main__':
    app.run(debug=True)