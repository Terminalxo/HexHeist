from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path

from .models import AdvancedOptions, MemoryOperation, TargetConfig


@dataclass(slots=True)
class BuiltCommand:
    executable: str
    arguments: list[str]

    def single_line(self) -> str:
        """Return a shell-readable preview. Execution never uses this string."""
        parts = [self.executable, *self.arguments]
        if os.name == "nt":
            return " ".join(_quote_windows(p) for p in parts)
        return " ".join(shlex.quote(p) for p in parts)

    def pretty(self) -> str:
        """Readable, multiline command preview for the current OS."""
        if os.name == "nt":
            quoted = [_quote_windows(self.executable), *(_quote_windows(a) for a in self.arguments)]
            return " ^\n  ".join(quoted)
        quoted = [shlex.quote(self.executable), *(shlex.quote(a) for a in self.arguments)]
        return " \\\n  ".join(quoted)


def _quote_windows(value: str) -> str:
    if not value or any(ch.isspace() or ch in '"&|<>^' for ch in value):
        return '"' + value.replace('"', '\\"') + '"'
    return value


def _custom_args(text: str) -> list[str]:
    if not text.strip():
        return []
    # The preview is shell-like, but actual execution is always argument-based.
    return shlex.split(text, posix=os.name != "nt")


def build_base_command(target: TargetConfig, advanced: AdvancedOptions | None = None) -> BuiltCommand:
    advanced = advanced or AdvancedOptions()
    exe = str(Path(target.executable).expanduser()) if target.executable else "avrdude"
    args: list[str] = []

    if target.config_file.strip():
        args += ["-C", str(Path(target.config_file).expanduser())]
    if target.programmer.strip():
        args += ["-c", target.programmer.strip()]
    if target.part.strip():
        args += ["-p", target.part.strip()]
    if target.port.strip():
        args += ["-P", target.port.strip()]
    if target.baud.strip():
        args += ["-b", target.baud.strip()]
    if target.bitclock.strip():
        args += ["-B", target.bitclock.strip()]

    if advanced.force_signature:
        args.append("-F")
    if advanced.no_write:
        args.append("-n")
    if advanced.disable_auto_erase:
        args.append("-D")
    if advanced.disable_verify:
        args.append("-V")
    if advanced.erase_before:
        args.append("-e")
    args.extend(["-v"] * max(0, min(4, int(advanced.verbose_count))))

    if advanced.exit_spec.strip():
        args += ["-E", advanced.exit_spec.strip()]
    for param in advanced.extended_params:
        if param.strip():
            args += ["-x", param.strip()]

    args.extend(_custom_args(advanced.custom_args))
    return BuiltCommand(executable=exe, arguments=args)


def with_memory_operations(
    target: TargetConfig,
    operations: list[MemoryOperation],
    advanced: AdvancedOptions | None = None,
) -> BuiltCommand:
    command = build_base_command(target, advanced)
    for operation in operations:
        operation.validate()
        command.arguments += ["-U", operation.as_update_spec()]
    return command


def signature_command(target: TargetConfig, advanced: AdvancedOptions | None = None) -> BuiltCommand:
    command = build_base_command(target, advanced)
    command.arguments += ["-U", "signature:r:-:h"]
    return command


def erase_command(target: TargetConfig, advanced: AdvancedOptions | None = None) -> BuiltCommand:
    command = build_base_command(target, advanced)
    command.arguments.append("-e")
    return command


def test_connection_command(target: TargetConfig, advanced: AdvancedOptions | None = None) -> BuiltCommand:
    return build_base_command(target, advanced)


def terminal_command(target: TargetConfig, advanced: AdvancedOptions | None = None) -> BuiltCommand:
    command = build_base_command(target, advanced)
    command.arguments.append("-t")
    return command
