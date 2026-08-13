# Contributing to HexHeist

Contributions are welcome.

## Before opening a pull request

- Keep changes focused.
- Run `pytest`, `python -m compileall .`, and `ruff check .`.
- Add tests for command-building or discovery behavior.
- Do not copy code from AVRDUDE or AVRDUDESS into HexHeist unless licensing and attribution have been reviewed for that specific contribution.
- Do not add a hard-coded "complete" MCU catalog. HexHeist should prefer the installed AVRDUDE catalog.
- Preserve shell-free `QProcess` execution.

## Hardware changes

If a change affects programming behavior, include in the PR description:

- OS
- AVRDUDE version
- programmer
- MCU/part
- connection type
- exact generated command
- relevant output
- expected and observed result

Never test fuse/lock changes on hardware you cannot recover.

## Style

- Python 3.10+
- type annotations for new core APIs
- small, testable core functions
- Qt UI work stays in `hexheist/ui`
- line length target: 120
