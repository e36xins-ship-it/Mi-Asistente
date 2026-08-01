#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para comunicarse con un K-TAG desde Windows 10.
Dependencias: pyserial, gkbus, python-can
"""

import os
import sys
import subprocess
import logging
import time
from typing import Optional

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def instalar_dependencias() -> bool:
    """Instala las dependencias necesarias: pyserial, gkbus, python-can."""
    logger.info("Instalando dependencias...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyserial", "gkbus", "python-can"])
        logger.info("✅ Dependencias instaladas correctamente.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error al instalar dependencias: {e}")
        return False

def detectar_puerto_ktag() -> Optional[str]:
    """Lista los puertos COM disponibles y sugiere cuál podría ser el K-TAG."""
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            logger.warning("No se encontraron puertos COM.")
            return None
        logger.info("Puertos COM disponibles:")
        for port in ports:
            logger.info(f"  {port.device} - {port.description} - {port.manufacturer}")
        # Sugerencia: buscar puertos que parezcan ser de un adaptador USB-Serial
        sugeridos = [p.device for p in ports if "USB" in p.description or "Serial" in p.description or "COM" in p.device]
        if sugeridos:
            logger.info(f"🔍 Posible K-TAG en: {sugeridos[0]}")
            return sugeridos[0]
        else:
            logger.info("No se pudo identificar un puerto específico para K-TAG. Prueba con el primer puerto.")
            return ports[0].device if ports else None
    except ImportError:
        logger.error("❌ pyserial no está instalado. Ejecuta instalar_dependencias() primero.")
        return None

def conectar_ktag(tipo: str = 'kline', puerto: Optional[str] = None):
    """
    Intenta conectar con el K-TAG.
    tipo: 'kline' o 'can'
    puerto: nombre del puerto COM (ej. 'COM3') o None para auto-detección.
    """
    if puerto is None:
        puerto = detectar_puerto_ktag()
        if puerto is None:
            logger.error("No se pudo detectar el puerto del K-TAG.")
            return None

    logger.info(f"Intentando conectar en {puerto} con tipo {tipo}...")
    try:
        if tipo == 'kline':
            from gkbus import KLineBus, KWP2000Client
            # Crear el bus K-Line
            bus = KLineBus(port=puerto, baudrate=10400)  # 10400 baudios típico para K-Line
            client = KWP2000Client(bus, ecu_id=0x11, tester_id=0xF1)
            # Intento de inicialización rápida (Fast Init)
            # Nota: Esto puede variar según el vehículo/ECU
            logger.info("Conectado a K-Line.")
            return client
        elif tipo == 'can':
            import can
            # Configurar interfaz CAN (asumiendo que es un adaptador tipo PCAN o similar)
            bus = can.interface.Bus(channel=puerto, bustype='serial', bitrate=500000)
            # O para un adaptador genérico: bustype='slcan', channel=puerto
            logger.info("Conectado a CAN Bus.")
            return bus
        else:
            logger.error(f"Tipo de conexión '{tipo}' no soportado.")
            return None
    except Exception as e:
        logger.error(f"❌ Error al conectar: {e}")
        return None

def leer_datos_ktag(comando: str, objeto_comunicacion) -> Optional[str]:
    """
    Envía un comando genérico al K-TAG y devuelve la respuesta.
    Si no hay objeto de comunicación real, devuelve una respuesta simulada.
    """
    if objeto_comunicacion is None:
        logger.warning("Objeto de comunicación nulo. Devolviendo respuesta simulada.")
        return f"Respuesta simulada al comando: {comando}"
    try:
        # Aquí se implementaría la lógica específica según el protocolo
        # Por ejemplo, para KWP2000:
        if hasattr(objeto_comunicacion, 'send_request'):
            respuesta = objeto_comunicacion.send_request(comando)
            logger.info(f"Comando enviado: {comando}")
            return str(respuesta)
        else:
            logger.warning("El objeto de comunicación no tiene método send_request.")
            return "Respuesta simulada (objeto sin método)"
    except Exception as e:
        logger.error(f"❌ Error al enviar comando: {e}")
        return None

def main():
    """Función principal de prueba."""
    logger.info("=== Prueba de conexión con K-TAG ===")
    # Paso 1: Verificar/instalar dependencias
    if not instalar_dependencias():
        logger.error("No se pudieron instalar las dependencias. Saliendo.")
        return

    # Paso 2: Detectar puerto
    puerto = detectar_puerto_ktag()
    if puerto is None:
        logger.error("No se detectó ningún puerto COM. Conecta el K-TAG y verifica drivers.")
        return

    # Paso 3: Conectar
    objeto = conectar_ktag(tipo='kline', puerto=puerto)
    if objeto is None:
        logger.error("No se pudo conectar al K-TAG.")
        return

    # Paso 4: Leer datos (simulado)
    respuesta = leer_datos_ktag("TEST", objeto)
    logger.info(f"Respuesta: {respuesta}")

    logger.info("Prueba completada.")

if __name__ == "__main__":
    main()
