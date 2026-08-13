# Technical References

HexHeist is implemented independently. These upstream references are useful when maintaining AVRDUDE integration.

## AVRDUDE

- Project: https://github.com/avrdudes/avrdude
- Current documentation: https://avrdudes.github.io/avrdude/
- Command-line options: https://avrdudes.github.io/avrdude/8.2/avrdude_3.html
- Parts list: https://avrdudes.github.io/avrdude/8.2/avrdude_45.html

Important behaviors relied on by HexHeist:

- `-p ?` lists parts known to the installed AVRDUDE configuration.
- `-c ?` lists programmers.
- `-U memory:op:file:format` is the generic memory-operation model.
- `-t` starts interactive terminal mode.
- AVRDUDE can expose device-specific memories beyond flash/EEPROM.

## AVRDUDESS

- Project: https://github.com/ZakKemble/AVRDUDESS

AVRDUDESS is referenced as an established AVRDUDE-GUI workflow and historical inspiration only. HexHeist does not copy or bundle AVRDUDESS source code, assets, presets, or device metadata.

## Qt / PySide6

- Qt for Python: https://doc.qt.io/qtforpython-6/

HexHeist uses `QProcess` for non-blocking AVRDUDE execution and Qt widgets/QSettings for the desktop UI and preferences.
