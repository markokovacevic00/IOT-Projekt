import signal
import tornado.ioloop
import tornado.web
import tornado.websocket
import paho.mqtt.client as mqtt
import json  # Dodano za rad s JSON-om
import time
import sqlite3

"""
Tornado Server s MQTT i SQLite bazom podataka
------------------------------------------------
- Prima podatke od ESP8266 putem MQTT-a
- Spaja se na SQLite bazu i sprema očitanja temperature
- Omogućuje komunikaciju s web sučeljem putem WebSocket-a
"""

# MQTT konfiguracija
MQTT_BROKER = "172.20.10.6"  # IP MQTT brokera
MQTT_PORT = 1883
TEMP_TOPIC = "sensor/temp"
ALARM_TOPIC = "sensor/alarm"
DOOR_TOPIC = "sensor/door"
ALARM_CONTROL_TOPIC = "sensor/alarm/control"  # Tema za kontrolu alarma

# Spremnik za jednog WebSocket klijenta
websocket_client = None

# Inicijalizacija baze podataka

def init_db():
    """ Kreira SQLite bazu podataka ako ne postoji """
    conn = sqlite3.connect("sensor_data.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS temperature_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            temperature REAL
        )
    ''')
    conn.commit()
    conn.close()

# Spremanje temperature u bazu

def save_temperature_to_db(temperature):
    """ Sprema očitanu temperaturu u SQLite bazu podataka """
    conn = sqlite3.connect("sensor_data.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO temperature_data (temperature) VALUES (?)", (temperature,))
    conn.commit()
    conn.close()

# HTTP handler za prikaz web sučelja

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        """ Prikazuje početnu HTML stranicu """
        self.render("indexProjekt.html")  # Zamijeni s pravim imenom HTML datoteke

# WebSocket handler

class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        """ Kada se otvori WebSocket veza """
        global websocket_client
        websocket_client = self
        print("WebSocket opened")

    def on_message(self, message):
        """ Prima poruke s web sučelja i prosljeđuje ih MQTT brokeru """
        global mqtt_client

        if message == "":
            return
        print(f"Received WebSocket message: {message}")

        try:
            data = json.loads(message)
            topic = data.get("topic")
            tValue = data.get("valueA")
            print(f"Received data: {topic} - {tValue}")
            if topic and tValue:
                mqtt_client.publish(topic, tValue)
        except json.JSONDecodeError:
            print("Greška: Neispravan JSON format")

    def on_close(self):
        """ Kada se WebSocket zatvori """
        global websocket_client
        websocket_client = None
        print("WebSocket closed")

# MQTT callback funkcije

def on_connect(client, userdata, flags, rc):
    """ Kada se ESP spaja na MQTT broker """
    if rc == 0:
        print("Connected to MQTT broker")
        client.subscribe(TEMP_TOPIC)
        client.subscribe(ALARM_TOPIC)
        client.subscribe(DOOR_TOPIC)
        client.subscribe(ALARM_CONTROL_TOPIC)
    else:
        print(f"Failed to connect, return code {rc}")


def on_message(client, userdata, msg):
    """ Obrada poruka primljenih putem MQTT-a """
    message = msg.payload.decode()
    print(f"Received MQTT message on {msg.topic}: {message}")

    # Ako je poruka s teme temperature, spremi u bazu
    if msg.topic == TEMP_TOPIC:
        try:
            temperature = float(message)
            save_temperature_to_db(temperature)
            print(f"Temperature {temperature} recorded in database.")
        except ValueError:
            print("Error: Invalid temperature value")

    # Kreiraj JSON objekt za WebSocket klijenta
    json_message = json.dumps({
        "topic": msg.topic,
        "message": message
    })

    # Pošalji poruku WebSocket klijentu ako postoji
    if websocket_client:
        try:
            websocket_client.write_message(json_message)
        except:
            pass  # Ignoriraj greške ako je klijent zatvoren

# Inicijalizacija MQTT klijenta
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

# Kreiranje Tornado aplikacije

def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/ws", WebSocketHandler),
    ])

# Funkcija za gašenje servera

def stop_tornado(signum, frame):
    print("Stopping Tornado app...")
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    tornado.ioloop.IOLoop.instance().add_callback_from_signal(lambda: tornado.ioloop.IOLoop.current().stop())

# Pokretanje aplikacije

if __name__ == "__main__":
    init_db()  # Inicijalizacija baze podataka
    app = make_app()
    app.listen(8888)
    print("Server is running on http://localhost:8888")

    # Pokreni MQTT petlju u pozadini
    mqtt_client.loop_start()

    # Registracija signala za uredno gašenje
    signal.signal(signal.SIGINT, stop_tornado)

    tornado.ioloop.IOLoop.current().start()
