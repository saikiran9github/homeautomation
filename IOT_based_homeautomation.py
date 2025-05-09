import RPi.GPIO as GPIO
import time
import adafruit_dht
import board
import paho.mqtt.client as mqtt

# ==== GPIO Setup ====
IR_PIN = 4
CLAP_PIN = 17
RELAY_PIN = 27
DHT_PIN = 22

GPIO.setmode(GPIO.BCM)
GPIO.setup(IR_PIN, GPIO.IN)
GPIO.setup(CLAP_PIN, GPIO.IN)
GPIO.setup(RELAY_PIN, GPIO.OUT)
GPIO.output(RELAY_PIN, GPIO.LOW)

# ==== DHT11 Sensor ====
dht_sensor = adafruit_dht.DHT11(board.D22)

# ==== MQTT Setup ====
MQTT_BROKER = "192.168.0.110"
MQTT_PORT = 1883
SENSOR_TOPIC = "home/sensors"
RELAY_TOPIC = "home/relay1/cmd"

# ==== State Variables ====
prev_ir = GPIO.input(IR_PIN)
prev_clap = GPIO.input(CLAP_PIN)
CLAP_LATCH_TIME = 0.15  # seconds
clap_latched = False
clap_time = 0
relay_state = False

# ==== MQTT Callback ====
def on_message(client, userdata, msg):
    global relay_state
    command = msg.payload.decode().strip().upper()
    print(f"📩 MQTT Received: {command}")

    if command == "ON":
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        relay_state = True
        print("⚡ Relay turned ON via MQTT")
    elif command == "OFF":
        GPIO.output(RELAY_PIN, GPIO.LOW)
        relay_state = False
        print("⚡ Relay turned OFF via MQTT")
    elif command == "TOGGLE":
        relay_state = not relay_state
        GPIO.output(RELAY_PIN, GPIO.HIGH if relay_state else GPIO.LOW)
        print(f"⚡ Relay TOGGLED via MQTT: {'ON' if relay_state else 'OFF'}")

# ==== MQTT Client ====
client = mqtt.Client(protocol=mqtt.MQTTv311)
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.subscribe(RELAY_TOPIC)
client.loop_start()

try:
    while True:
        now = time.time()
        ir_state = GPIO.input(IR_PIN)
        clap_state = GPIO.input(CLAP_PIN)

        # ==== IR Motion Detection (Falling Edge) ====
        if prev_ir == GPIO.HIGH and ir_state == GPIO.LOW:
            print("👀 IR Motion Detected!")
            client.publish(SENSOR_TOPIC, "Motion Detected by IR")

            # Toggle relay
            relay_state = not relay_state
            GPIO.output(RELAY_PIN, GPIO.HIGH if relay_state else GPIO.LOW)
            print(f"⚡ Relay TOGGLED by IR: {'ON' if relay_state else 'OFF'}")

        # ==== Clap Detection with Latch ====
        if clap_state == GPIO.HIGH and not clap_latched:
            clap_time = now
            clap_latched = True

        if clap_latched and (now - clap_time <= CLAP_LATCH_TIME):
            print("👏 Clap Detected!")
            client.publish(SENSOR_TOPIC, "Clap Detected")

            # Toggle relay
            relay_state = not relay_state
            GPIO.output(RELAY_PIN, GPIO.HIGH if relay_state else GPIO.LOW)
            print(f"⚡ Relay TOGGLED by Clap: {'ON' if relay_state else 'OFF'}")

            clap_latched = False

        # ==== DHT Reading & MQTT ====
        try:
            temp = dht_sensor.temperature
            hum = dht_sensor.humidity
            if temp and hum:
                print(f"🌡️ Temp: {temp}°C, 💧 Humidity: {hum}%")
                client.publish(SENSOR_TOPIC, f"Temp: {temp}°C, Humidity: {hum}%")
        except Exception as e:
            print("❌ DHT11 Error:", e)

        prev_ir = ir_state
        prev_clap = clap_state
        time.sleep(0.01)

except KeyboardInterrupt:
    print("👋 Exiting...")

finally:
    GPIO.cleanup()
    client.loop_stop()
    client.disconnect()
