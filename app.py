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
def get_db_connect():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# Función para agregar un elemento a la memoria reciente
def add_element(element):
    conn = get_db_connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO recent_memory (element, timestamp) VALUES (%s, %s)", (element, datetime.datetime.now()))
    conn.commit()
    conn.close()

# Función para obtener la cantidad de elementos en la memoria reciente que contienen una palabra específica
def count_elements_with_word(word):
    conn = get_db_connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM recent_memory WHERE element LIKE %s", ('%' + word + '%',))
    count = cur.fetchone()[0]
    conn.close()
    return count

# Función para eliminar un elemento de la memoria reciente
def delete_element(element):
    conn = get_db_connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM recent_memory WHERE element = %s", (element,))
    conn.commit()
    conn.close()

# Ruta para agregar un elemento a la memoria reciente
@app.route('/add_element', methods=['POST'])
def add_element_route():
    element = request.json['element']
    add_element(element)
    return jsonify({'message': 'Elemento agregado con éxito'})

# Ruta para obtener la cantidad de elementos en la memoria reciente que contienen una palabra específica
@app.route('/count_elements_with_word', methods=['GET'])
def count_elements_with_word_route():
    word = request.args.get('word')
    count = count_elements_with_word(word)
    return jsonify({'count': count})

# Ruta para eliminar un elemento de la memoria reciente
@app.route('/delete_element', methods=['DELETE'])
def delete_element_route():
    element = request.json['element']
    delete_element(element)
    return jsonify({'message': 'Elemento eliminado con éxito'})

if __name__ == '__main__':
    app.run(debug=True)