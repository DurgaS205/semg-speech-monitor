# sEMG-speech-monitor
Full stack stutter monitoring system

Surface Electromyography (sEMG) Data Acquisition and Logging System

Project Description

This project implements a Surface Electromyography (sEMG) data acquisition and logging system for capturing muscle activity signals in real time. The system collects sEMG signals using a microcontroller-based acquisition setup and transmits the data to a Python-based server for storage and further analysis.

Surface electromyography (sEMG) measures the electrical activity produced by skeletal muscles using electrodes placed on the skin surface. These signals are widely used in biomedical research, prosthetic control, rehabilitation engineering, and human–machine interaction systems.

The developed system records time‑stamped sEMG data and stores it in a structured CSV format, enabling easy integration with signal processing and machine learning workflows.

⸻

Objectives

The main objectives of this project are:
	•	To acquire real-time sEMG signals from muscle activity.
	•	To implement a server-based data logging system.
	•	To store the collected signals in a structured and analyzable format.
	•	To enable further signal processing and machine learning analysis.

⸻

System Architecture

sEMG Sensor
   │
   ▼
Microcontroller (Arduino / ESP32)
   │
HTTP POST Transmission
   │
   ▼
Python Flask Server
   │
   ▼
CSV Data Storage
   │
   ▼
Signal Processing / Data Analysis


⸻

Hardware Components
	•	Surface EMG sensor module
	•	Microcontroller (Arduino / ESP32)
	•	Surface electrodes
	•	USB / serial communication interface

⸻

Software Components

Component	Technology
Backend Server	Python
Web Framework	Flask
Data Storage	CSV
Communication Protocol	HTTP POST
Data Format	JSON


⸻

Project Structure

semg-data-logger/
│
├── server.py
├── storage.py
├── emg_session.csv
├── README.md

File Description

server.py

Handles HTTP requests from the microcontroller and manages recording sessions.

storage.py

Implements CSV logging functionality and stores timestamped sEMG values.

emg_session.csv

Contains the recorded sEMG data for each session.


Applications

This system can be used in:
	•	Muscle activity monitoring
	•	Rehabilitation engineering
	•	Prosthetic device control
	•	Gesture recognition systems
	•	Human–machine interface research

⸻

Future Improvements
	•	Real-time signal visualization
	•	Signal filtering (band-pass / notch filtering)
	•	Multi-channel sEMG acquisition
	•	Database integration (SQLite/PostgreSQL)
	•	Machine learning–based gesture classification

⸻

Conclusion

The developed system provides a simple and scalable framework for real-time surface EMG signal acquisition and storage. The recorded dataset can be used for further analysis in biomedical signal processing, pattern recognition, and machine learning applications.
