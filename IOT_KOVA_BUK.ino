#include <DHT22.h>
#include <Wire.h>
#include <LCD_I2C.h>
#include <Servo.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>

// WiFi i MQTT podešavanja
const char* ssid = "iPhone od: Marko";    
const char* password = "markan123";  
const char* mqtt_server = "172.20.10.6"; //Ili IP adresa MQTT brokera
const int mqtt_port = 1883;
const char* mqtt_topic_temp = "sensor/temp";

WiFiClient espClient;
PubSubClient client(espClient);

// Definisanje pinova
#define DHT_PIN 13
#define LED_PIN 16
#define PIR_PIN 14
#define SERVO_PIN 2
#define BUZZER_PIN 12

DHT22 dht22(DHT_PIN); 
LCD_I2C lcd(0x20, 20, 4);
Servo myservo;

int pirState = LOW;
int val = 0; 
int buzzerState = 1;
unsigned long previousMillis = 0;
unsigned long previousMillis2 = 0;

// Non-blocking delay funkcija
bool nonBlockingDelay(unsigned long interval, unsigned long &previousMillis) {
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;
    return true;
  }
  return false;
}

// Funkcija za povezivanje na WiFi
void setup_wifi() {
  WiFi.begin(ssid, password);
  Serial.print("Povezivanje na WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi povezano!");
  Serial.print("IP adresa: ");
  Serial.println(WiFi.localIP());
}

// Funkcija za povezivanje na MQTT broker
void reconnect() {
  while (!client.connected()) {
    Serial.print("Pokušaj povezivanja na MQTT...");
    if (client.connect("ESP8266Client")) {
      Serial.println("Povezano!");
    } else {
      Serial.print("Neuspješno, kod: ");
      Serial.print(client.state());
      Serial.println(" Pokušavam ponovno za 5 sekundi.");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(921600);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  pinMode(PIR_PIN, INPUT);
  myservo.attach(SERVO_PIN);

  setup_wifi();
  
  client.setServer(mqtt_server, mqtt_port);

  Wire.begin(4, 5);
  lcd.begin();
  lcd.clear();
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  int pos;
  if (Serial.available()) {
    char ch = Serial.read();
    if (ch >= '0' && ch <= '9') {
      buzzerState = (ch - '0');
    }
  }

  // PIR senzor
  val = digitalRead(PIR_PIN);
  if (val == HIGH) {
    digitalWrite(LED_PIN, HIGH);
    if (pirState == LOW) {
      for (pos = 0; pos <= 180; pos++) {
        myservo.write(pos);
        delay(15);
      }
      Serial.println("Motion detected!");
      pirState = HIGH;
    }
  } else {
    digitalWrite(LED_PIN, LOW);
    if (pirState == HIGH) {
      if (nonBlockingDelay(3000, previousMillis2)) {
        for (pos = 180; pos >= 0; pos--) {
          myservo.write(pos);
          delay(15);
        }
      }
      Serial.println("Motion ended!");
      pirState = LOW;
    }
  }

  // DHT22 - Čitanje temperature i slanje na MQTT
  float t = dht22.getTemperature();
  float h = dht22.getHumidity();

  if (t > 25 && buzzerState == 1) {
    tone(BUZZER_PIN, 1000);
    digitalWrite(LED_PIN, HIGH);
    if (nonBlockingDelay(3000, previousMillis)) {
      noTone(BUZZER_PIN);
      digitalWrite(LED_PIN, LOW);
    }
  } else if (buzzerState == 0) {
    noTone(BUZZER_PIN);
    digitalWrite(LED_PIN, LOW);
  }

  if (dht22.getLastError() != dht22.OK) {
    Serial.print("Greška sa senzorom: ");
    Serial.println(dht22.getLastError());
  }

  Serial.print("h="); Serial.print(h, 1); Serial.print("\t");
  Serial.print("t="); Serial.println(t, 1);

  lcd.setCursor(0, 0);
  lcd.print("T= "); lcd.setCursor(3, 0); lcd.print(t);
  lcd.setCursor(0, 1);
  lcd.print("H= "); lcd.setCursor(3, 1); lcd.print(h);

  // MQTT publish temperature
  String tempStr = String(t, 2);  // Konvertuje float u string sa 2 decimale
  client.publish(mqtt_topic_temp, tempStr.c_str());  // .c_str() konvertuje u C-string


  delay(2000);
}
