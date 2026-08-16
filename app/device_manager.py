"""Wrapper around the bundled adb.exe / scrcpy.exe binaries."""
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

CREATE_NO_WINDOW = 0x08000000
DEFAULT_TCPIP_PORT = 5555


def resource_dir() -> Path:
    """Return the folder containing adb.exe/scrcpy.exe, in dev or frozen mode."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent / "resources"
    return base / "bin"


ADB_PATH = resource_dir() / "adb.exe"
SCRCPY_PATH = resource_dir() / "scrcpy.exe"


class DeviceError(RuntimeError):
    pass


def is_wifi_serial(serial: str) -> bool:
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}:\d+$", serial):
        return True
    # Devices adb auto-discovers over the network via mDNS (no manual
    # `adb connect` needed) get a serial like "adb-XXXX._adb-tls-connect._tcp".
    return "_tcp" in serial


@dataclass
class Device:
    serial: str
    name: str
    is_wifi: bool


def _run(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            [str(ADB_PATH), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
    except FileNotFoundError as exc:
        raise DeviceError(f"No se encontro adb.exe en {ADB_PATH}") from exc
    except subprocess.TimeoutExpired as exc:
        raise DeviceError("El dispositivo no respondio a tiempo (timeout).") from exc


def start_server() -> None:
    _run(["start-server"])


def list_devices() -> list[Device]:
    """Return devices reported by `adb devices`, excluding unauthorized/offline ones."""
    result = _run(["devices", "-l"])
    devices: list[Device] = []
    for line in result.stdout.splitlines()[1:]:
        line = line.strip()
        if not line or "\t" not in line and " " not in line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        if state != "device":
            continue
        name = get_device_name(serial) or serial
        devices.append(Device(serial=serial, name=name, is_wifi=is_wifi_serial(serial)))
    return devices


def list_usb_devices() -> list[Device]:
    """Return only devices connected physically by USB cable (not Wi-Fi)."""
    return [d for d in list_devices() if not d.is_wifi]


def find_wifi_device() -> Optional[Device]:
    """Return a Wi-Fi device adb already knows about right now, including one
    auto-discovered over the network via mDNS with no `adb connect` needed.
    Once a phone has been paired at least once, this lets NayerControl find
    it again on its own even after its Wireless debugging IP/port changes,
    without the user having to copy anything from the phone's screen."""
    for device in list_devices():
        if device.is_wifi:
            return device
    return None


def list_unauthorized() -> list[str]:
    result = _run(["devices"])
    pending = []
    for line in result.stdout.splitlines()[1:]:
        line = line.strip()
        if line.endswith("unauthorized"):
            pending.append(line.split()[0])
    return pending


def get_device_name(serial: str) -> Optional[str]:
    result = _run(["-s", serial, "shell", "getprop", "ro.product.model"])
    name = result.stdout.strip()
    return name or None


def connect_tcpip(ip: str, port: int = DEFAULT_TCPIP_PORT, timeout: int = 8) -> None:
    result = _run(["connect", f"{ip}:{port}"], timeout=timeout)
    output = (result.stdout + result.stderr).lower()
    if "connected" not in output and "already connected" not in output:
        raise DeviceError(f"No se pudo conectar a {ip}:{port} - {result.stdout.strip()}")


def pair(ip: str, pair_port: int, code: str, timeout: int = 15) -> None:
    """Android 11+ 'wireless debugging' pairing flow (adb pair ip:port code)."""
    result = _run(["pair", f"{ip}:{pair_port}", code], timeout=timeout)
    output = (result.stdout + result.stderr).lower()
    if "successfully paired" not in output:
        raise DeviceError(f"Emparejamiento fallido: {result.stdout.strip() or result.stderr.strip()}")


def disconnect(serial: str) -> None:
    _run(["disconnect", serial])


def kill_server() -> None:
    _run(["kill-server"])


def build_scrcpy_args(serial: str, options: dict) -> list[str]:
    args = ["-s", serial]

    over_wifi = is_wifi_serial(serial) and options.get("wifi_optimize", True)
    if over_wifi:
        # Wi-Fi has less bandwidth and more latency than USB: cap bitrate,
        # resolution and frame rate, and skip audio, to keep the mirror smooth.
        bitrate = options.get("wifi_bitrate_mbps")
        max_size = options.get("wifi_max_size")
        max_fps = options.get("wifi_max_fps")
        if options.get("wifi_no_audio", True):
            args.append("--no-audio")
    else:
        bitrate = options.get("bitrate_mbps")
        max_size = options.get("max_size")
        max_fps = None

    if bitrate:
        args += ["-b", f"{bitrate}M"]
    if max_size:
        args += ["-m", str(max_size)]
    if max_fps:
        args += ["--max-fps", str(max_fps)]
    if options.get("fullscreen"):
        args.append("-f")
    if options.get("turn_screen_off"):
        args.append("-S")
    if options.get("stay_awake"):
        args.append("-w")
    return args


def launch_mirror(serial: str, options: dict) -> subprocess.Popen:
    if not SCRCPY_PATH.exists():
        raise DeviceError(f"No se encontro scrcpy.exe en {SCRCPY_PATH}")
    args = build_scrcpy_args(serial, options)
    return subprocess.Popen(
        [str(SCRCPY_PATH), *args],
        cwd=str(SCRCPY_PATH.parent),
        creationflags=CREATE_NO_WINDOW,
    )
