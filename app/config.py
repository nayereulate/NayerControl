"""Persistent app configuration stored in %APPDATA%\\NayerControl."""
import json
import os
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "NayerControl"
CONFIG_FILE = APP_DIR / "config.json"

DEFAULTS = {
    "devices": {},       # serial -> {"name": str, "ip": str, "port": int}
    "last_device": None,  # serial of the last used device
    "connection_mode": "wifi",  # "wifi" or "usb"
    "bitrate_mbps": 8,
    "max_size": 0,        # 0 = original resolution
    "fullscreen": False,
    "turn_screen_off": False,
    "stay_awake": True,
}


def _ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load() -> dict:
    _ensure_app_dir()
    if not CONFIG_FILE.exists():
        return dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)


def save(config: dict) -> None:
    _ensure_app_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def remember_device(config: dict, serial: str, name: str, ip: str, port: int) -> None:
    config["devices"][serial] = {"name": name, "ip": ip, "port": port}
    config["last_device"] = serial
    save(config)


def forget_device(config: dict, serial: str) -> None:
    config["devices"].pop(serial, None)
    if config.get("last_device") == serial:
        config["last_device"] = None
    save(config)
