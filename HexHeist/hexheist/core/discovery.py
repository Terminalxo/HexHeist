from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
from pathlib import Path

from .models import AvrdudeEntry


DEFAULT_PARTS = [
    AvrdudeEntry("m328p", "ATmega328P"),
    AvrdudeEntry("m2560", "ATmega2560"),
    AvrdudeEntry("m32u4", "ATmega32U4"),
    AvrdudeEntry("m16", "ATmega16"),
    AvrdudeEntry("m32", "ATmega32"),
    AvrdudeEntry("t85", "ATtiny85"),
    AvrdudeEntry("t13", "ATtiny13"),
]

DEFAULT_PROGRAMMERS = [
    AvrdudeEntry("usbasp", "USBasp"),
    AvrdudeEntry("arduino", "Arduino / STK500v1 bootloader"),
    AvrdudeEntry("avrisp", "AVR ISP"),
    AvrdudeEntry("avrispmkII", "AVRISP mkII"),
    AvrdudeEntry("usbtiny", "USBtinyISP"),
    AvrdudeEntry("stk500v1", "STK500 v1"),
    AvrdudeEntry("stk500v2", "STK500 v2"),
]


def avrdude_candidates(saved_path: str = "") -> list[str]:
    """Return plausible AVRDUDE executables in priority order."""
    candidates: list[str] = []

    def add(path: str | None) -> None:
        if not path:
            return
        p = os.path.abspath(os.path.expanduser(path))
        if p not in candidates and os.path.isfile(p) and os.access(p, os.X_OK):
            candidates.append(p)

    add(saved_path)
    add(shutil.which("avrdude"))
    add(shutil.which("avrdude.exe"))

    if sys_platform() == "macos":
        for path in (
            "/opt/homebrew/bin/avrdude",
            "/usr/local/bin/avrdude",
            "/opt/local/bin/avrdude",
        ):
            add(path)
        patterns = [
            "/Applications/Arduino*.app/Contents/Java/hardware/tools/avr/bin/avrdude",
            "/Applications/Arduino*.app/Contents/Resources/app/lib/backend/resources/arduino-cli",
            os.path.expanduser("~/Library/Arduino15/packages/*/tools/avrdude/*/bin/avrdude"),
        ]
    elif sys_platform() == "windows":
        program_files = [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")]
        local = os.environ.get("LOCALAPPDATA", "")
        patterns = [
            *(os.path.join(p, "Arduino*", "hardware", "tools", "avr", "bin", "avrdude.exe") for p in program_files if p),
            os.path.join(local, "Arduino15", "packages", "*", "tools", "avrdude", "*", "bin", "avrdude.exe"),
            "C:/WinAVR-*/bin/avrdude.exe",
        ]
    else:
        for path in ("/usr/bin/avrdude", "/usr/local/bin/avrdude", "/snap/bin/avrdude"):
            add(path)
        patterns = [
            os.path.expanduser("~/.arduino15/packages/*/tools/avrdude/*/bin/avrdude"),
            os.path.expanduser("~/Arduino*/hardware/tools/avr/bin/avrdude"),
        ]

    for pattern in patterns:
        for match in glob.glob(pattern):
            add(match)
    return candidates


def sys_platform() -> str:
    import sys

    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    return "linux"


def probe_version(executable: str, timeout: float = 4.0) -> str:
    try:
        proc = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    output = (proc.stdout + "\n" + proc.stderr).strip()
    match = re.search(r"avrdude(?:\s+version)?\s+([0-9]+(?:\.[0-9A-Za-z._+-]+)*)", output, re.I)
    return match.group(1) if match else (output.splitlines()[0].strip() if output else "")


def _run_listing(executable: str, kind: str, timeout: float = 8.0) -> str:
    switch = "-p" if kind == "part" else "-c"
    try:
        proc = subprocess.run(
            [executable, switch, "?"],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return (proc.stdout or "") + "\n" + (proc.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return ""


def parse_listing(text: str) -> list[AvrdudeEntry]:
    """Parse AVRDUDE 6.x–8.x style part/programmer listings conservatively."""
    entries: list[AvrdudeEntry] = []
    seen: set[str] = set()

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("avrdude:", "AVRDUDE", "Valid ", "The following", "Use ", "Syntax")):
            continue
        line = re.sub(r"^[|+`'\\\- ]+", "", line).strip()

        # Common forms include:
        #   m328p = ATmega328P ...
        #   m328p     ATmega328P ...
        #   usbasp = USBasp, http://...
        match = re.match(r"^([A-Za-z0-9_.:+/\-]+)\s*(?:=|\s{2,}|\t+)\s*(.+?)\s*$", line)
        if not match:
            continue
        ident, description = match.groups()
        ident = ident.strip()
        if ident in {"?", "id", "part", "programmer"} or len(ident) > 80:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.:+/\-]+", ident):
            continue
        description = description.strip().strip('"')
        if ident not in seen:
            entries.append(AvrdudeEntry(ident, description))
            seen.add(ident)

    return sorted(entries, key=lambda x: (x.description.lower(), x.id.lower()))


def discover_parts(executable: str) -> list[AvrdudeEntry]:
    return parse_listing(_run_listing(executable, "part")) or DEFAULT_PARTS.copy()


def discover_programmers(executable: str) -> list[AvrdudeEntry]:
    return parse_listing(_run_listing(executable, "programmer")) or DEFAULT_PROGRAMMERS.copy()


def serial_ports() -> list[tuple[str, str]]:
    """Return (device, description); gracefully degrades when pyserial is absent."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    ports = [(p.device, p.description or "") for p in list_ports.comports()]
    return sorted(ports, key=lambda p: p[0].lower())
