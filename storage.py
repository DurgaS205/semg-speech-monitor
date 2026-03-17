import csv
from datetime import datetime
import os

FILE_NAME = "emg_session.csv"


def save_emg_value(patient_name, session_time, value):

    file_exists = os.path.isfile(FILE_NAME)

    with open(FILE_NAME, "a", newline="") as file:

        writer = csv.writer(file)

        # write header only once
        if not file_exists:
            writer.writerow([
                "Patient ID"
                "Patient_Name",
                "Session_Time",
                "Timestamp",
                "sEMG_Value",
                "Remarks"
            ])

        writer.writerow([
            patient_name,
            session_time,
            datetime.now(),
            value,
            ""
        ])