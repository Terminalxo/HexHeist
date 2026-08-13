from __future__ import annotations

import os
import platform
import re
import sys
from datetime import datetime
from pathlib import Path

from PySide6 import QtCore
from PySide6.QtCore import QProcess, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QCompleter,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core.commands import (
    BuiltCommand,
    build_base_command,
    erase_command,
    signature_command,
    terminal_command,
    test_connection_command,
    with_memory_operations,
)
from ..core.discovery import (
    DEFAULT_PARTS,
    DEFAULT_PROGRAMMERS,
    avrdude_candidates,
    discover_parts,
    discover_programmers,
    probe_version,
    serial_ports,
)
from ..core.models import AdvancedOptions, AvrdudeEntry, MemoryOperation, TargetConfig
from ..core.settings import AppSettings
from .components import Card, HexLogo
from .theme import resolve_theme, stylesheet


class DiscoveryWorker(QtCore.QObject):
    finished = Signal(str, str, object, object)

    def __init__(self, saved_path: str = "") -> None:
        super().__init__()
        self.saved_path = saved_path

    @Slot()
    def run(self) -> None:
        candidates = avrdude_candidates(self.saved_path)
        for path in candidates:
            version = probe_version(path)
            if version:
                self.finished.emit(path, version, discover_parts(path), discover_programmers(path))
                return
        self.finished.emit("", "", DEFAULT_PARTS.copy(), DEFAULT_PROGRAMMERS.copy())


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = AppSettings()
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._stdout_ready)
        self.process.readyReadStandardError.connect(self._stderr_ready)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)

        self.avrdude_version = ""
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._running_label = ""
        self._terminal_running = False
        self._pending_fuse_fields: list[tuple[str, QLineEdit]] = []
        self._discovery_thread: QThread | None = None
        self._discovery_worker: DiscoveryWorker | None = None
        self._memory_ops: list[MemoryOperation] = []
        self.nav_buttons: list[QPushButton] = []

        self.setWindowTitle(f"HexHeist {__version__}")
        self.resize(1240, 820)
        self.setMinimumSize(980, 680)
        self.setAcceptDrops(True)
        geometry = self.settings.get("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)

        self._build_ui()
        self._build_menu()
        self._build_shortcuts()
        self._load_saved_values()
        self._apply_theme(str(self.settings.get("appearance/theme", "system")))
        self.refresh_ports()
        self._update_command_preview()
        QTimer.singleShot(50, self.detect_avrdude)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(215)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 18, 14, 18)
        side.setSpacing(8)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        brand.addWidget(HexLogo(40))
        brand_text = QVBoxLayout()
        title = QLabel("HexHeist")
        title.setObjectName("LogoText")
        sub = QLabel("AVR programming, refined")
        sub.setObjectName("Muted")
        brand_text.addWidget(title)
        brand_text.addWidget(sub)
        brand.addLayout(brand_text)
        side.addLayout(brand)
        side.addSpacing(16)

        nav = [
            ("◆  Device & Flash", 0),
            ("▦  Memories", 1),
            ("⌁  Fuses & Locks", 2),
            ("›_  Terminal", 3),
            ("⚙  Advanced", 4),
            ("≡  Console", 5),
        ]
        for text, index in nav:
            button = QPushButton(text)
            button.setObjectName("Nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self._switch_page(i))
            side.addWidget(button)
            self.nav_buttons.append(button)
        self.nav_buttons[0].setChecked(True)
        side.addStretch(1)

        self.side_status = QLabel("● AVRDUDE: detecting…")
        self.side_status.setObjectName("StatusNeutral")
        self.side_status.setWordWrap(True)
        side.addWidget(self.side_status)
        self.side_version = QLabel("Runtime device list")
        self.side_version.setObjectName("Muted")
        side.addWidget(self.side_version)
        outer.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(26, 18, 26, 18)
        content_layout.setSpacing(14)

        topbar = QFrame()
        topbar.setObjectName("TopBar")
        top = QHBoxLayout(topbar)
        top.setContentsMargins(0, 0, 0, 0)
        heading = QVBoxLayout()
        self.page_title = QLabel("Device & Flash")
        self.page_title.setObjectName("Title")
        self.page_subtitle = QLabel("Connect a programmer, select a target, and program firmware.")
        self.page_subtitle.setObjectName("Subtitle")
        heading.addWidget(self.page_title)
        heading.addWidget(self.page_subtitle)
        top.addLayout(heading)
        top.addStretch(1)
        self.status_chip = QLabel("● Detecting AVRDUDE")
        self.status_chip.setObjectName("StatusNeutral")
        top.addWidget(self.status_chip)
        top.addSpacing(8)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("System", "system")
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.setFixedWidth(112)
        self.theme_combo.currentIndexChanged.connect(self._theme_changed)
        top.addWidget(self.theme_combo)
        content_layout.addWidget(topbar)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFixedHeight(6)
        content_layout.addWidget(self.progress)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_device_page())
        self.pages.addWidget(self._build_memories_page())
        self.pages.addWidget(self._build_fuses_page())
        self.pages.addWidget(self._build_terminal_page())
        self.pages.addWidget(self._build_advanced_page())
        self.pages.addWidget(self._build_console_page())
        content_layout.addWidget(self.pages, 1)
        outer.addWidget(content, 1)

        self.statusBar().showMessage("Ready")

    def _scroll_page(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(widget)
        return scroll

    def _build_device_page(self) -> QWidget:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 6, 6)
        layout.setSpacing(14)

        grid = QGridLayout()
        grid.setSpacing(14)
        target_card = Card("Target", "HexHeist loads the complete part/programmer catalog from your installed AVRDUDE.")
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.avrdude_path = QLineEdit()
        self.avrdude_path.setPlaceholderText("AVRDUDE executable")
        self.avrdude_path.textChanged.connect(self._update_command_preview)
        path_row = QWidget()
        path_layout = QHBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(7)
        path_layout.addWidget(self.avrdude_path, 1)
        browse = QPushButton("Browse")
        browse.clicked.connect(self.browse_avrdude)
        detect = QPushButton("Detect")
        detect.setObjectName("Primary")
        detect.clicked.connect(self.detect_avrdude)
        path_layout.addWidget(browse)
        path_layout.addWidget(detect)
        form.addRow("AVRDUDE", path_row)

        self.programmer_combo = self._search_combo()
        self.programmer_combo.currentIndexChanged.connect(self._target_changed)
        self.programmer_combo.editTextChanged.connect(self._update_command_preview)
        form.addRow("Programmer", self.programmer_combo)

        self.part_combo = self._search_combo()
        self.part_combo.currentIndexChanged.connect(self._target_changed)
        self.part_combo.editTextChanged.connect(self._update_command_preview)
        form.addRow("MCU / Part", self.part_combo)

        self.port_combo = self._search_combo()
        self.port_combo.currentIndexChanged.connect(self._target_changed)
        self.port_combo.editTextChanged.connect(self._update_command_preview)
        port_row = QWidget()
        port_layout = QHBoxLayout(port_row)
        port_layout.setContentsMargins(0, 0, 0, 0)
        port_layout.setSpacing(7)
        port_layout.addWidget(self.port_combo, 1)
        port_refresh = QPushButton("↻")
        port_refresh.setToolTip("Refresh serial ports")
        port_refresh.setFixedWidth(38)
        port_refresh.clicked.connect(self.refresh_ports)
        port_layout.addWidget(port_refresh)
        form.addRow("Port", port_row)

        self.baud_edit = QLineEdit()
        self.baud_edit.setPlaceholderText("Optional, e.g. 115200")
        self.baud_edit.textChanged.connect(self._target_changed)
        form.addRow("Baud rate", self.baud_edit)

        self.bitclock_edit = QLineEdit()
        self.bitclock_edit.setPlaceholderText("Optional -B value, e.g. 10 or 2us")
        self.bitclock_edit.textChanged.connect(self._target_changed)
        form.addRow("Bit clock", self.bitclock_edit)
        target_card.layout.addLayout(form)

        actions = QHBoxLayout()
        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self.test_connection)
        self.signature_button = QPushButton("Read Signature")
        self.signature_button.clicked.connect(self.read_signature)
        self.erase_button = QPushButton("Erase Chip")
        self.erase_button.setObjectName("Danger")
        self.erase_button.clicked.connect(self.erase_chip)
        actions.addWidget(self.test_button)
        actions.addWidget(self.signature_button)
        actions.addStretch(1)
        actions.addWidget(self.erase_button)
        target_card.layout.addLayout(actions)
        grid.addWidget(target_card, 0, 0)

        firmware_card = Card("Firmware", "Quick flash workflow for the selected target.")
        self.firmware_path = QLineEdit()
        self.firmware_path.setPlaceholderText("Drop or select .hex, .elf, .bin, .srec…")
        self.firmware_path.textChanged.connect(self._firmware_changed)
        fw_row = QHBoxLayout()
        fw_row.addWidget(self.firmware_path, 1)
        fw_browse = QPushButton("Choose File")
        fw_browse.clicked.connect(self.open_firmware)
        fw_row.addWidget(fw_browse)
        firmware_card.layout.addLayout(fw_row)

        self.firmware_meta = QLabel("No firmware selected")
        self.firmware_meta.setObjectName("Muted")
        self.firmware_meta.setWordWrap(True)
        firmware_card.layout.addWidget(self.firmware_meta)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Input format"))
        self.firmware_format = QComboBox()
        self._add_format_items(self.firmware_format, input_mode=True)
        self.firmware_format.currentIndexChanged.connect(self._update_command_preview)
        fmt_row.addWidget(self.firmware_format, 1)
        firmware_card.layout.addLayout(fmt_row)

        fw_actions = QHBoxLayout()
        self.write_flash_button = QPushButton("Flash Firmware")
        self.write_flash_button.setObjectName("Primary")
        self.write_flash_button.clicked.connect(self.flash_firmware)
        self.verify_flash_button = QPushButton("Verify")
        self.verify_flash_button.clicked.connect(self.verify_firmware)
        fw_actions.addWidget(self.write_flash_button)
        fw_actions.addWidget(self.verify_flash_button)
        firmware_card.layout.addLayout(fw_actions)
        grid.addWidget(firmware_card, 0, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        layout.addLayout(grid)

        command_card = Card("Command Preview", "The exact executable and arguments that HexHeist will launch.")
        command_top = QHBoxLayout()
        self.pretty_check = QCheckBox("Pretty view")
        self.pretty_check.toggled.connect(self._update_command_preview)
        command_top.addWidget(self.pretty_check)
        command_top.addStretch(1)
        copy_command = QPushButton("Copy Command")
        copy_command.clicked.connect(self.copy_command)
        command_top.addWidget(copy_command)
        command_card.layout.addLayout(command_top)
        self.command_preview = QPlainTextEdit()
        self.command_preview.setReadOnly(True)
        self.command_preview.setMaximumHeight(115)
        self.command_preview.setPlaceholderText("Select a programmer and target to preview the command.")
        command_card.layout.addWidget(self.command_preview)
        layout.addWidget(command_card)
        layout.addStretch(1)
        return self._scroll_page(body)

    def _build_memories_page(self) -> QWidget:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 6, 6)
        layout.setSpacing(14)

        card = Card("Memory Operation Builder", "Queue one or more AVRDUDE -U operations. Memory names are editable for newer/XMEGA/UPDI parts.")
        row = QGridLayout()
        row.setHorizontalSpacing(10)
        row.setVerticalSpacing(8)

        self.memory_type = QComboBox()
        self.memory_type.setEditable(True)
        self.memory_type.addItems([
            "flash", "eeprom", "application", "apptable", "boot", "data", "usersig",
            "prodsig", "signature", "calibration", "fuse", "lfuse", "hfuse", "efuse", "lock",
            "fuse0", "fuse1", "fuse2", "fuse3", "fuse4", "fuse5",
        ])
        self.memory_action = QComboBox()
        self.memory_action.addItem("Read", "r")
        self.memory_action.addItem("Write", "w")
        self.memory_action.addItem("Verify", "v")
        self.memory_action.currentIndexChanged.connect(self._memory_action_changed)
        self.memory_file = QLineEdit()
        self.memory_file.setPlaceholderText("Output/input file, '-' for stdio, or immediate value")
        memory_browse = QPushButton("Browse")
        memory_browse.clicked.connect(self.browse_memory_file)
        self.memory_format = QComboBox()
        self._add_format_items(self.memory_format, input_mode=False)
        add_button = QPushButton("Add to Queue")
        add_button.setObjectName("Primary")
        add_button.clicked.connect(self.add_memory_operation)

        row.addWidget(QLabel("Memory"), 0, 0)
        row.addWidget(QLabel("Action"), 0, 1)
        row.addWidget(QLabel("File / Value"), 0, 2)
        row.addWidget(QLabel("Format"), 0, 4)
        row.addWidget(self.memory_type, 1, 0)
        row.addWidget(self.memory_action, 1, 1)
        row.addWidget(self.memory_file, 1, 2)
        row.addWidget(memory_browse, 1, 3)
        row.addWidget(self.memory_format, 1, 4)
        row.addWidget(add_button, 1, 5)
        row.setColumnStretch(2, 1)
        card.layout.addLayout(row)
        layout.addWidget(card)

        queue = Card("Operation Queue", "AVRDUDE executes queued -U operations in order in a single process.")
        self.memory_table = QTableWidget(0, 5)
        self.memory_table.setHorizontalHeaderLabels(["Memory", "Action", "File / Value", "Format", ""])
        self.memory_table.horizontalHeader().setStretchLastSection(False)
        self.memory_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.memory_table.verticalHeader().setVisible(False)
        self.memory_table.setAlternatingRowColors(True)
        self.memory_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        queue.layout.addWidget(self.memory_table)
        queue_actions = QHBoxLayout()
        clear = QPushButton("Clear Queue")
        clear.clicked.connect(self.clear_memory_queue)
        run = QPushButton("Run Queue")
        run.setObjectName("Primary")
        run.clicked.connect(self.run_memory_queue)
        queue_actions.addWidget(clear)
        queue_actions.addStretch(1)
        queue_actions.addWidget(run)
        queue.layout.addLayout(queue_actions)
        layout.addWidget(queue, 1)
        return body

    def _build_fuses_page(self) -> QWidget:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 6, 6)
        layout.setSpacing(14)

        warning = Card("Fuse & Lock Safety", "Fuse and lock writes can disable ISP access, change clocking, or lock memory. Verify values against the MCU datasheet before writing.")
        layout.addWidget(warning)

        card = Card("Fuse / Lock Bytes", "Select the memories supported by your MCU. Values are entered as hexadecimal bytes such as 0xFF.")
        grid = QGridLayout()
        self.fuse_controls: dict[str, tuple[QCheckBox, QLineEdit]] = {}
        memories = [
            ("lfuse", "Low fuse"),
            ("hfuse", "High fuse"),
            ("efuse", "Extended fuse"),
            ("fuse", "Unified fuse"),
            ("lock", "Lock byte"),
            ("fuse0", "Fuse 0"),
            ("fuse1", "Fuse 1"),
            ("fuse2", "Fuse 2"),
            ("fuse3", "Fuse 3"),
            ("fuse4", "Fuse 4"),
            ("fuse5", "Fuse 5"),
        ]
        for idx, (memory, label_text) in enumerate(memories):
            check = QCheckBox(label_text)
            check.setChecked(memory in {"lfuse", "hfuse", "efuse", "lock"})
            edit = QLineEdit()
            edit.setPlaceholderText("0xFF")
            edit.setMaxLength(8)
            edit.textChanged.connect(self._update_fuse_preview)
            check.toggled.connect(self._update_fuse_preview)
            r, c = divmod(idx, 2)
            box = QWidget()
            box_l = QHBoxLayout(box)
            box_l.setContentsMargins(0, 0, 0, 0)
            box_l.addWidget(check)
            box_l.addWidget(edit)
            grid.addWidget(box, r, c)
            self.fuse_controls[memory] = (check, edit)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        card.layout.addLayout(grid)

        actions = QHBoxLayout()
        read = QPushButton("Read Selected")
        read.clicked.connect(self.read_fuses)
        write = QPushButton("Write Selected")
        write.setObjectName("Danger")
        write.clicked.connect(self.write_fuses)
        actions.addWidget(read)
        actions.addStretch(1)
        actions.addWidget(write)
        card.layout.addLayout(actions)
        layout.addWidget(card)

        preview = Card("Fuse Command Preview")
        self.fuse_preview = QPlainTextEdit()
        self.fuse_preview.setReadOnly(True)
        self.fuse_preview.setMaximumHeight(125)
        preview.layout.addWidget(self.fuse_preview)
        layout.addWidget(preview)
        layout.addStretch(1)
        return self._scroll_page(body)

    def _build_terminal_page(self) -> QWidget:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 6, 6)
        layout.setSpacing(14)

        card = Card("AVRDUDE Interactive Terminal", "Starts AVRDUDE with -t and sends commands to its standard input. Type 'help' inside the terminal for commands supported by your AVRDUDE version.")
        top = QHBoxLayout()
        self.terminal_start = QPushButton("Start Terminal")
        self.terminal_start.setObjectName("Primary")
        self.terminal_start.clicked.connect(self.start_terminal)
        self.terminal_stop = QPushButton("Stop")
        self.terminal_stop.clicked.connect(self.stop_process)
        top.addWidget(self.terminal_start)
        top.addWidget(self.terminal_stop)
        top.addStretch(1)
        card.layout.addLayout(top)

        self.terminal_output = QPlainTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setPlaceholderText("Terminal output will appear here.")
        card.layout.addWidget(self.terminal_output, 1)

        input_row = QHBoxLayout()
        self.terminal_input = QLineEdit()
        self.terminal_input.setPlaceholderText("AVRDUDE terminal command, e.g. help, dump flash 0 32, quit")
        self.terminal_input.returnPressed.connect(self.send_terminal_command)
        send = QPushButton("Send")
        send.clicked.connect(self.send_terminal_command)
        input_row.addWidget(self.terminal_input, 1)
        input_row.addWidget(send)
        card.layout.addLayout(input_row)
        layout.addWidget(card, 1)
        return body

    def _build_advanced_page(self) -> QWidget:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 6, 6)
        layout.setSpacing(14)

        card = Card("Advanced AVRDUDE Options", "These switches apply to commands generated from the other HexHeist pages.")
        grid = QGridLayout()
        self.force_check = QCheckBox("Force signature / initialization (-F)")
        self.no_write_check = QCheckBox("No-write test mode (-n)")
        self.no_erase_check = QCheckBox("Disable automatic erase (-D)")
        self.no_verify_check = QCheckBox("Disable automatic write verification (-V)")
        self.explicit_erase_check = QCheckBox("Chip erase before operation (-e)")
        for widget in (self.force_check, self.no_write_check, self.no_erase_check, self.no_verify_check, self.explicit_erase_check):
            widget.toggled.connect(self._advanced_changed)
        grid.addWidget(self.force_check, 0, 0)
        grid.addWidget(self.no_write_check, 0, 1)
        grid.addWidget(self.no_erase_check, 1, 0)
        grid.addWidget(self.no_verify_check, 1, 1)
        grid.addWidget(self.explicit_erase_check, 2, 0)
        card.layout.addLayout(grid)

        form = QFormLayout()
        self.verbose_spin = QSpinBox()
        self.verbose_spin.setRange(0, 4)
        self.verbose_spin.valueChanged.connect(self._advanced_changed)
        form.addRow("Verbosity (-v)", self.verbose_spin)
        self.exit_spec_edit = QLineEdit()
        self.exit_spec_edit.setPlaceholderText("Optional -E exitspec")
        self.exit_spec_edit.textChanged.connect(self._advanced_changed)
        form.addRow("Exit specification", self.exit_spec_edit)
        self.extended_edit = QLineEdit()
        self.extended_edit.setPlaceholderText("-x parameters separated by semicolons, e.g. param1;param2=value")
        self.extended_edit.textChanged.connect(self._advanced_changed)
        form.addRow("Extended parameters", self.extended_edit)
        self.config_edit = QLineEdit()
        self.config_edit.setPlaceholderText("Optional custom avrdude.conf")
        self.config_edit.textChanged.connect(self._advanced_changed)
        cfg_row = QWidget()
        cfg_layout = QHBoxLayout(cfg_row)
        cfg_layout.setContentsMargins(0, 0, 0, 0)
        cfg_layout.addWidget(self.config_edit, 1)
        cfg_browse = QPushButton("Browse")
        cfg_browse.clicked.connect(self.browse_config)
        cfg_layout.addWidget(cfg_browse)
        form.addRow("Configuration file", cfg_row)
        self.custom_args_edit = QLineEdit()
        self.custom_args_edit.setPlaceholderText("Expert-only custom AVRDUDE arguments")
        self.custom_args_edit.textChanged.connect(self._advanced_changed)
        form.addRow("Custom arguments", self.custom_args_edit)
        card.layout.addLayout(form)
        layout.addWidget(card)

        history = Card("Command History", "The last 20 commands generated and executed by HexHeist.")
        self.history_view = QPlainTextEdit()
        self.history_view.setReadOnly(True)
        self.history_view.setMaximumHeight(220)
        history.layout.addWidget(self.history_view)
        clear_history = QPushButton("Clear History")
        clear_history.clicked.connect(self.clear_history)
        history.layout.addWidget(clear_history, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(history)
        layout.addStretch(1)
        return self._scroll_page(body)

    def _build_console_page(self) -> QWidget:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 6, 6)
        layout.setSpacing(14)

        card = Card("Operation Console", "Live standard output and diagnostics from AVRDUDE.")
        actions = QHBoxLayout()
        self.console_autoscroll = QCheckBox("Auto-scroll")
        self.console_autoscroll.setChecked(True)
        actions.addWidget(self.console_autoscroll)
        actions.addStretch(1)
        stop = QPushButton("Stop Process")
        stop.clicked.connect(self.stop_process)
        copy = QPushButton("Copy Output")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.console.toPlainText()))
        clear = QPushButton("Clear")
        clear.clicked.connect(self.console_clear)
        export = QPushButton("Export Log")
        export.clicked.connect(self.export_log)
        actions.addWidget(stop)
        actions.addWidget(copy)
        actions.addWidget(clear)
        actions.addWidget(export)
        card.layout.addLayout(actions)
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        card.layout.addWidget(self.console, 1)
        layout.addWidget(card, 1)
        return body

    def _search_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        completer = combo.completer()
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        return combo

    @staticmethod
    def _add_format_items(combo: QComboBox, input_mode: bool) -> None:
        if input_mode:
            combo.addItem("Auto detect (a)", "a")
        combo.addItem("Intel HEX (i)", "i")
        combo.addItem("Intel HEX + comments (I)", "I")
        combo.addItem("Raw binary (r)", "r")
        combo.addItem("Motorola S-record (s)", "s")
        if input_mode:
            combo.addItem("ELF input (e)", "e")
        combo.addItem("Immediate values (m)", "m")
        combo.addItem("Hex values (h)", "h")
        combo.addItem("Decimal values (d)", "d")
        combo.addItem("Octal values (o)", "o")
        combo.addItem("Binary values (b)", "b")

    # ------------------------------------------------------------- navigation
    def _switch_page(self, index: int) -> None:
        titles = [
            ("Device & Flash", "Connect a programmer, select a target, and program firmware."),
            ("Memories", "Read, write, or verify any memory exposed by AVRDUDE."),
            ("Fuses & Locks", "Read and program configuration and protection bytes carefully."),
            ("Terminal", "Use AVRDUDE's interactive terminal without leaving HexHeist."),
            ("Advanced", "Fine-tune command-line options and inspect command history."),
            ("Console", "Inspect live AVRDUDE output, errors, and exported logs."),
        ]
        self.pages.setCurrentIndex(index)
        self.page_title.setText(titles[index][0])
        self.page_subtitle.setText(titles[index][1])
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)

    # --------------------------------------------------------------- settings
    def _load_saved_values(self) -> None:
        theme = str(self.settings.get("appearance/theme", "system"))
        idx = self.theme_combo.findData(theme)
        self.theme_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.avrdude_path.setText(str(self.settings.get("avrdude/path", "")))
        self.baud_edit.setText(str(self.settings.get("target/baud", "")))
        self.bitclock_edit.setText(str(self.settings.get("target/bitclock", "")))
        self.config_edit.setText(str(self.settings.get("avrdude/config", "")))
        self.firmware_path.setText(str(self.settings.get("firmware/last", "")))
        self.force_check.setChecked(str(self.settings.get("advanced/force", "false")).lower() == "true")
        self.no_write_check.setChecked(str(self.settings.get("advanced/no_write", "false")).lower() == "true")
        self.no_erase_check.setChecked(str(self.settings.get("advanced/no_erase", "false")).lower() == "true")
        self.no_verify_check.setChecked(str(self.settings.get("advanced/no_verify", "false")).lower() == "true")
        self.verbose_spin.setValue(int(self.settings.get("advanced/verbose", 0) or 0))
        self.exit_spec_edit.setText(str(self.settings.get("advanced/exit_spec", "")))
        self.extended_edit.setText(str(self.settings.get("advanced/extended", "")))
        self.custom_args_edit.setText(str(self.settings.get("advanced/custom_args", "")))
        self._refresh_history()

    def _save_target_values(self) -> None:
        self.settings.set("avrdude/path", self.avrdude_path.text().strip())
        self.settings.set("target/programmer", self._combo_value(self.programmer_combo))
        self.settings.set("target/part", self._combo_value(self.part_combo))
        self.settings.set("target/port", self._combo_value(self.port_combo))
        self.settings.set("target/baud", self.baud_edit.text().strip())
        self.settings.set("target/bitclock", self.bitclock_edit.text().strip())

    def _save_advanced(self) -> None:
        self.settings.set("advanced/force", self.force_check.isChecked())
        self.settings.set("advanced/no_write", self.no_write_check.isChecked())
        self.settings.set("advanced/no_erase", self.no_erase_check.isChecked())
        self.settings.set("advanced/no_verify", self.no_verify_check.isChecked())
        self.settings.set("advanced/verbose", self.verbose_spin.value())
        self.settings.set("advanced/exit_spec", self.exit_spec_edit.text())
        self.settings.set("advanced/extended", self.extended_edit.text())
        self.settings.set("advanced/custom_args", self.custom_args_edit.text())
        self.settings.set("avrdude/config", self.config_edit.text())

    # --------------------------------------------------------------- discovery
    def detect_avrdude(self) -> None:
        if self._discovery_thread and self._discovery_thread.isRunning():
            return
        saved = self.avrdude_path.text().strip()
        self._set_detection_state("detecting")
        self.statusBar().showMessage("Detecting AVRDUDE and loading device catalog…")
        thread = QThread(self)
        worker = DiscoveryWorker(saved)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._discovery_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._discovery_thread = thread
        self._discovery_worker = worker
        thread.start()

    @Slot(str, str, object, object)
    def _discovery_finished(self, path: str, version: str, parts: list[AvrdudeEntry], programmers: list[AvrdudeEntry]) -> None:
        self._discovery_thread = None
        self._discovery_worker = None
        if not path:
            self._set_detection_state("missing")
            self._populate_combo(self.part_combo, parts, str(self.settings.get("target/part", "m328p")))
            self._populate_combo(self.programmer_combo, programmers, str(self.settings.get("target/programmer", "usbasp")))
            self.statusBar().showMessage("AVRDUDE not found. Install it or browse to the executable.")
            self._append_log("WARN", "AVRDUDE was not found. Device lists are showing a small offline fallback set.")
            return
        self.avrdude_path.setText(path)
        self.avrdude_version = version
        self.settings.set("avrdude/path", path)
        self._populate_combo(self.part_combo, parts, str(self.settings.get("target/part", "m328p")))
        self._populate_combo(self.programmer_combo, programmers, str(self.settings.get("target/programmer", "usbasp")))
        self._set_detection_state("ready")
        self.statusBar().showMessage(f"AVRDUDE {version} ready · {len(parts)} parts · {len(programmers)} programmers")
        self._append_log("INFO", f"Detected AVRDUDE {version} at {path}")
        self._append_log("INFO", f"Loaded {len(parts)} parts and {len(programmers)} programmers from AVRDUDE.")
        self._update_command_preview()

    def _set_detection_state(self, state: str) -> None:
        if state == "ready":
            text = f"● AVRDUDE {self.avrdude_version or 'ready'}"
            name = "StatusGood"
        elif state == "missing":
            text = "● AVRDUDE not found"
            name = "StatusBad"
        else:
            text = "● Detecting AVRDUDE"
            name = "StatusNeutral"
        self.status_chip.setText(text)
        self.status_chip.setObjectName(name)
        self.status_chip.style().unpolish(self.status_chip)
        self.status_chip.style().polish(self.status_chip)
        self.side_status.setText(text)
        self.side_status.setObjectName(name)
        self.side_status.style().unpolish(self.side_status)
        self.side_status.style().polish(self.side_status)
        self.side_version.setText("Runtime catalog" if state != "ready" else f"v{self.avrdude_version}")

    def _populate_combo(self, combo: QComboBox, entries: list[AvrdudeEntry], preferred: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        preferred_index = -1
        for entry in entries:
            combo.addItem(entry.display_name, entry.id)
            if entry.id.lower() == preferred.lower():
                preferred_index = combo.count() - 1
        if preferred_index >= 0:
            combo.setCurrentIndex(preferred_index)
        elif preferred:
            combo.setEditText(preferred)
        combo.blockSignals(False)
        self._update_command_preview()

    def refresh_ports(self) -> None:
        current = str(self.settings.get("target/port", "")) or self._combo_value(getattr(self, "port_combo", QComboBox()))
        ports = serial_ports()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        self.port_combo.addItem("Auto / programmer default", "")
        for device, description in ports:
            label = f"{device}  ·  {description}" if description and description != "n/a" else device
            self.port_combo.addItem(label, device)
        idx = self.port_combo.findData(current)
        if idx >= 0:
            self.port_combo.setCurrentIndex(idx)
        elif current:
            self.port_combo.setEditText(current)
        self.port_combo.blockSignals(False)
        self._update_command_preview()

    # --------------------------------------------------------------- commands
    def _target(self) -> TargetConfig:
        return TargetConfig(
            executable=self.avrdude_path.text().strip() or "avrdude",
            config_file=self.config_edit.text().strip(),
            programmer=self._combo_value(self.programmer_combo),
            part=self._combo_value(self.part_combo),
            port=self._combo_value(self.port_combo),
            baud=self.baud_edit.text().strip(),
            bitclock=self.bitclock_edit.text().strip(),
        )

    def _advanced(self) -> AdvancedOptions:
        params = [p.strip() for p in self.extended_edit.text().split(";") if p.strip()]
        return AdvancedOptions(
            force_signature=self.force_check.isChecked(),
            no_write=self.no_write_check.isChecked(),
            disable_auto_erase=self.no_erase_check.isChecked(),
            disable_verify=self.no_verify_check.isChecked(),
            erase_before=self.explicit_erase_check.isChecked(),
            verbose_count=self.verbose_spin.value(),
            exit_spec=self.exit_spec_edit.text().strip(),
            extended_params=params,
            custom_args=self.custom_args_edit.text().strip(),
        )

    @staticmethod
    def _combo_value(combo: QComboBox) -> str:
        text = combo.currentText().strip()
        index = combo.currentIndex()
        data = combo.currentData()
        # Editable QComboBox can retain the previous row's userData while the user
        # types custom text. Only trust userData when the displayed text still
        # exactly matches the selected catalog row.
        if index >= 0 and data is not None and combo.itemText(index).strip() == text:
            return str(data)
        # Our display entries use "description · id"; custom plain IDs pass through.
        if "  ·  " in text:
            return text.rsplit("  ·  ", 1)[-1].strip()
        return text

    def _validate_ready(self) -> bool:
        target = self._target()
        if not target.programmer:
            QMessageBox.warning(self, "Programmer Required", "Select or enter an AVRDUDE programmer ID.")
            return False
        if not target.part:
            QMessageBox.warning(self, "MCU Required", "Select or enter an AVRDUDE part ID.")
            return False
        exe = target.executable
        if os.path.sep in exe or (os.altsep and os.altsep in exe):
            if not Path(exe).expanduser().exists():
                QMessageBox.warning(self, "AVRDUDE Not Found", "The selected AVRDUDE executable does not exist.")
                return False
        return True

    def _run(self, command: BuiltCommand, label: str, terminal: bool = False, fuse_read: list[tuple[str, QLineEdit]] | None = None) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, "AVRDUDE Busy", "An AVRDUDE process is already running.")
            return
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._running_label = label
        self._terminal_running = terminal
        self._pending_fuse_fields = fuse_read or []
        preview = command.single_line()
        self.settings.add_command(preview)
        self._refresh_history()
        self._append_log("CMD", preview)
        if terminal:
            self.terminal_output.appendPlainText(f"$ {preview}\n")
        self._set_busy(True, f"{label}…")
        self.process.setProgram(command.executable)
        self.process.setArguments(command.arguments)
        self.process.start()

    def test_connection(self) -> None:
        if self._validate_ready():
            self._run(test_connection_command(self._target(), self._advanced()), "Testing connection")

    def read_signature(self) -> None:
        if self._validate_ready():
            self._run(signature_command(self._target(), self._advanced()), "Reading signature")

    def erase_chip(self) -> None:
        if not self._validate_ready():
            return
        if QMessageBox.warning(
            self,
            "Erase Chip?",
            "This performs a chip erase on the selected target. Continue?",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        ) == QMessageBox.StandardButton.Yes:
            adv = self._advanced()
            adv.erase_before = False
            self._run(erase_command(self._target(), adv), "Erasing chip")

    def flash_firmware(self) -> None:
        self._quick_flash("w")

    def verify_firmware(self) -> None:
        self._quick_flash("v")

    def _quick_flash(self, action: str) -> None:
        if not self._validate_ready():
            return
        filename = self.firmware_path.text().strip()
        if not filename or not Path(filename).expanduser().is_file():
            QMessageBox.warning(self, "Firmware Required", "Choose an existing firmware file first.")
            return
        operation = MemoryOperation("flash", action, filename, str(self.firmware_format.currentData() or "a"))
        if action == "w":
            summary = (
                f"Programmer: {self._target().programmer}\n"
                f"MCU: {self._target().part}\n"
                f"Firmware: {filename}\n"
                f"Port: {self._target().port or 'default'}\n\n"
                "Write this firmware to flash?"
            )
            if QMessageBox.question(self, "Flash Firmware?", summary) != QMessageBox.StandardButton.Yes:
                return
        try:
            command = with_memory_operations(self._target(), [operation], self._advanced())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Operation", str(exc))
            return
        self._run(command, "Flashing firmware" if action == "w" else "Verifying flash")

    # --------------------------------------------------------------- memories
    def _memory_action_changed(self) -> None:
        action = self.memory_action.currentData()
        self.memory_file.setPlaceholderText("Output file" if action == "r" else "Input file / immediate value")

    def browse_memory_file(self) -> None:
        action = self.memory_action.currentData()
        if action == "r":
            filename, _ = QFileDialog.getSaveFileName(self, "Read Memory To File", str(Path.home()))
        else:
            filename, _ = QFileDialog.getOpenFileName(self, "Select Memory Input File", str(Path.home()), "All files (*)")
        if filename:
            self.memory_file.setText(filename)

    def add_memory_operation(self) -> None:
        memory = self.memory_type.currentText().strip()
        action = str(self.memory_action.currentData())
        filename = self.memory_file.text().strip()
        fmt = str(self.memory_format.currentData())
        op = MemoryOperation(memory, action, filename, fmt)
        try:
            op.validate()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Memory Operation", str(exc))
            return
        self._memory_ops.append(op)
        self._rebuild_memory_table()
        self.memory_file.clear()

    def _rebuild_memory_table(self) -> None:
        self.memory_table.setRowCount(len(self._memory_ops))
        action_names = {"r": "Read", "w": "Write", "v": "Verify"}
        for row, op in enumerate(self._memory_ops):
            for col, value in enumerate((op.memory, action_names[op.action], op.filename, op.file_format)):
                self.memory_table.setItem(row, col, QTableWidgetItem(value))
            remove = QPushButton("Remove")
            remove.clicked.connect(lambda checked=False, r=row: self.remove_memory_operation(r))
            self.memory_table.setCellWidget(row, 4, remove)

    def remove_memory_operation(self, row: int) -> None:
        if 0 <= row < len(self._memory_ops):
            self._memory_ops.pop(row)
            self._rebuild_memory_table()

    def clear_memory_queue(self) -> None:
        self._memory_ops.clear()
        self._rebuild_memory_table()

    def run_memory_queue(self) -> None:
        if not self._memory_ops:
            QMessageBox.information(self, "Empty Queue", "Add at least one memory operation.")
            return
        if not self._validate_ready():
            return
        has_write = any(op.action == "w" for op in self._memory_ops)
        if has_write and QMessageBox.warning(
            self,
            "Run Write Operations?",
            "The queue contains one or more write operations. Verify the target, memory names, and files before continuing.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            command = with_memory_operations(self._target(), self._memory_ops, self._advanced())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Queue", str(exc))
            return
        self._run(command, "Running memory queue")

    # ----------------------------------------------------------- fuses / locks
    def _selected_fuses(self) -> list[tuple[str, QLineEdit]]:
        selected = []
        for memory, (check, edit) in self.fuse_controls.items():
            if check.isChecked():
                selected.append((memory, edit))
        return selected

    def read_fuses(self) -> None:
        if not self._validate_ready():
            return
        selected = self._selected_fuses()
        if not selected:
            QMessageBox.information(self, "Nothing Selected", "Select at least one fuse or lock memory.")
            return
        ops = [MemoryOperation(memory, "r", "-", "h") for memory, _ in selected]
        try:
            command = with_memory_operations(self._target(), ops, self._advanced())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Fuse Read", str(exc))
            return
        self._run(command, "Reading fuses / locks", fuse_read=selected)

    def write_fuses(self) -> None:
        if not self._validate_ready():
            return
        ops: list[MemoryOperation] = []
        for memory, edit in self._selected_fuses():
            value = edit.text().strip()
            if not value:
                continue
            if not re.fullmatch(r"(?:0x)?[0-9A-Fa-f]{1,8}", value):
                QMessageBox.warning(self, "Invalid Fuse Value", f"{memory}: enter a hexadecimal value such as 0xFF.")
                return
            if not value.lower().startswith("0x"):
                value = "0x" + value
            ops.append(MemoryOperation(memory, "w", value, "m"))
        if not ops:
            QMessageBox.information(self, "No Values", "Select fuse/lock memories and enter values to write.")
            return
        detail = "\n".join(f"{op.memory} = {op.filename}" for op in ops)
        if QMessageBox.critical(
            self,
            "Write Fuses / Locks?",
            "Incorrect fuse or lock values can make a target inaccessible through the current programming interface.\n\n"
            + detail
            + "\n\nContinue only if these values are confirmed from the device datasheet.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            command = with_memory_operations(self._target(), ops, self._advanced())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Fuse Write", str(exc))
            return
        self._run(command, "Writing fuses / locks")

    def _update_fuse_preview(self) -> None:
        ops = []
        for memory, edit in self._selected_fuses():
            value = edit.text().strip()
            if value:
                value = value if value.lower().startswith("0x") else f"0x{value}"
                ops.append(MemoryOperation(memory, "w", value, "m"))
        try:
            command = with_memory_operations(self._target(), ops, self._advanced()) if ops else build_base_command(self._target(), self._advanced())
            self.fuse_preview.setPlainText(command.pretty() if self.pretty_check.isChecked() else command.single_line())
        except Exception as exc:
            self.fuse_preview.setPlainText(f"Cannot build preview: {exc}")

    # --------------------------------------------------------------- terminal
    def start_terminal(self) -> None:
        if not self._validate_ready():
            return
        self.terminal_output.clear()
        self._run(terminal_command(self._target(), self._advanced()), "Interactive terminal", terminal=True)
        self._switch_page(3)

    def send_terminal_command(self) -> None:
        text = self.terminal_input.text().strip()
        if not text:
            return
        if not self._terminal_running or self.process.state() == QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, "Terminal Not Running", "Start the AVRDUDE terminal first.")
            return
        self.terminal_output.appendPlainText(f"> {text}")
        self.process.write((text + "\n").encode("utf-8"))
        self.terminal_input.clear()

    # --------------------------------------------------------------- QProcess
    def _stdout_ready(self) -> None:
        text = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._stdout_buffer += text
        self._append_raw(text)
        if self._terminal_running:
            self.terminal_output.moveCursor(QTextCursor.MoveOperation.End)
            self.terminal_output.insertPlainText(text)

    def _stderr_ready(self) -> None:
        text = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        self._stderr_buffer += text
        self._append_raw(text)
        if self._terminal_running:
            self.terminal_output.moveCursor(QTextCursor.MoveOperation.End)
            self.terminal_output.insertPlainText(text)

    def _process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        del exit_status
        label = self._running_label or "AVRDUDE"
        if self._pending_fuse_fields and exit_code == 0:
            values = re.findall(r"0x[0-9A-Fa-f]+", self._stdout_buffer)
            for (memory, field), value in zip(self._pending_fuse_fields, values):
                field.setText(value)
                self._append_log("INFO", f"{memory} = {value}")
        self._pending_fuse_fields = []
        self._terminal_running = False
        if exit_code == 0:
            self._append_log("OK", f"{label} completed successfully (exit code 0).")
            self.statusBar().showMessage(f"{label} completed successfully")
        else:
            self._append_log("ERROR", f"{label} failed (exit code {exit_code}).")
            self.statusBar().showMessage(f"{label} failed · exit code {exit_code}")
        self._set_busy(False)

    def _process_error(self, error: QProcess.ProcessError) -> None:
        self._append_log("ERROR", f"Process error: {self.process.errorString()} ({error.name})")
        self.statusBar().showMessage(f"AVRDUDE process error: {self.process.errorString()}")
        if self.process.state() == QProcess.ProcessState.NotRunning:
            self._set_busy(False)

    def stop_process(self) -> None:
        if self.process.state() == QProcess.ProcessState.NotRunning:
            return
        self._append_log("WARN", "Stopping AVRDUDE process…")
        self.process.terminate()
        QTimer.singleShot(1800, self._kill_if_running)

    def _kill_if_running(self) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self.progress.setRange(0, 0 if busy else 1)
        if not busy:
            self.progress.setValue(0)
        for widget in (
            self.test_button, self.signature_button, self.erase_button,
            self.write_flash_button, self.verify_flash_button,
            self.programmer_combo, self.part_combo, self.port_combo,
            self.baud_edit, self.bitclock_edit,
        ):
            widget.setEnabled(not busy)
        if message:
            self.statusBar().showMessage(message)

    # --------------------------------------------------------------- console
    def _append_log(self, level: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console.appendPlainText(f"[{timestamp}] {level:<5} {message}")
        if self.console_autoscroll.isChecked():
            bar = self.console.verticalScrollBar()
            bar.setValue(bar.maximum())

    def _append_raw(self, text: str) -> None:
        if not text:
            return
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        if not text.endswith("\n"):
            cursor.insertText("\n")
        if self.console_autoscroll.isChecked():
            bar = self.console.verticalScrollBar()
            bar.setValue(bar.maximum())

    def console_clear(self) -> None:
        self.console.clear()

    def export_log(self) -> None:
        default = str(Path.home() / f"hexheist-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log.txt")
        filename, _ = QFileDialog.getSaveFileName(self, "Export HexHeist Log", default, "Text files (*.txt);;All files (*)")
        if filename:
            Path(filename).write_text(self.console.toPlainText(), encoding="utf-8")
            self.statusBar().showMessage(f"Log exported to {filename}")

    # --------------------------------------------------------------- files/UI
    def open_firmware(self) -> None:
        start = str(self.settings.get("firmware/directory", str(Path.home())))
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Firmware",
            start,
            "Firmware (*.hex *.ihx *.elf *.bin *.srec *.s19 *.eep);;All files (*)",
        )
        if filename:
            self.load_firmware(filename)

    def load_firmware(self, filename: str) -> None:
        path = Path(filename).expanduser()
        if not path.is_file():
            return
        self.firmware_path.setText(str(path))
        self.settings.set("firmware/directory", str(path.parent))
        self.settings.set("firmware/last", str(path))
        self.settings.add_recent_file(str(path))
        self._rebuild_recent_menu()
        self._choose_format_for_suffix(path.suffix.lower())

    def _choose_format_for_suffix(self, suffix: str) -> None:
        mapping = {".hex": "i", ".ihx": "i", ".elf": "e", ".bin": "r", ".srec": "s", ".s19": "s"}
        fmt = mapping.get(suffix, "a")
        idx = self.firmware_format.findData(fmt)
        if idx >= 0:
            self.firmware_format.setCurrentIndex(idx)

    def _firmware_changed(self) -> None:
        filename = self.firmware_path.text().strip()
        path = Path(filename).expanduser() if filename else None
        if path and path.is_file():
            self.firmware_meta.setText(f"{path.name}  ·  {path.stat().st_size:,} bytes  ·  {path.suffix.lower() or 'unknown format'}")
        else:
            self.firmware_meta.setText("No firmware selected" if not filename else "File does not exist")
        self._update_command_preview()

    def browse_avrdude(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Select AVRDUDE Executable", str(Path.home()), "All files (*)")
        if filename:
            self.avrdude_path.setText(filename)
            self.detect_avrdude()

    def browse_config(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Select avrdude.conf", str(Path.home()), "Config files (*.conf);;All files (*)")
        if filename:
            self.config_edit.setText(filename)

    def _target_changed(self) -> None:
        self._save_target_values()
        self._update_command_preview()
        self._update_fuse_preview()

    def _advanced_changed(self) -> None:
        self._save_advanced()
        self._update_command_preview()
        self._update_fuse_preview()

    def _update_command_preview(self) -> None:
        if not hasattr(self, "command_preview"):
            return
        try:
            filename = self.firmware_path.text().strip() if hasattr(self, "firmware_path") else ""
            if filename:
                op = MemoryOperation("flash", "w", filename, str(self.firmware_format.currentData() or "a"))
                # Preview should still work for a not-yet-existing path typed by a user.
                command = build_base_command(self._target(), self._advanced())
                command.arguments += ["-U", op.as_update_spec()]
            else:
                command = build_base_command(self._target(), self._advanced())
            self.command_preview.setPlainText(command.pretty() if self.pretty_check.isChecked() else command.single_line())
        except Exception as exc:
            self.command_preview.setPlainText(f"Cannot build command: {exc}")

    def copy_command(self) -> None:
        QApplication.clipboard().setText(self.command_preview.toPlainText())
        self.statusBar().showMessage("Command copied")

    def _theme_changed(self) -> None:
        theme = str(self.theme_combo.currentData() or "system")
        self.settings.set("appearance/theme", theme)
        self._apply_theme(theme)

    def _apply_theme(self, requested: str) -> None:
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        _, colors = resolve_theme(requested, app)
        app.setStyleSheet(stylesheet(colors))

    def _refresh_history(self) -> None:
        if hasattr(self, "history_view"):
            self.history_view.setPlainText("\n\n".join(self.settings.command_history()))

    def clear_history(self) -> None:
        self.settings.set("history/commands", [])
        self._refresh_history()

    # --------------------------------------------------------------- menu
    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        open_action = QAction("Open Firmware…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_firmware)
        file_menu.addAction(open_action)
        self.recent_menu = file_menu.addMenu("Recent Firmware")
        self._rebuild_recent_menu()
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view = self.menuBar().addMenu("View")
        for label, data in (("System Theme", "system"), ("Light Theme", "light"), ("Dark Theme", "dark")):
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, d=data: self._set_theme_from_menu(d))
            view.addAction(action)

        tools = self.menuBar().addMenu("Tools")
        detect = QAction("Detect AVRDUDE", self)
        detect.triggered.connect(self.detect_avrdude)
        tools.addAction(detect)
        ports = QAction("Refresh Serial Ports", self)
        ports.triggered.connect(self.refresh_ports)
        tools.addAction(ports)

        help_menu = self.menuBar().addMenu("Help")
        about = QAction("About HexHeist", self)
        about.triggered.connect(self.show_about)
        help_menu.addAction(about)

    def _rebuild_recent_menu(self) -> None:
        if not hasattr(self, "recent_menu"):
            return
        self.recent_menu.clear()
        files = self.settings.recent_files()
        if not files:
            action = self.recent_menu.addAction("No recent files")
            action.setEnabled(False)
            return
        for filename in files:
            action = self.recent_menu.addAction(Path(filename).name)
            action.setToolTip(filename)
            action.triggered.connect(lambda checked=False, f=filename: self.load_firmware(f))

    def _set_theme_from_menu(self, value: str) -> None:
        idx = self.theme_combo.findData(value)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)

    def _build_shortcuts(self) -> None:
        modifier = "Meta" if sys.platform == "darwin" else "Ctrl"
        shortcuts = [
            (f"{modifier}+R", self.read_signature),
            (f"{modifier}+W", self.flash_firmware),
            (f"{modifier}+Shift+V", self.verify_firmware),
            (f"{modifier}+E", self.erase_chip),
            (f"{modifier}+L", self.console_clear),
            ("F5", self.test_connection),
            ("F1", self.show_about),
        ]
        for sequence, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)

    def show_about(self) -> None:
        qt_version = QtCore.qVersion()
        text = (
            f"<h2>HexHeist {__version__}</h2>"
            "<p>A modern cross-platform graphical frontend for AVRDUDE.</p>"
            f"<p><b>Python:</b> {platform.python_version()}<br>"
            f"<b>Qt:</b> {qt_version}<br>"
            f"<b>AVRDUDE:</b> {self.avrdude_version or 'not detected'}<br>"
            f"<b>OS:</b> {platform.platform()}</p>"
            "<p>HexHeist executes the separately installed AVRDUDE command-line program and does not bundle AVRDUDE.</p>"
        )
        QMessageBox.about(self, "About HexHeist", text)

    # --------------------------------------------------------------- drag/drop
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.suffix.lower() in {".hex", ".ihx", ".elf", ".bin", ".srec", ".s19", ".eep"}:
                    self.load_firmware(str(path))
                    self._switch_page(0)
                    event.acceptProposedAction()
                    return

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.process.state() != QProcess.ProcessState.NotRunning:
            result = QMessageBox.question(self, "Quit HexHeist?", "AVRDUDE is still running. Stop it and quit?")
            if result != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.process.kill()
            self.process.waitForFinished(500)
        self._save_target_values()
        self._save_advanced()
        self.settings.set("window/geometry", self.saveGeometry())
        event.accept()
