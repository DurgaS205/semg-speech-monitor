import random
import time

def generate_emg_data():
    """Simulate EMG signal values"""
    while True:
        value = random.randint(1500, 2500)
        yield value
        time.sleep(0.1)
