from __future__ import annotations

from PySide6.QtCore import QSettings


ORG_NAME = "HexHeist"
APP_NAME = "HexHeist"


class AppSettings:
    """Typed convenience wrapper around QSettings."""

    def __init__(self) -> None:
        self.q = QSettings(ORG_NAME, APP_NAME)

    def get(self, key: str, default=None):
        return self.q.value(key, default)

    def set(self, key: str, value) -> None:
        self.q.setValue(key, value)

    def recent_files(self) -> list[str]:
        raw = self.q.value("recent/files", [])
        if isinstance(raw, str):
            return [raw]
        return list(raw or [])

    def add_recent_file(self, filename: str) -> None:
        files = [f for f in self.recent_files() if f != filename]
        files.insert(0, filename)
        self.q.setValue("recent/files", files[:10])

    def command_history(self) -> list[str]:
        raw = self.q.value("history/commands", [])
        if isinstance(raw, str):
            return [raw]
        return list(raw or [])

    def add_command(self, command: str) -> None:
        history = self.command_history()
        history.insert(0, command)
        self.q.setValue("history/commands", history[:20])
