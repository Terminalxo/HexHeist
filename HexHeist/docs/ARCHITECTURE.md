# HexHeist Architecture

## Overview

HexHeist is intentionally a **GUI orchestration layer** around the separately installed AVRDUDE executable.

```text
PySide6 UI
   │
   ├── Target / programmer configuration
   ├── Memory operation builder
   ├── Fuse/lock editor
   ├── Terminal
   └── Advanced options
   │
   ▼
Command model (pure Python)
   │
   ▼
QProcess (executable + argument list)
   │
   ▼
AVRDUDE
   │
   ▼
Programmer / bootloader
   │
   ▼
AVR target
```

## Module responsibilities

### `hexheist/core/models.py`

Small dataclasses representing:

- discovered AVRDUDE entries
- target connection configuration
- advanced switches
- `-U` memory operations

No Qt dependency.

### `hexheist/core/commands.py`

Builds commands from structured data. It deliberately returns:

- executable path
- argument list

The UI displays a shell-readable preview, but never executes that preview string.

### `hexheist/core/discovery.py`

Responsible for:

- finding plausible AVRDUDE installations
- probing the version
- running `-p ?` and `-c ?`
- parsing part/programmer lists
- enumerating serial ports

Discovery is runtime-based so HexHeist follows the user's AVRDUDE installation instead of maintaining its own copy of `avrdude.conf`.

### `hexheist/core/settings.py`

Thin wrapper over `QSettings` for persistent preferences, recent files and command history.

### `hexheist/ui/theme.py`

Defines high-contrast light/dark palettes and a Qt stylesheet. System mode maps the operating-system palette to a HexHeist light or dark theme.

### `hexheist/ui/components.py`

Small reusable widgets including the card container and vector HexHeist logo.

### `hexheist/ui/main_window.py`

Coordinates the desktop UI, discovery worker, `QProcess`, validation, dialogs, log display, terminal I/O, persistence and navigation.

## Process safety

A programming command is launched as:

```python
process.setProgram(command.executable)
process.setArguments(command.arguments)
process.start()
```

It is **not** launched as `shell=True`, `cmd /c`, `sh -c`, or a single concatenated command string.

## Discovery lifecycle

1. UI starts immediately.
2. A `QThread` runs AVRDUDE discovery.
3. Candidate paths are checked in priority order.
4. Version probing confirms the executable.
5. Part/programmer catalogs are queried.
6. The worker emits results back to the UI thread.
7. Searchable selectors are populated while preserving saved selections.

## Memory model

HexHeist does not hard-code AVR memories as a closed enum. The UI suggests common memory names but allows custom text, because AVRDUDE configurations contain device-specific memories.

Each memory operation maps to:

```text
-U memory:operation:file:format
```

Multiple operations are appended in UI queue order.

## Interactive terminal

Terminal mode uses the same `QProcess`, started with `-t`. UI input is written to the process's stdin. stdout/stderr are mirrored into both the terminal view and global console.

## Extension points

Future work can add:

- richer part metadata via current AVRDUDE developer/terminal commands
- fuse-bit semantic descriptions sourced from device packs/datasheets
- programmer-specific `-x` UI schemas
- presets/profiles
- packaging/signing pipelines
- optional libavrdude integration where stable and available

These additions should keep the command-model layer testable without Qt or physical hardware.
