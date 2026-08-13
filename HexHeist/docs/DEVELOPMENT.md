# HexHeist Development Guide

## Environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Run

```bash
python main.py
```

or after an editable install:

```bash
pip install -e .
hexheist
```

## Test

```bash
pytest
python -m compileall .
ruff check .
```

The core command/discovery tests are hardware-independent.

## Hardware validation matrix

Before tagging a release, validate on disposable/recoverable hardware.

### OS

- macOS (Apple Silicon preferred)
- Windows 11
- current Ubuntu/Debian Linux

### Programming paths

- USB programmer (USBasp or equivalent)
- serial bootloader/programmer
- at least one current UPDI-capable programmer if available

### Operations

- AVRDUDE discovery
- full part/programmer catalog load
- serial-port refresh
- test connection
- signature read
- flash write
- flash verify
- flash read through generic memory queue
- EEPROM read/write/verify
- fuse read
- fuse write on a sacrificial/recoverable target
- lock read (avoid irreversible lock testing unless recovery is planned)
- chip erase
- terminal `help` and `quit`
- Stop Process
- log export
- recent files
- settings persistence
- light/dark/system modes

## Coding rules

- Keep command construction in `core/commands.py`.
- Do not execute shell strings.
- Avoid adding a local duplicated MCU/programmer catalog; runtime AVRDUDE remains the source of truth.
- UI code should not guess device-specific fuse meanings.
- Destructive actions need confirmation.
- New command-model behavior should include unit tests.

## Release checklist

1. Update `hexheist.__version__` and `pyproject.toml` together.
2. Run unit/static tests.
3. Complete the hardware validation matrix appropriate for changed areas.
4. Update README and CHANGELOG.
5. Verify a clean installation in new virtual environments.
6. Build/sign platform packages only from a tagged, tested commit.

## Packaging roadmap

The source release intentionally does not require a platform-specific packager. Future release automation can use PyInstaller or Briefcase after hardware/UI validation. macOS signing/notarization and Windows code signing should be treated as release-engineering tasks rather than application runtime logic.
