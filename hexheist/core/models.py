from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


MemoryAction = Literal["r", "w", "v"]


@dataclass(slots=True)
class AvrdudeEntry:
    """One AVRDUDE part or programmer entry discovered at runtime."""

    id: str
    description: str = ""

    @property
    def display_name(self) -> str:
        return f"{self.description}  ·  {self.id}" if self.description else self.id


@dataclass(slots=True)
class TargetConfig:
    """Connection details shared by every AVRDUDE operation."""

    executable: str = "avrdude"
    config_file: str = ""
    programmer: str = "usbasp"
    part: str = "m328p"
    port: str = ""
    baud: str = ""
    bitclock: str = ""


@dataclass(slots=True)
class AdvancedOptions:
    """Common AVRDUDE command-line switches exposed by HexHeist."""

    force_signature: bool = False          # -F
    no_write: bool = False                 # -n
    disable_auto_erase: bool = False       # -D
    disable_verify: bool = False           # -V
    erase_before: bool = False             # -e
    verbose_count: int = 0                 # -v, -vv, ...
    exit_spec: str = ""                    # -E
    extended_params: list[str] = field(default_factory=list)  # -x
    custom_args: str = ""


@dataclass(slots=True)
class MemoryOperation:
    """One AVRDUDE -U memory operation."""

    memory: str
    action: MemoryAction
    filename: str
    file_format: str = "a"

    def as_update_spec(self) -> str:
        return f"{self.memory}:{self.action}:{self.filename}:{self.file_format}"

    @property
    def label(self) -> str:
        actions = {"r": "Read", "w": "Write", "v": "Verify"}
        return f"{actions.get(self.action, self.action)} {self.memory}"

    def validate(self) -> None:
        if not self.memory.strip():
            raise ValueError("Memory type cannot be empty.")
        if self.action not in {"r", "w", "v"}:
            raise ValueError(f"Unsupported memory action: {self.action}")
        if not self.filename.strip():
            raise ValueError("A file, '-' (stdout/stdin), or immediate value is required.")
        if self.action in {"w", "v"} and self.file_format != "m":
            path = Path(self.filename).expanduser()
            if self.filename != "-" and not path.exists():
                raise ValueError(f"Input file does not exist: {path}")
