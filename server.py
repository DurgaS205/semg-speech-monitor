from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from storage import save_emg_value
import threading
import serial
from datetime import datetime
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# change COM port if needed
ser = serial.Serial('COM7', 115200)

running = False
patient_name = "Adita. P. Nair"   # for now single test subject
session_time = None


@app.route("/")
def home():
    return "sEMG Backend Running"


@app.route("/start")
def start_session():
    global running, session_time

    running = True
    session_time = datetime.now()

    return jsonify({
        "status": "session started",
        "patient": patient_name,
        "session_time": str(session_time)
    })


@app.route("/stop")
def stop_session():
    global running
    running = False

    return jsonify({"status": "session stopped"})


@app.route("/history")
def history():
    try:
        with open("emg_session.csv", "r") as f:
            data = f.readlines()
        return {"data": data}
    except:
        return {"data": []}


def emg_stream():
    global running

    while True:

        if running and ser.in_waiting:

            line = ser.readline().decode().strip()

            if line != "":
                value = int(line)

                print("EMG:", value)

                socketio.emit("emg_data", {"value": value})

                save_emg_value(
                    patient_name,
                    session_time,
                    value
                )

        time.sleep(0.001)


@socketio.on("connect")
def client_connected():
    print("Frontend connected")


if __name__ == "__main__":
    thread = threading.Thread(target=emg_stream)
    thread.daemon = True
    thread.start()

    socketio.run(app, host="0.0.0.0", port=5000)