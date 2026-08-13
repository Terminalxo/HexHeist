from pathlib import Path

from hexheist.core.commands import build_base_command, with_memory_operations
from hexheist.core.models import AdvancedOptions, MemoryOperation, TargetConfig


def test_base_command_has_programmer_and_part():
    cmd = build_base_command(TargetConfig(executable="avrdude", programmer="usbasp", part="m328p"))
    assert cmd.executable == "avrdude"
    assert cmd.arguments == ["-c", "usbasp", "-p", "m328p"]


def test_connection_options_are_separate_arguments():
    target = TargetConfig(
        executable="/Applications/Tools Folder/avrdude",
        programmer="arduino",
        part="m328p",
        port="/dev/cu.usb modem 1",
        baud="115200",
        bitclock="10",
    )
    cmd = build_base_command(target)
    assert cmd.arguments == [
        "-c", "arduino", "-p", "m328p", "-P", "/dev/cu.usb modem 1", "-b", "115200", "-B", "10"
    ]
    assert "Tools Folder" in cmd.single_line()


def test_memory_write_builds_u_argument(tmp_path: Path):
    firmware = tmp_path / "blink.hex"
    firmware.write_text(":00000001FF\n")
    op = MemoryOperation("flash", "w", str(firmware), "i")
    cmd = with_memory_operations(TargetConfig(programmer="usbasp", part="m328p"), [op])
    assert cmd.arguments[-2:] == ["-U", f"flash:w:{firmware}:i"]


def test_immediate_fuse_does_not_require_file():
    op = MemoryOperation("lfuse", "w", "0x62", "m")
    cmd = with_memory_operations(TargetConfig(programmer="usbasp", part="m328p"), [op])
    assert cmd.arguments[-1] == "lfuse:w:0x62:m"


def test_advanced_flags_and_repeated_x():
    advanced = AdvancedOptions(
        force_signature=True,
        no_write=True,
        disable_auto_erase=True,
        disable_verify=True,
        verbose_count=2,
        exit_spec="reset",
        extended_params=["foo", "bar=1"],
    )
    cmd = build_base_command(TargetConfig(programmer="usbasp", part="m328p"), advanced)
    assert "-F" in cmd.arguments
    assert "-n" in cmd.arguments
    assert "-D" in cmd.arguments
    assert "-V" in cmd.arguments
    assert cmd.arguments.count("-v") == 2
    assert cmd.arguments.count("-x") == 2


def test_pretty_preview_contains_continuations():
    cmd = build_base_command(TargetConfig(programmer="usbasp", part="m328p"))
    pretty = cmd.pretty()
    assert "avrdude" in pretty
    assert "usbasp" in pretty
    assert "m328p" in pretty
