import os
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
from datetime import datetime

# ==========================================
# CONFIGURACIÓN WHATSAPP API (META)
# ==========================================
WHATSAPP_TOKEN = "vEAAP0nIJGPpMBSgBOV5ZCET6TssYB1ZCG5ZAZAJMkhyaFZBhlijrZCSGsIOjP3uJc7yPNO27gpYkf5HPj4OCqEa9re43edkU28ctxAdL9G2b6AP6iLTkYgZAxfWfjhb5dXhwjXQUIetLovdd9cyBq93h9VZAQvURbfOYLKrFZBfZAt0rJeLb587HtTki4hofXLdvUz9SXZAvfQvg4QZCZCDITeXofCl79GouNSVLogZAEMwwuaIDuFWk8a5pjeAsaMpN8UZBRNePg7WIp0WBTj8r6buEFMZCZBhyIirl6i1tlNZBYwtJWUZD"
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
        print(f"No hay número registrado para el trabajador: {trabajador}")
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
            "language": { "code": "es_CL" }, # En tu imagen dice "Spanish (CHL)" para alerta_staff
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": cliente},            # {{1}}
                        {"type": "text", "text": telefono_cliente},   # {{2}}
                        {"type": "text", "text": servicio},           # {{3}}
                        {"type": "text", "text": fecha},              # {{4}}
                        {"type": "text", "text": hora}                # {{5}}
                    ]
                }
            ]
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"Alerta enviada a {trabajador}: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error alertando al staff: {e}")

def enviar_confirmacion_cliente(telefono, cliente, servicio, fecha, hora, barbero):
    """Envía la plantilla 'confirmacion_oficial' al cliente"""
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    numero_limpio = str(telefono).replace('+', '').replace(' ', '')
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Define el nombre de la empresa según con quién reservó
    if barbero in ["Camila", "Valentina"]:
        nombre_empresa = "Guara's Studio VIP"
    else:
        nombre_empresa = "Guaro's Barbershop"
    
    data = {
        "messaging_product": "whatsapp",
        "to": numero_limpio,
        "type": "template",
        "template": {
            "name": "confirmacion_oficial", 
            "language": { "code": "es" },   # En tu imagen dice "Spanish" para confirmacion_oficial
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": cliente},         # {{1}} Nombre del cliente
                        {"type": "text", "text": nombre_empresa},  # {{2}} Nombre de la empresa
                        {"type": "text", "text": servicio},        # {{3}} Servicio
                        {"type": "text", "text": fecha},           # {{4}} Fecha
                        {"type": "text", "text": hora}             # {{5}} Hora
                    ]
                }
            ]
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"Confirmación enviada al cliente ({numero_limpio}): {response.status_code} - {response.text}")
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

# Asegurar que la BD se cree al iniciar
init_db()

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
    
    # Enviar WhatsApp al staff y al cliente
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
    app.run(debug=True, port=5000)
