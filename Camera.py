import cv2
import time
import smtplib
import numpy as np
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os

# ---------------- CONFIG ----------------
CAMERAS = {
   "10.1.89.112 - Row C - Back Side": "rtsp://admin:Intel@2024@192.168.1.115/camera1"
}

CHECK_INTERVAL_SEC = 60
RETRIES = 3
READ_FRAME_TIMEOUT_SEC = 5
VARIANCE_THRESHOLD = 10.0

# Email settings
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "shyamala7680@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "gsoucldicintuyiy")  # Use env vars in cloud
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "bharathkaleeswaran004@gmail.com")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ---------------- Status Tracking ----------------
camera_status = {name: None for name in CAMERAS}
status_changes = []
sno_counter = 1

# ---------------- Email Function ----------------
def send_email_alert(subject, body_html):
    """Send HTML formatted email"""
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        logging.info(f"[EMAIL] Sent to {RECEIVER_EMAIL}")
    except Exception as e:
        logging.error(f"[EMAIL ERROR] {e}")

# ---------------- Frame Validation ----------------
def is_frame_valid(frame):
    if frame is None or frame.size == 0:
        return False
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    except:
        return False
    return float(np.var(gray)) >= VARIANCE_THRESHOLD

# ---------------- Status Change Logger ----------------
def log_status_change(camera_name, prev_status, new_status):
    """Log status changes and build HTML table"""
    global sno_counter, status_changes

    now = datetime.now().strftime("%d-%m-%Y %I:%M:%S%p")
    status_change_str = f"{prev_status} ({now}) → {new_status} ({now})"
    color = "green" if new_status == "online" else "red"

    entry = f"""
        <tr>
            <td>{sno_counter}</td>
            <td>{camera_name}</td>
            <td>{status_change_str}</td>
            <td style="color:{color}; font-weight:bold;">{new_status}</td>
        </tr>
    """
    status_changes.append(entry)
    sno_counter += 1

    # Build HTML email
    table_html = f"""
    <html>
    <head>
    <style>
        table {{
            border-collapse: collapse;
            width: 90%;
        }}
        th, td {{
            border: 1px solid black;
            padding: 8px;
            text-align: center;
        }}
        th {{
            background-color: #f2f2f2;
        }}
    </style>
    </head>
    <body>
        <h2>Camera Status Change Alert</h2>
        <table>
            <tr>
                <th>S.No</th>
                <th>Name (IP)</th>
                <th>Status Change</th>
                <th>Current Status</th>
            </tr>
            {''.join(status_changes)}
        </table>
    </body>
    </html>
    """
    send_email_alert("Camera Status Change Alert", table_html)

# ---------------- Camera Check ----------------
def check_camera(camera_name, rtsp_url):
    global camera_status
    prev_status = camera_status[camera_name]

    for attempt in range(1, RETRIES + 1):
        logging.info(f"[{camera_name}] Attempt {attempt}/{RETRIES}")
        try:
            cap = cv2.VideoCapture(rtsp_url)  # headless cloud-friendly
        except Exception as e:
            logging.error(f"[{camera_name}] Capture error: {e}")
            time.sleep(2)
            continue

        if not cap.isOpened():
            logging.warning(f"[{camera_name}] Could not open stream")
            time.sleep(2)
            continue

        start = time.time()
        while time.time() - start < READ_FRAME_TIMEOUT_SEC:
            ret, frame = cap.read()
            if ret and is_frame_valid(frame):
                cap.release()
                new_status = "online"
                if prev_status != new_status:
                    log_status_change(camera_name, prev_status or "offline", new_status)
                camera_status[camera_name] = new_status
                return True
            time.sleep(1)

        cap.release()
        logging.warning(f"[{camera_name}] No valid frame")

    # If all retries fail
    new_status = "offline"
    if prev_status != new_status:
        log_status_change(camera_name, prev_status or "online", new_status)
    camera_status[camera_name] = new_status
    return False

# ---------------- Main Loop ----------------
def main_loop():
    logging.info("📷 Multi-Camera Health Monitor Started (Cloud Compatible)")
    try:
        while True:
            for cam_name, rtsp in CAMERAS.items():
                check_camera(cam_name, rtsp)
            logging.info(f"Waiting {CHECK_INTERVAL_SEC} seconds...\n")
            time.sleep(CHECK_INTERVAL_SEC)
    except KeyboardInterrupt:
        logging.info("Stopped by user")

if __name__ == "__main__":
    main_loop()
