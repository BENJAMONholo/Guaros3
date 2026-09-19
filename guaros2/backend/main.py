import os
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
from datetime import datetime

# ==========================================
# CONFIGURACIÓN WHATSAPP API (META)
# ==========================================
WHATSAPP_TOKEN = "EAAP0nIJGPpMBSvXYuCSl69eQzy42IVoBrvUP4HUWCs35sbJQuqoOHWc5PuGFSaeGsCBQbzv8S2HZB2Al7zBxe40KLkNsiQp1ZBNYB3ftUDlBHrOADXeaZBfa7EnV7cj8fV0Yjru4BTM6v4THZBEt9fAci8nMJtqBeCOM5w0z3sZBh6ZB8Ta4uLw56L6oARYUzDNoTrUngQp8fx5C3etzTR9WzAnZA6ZAQ0BCPwTXcctfKGunFAldK3gSQ4iImJvn6G4nJhumVYXyPiXF6jfMFopVIiKUp3aV5FZC9kiK19wZDZD"
PHONE_NUMBER_ID = "1266414733229758"

# Mapeo de números del personal
STAFF_NUMBERS = {
    "Alex": "56950963280",       # Barbero
    "David": "56950963280",      # Barbero
    "Camila": "56982311045",     # Uñas / Studio
    "Valentina": "56982311045"   # Uñas / Studio
}

def enviar_alerta_staff(trabajador, cliente, telefono_cliente, servicio, fecha, hora):
    """Envía la plantilla pre-aprobada 'alerta_staff' al trabajador correspondiente"""
    numero_destino = STAFF_NUMBERS.get(trabajador)
    if not numero_destino:
        return

    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    numero_limpio = str(numero_destino).replace('+', '').replace(' ', '')
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "messaging_product": "whatsapp",
        "to": numero_limpio,
        "type": "template",
        "template": {
            "name": "alerta_staff", 
            "language": { "code": "es_CL" }, # Asegúrate de que coincida con lo que pusiste en Meta
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": cliente},            
                        {"type": "text", "text": telefono_cliente},   
                        {"type": "text", "text": servicio},           
                        {"type": "text", "text": fecha},              
                        {"type": "text", "text": hora}                
                    ]
                }
            ]
        }
    }
    
    try:
        requests.post(url, headers=headers, json=data)
    except Exception as e:
        print(f"Error alertando al staff: {e}")

def enviar_confirmacion_cliente(telefono, cliente, servicio, fecha, hora):
    """Envía la plantilla de prueba predeterminada de Meta para verificar la conexión"""
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    numero_limpio = str(telefono).replace('+', '').replace(' ', '')
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Usamos "hello_world" que no requiere variables y está siempre aprobada
    data = {
        "messaging_product": "whatsapp",
        "to": numero_limpio,
        "type": "template",
        "template": {
            "name": "hello_world",
            "language": { "code": "en_US" }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"Respuesta enviando prueba hello_world: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error enviando confirmación al cliente: {e}")
# ==========================================
# CONFIGURACIÓN DEL SERVIDOR FLASK
# ==========================================
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
CORS(app) 

DB_NAME = "citas.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reservas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            telefono TEXT,
            servicio TEXT,
            barbero TEXT,
            fecha TEXT,
            hora TEXT
        )
    ''')
    conn.commit()
    conn.close()

# ======= EL CAMBIO ESTÁ AQUÍ =======
# Llamamos a la función directamente en el archivo principal 
# para que Render cree la base de datos sí o sí.
init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)

def limpiar_historial():
    hoy = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reservas WHERE fecha < ?", (hoy,))
    conn.commit()
    conn.close()

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    assets_dir = os.path.join(app.static_folder, 'assets')
    return send_from_directory(assets_dir, filename)

@app.route('/api/agendar', methods=['POST'])
def agendar():
    datos = request.json
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM reservas WHERE fecha = ? AND hora = ? AND barbero = ?", 
                  (datos['fecha'], datos['hora'], datos['barbero']))
    if cursor.fetchone():
        conn.close()
        return jsonify({"error": "Lo sentimos, esta hora acaba de ser reservada por otro usuario."}), 400

    cursor.execute('''
        INSERT INTO reservas (cliente, telefono, servicio, barbero, fecha, hora)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (datos['cliente'], datos['telefono'], datos['servicio'], datos['barbero'], datos['fecha'], datos['hora']))
    conn.commit()
    conn.close()
    
    # Disparar alertas (Asegurarse de mandar el 'barbero' a la de confirmación para el nombre de empresa)
    enviar_alerta_staff(datos['barbero'], datos['cliente'], datos['telefono'], datos['servicio'], datos['fecha'], datos['hora'])
    enviar_confirmacion_cliente(datos['telefono'], datos['cliente'], datos['servicio'], datos['fecha'], datos['hora'], datos['barbero'])
    
    return jsonify({"mensaje": "Cita agendada con éxito"}), 200

@app.route('/api/disponibilidad', methods=['GET'])
def disponibilidad():
    fecha = request.args.get('fecha')
    barbero = request.args.get('barbero')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT hora FROM reservas WHERE fecha = ? AND barbero = ?", (fecha, barbero))
    ocupadas = [fila[0] for fila in cursor.fetchall()]
    conn.close()
    return jsonify({"ocupadas": ocupadas})

@app.route('/api/citas', methods=['GET'])
def obtener_citas():
    limpiar_historial()
    fecha = request.args.get('fecha')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT cliente, servicio, hora, barbero, telefono FROM reservas WHERE fecha = ? ORDER BY hora", (fecha,))
    citas = [{"cliente": f[0], "servicio": f[1], "hora": f[2], "barbero": f[3], "telefono": f[4]} for f in cursor.fetchall()]
    conn.close()
    return jsonify(citas)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
