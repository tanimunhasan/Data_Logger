import serial
import time
import csv
import os

# === USER CONFIGURATION ===
COM_PORT = 'COM5'       # Change as needed
BAUD_RATE = 9600        # Change based on your device
CSV_FILE = 'serial_log.csv'

def main():
    try:
        # Check if CSV file exists; if not, write header
        file_exists = os.path.isfile(CSV_FILE)
        with serial.Serial(COM_PORT, BAUD_RATE, timeout=1) as ser, open(CSV_FILE, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            if not file_exists:
                writer.writerow(['Timestamp', 'Data'])  # Write header

            print(f"[INFO] Logging started on {COM_PORT} at {BAUD_RATE} baud rate...")
            while True:
                if ser.in_waiting:
                    line = ser.readline().decode(errors='ignore').strip()
                    if line:
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                        writer.writerow([timestamp, line])
                        csvfile.flush()
                        print(f"{timestamp} - {line}")

    except serial.SerialException as e:
        print(f"[ERROR] Serial error: {e}")
    except KeyboardInterrupt:
        print("\n[INFO] Logging stopped by user.")

if __name__ == "__main__":
    main()
