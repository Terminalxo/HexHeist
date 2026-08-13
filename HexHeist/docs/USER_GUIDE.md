# HexHeist User Guide

## 1. AVRDUDE status

The top-right and lower-left status indicators show whether AVRDUDE has been detected. When detection succeeds, HexHeist displays the version and loads the part/programmer lists reported by that executable.

If detection fails:

1. Install AVRDUDE.
2. Restart HexHeist or click **Detect**.
3. If necessary, use **Browse** and select the executable manually.

## 2. Selecting a programmer and MCU

Both selectors are searchable and editable. The visible entry includes a human-readable description and the AVRDUDE ID. The ID is what is passed to `-c` or `-p`.

If you maintain a custom `avrdude.conf`, you can enter IDs not shown in the discovered list.

## 3. Ports

Click the refresh button beside **Port** to enumerate serial ports. Leave the port on **Auto / programmer default** when the selected programmer does not require a specific port.

The field is editable because AVRDUDE supports connection strings beyond normal serial devices, including USB selectors and network endpoints for some programmers.

## 4. Firmware programming

The quick workflow always targets `flash` memory.

- **Flash Firmware** creates a `flash:w` operation.
- **Verify** creates a `flash:v` operation.

The selected format is inferred from the file extension when possible and can be changed manually.

## 5. Memories page

Use this page when you need something other than the quick flash flow.

1. Enter/select a memory.
2. Choose Read, Write or Verify.
3. Select a file or enter an immediate value where appropriate.
4. Choose the format.
5. Click **Add to Queue**.
6. Repeat for additional operations.
7. Review the queue.
8. Click **Run Queue**.

For reads, AVRDUDE writes the requested memory to the output file. `-` can be used where AVRDUDE supports stdin/stdout semantics.

## 6. Fuse and lock page

Classic AVR parts often expose `lfuse`, `hfuse`, `efuse` and `lock`. Newer devices can expose numbered fuse memories.

### Read

Select only the memories expected on the device, then click **Read Selected**. On a successful read, HexHeist attempts to populate the selected value fields from AVRDUDE's stdout.

### Write

Enter hexadecimal values, select the relevant memories and click **Write Selected**. HexHeist converts values into AVRDUDE immediate-mode `-U ...:w:...:m` operations.

A confirmation dialog is mandatory.

## 7. Terminal

Click **Start Terminal**. Once AVRDUDE is connected, type commands in the field at the bottom. Start with:

```text
help
```

Type `quit` using AVRDUDE's own terminal command to exit cleanly, or use **Stop** to terminate the process.

## 8. Advanced options

Only enable options you understand. In particular:

- `-F` bypasses protections/checks that normally stop on signature or initialization problems.
- `-D` changes erase behavior.
- `-V` disables automatic verification after writes.
- `-n` prevents memory writes performed through `-U` and is useful for testing commands.

Programmer-specific extended options (`-x`) are separated with semicolons in HexHeist; each item becomes a separate `-x` argument.

## 9. Logs

The Console page records:

- timestamped HexHeist operation messages
- the exact command preview
- AVRDUDE stdout
- AVRDUDE stderr
- exit code / success status

Use **Export Log** when asking for help. Avoid publishing logs that contain private filesystem paths or serial identifiers if that matters in your environment.

## 10. Troubleshooting

### AVRDUDE not found

Install AVRDUDE or browse to its executable.

### `permission denied` on Linux/macOS

Check access to the serial/USB device. Linux often requires appropriate udev rules or membership in a serial-device group such as `dialout`, depending on the distribution/device.

### Programmer cannot see target

Check:

- programmer selection
- target MCU selection
- cable orientation and wiring
- reset wiring
- target power/voltage
- ISP/UPDI/TPI/JTAG interface compatibility
- port/USB pass-through
- bit clock for a slow target

### Device signature mismatch

Do not immediately enable `-F`. First verify the selected MCU and physical connection. `-F` is an expert recovery/debug option, not a normal fix for selecting the wrong target.

### macOS virtual machine

Attach the programmer USB device to the guest OS. If the host retains it, the guest AVRDUDE process cannot communicate with it.
