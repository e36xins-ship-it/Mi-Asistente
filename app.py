import threading
import time
import json
import os
from datetime import datetime

# ============================================
# CONFIGURACIÓN DE APRENDIZAJE CONTINUO
# ============================================

INTERVALO_APRENDIZAJE = 600  # 10 minutos (en segundos)
ARCHIVO_HISTORIAL = "aprendizaje.json"

# Cargar historial de mejoras previas
try:
    with open(ARCHIVO_HISTORIAL, "r") as f:
        historial_mejoras = json.load(f)
except FileNotFoundError:
    historial_mejoras = []

# ============================================
# FUNCIÓN DE APRENDIZAJE (el corazón del sistema)
# ============================================

def aprender_y_mejorar():
    """
    Esta función se ejecuta automáticamente cada INTERVALO_APRENDIZAJE.
    1. Pide a Gemini que sugiera una mejora concreta.
    2. Evalúa si es viable.
    3. Si es viable, la aplica (o la guarda para aprobación).
    4. Registra la mejora para no repetirla.
    """
    print("🧠 Iniciando ciclo de aprendizaje...")
    
    # 1. Generar una idea de mejora basada en el contexto
    prompt_contexto = f"""
    Eres el asistente Aether, un sistema autónomo que se mejora a sí mismo.
    Ya has implementado estas mejoras anteriormente:
    {json.dumps(historial_mejoras[-5:], indent=2)}
    
    Tu objetivo es sugerir UNA MEJORA NUEVA Y CONCRETA para tu propio código.
    La mejora debe ser:
    - Pequeña y aplicable (no reescribir todo).
    - Que añada una nueva funcionalidad útil.
    - Que no rompa el sistema actual.
    
    Responde ÚNICAMENTE con:
    1. Título de la mejora.
    2. Código Python completo que se debe añadir o modificar (si aplica).
    3. Explicación de por qué es útil.
    """
    
    try:
        respuesta = llamar_gemini(prompt_contexto)
        print(f"💡 Idea generada: {respuesta[:200]}...")
        
        # 2. Guardar la mejora en un archivo temporal para revisión
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(f"mejora_{timestamp}.txt", "w") as f:
            f.write(respuesta)
        
        # 3. Registrar la mejora en el historial
        historial_mejoras.append({
            "timestamp": timestamp,
            "mejora": respuesta[:500]  # Guardamos un resumen
        })
        with open(ARCHIVO_HISTORIAL, "w") as f:
            json.dump(historial_mejoras[-50:], f, indent=2)  # Guardamos las últimas 50
        
        print(f"✅ Mejora guardada en mejora_{timestamp}.txt")
        return True
        
    except Exception as e:
        print(f"❌ Error en ciclo de aprendizaje: {e}")
        return False

# ============================================
# BUCLE DE MANTENIMIENTO Y APRENDIZAJE
# ============================================

def bucle_aprendizaje():
    """
    Bucle que se ejecuta en un hilo separado.
    Cada INTERVALO_APRENDIZAJE, ejecuta aprender_y_mejorar()
    Además, responde a un "ping" interno para mantener vivo el servicio.
    """
    while True:
        inicio_ciclo = time.time()
        
        # 1. Autoaprendizaje
        aprender_y_mejorar()
        
        # 2. Mantener vivo el servicio (ping interno)
        try:
            requests.get(f"http://localhost:{os.environ.get('PORT', 10000)}/health")
            print("🔋 Ping de mantenimiento enviado")
        except Exception as e:
            print(f"❌ Error en ping interno: {e}")
        
        # 3. Calcular tiempo de espera hasta el próximo ciclo
        tiempo_ejecucion = time.time() - inicio_ciclo
        tiempo_espera = max(0, INTERVALO_APRENDIZAJE - tiempo_ejecucion)
        print(f"⏳ Próximo ciclo en {tiempo_espera:.0f} segundos")
        time.sleep(tiempo_espera)

# ============================================
# ENDPOINT PARA EJECUTAR APRENDIZAJE MANUAL
# ============================================

@app.route('/aprender', methods=['POST'])
def aprender_manual():
    """
    Endpoint para activar el aprendizaje bajo demanda.
    Útil para probar o forzar una mejora.
    """
    try:
        resultado = aprender_y_mejorar()
        if resultado:
            return jsonify({"status": "ok", "message": "Ciclo de aprendizaje iniciado"})
        else:
            return jsonify({"status": "error", "message": "Error en el aprendizaje"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# INICIAR EL BUCLE DE APRENDIZAJE EN SEGUNDO PLANO
# ============================================

# Al iniciar el servicio, lanzar el bucle en un hilo
threading.Thread(target=bucle_aprendizaje, daemon=True).start()

# También iniciar el keep-alive básico (por si acaso)
threading.Thread(target=keep_alive, daemon=True).start()