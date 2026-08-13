# Feature Matrix

HexHeist is inspired by the workflow of established AVRDUDE GUIs, but its implementation is independent and cross-platform.

## Current 1.0 feature set

| Capability | HexHeist 1.0 |
|---|---|
| AVRDUDE frontend | Yes |
| Windows/macOS/Linux source support | Yes |
| Light theme | Yes |
| Dark theme | Yes |
| System theme | Yes |
| Runtime AVRDUDE detection | Yes |
| Runtime MCU/part catalog | Yes |
| Runtime programmer catalog | Yes |
| Editable custom part/programmer IDs | Yes |
| Serial port listing | Yes |
| Flash write | Yes |
| Flash verify | Yes |
| Flash read | Yes, through Memories |
| EEPROM read/write/verify | Yes, through Memories |
| Generic AVRDUDE memories | Yes |
| Multi-operation `-U` queue | Yes |
| Signature read | Yes |
| Chip erase | Yes |
| Fuse reads | Yes |
| Fuse writes | Yes |
| Lock read/write | Yes |
| Numbered modern fuse memories | Yes |
| Interactive terminal mode | Yes |
| Bit clock | Yes |
| Baud/port | Yes |
| Force / no-write / no-erase / no-verify | Yes |
| Verbosity | Yes |
| Exit specs | Yes |
| Programmer extended parameters | Yes |
| Custom avrdude.conf | Yes |
| Expert arbitrary command arguments | Yes |
| Command preview | Yes |
| Pretty multiline preview | Yes |
| Live stdout/stderr | Yes |
| Stop running process | Yes |
| Log export | Yes |
| Recent firmware files | Yes |
| Command history | Yes |
| Drag and drop firmware | Yes |
| Settings persistence | Yes |

## Areas intentionally not encoded as static data

### MCU/board catalog

HexHeist does not ship a copied snapshot of AVRDUDE's part database. The installed AVRDUDE is queried at runtime. This is the mechanism used to cover the full catalog available on a given machine.

### Fuse bit names

HexHeist 1.0 edits fuse memories as values. It does not ship a second device-specific database that assigns a semantic name to every bit for every part. This avoids stale or incorrect definitions. A future semantic fuse editor should source authoritative device metadata and should always show the raw resulting value.

### Programmer-specific option forms

Programmers can define different extended parameters. HexHeist supports repeated `-x` arguments without pretending every programmer uses the same schema.

## Future enhancements

- profile/preset manager with JSON import/export
- optional semantic fuse-bit visualization backed by authoritative device packs
- compatible-part filtering for selected programmer
- richer device info page using modern AVRDUDE metadata commands
- packaged, signed applications for each OS
- CI hardware-in-loop test harness where practical
