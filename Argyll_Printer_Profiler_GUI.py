#!/usr/bin/env python3
"""Argyll Printer Profiler GUI - Complete Production Version

This is the complete production-ready GUI version of Argyll Printer Profiler,
implementing all workflows from the original CLI version with full functionality.

Version: 1.3.8
Platform: Windows, macOS, Linux
"""

from __future__ import annotations

import datetime as dt
import getpass
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTextEdit,
    QProgressBar,
    QFileDialog,
    QMessageBox,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QTabWidget,
    QGroupBox,
    QScrollArea,
    QFrame,
    QDialog,
    QRadioButton,
    QButtonGroup,
    QCheckBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QMutex, QWaitCondition
from PyQt6.QtGui import QFont, QTextCursor, QColor

VERSION = "1.3.8"


@dataclass
class AppState:
    """Holds script state and mirrors the CLI global variables."""

    script_dir: Path
    script_name: str
    temp_log: Path
    setup_file: Path
    PLATFORM: str

    # Mirrors CLI globals (cleared on each main menu iteration)
    source_folder: str = ""
    dialog_title: str = ""
    name: str = ""
    desc: str = ""
    action: str = ""
    profile_folder: str = ""
    new_name: str = ""
    ti3_mtime_before: str = ""
    ti3_mtime_after: str = ""
    tif_files: list[Path] = field(default_factory=list)
    new_icc_path: str = ""
    profile_installation_path: str = ""
    profile_extension: str = ""

    # Additional globals used by the ported workflow
    inst_arg: str = ""
    inst_name: str = ""

    # mtime of .ti3 file before chartread (for resume_measurement workflow)
    ti3_mtime_before: str = ""

    # Selected target option (1-6) for generate_target step
    target_option_selected: str = ""

    # Workflow state tracking (preserved when navigating back)
    profile_name_entered: bool = False  # Step 1: Profile name entered
    instrument_selected: bool = False  # Step 2: Instrument selected
    target_generated: bool = False  # Step 3: Target generated
    target_file_path: str = ""  # Path to generated target file
    measurement_completed: bool = False  # Step 4: Measurement completed
    measurement_file_path: str = ""  # Path to completed measurement file
    profile_created: bool = False  # Step 5: Profile created
    sanity_check_completed: bool = False  # Sanity check completed
    profile_installed: bool = False  # Profile installed
    ti3_file_selected: bool = False  # .ti3 file selected for workflows 2-5
    ti2_file_selected: bool = False  # .ti2 file selected for workflow 3
    copy_overwrite_choice_made: bool = False  # Copy/overwrite choice made for workflows 2-4
    copy_overwrite_choice: int = 0  # 1=create new, 2=overwrite, 3=abort


class GUILogger:
    """GUI logger that writes to terminal widget and log file."""

    def __init__(self, terminal_widget: QTextEdit, log_path: Path) -> None:
        self.terminal = terminal_widget
        self.log_path = log_path
        self._ensure_log_file()

    def _ensure_log_file(self) -> None:
        """Ensure log file exists and is writable."""
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_path.touch(exist_ok=True)
        except OSError as e:
            self.writeln(f"Cannot create log file at '{self.log_path}': {e}")

    def write(self, text: str) -> None:
        """Write text to terminal and log file."""
        # Write to terminal widget
        self.terminal.moveCursor(QTextCursor.MoveOperation.End)
        self.terminal.insertPlainText(text)
        self.terminal.ensureCursorVisible()

        # Append to log file
        with self.log_path.open("a", encoding="utf-8", errors="replace") as f:
            f.write(text)

    def writeln(self, text: str = "") -> None:
        """Write a line with newline."""
        self.write(text + "\n")

    def log_only(self, text: str = "") -> None:
        """Write to log file only, not to terminal."""
        with self.log_path.open("a", encoding="utf-8", errors="replace") as f:
            f.write(text + "\n")

    def clear(self) -> None:
        """Clear the terminal widget."""
        self.terminal.clear()


def log_event_enter(log: GUILogger, name: str) -> None:
    """Write a log-only timestamped ENTER marker for higher-level flow steps."""
    now = dt.datetime.now().astimezone()
    log.log_only(f"===== {now.strftime('%Y-%m-%d %H:%M:%S %z')} | ENTER | {name} =====")


def detect_platform() -> str:
    """Detect OS and return one of: windows, macos, linux."""
    sysname = platform.system().lower()
    if "windows" in sysname:
        return "windows"
    if "darwin" in sysname:
        return "macos"
    if "linux" in sysname:
        return "linux"
    raise RuntimeError(f"Unsupported operating system: {platform.system()}")


def pick_file_gui(title: str, filetypes: list[tuple[str, str]], initialdir: Optional[Path] = None, is_folder: bool = False, platform: str = "", parent: Optional[QWidget] = None) -> Optional[str]:
    """GUI file/folder picker using PyQt6. Returns path or None if cancelled.

    Mimics the original tkinter-based pick_file_gui function structure.
    """
    from PyQt6.QtWidgets import QFileDialog
    from PyQt6.QtWidgets import QFileDialog as NativeFileDialog

    kwargs: dict[str, object] = {
        "caption": title,
    }
    if parent is not None:
        kwargs["parent"] = parent

    if initialdir is not None:
        try:
            init = initialdir.expanduser()
            if init.is_dir():
                kwargs["directory"] = str(init)
        except Exception:
            pass

    # Use non-native dialog to ensure title shows on all platforms
    kwargs["options"] = QFileDialog.Option.DontUseNativeDialog

    if is_folder:
        # Use getExistingDirectory for folder selection
        path = QFileDialog.getExistingDirectory(**kwargs)
    else:
        # Convert filetypes to PyQt6 format
        filters = []
        for name, pattern in filetypes:
            filters.append(f"{name} ({pattern})")
        filter_str = ";;".join(filters)
        kwargs["filter"] = filter_str

        # Use getOpenFileName for file selection
        path, _ = QFileDialog.getOpenFileName(**kwargs)

    return path if path else None


def load_setup_file_shell_style(setup_path: Path) -> dict[str, str]:
    """Load setup variables from a shell-style setup file."""
    if not setup_path.exists():
        raise FileNotFoundError(f"Setup file not found: {setup_path}")

    _SETUP_ASSIGN_RE = re.compile(r'^\s*(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<val>.+?)\s*$')

    cfg: dict[str, str] = {}
    for raw_line in setup_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        m = _SETUP_ASSIGN_RE.match(line)
        if m:
            cfg[m.group("key")] = m.group("val")
    return cfg


def show_profile_name_dialog(parent: QWidget, cfg: dict[str, str], current_name: str | None = None, allow_empty: bool = True, prompt: str = "Enter filename: ") -> tuple[bool, str]:
    """Show dialog to enter profile name with full information from print_profile_name_menu.

    Args:
        parent: Parent widget
        cfg: Configuration dictionary
        current_name: Current profile name (None if not set)
        allow_empty: Whether to allow empty input (keeps current name)
        prompt: Prompt text to show

    Returns:
        Tuple of (success, new_name)
    """
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QWidget, QGroupBox

    dialog = QDialog(parent)
    dialog.setWindowTitle("Specify Profile Description / File Name")
    dialog.setMinimumWidth(600)
    layout = QVBoxLayout()

    # Add the full information from print_profile_name_menu
    info_group = QGroupBox("Profile Name Information")
    info_layout = QVBoxLayout()

    info_layout.addWidget(QLabel("The following is highly recommended to include:"))
    info_layout.addWidget(QLabel("  - Printer ID"))
    info_layout.addWidget(QLabel("  - Paper ID (Manufacturer, Product ID, Substrate Type)"))
    info_layout.addWidget(QLabel("  - Color Space"))
    info_layout.addWidget(QLabel("  - Target used for profile"))
    info_layout.addWidget(QLabel("  - Instrument/calibration type used"))
    info_layout.addWidget(QLabel("  - Date created"))
    info_layout.addSpacing(10)

    example = cfg.get("EXAMPLE_FILE_NAMING", "")
    if example:
        example_group = QGroupBox("Example File Naming Convention (select and copy)")
        example_layout = QVBoxLayout()
        example_input = QLineEdit(example)
        example_input.setReadOnly(True)
        example_input.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ccc; padding: 5px;")
        example_layout.addWidget(example_input)
        example_group.setLayout(example_layout)
        info_layout.addWidget(example_group)

    info_layout.addWidget(QLabel("For simplicity, profile description and filename are made identical."))
    info_layout.addWidget(QLabel("The profile description is what you will see in Photoshop and ColorSync Utility."))
    info_layout.addSpacing(10)
    info_layout.addWidget(QLabel("Enter a desired filename for this profile."))
    info_layout.addWidget(QLabel("If your filename is foobar, your profile will be named foobar with extension .icc or .icm."))
    info_layout.addSpacing(10)

    if current_name:
        info_layout.addWidget(QLabel(f"Current name: {current_name}"))
    info_layout.addSpacing(10)

    info_group.setLayout(info_layout)
    layout.addWidget(info_group)

    # Add input field
    layout.addSpacing(10)
    prompt_label = QLabel(prompt)
    layout.addWidget(prompt_label)

    name_input = QLineEdit()
    name_input.setPlaceholderText("Enter profile name...")
    if current_name:
        name_input.setText(current_name)
    layout.addWidget(name_input)

    # Add valid values label below input field
    layout.addSpacing(5)
    valid_label = QLabel("Valid values: Letters A-Z a-z, digits 0-9, dash -, underscore _, parentheses ( ), dot .")
    valid_label.setStyleSheet("color: gray; font-size: 11px; font-style: italic;")
    layout.addWidget(valid_label)

    # Add buttons
    button_layout = QHBoxLayout()
    button_layout.addStretch()

    cancel_btn = QPushButton("Cancel")
    ok_btn = QPushButton("OK")
    button_layout.addWidget(cancel_btn)
    button_layout.addWidget(ok_btn)
    layout.addLayout(button_layout)

    dialog.setLayout(layout)

    result = {"name": "", "success": False}

    def on_ok():
        name = name_input.text().strip()
        if not name:
            if allow_empty and current_name:
                result["name"] = current_name
            else:
                return
        if name and not re.fullmatch(r"[A-Za-z0-9._()\-]+", name):
            QMessageBox.warning(dialog, "Invalid Name", "Invalid file name characters. Please try again.")
            return
        result["name"] = name if name else current_name
        result["success"] = True
        dialog.accept()

    def on_cancel():
        dialog.reject()

    ok_btn.clicked.connect(on_ok)
    cancel_btn.clicked.connect(on_cancel)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        return result["success"], result["name"]
    else:
        return False, ""


def create_standard_dialog(parent: QWidget, title: str, content_widget: QWidget, on_ok: callable, on_cancel: callable = None) -> QDialog:
    """Create a standardized dialog with OK and Cancel buttons.

    Args:
        parent: Parent widget
        title: Dialog window title
        content_widget: Widget containing the dialog content
        on_ok: Function to call when OK is clicked
        on_cancel: Optional function to call when Cancel is clicked

    Returns:
        QDialog instance
    """
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QWidget

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(500)  # Set minimum width for consistency

    layout = QVBoxLayout()

    # Add content widget
    layout.addWidget(content_widget)

    # Add button layout
    button_layout = QHBoxLayout()
    button_layout.addStretch()

    cancel_btn = QPushButton("Cancel")
    cancel_btn.clicked.connect(lambda: dialog.reject() if on_cancel is None else on_cancel())
    button_layout.addWidget(cancel_btn)

    ok_btn = QPushButton("OK")
    ok_btn.clicked.connect(on_ok)
    button_layout.addWidget(ok_btn)

    layout.addLayout(button_layout)

    dialog.setLayout(layout)

    # If no custom cancel handler, just close the dialog
    if on_cancel is None:
        def default_cancel():
            dialog.reject()
        cancel_btn.clicked.connect(default_cancel)

    return dialog


def load_setup_file_shell_style(setup_path: Path) -> dict[str, str]:
    """Load setup variables from a shell-style setup file."""
    if not setup_path.exists():
        raise FileNotFoundError(f"Setup file not found: {setup_path}")

    _SETUP_ASSIGN_RE = re.compile(r'^\s*(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<val>.+?)\s*$')

    cfg: dict[str, str] = {}
    for raw_line in setup_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        m = _SETUP_ASSIGN_RE.match(line)
        if not m:
            continue

        key = m.group("key")
        val = m.group("val").strip()

        # Best-effort stripping of inline comments " # ...".
        if " #" in val:
            val = val.split(" #", 1)[0].rstrip()

        # Strip outer quotes if present
        if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
            val = val[1:-1]

        cfg[key] = val

    return cfg


def update_setup_value_shell_style(setup_path: Path, key: str, value: str) -> None:
    """Update a single value in the shell-style setup file."""
    if not setup_path.exists():
        raise FileNotFoundError(f"Setup file not found: {setup_path}")

    _SETUP_ASSIGN_RE = re.compile(r'^\s*(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<val>.+?)\s*$')

    lines = setup_path.read_text(encoding="utf-8", errors="replace").splitlines()
    updated_lines = []
    found = False

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            updated_lines.append(line)
            continue

        m = _SETUP_ASSIGN_RE.match(line)
        if m and m.group("key") == key:
            # Update this line
            updated_lines.append(f'{key}="{value}"')
            found = True
        else:
            updated_lines.append(line)

    if not found:
        # Add new line at the end
        updated_lines.append(f'{key}="{value}"')

    setup_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


def handle_command_error(proc: subprocess.CompletedProcess, log: GUILogger) -> None:
    """Handle command errors with standardized error output."""
    cmd_name = proc.args[0] if proc.args else "Unknown command"
    error_output = proc.stderr.strip() if proc.stderr else "No error details available"

    log.writeln("")
    log.writeln(f"Command failed: {cmd_name}")
    log.writeln(f"Exit code: {proc.returncode}")
    log.writeln(f"Error: {error_output}")
    log.writeln(f"Command: {' '.join(proc.args)}")
    log.writeln("")


def run_cmd(args: list[str], log: GUILogger, cwd: Optional[Path] = None) -> int:
    """Run external command with output streaming."""
    log.writeln(f"Command Used: {' '.join(args)}")

    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
        )

        # Stream output character by character
        while True:
            char = proc.stdout.read(1)
            if not char:
                break
            log.write(char)

        exit_code = proc.wait()

        if exit_code != 0:
            log.writeln("")
            log.writeln(f"Command failed with exit code: {exit_code}")
            log.writeln("")

        return exit_code

    except FileNotFoundError:
        log.writeln("")
        log.writeln(f"Command not found: {args[0]}")
        log.writeln("")
        return 127
    except Exception as e:
        log.writeln("")
        log.writeln(f"Error running command: {e}")
        log.writeln("")
        return 1


def validate_cfg_paths(state: Optional[AppState], cfg: dict[str, str], log: GUILogger) -> bool:
    """Validate configuration paths."""
    required_paths = {
        "PRINTER_ICC_PATH": "Color space profile for printer profile creation",
        "PRINTER_PROFILES_PATH": "Directory where printer profiles are installed",
    }

    for key, description in required_paths.items():
        path = cfg.get(key, "")
        if not path:
            log.writeln(f"Warning: {key} is not set ({description})")
            continue

        path_obj = Path(path)
        if not path_obj.exists():
            log.writeln(f"Warning: {key} path does not exist: {path}")
            log.writeln(f"  ({description})")
            return False

    return True


def check_required_commands(required_cmds: list[str], log: GUILogger, platform_name: str) -> None:
    """Check that required ArgyllCMS commands are available."""
    log.writeln("Checking required ArgyllCMS commands...")
    missing = []

    for cmd in required_cmds:
        if not shutil.which(cmd):
            missing.append(cmd)
            log.writeln(f"  Missing: {cmd}")
        else:
            log.writeln(f"  Found: {cmd}")

    if missing:
        log.writeln("")
        log.writeln(f"Error: Required commands not found: {', '.join(missing)}")
        log.writeln("Please install ArgyllCMS and ensure it's in your PATH.")
        log.writeln("")
        log.writeln("Download ArgyllCMS from: https://www.argyllcms.com/")
        log.writeln("")
        if platform_name == "linux":
            log.writeln("On Linux, you can install with:")
            log.writeln("  sudo apt install argyll")
        elif platform_name == "macos":
            log.writeln("On macOS, you can install with Homebrew:")
            log.writeln("  brew install argyll-cms")
        elif platform_name == "windows":
            log.writeln("On Windows, download and install from the ArgyllCMS website.")
        log.writeln("")
        raise RuntimeError(f"Missing required commands: {', '.join(missing)}")

    log.writeln("All required commands found.")
    log.writeln("")


def _collect_matching_tifs(folder: Path, base_name: str) -> list[Path]:
    """Collect TIFF files matching base name pattern."""
    tif_files = []
    if not folder.is_dir():
        return tif_files

    for f in folder.glob(f"{base_name}*.tif"):
        if f.is_file():
            tif_files.append(f)

    # Sort naturally (handle _01, _02, etc.)
    def natural_key(path: Path) -> tuple:
        name = path.stem
        parts = []
        for part in re.split(r'(\d+)', name):
            parts.append(int(part) if part.isdigit() else part.lower())
        return tuple(parts)

    return sorted(tif_files, key=natural_key)


class CommandThread(QThread):
    """Thread for running commands without blocking GUI."""

    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)
    error_signal = pyqtSignal(str)

    def __init__(self, args: list[str], cwd: Optional[Path] = None):
        super().__init__()
        self.args = args
        self.cwd = cwd

    def run(self):
        """Run the command and emit output."""
        try:
            proc = subprocess.Popen(
                self.args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.cwd,
            )

            # Stream output character by character
            while True:
                char = proc.stdout.read(1)
                if not char:
                    break
                self.output_signal.emit(char)

            exit_code = proc.wait()
            self.finished_signal.emit(exit_code)

        except FileNotFoundError:
            self.error_signal.emit(f"Command not found: {self.args[0]}")
            self.finished_signal.emit(127)
        except Exception as e:
            self.error_signal.emit(f"Error running command: {e}")
            self.finished_signal.emit(1)


class ProgressStep:
    """Represents a step in the workflow."""

    def __init__(self, name: str, completed: bool = False):
        self.name = name
        self.completed = completed


class MainWindow(QMainWindow):
    """Main window for the Argyll Printer Profiler GUI."""

    def __init__(self):
        super().__init__()
        self.state: Optional[AppState] = None
        self.cfg: dict[str, str] = {}
        self.log: Optional[GUILogger] = None
        self.workflow_steps: list[str] = []
        self.current_step_index = 0
        self.command_thread: Optional[CommandThread] = None
        self.workflow_history: list[str] = []

        # Progress labels for different workflows
        self.generate_progress: Optional[QLabel] = None
        self.measure_progress: Optional[QLabel] = None
        self.create_progress: Optional[QLabel] = None
        self.install_progress: Optional[QLabel] = None
        self.sanity_progress: Optional[QLabel] = None

        self.init_ui()
        self.init_application()
        self.show_main_menu()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle(f"Argyll Printer Profiler GUI - Version {VERSION}")
        # Window default size in pixels (width x height)
        self.setMinimumSize(800, 1100)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # Workflow title label (above progress section)
        self.workflow_title_label = QLabel("No workflow selected")
        self.workflow_title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #0066cc;")
        main_layout.addWidget(self.workflow_title_label)

        # Progress bar section (outside content group box for workflows)
        self.progress_section = self.create_progress_section()
        main_layout.addWidget(self.progress_section)

        # Step header label - displays current step title (outside content group box)
        self.step_header_label = QLabel("")
        self.step_header_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.step_header_label.setVisible(False)  # Hidden by default
        main_layout.addWidget(self.step_header_label)

        # Content group box - encompasses content split and navigation (not progress)
        self.content_group_box = QGroupBox()
        content_group_layout = QVBoxLayout()

        # Horizontal layout for content (2/3) and information (1/3)
        content_split_layout = QHBoxLayout()
        content_split_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins to align top borders

        # Content area (scrollable) - 2/3 of width
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setContentsMargins(0, 0, 0, 0)  # Remove margins to align top border
        from PyQt6.QtWidgets import QSizePolicy
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_split_layout.addWidget(self.scroll_area, 2)  # Stretch factor 2 (2/3 of width)

        # Information panel - 1/3 of width
        self.information_panel = self.create_information_panel()
        content_split_layout.addWidget(self.information_panel, 1)  # Stretch factor 1 (1/3 of width)

        content_group_layout.addLayout(content_split_layout, 1)  # Stretch factor 1 to take available space

        # Navigation buttons
        self.nav_section = self.create_navigation_section()
        content_group_layout.addWidget(self.nav_section)

        self.content_group_box.setLayout(content_group_layout)
        main_layout.addWidget(self.content_group_box, 1)  # Stretch factor 1 to take available space

        # Terminal output section - fixed height below content
        self.terminal_section = self.create_terminal_section()
        self.terminal_section.setMaximumHeight(675)  # Fixed height for terminal (50% taller)
        self.terminal_section.setMinimumHeight(337)  # Minimum height (50% taller)
        main_layout.addWidget(self.terminal_section, 0)  # Stretch factor 0 to keep fixed size

    def create_progress_section(self) -> QGroupBox:
        """Create the progress section."""
        group = QGroupBox("Workflow Progress")
        layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - %v/%m steps")
        layout.addWidget(self.progress_bar)

        self.step_labels = []
        self.steps_layout = QHBoxLayout()
        layout.addLayout(self.steps_layout)

        group.setLayout(layout)
        return group

    def create_terminal_section(self) -> QGroupBox:
        """Create the terminal output section."""
        group = QGroupBox("Terminal Output")
        layout = QVBoxLayout()

        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        # Font size will be set in init_application from TERMINAL_FONT_SIZE parameter
        # Terminal fills the fixed-height section
        from PyQt6.QtWidgets import QSizePolicy
        self.terminal.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.terminal)

        # Set group box size policy to fixed height
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        group.setLayout(layout)
        return group

    def create_information_panel(self) -> QGroupBox:
        """Create the information panel for displaying progress and status."""
        from PyQt6.QtWidgets import QSizePolicy
        group = QGroupBox("Information")
        layout = QVBoxLayout()

        # Set layout margins to 0 to align top border with content area
        layout.setContentsMargins(0, 0, 0, 0)

        # Information label for displaying progress/status
        self.information_label = QLabel("Ready")
        self.information_label.setWordWrap(True)
        self.information_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.information_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.information_label)

        # Add stretch to push content to top
        layout.addStretch()

        group.setLayout(layout)

        # Set size policy to match scroll area (expanding in both directions)
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return group

    def create_navigation_section(self) -> QWidget:
        """Create the navigation button section."""
        widget = QWidget()
        layout = QHBoxLayout()

        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.on_back_clicked)
        self.back_button.setEnabled(False)
        self.back_button.setStyleSheet("QPushButton:disabled { color: #808080; }")
        layout.addWidget(self.back_button)

        self.abort_button = QPushButton("Abort And Go Back to Main Menu")
        self.abort_button.setStyleSheet("background-color: #ffcccc; color: black;")
        self.abort_button.clicked.connect(self.on_abort_clicked)
        self.abort_button.setEnabled(False)
        layout.addWidget(self.abort_button)

        layout.addStretch()

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.on_next_clicked)
        self.next_button.setEnabled(False)
        self.next_button.setStyleSheet("QPushButton:disabled { color: #808080; }")
        layout.addWidget(self.next_button)

        widget.setLayout(layout)
        return widget

    def init_application(self):
        """Initialize the application state."""
        try:
            # Detect platform
            PLATFORM = detect_platform()

            # Get script path
            script_path = Path(__file__).resolve()
            script_dir = script_path.parent
            script_name = script_path.name

            # Create log file path
            today = dt.date.today().strftime("%Y%m%d")
            temp_log = script_dir / f"Argyll_Printer_Profiler_GUI_{today}.log"
            setup_file = script_dir / "Argyll_Printer_Profiler_setup.ini"

            # Create logger
            self.log = GUILogger(self.terminal, temp_log)

            # Create application state
            self.state = AppState(
                script_dir=script_dir,
                script_name=script_name,
                temp_log=temp_log,
                setup_file=setup_file,
                PLATFORM=PLATFORM,
            )

            # Print banner
            self.print_banner()

            # Add session separator
            self.session_separator()

            # Load setup configuration
            if not setup_file.exists():
                self.log.writeln("Error: Setup file not found:")
                self.log.writeln(f"   {setup_file}")
                QMessageBox.critical(self, "Error", f"Setup file not found:\n{setup_file}")
                return

            self.cfg = load_setup_file_shell_style(setup_file)

            # Update terminal font size from config
            terminal_font_size = int(self.cfg.get("TERMINAL_FONT_SIZE", "10"))
            self.terminal.setFont(QFont("Courier New", terminal_font_size))

            # Check required commands
            required_cmds = ["targen", "chartread", "colprof", "printtarg", "profcheck"]
            check_required_commands(required_cmds, self.log, PLATFORM)

            # Check Linux window management tools
            if PLATFORM == "linux":
                if not shutil.which("xdotool") and not shutil.which("wmctrl"):
                    self.log.writeln("Warning: On Linux, window management tools (xdotool or wmctrl) are recommended for better file dialog experience.")

            # Extract Argyll version
            try:
                result = subprocess.run(["colprof"], capture_output=True, text=True)
                argyll_version_line = (result.stdout + result.stderr).split('\n')[0]
                match = re.search(r'Version ([0-9.]+)', argyll_version_line)
                argyll_version = match.group(1) if match else "unknown"
            except (subprocess.SubprocessError, AttributeError):
                argyll_version = "unknown"

            self.log.writeln("ArgyllCMS detected")
            self.log.writeln(f"Version: {argyll_version}")
            self.log.writeln("")

        except Exception as e:
            QMessageBox.critical(self, "Initialization Error", f"Failed to initialize application:\n{e}")
            sys.exit(1)

    def print_banner(self):
        """Print the banner to terminal."""
        self.log.writeln("=" * 70)
        self.log.writeln("    ___        _                        _           _ _       ")
        self.log.writeln("   / _ \\ _   _| |_ ___  _ __ ___   __ _| |_ ___  __| | |      ")
        self.log.writeln("  | | | | | | | __/ _ \\| '_ ` _ \\ / _` | __/ _ \\/ _` | |   ")
        self.log.writeln("  | |_| | |_| | || (_) | | | | | | (_| | ||  __/ (_| | |      ")
        self.log.writeln("   \\___/ \\__,_|\\__\\___/|_| |_| |_|\\__,_|\\__\\___|\\__,_|_|      ")
        self.log.writeln("                                                              ")
        self.log.writeln("        Argyll Printer Profiler GUI (Automated Workflow)       ")
        self.log.writeln("        Color Target Generation & ICC/ICM Profiling           ")
        self.log.writeln("=" * 70)
        self.log.writeln("")
        self.log.writeln("Automated ArgyllCMS GUI for calibrating printers on macOS, Linux, and Windows.")
        self.log.writeln("A selection of targets is provided as examples in the folder Pre-made_Targets.")
        self.log.writeln("These are adapted for use with X-Rite ColorMunki Photo, i1Studio and i1Pro.")
        self.log.writeln("Modify target charts and command arguments in .ini file.")
        self.log.writeln("")
        self.log.writeln("Author:  Knut Larsson")
        self.log.writeln(f"Version: {VERSION}")
        self.log.writeln("")

    def session_separator(self):
        """Write a session separator to log."""
        now = dt.datetime.now().astimezone()
        self.log.log_only("")
        self.log.log_only("=" * 80)
        self.log.log_only("NEW GUI SESSION STARTED")
        self.log.log_only(f"Date & Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z (%z)')}")
        self.log.log_only(f"Platform: {self.state.PLATFORM}")
        self.log.log_only("=" * 80)
        self.log.log_only("")

    def set_content_widget(self, widget: QWidget):
        """Set the main content widget."""
        # Set layout margins to 0 to align top border with information panel
        if widget.layout():
            widget.layout().setContentsMargins(0, 0, 0, 0)
        self.scroll_area.setWidget(widget)

    def update_information_panel(self, text: str, color: str = "black"):
        """Update the information panel with text and color.

        Args:
            text: Text to display
            color: Color for the text (e.g., "black", "red", "green", "blue")
        """
        self.information_label.setText(text)
        self.information_label.setStyleSheet(f"font-size: 12px; color: {color};")

    def update_progress(self, steps: list[str], current_index: int):
        """Update the progress bar and step indicators."""
        self.workflow_steps = [ProgressStep(name) for name in steps]
        self.current_step_index = current_index

        # Clear previous step labels
        for label in self.step_labels:
            label.deleteLater()
        self.step_labels.clear()

        # Update progress bar
        self.progress_bar.setMaximum(len(steps))
        self.progress_bar.setValue(current_index)

        # Create step indicators
        for i, step in enumerate(self.workflow_steps):
            label = QLabel(step.name)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            if i < current_index:
                label.setStyleSheet("color: green; font-weight: bold;")
                step.completed = True
            elif i == current_index:
                label.setStyleSheet("color: blue; font-weight: bold;")
            else:
                label.setStyleSheet("color: gray;")

            self.steps_layout.addWidget(label)
            self.step_labels.append(label)

    def update_progress_display(self):
        """Update the progress bar and step label styles based on current step index."""
        # Update progress bar
        self.progress_bar.setValue(self.current_step_index)

        # Update step label styles
        for i, label in enumerate(self.step_labels):
            if i < self.current_step_index:
                label.setStyleSheet("color: green; font-weight: bold;")
                if i < len(self.workflow_steps):
                    self.workflow_steps[i].completed = True
            elif i == self.current_step_index:
                label.setStyleSheet("color: blue; font-weight: bold;")
            else:
                label.setStyleSheet("color: gray;")

    def enable_and_focus_next_button(self):
        """Enable Next button, set focus, and highlight it."""
        self.next_button.setEnabled(True)
        self.next_button.setFocus()
        self.next_button.setStyleSheet("")  # Normal styling

    def enable_next_button(self):
        """Enable Next button and highlight it without setting focus."""
        self.next_button.setEnabled(True)
        self.next_button.setStyleSheet("")  # Normal styling

    def on_back_clicked(self):
        """Handle back button click."""
        # Prevent clicking when disabled
        if not self.back_button.isEnabled():
            return

        if self.current_page == "main_menu":
            return

        self.log.writeln("")
        self.log.writeln(f"--- Navigating back from '{self.current_page}' ---")
        self.log.writeln("")

        # For informational pages, go directly to main menu
        if self.current_page in ["setup_parameters", "improving_accuracy", "de_reference"]:
            self.show_main_menu()
            return

        # Navigate back based on current page
        self.navigate_back()

    def on_next_clicked(self):
        """Handle next button click."""
        self.log.writeln("")
        self.log.writeln(f"--- Navigating forward from '{self.current_page}' ---")
        self.log.writeln("")

        # Check for existing profile folder when on profile name page
        if self.current_page == "specify_name":
            # Skip folder preparation if profile name already entered and folder exists
            # and name hasn't changed
            if self.state.profile_name_entered and self.state.profile_folder:
                profile_folder = Path(self.state.profile_folder)
                if profile_folder.is_dir():
                    # Check if name has changed by comparing folder name with current name
                    folder_name = profile_folder.name
                    if folder_name == self.state.name:
                        self.log.writeln(f"Profile folder already exists: '{self.state.profile_folder}'")
                        self.log.writeln("Using existing folder and files.")
                        self.log.writeln("")
                    else:
                        # Name changed, need to recreate folder
                        self.log.writeln(f"Profile name changed from '{folder_name}' to '{self.state.name}'")
                        self.log.writeln("Creating new profile folder...")
                        self.log.writeln("")
                        if not self.prepare_profile_folder():
                            return
                        self.state.profile_name_entered = True
                else:
                    # Folder was deleted, need to recreate
                    if not self.prepare_profile_folder():
                        return
                    self.state.profile_name_entered = True
            else:
                # First time or name changed
                if not self.prepare_profile_folder():
                    return
                self.state.profile_name_entered = True

        # Navigate forward based on current page
        self.navigate_forward()

    def on_abort_clicked(self):
        """Handle abort button click - go back to main menu."""
        self.log.writeln("")
        self.log.writeln("--- Workflow aborted by user ---")
        self.log.writeln("")

        # Close sanity file handle if open
        if hasattr(self, 'sanity_file_handle') and self.sanity_file_handle:
            self.sanity_file_handle.close()
            self.sanity_file_handle = None

        self.log.writeln("Aborting workflow and returning to main menu...")
        self.log.writeln("")

        # Reset workflow state
        self.workflow_history = []
        self.workflow_steps = []
        self.current_step_index = 0
        self.workflow_type = None

        # Clear workflow state tracking
        self.state.profile_name_entered = False
        self.state.instrument_selected = False
        self.state.target_generated = False
        self.state.target_file_path = ""
        self.state.measurement_completed = False
        self.state.measurement_file_path = ""
        self.state.profile_created = False
        self.state.sanity_check_completed = False
        self.state.profile_installed = False
        self.state.ti3_file_selected = False
        self.state.ti2_file_selected = False
        self.state.copy_overwrite_choice_made = False
        self.state.copy_overwrite_choice = 0
        self.state.target_option_selected = ""

        # Clear progress display
        self.progress_bar.setValue(0)
        self.progress_bar.setRange(0, 0)
        for label in self.step_labels:
            label.deleteLater()
        self.step_labels = []

        # Go back to main menu
        self.show_main_menu()

    def copy_or_overwrite_submenu(self, overwrite_message_line_1: str, overwrite_message_line_2: Optional[str] = None) -> bool:
        """Show the copy/overwrite/abort submenu used by select_ti2_file/select_ti3_file.

        This is a direct port of the Bash submenu text and behavior.
        """
        # Check if choice was already made (navigating back)
        if self.state.copy_overwrite_choice_made:
            choice = self.state.copy_overwrite_choice
            self.log.writeln("")
            self.log.writeln(f"Using previous choice: {choice}")
            self.log.writeln("")
        else:
            self.log.writeln("")
            self.log.writeln("Do you want to:")
            self.log.writeln("")
            self.log.writeln("1: Create new profile (copy files into new folder)")
            self.log.writeln(overwrite_message_line_1)
            if overwrite_message_line_2 is not None:
                self.log.writeln(overwrite_message_line_2)
            self.log.writeln("3: Abort operation")
            self.log.writeln("")

            # Create content widget for standardized dialog
            content = QWidget()
            content_layout = QVBoxLayout()

            title = QLabel("Do you want to:")
            title.setStyleSheet("font-weight: bold; font-size: 14px;")
            content_layout.addWidget(title)

            content_layout.addSpacing(10)

            # Radio buttons for options
            self.copy_choice_group = QButtonGroup()
            radio1 = QRadioButton("Create new profile (copy files into new folder)")
            radio1.setChecked(True)
            self.copy_choice_group.addButton(radio1, 1)
            content_layout.addWidget(radio1)

            radio2 = QRadioButton(overwrite_message_line_1.replace("2: ", ""))
            self.copy_choice_group.addButton(radio2, 2)
            content_layout.addWidget(radio2)

            if overwrite_message_line_2 is not None:
                radio2_extra = QLabel(overwrite_message_line_2)
                radio2_extra.setStyleSheet("padding-left: 30px;")
                radio2_extra.setWordWrap(True)
                content_layout.addWidget(radio2_extra)

            radio3 = QRadioButton("Abort operation")
            self.copy_choice_group.addButton(radio3, 3)
            content_layout.addWidget(radio3)

            content.setLayout(content_layout)

            # Create standardized dialog
            dialog = create_standard_dialog(self, "Choose Action", content, lambda: dialog.accept(), lambda: dialog.reject())

            if dialog.exec() != QDialog.DialogCode.Accepted:
                self.log.writeln("User chose to abort.")
                return False

            choice = self.copy_choice_group.checkedId()
            # Store the choice for future navigation
            self.state.copy_overwrite_choice = choice
            self.state.copy_overwrite_choice_made = True

        if choice == 1:
            # Create new profile (copy files into new folder)
            if not self.prepare_profile_folder():
                self.log.writeln("Profile preparation failed...")
                return False

            # If source and destination are the same folder, skip copy, rename and check
            # because nothing should be copied and files should not be renamed/checked.
            source = Path(self.state.source_folder)
            dest = Path(self.state.profile_folder)

            def _same_dir(a: Path, b: Path) -> bool:
                try:
                    return a.resolve() == b.resolve()
                except OSError:
                    return a.absolute() == b.absolute()

            if _same_dir(source, dest):
                # Same folder: skip copy, rename and check
                self.state.name = self.state.new_name
                self.state.desc = self.state.new_name
                return True

            # Source and destination are different folders
            if not self.copy_files_ti1_ti2_ti3_tif():
                self.log.writeln("File copy failed...")
                return False

            if not self.rename_files_ti1_ti2_ti3_tif():
                self.log.writeln("File renaming failed...")
                return False

            if not self.check_files_in_new_location_after_copy():
                self.log.writeln("File check after copy failed...")
                return False
            return True

        if choice == 2:
            # Overwrite existing (use files in their current location)
            self.state.profile_folder = self.state.source_folder
            self.log.writeln("Working folder for profile:")
            self.log.writeln(self.state.profile_folder)
            try:
                os.chdir(self.state.profile_folder)
            except OSError:
                self.log.writeln(f"Failed to change directory to '{self.state.profile_folder}'")
                return False
            return True

        if choice == 3:
            # Abort
            self.log.writeln("User chose to abort.")
            return False

        return False

    def prepare_profile_folder(self) -> bool:
        """Create/select profile folder (port of CLI prepare_profile_folder)."""
        if not self.state.name:
            self.log.writeln("name variable not set")
            return False

        if not self.workflow_type:
            self.log.writeln("workflow_type not set")
            return False

        created_profiles_folder = self.cfg.get("CREATED_PROFILES_FOLDER", "Created_Profiles")

        # Default fallback
        self.state.new_name = self.state.name

        # Do only if action 2 or 3 or 4
        if self.workflow_type in {"resume_measurement", "read_from_scratch", "profile_from_measurement"}:
            # Show dialog to enter new name or keep current
            allow_empty = True if self.workflow_type != "profile_from_measurement" else False

            if allow_empty:
                prompt = "Enter filename (leave empty to keep current): "
            else:
                prompt = "Enter filename: "

            success, new_name = show_profile_name_dialog(self, self.cfg, self.state.name, allow_empty, prompt)
            if not success:
                if allow_empty:
                    self.state.new_name = self.state.name
                else:
                    return False
            else:
                self.state.new_name = new_name

        # Check if folder exists and handle conflicts
        while True:
            profile_folder = self.state.script_dir / created_profiles_folder / self.state.new_name

            if not profile_folder.is_dir():
                break

            # Folder exists - show dialog with options
            self.log.writeln("")
            self.log.writeln(f"Profile folder already exists: '{str(profile_folder)}'")
            self.log.writeln("")
            self.log.writeln("Contents:")

            try:
                for p in sorted(profile_folder.iterdir()):
                    self.log.writeln(f"  {p.name}")
            except OSError:
                self.log.writeln(f"  (Unable to list contents of '{str(profile_folder)}')")
            self.log.writeln("")

            # Create dialog with 3 options
            dialog = QDialog(self)
            dialog.setWindowTitle("Profile Folder Already Exists")
            dialog.setModal(True)
            layout = QVBoxLayout()

            title = QLabel("Profile folder already exists:")
            title.setStyleSheet("font-weight: bold; font-size: 14px;")
            layout.addWidget(title)

            folder_label = QLabel(str(profile_folder))
            folder_label.setStyleSheet("font-family: monospace; color: blue;")
            layout.addWidget(folder_label)

            layout.addSpacing(10)

            options_label = QLabel("Choose an option:")
            options_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(options_label)

            layout.addSpacing(10)

            # Radio buttons for options
            self.folder_choice_group = QButtonGroup()
            radio1 = QRadioButton("Use existing folder (delete existing files)")
            radio1.setChecked(True)
            self.folder_choice_group.addButton(radio1, 1)
            layout.addWidget(radio1)

            radio2 = QRadioButton("Enter a different name")
            self.folder_choice_group.addButton(radio2, 2)
            layout.addWidget(radio2)

            radio3 = QRadioButton("Cancel operation")
            self.folder_choice_group.addButton(radio3, 3)
            layout.addWidget(radio3)

            layout.addSpacing(20)

            # OK button only (Cancel is handled by radio button 3)
            ok_btn = QPushButton("OK")
            ok_btn.clicked.connect(dialog.accept)
            layout.addWidget(ok_btn)

            dialog.setLayout(layout)

            if dialog.exec() != QDialog.DialogCode.Accepted:
                self.log.writeln("Creating profile folder cancelled.")
                return False

            choice = self.folder_choice_group.checkedId()

            if choice == 1:
                # Use existing folder - delete contents
                self.log.writeln("")
                self.log.writeln(f"Using existing folder: '{str(profile_folder)}'")

                # Only delete if new_name differs from name (matching original code)
                if self.state.new_name != self.state.name:
                    # Delete existing contents to avoid leftover files from previous runs
                    self.log.writeln("Deleting existing contents to avoid leftover files from previous runs...")
                    for item in profile_folder.iterdir():
                        try:
                            if item.is_file() or item.is_symlink():
                                item.unlink()
                            elif item.is_dir():
                                shutil.rmtree(item)
                        except OSError as e:
                            self.log.writeln(f"Warning: Failed to delete {item.name}: {e}")
                break

            elif choice == 2:
                # Enter different name - show dialog
                self.log.writeln("")
                self.log.writeln("Please enter a different profile name.")

                success, new_name = show_profile_name_dialog(self, self.cfg, self.state.name, False, "Enter a different profile name:")
                if not success:
                    self.log.writeln("")
                    self.log.writeln("Creating profile folder cancelled.")
                    return False
                else:
                    self.state.new_name = new_name
                    # Continue loop to check if new name also exists
                    continue

            elif choice == 3:
                # Cancel
                self.log.writeln("")
                self.log.writeln("Creating profile folder cancelled.")
                return False

        try:
            profile_folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.log.writeln(f"Failed to create profile folder: '{str(profile_folder)}'")
            return False

        self.log.writeln("Working folder for profile:")
        self.log.writeln(f"'{str(profile_folder)}'")
        try:
            os.chdir(profile_folder)
        except OSError:
            self.log.writeln(f"Failed to change directory to '{str(profile_folder)}'")
            return False

        self.state.profile_folder = str(profile_folder)
        self.state.desc = self.state.new_name
        return True

    def copy_files_ti1_ti2_ti3_tif(self) -> bool:
        """Copy relevant .ti1/.ti2/.ti3/.tif files into working folder."""

        if not self.state.source_folder or not self.state.profile_folder:
            return False

        source = Path(self.state.source_folder)
        dest = Path(self.state.profile_folder)

        def _copy_if_exists(path: Path, required: bool, missing_message: str) -> bool:
            if not self.state.name or not path.is_file():
                if required:
                    self.log.writeln(missing_message)
                    return False
                if missing_message:
                    self.log.writeln(missing_message)
                return True
            try:
                shutil.copy2(path, dest / path.name)
            except OSError:
                self.log.writeln(f"Failed to copy {path.name} to directory '{str(dest)}'")
                self.log.writeln("Profile folder is left as is:")
                self.log.writeln(f"'{str(dest)}'")
                return False
            return True

        self.log.writeln(f"Copying files from '{str(source)}' to '{str(dest)}'...")

        # .ti1 is optional
        if not _copy_if_exists(
            source / f"{self.state.name}.ti1",
            required=False,
            missing_message=f"No .ti1 file found in selected folder '{self.state.name}'. Not required, thus ignoring.",
        ):
            return False

        # .ti2 required unless action 4
        if self.workflow_type == "profile_from_measurement":
            if not _copy_if_exists(
                source / f"{self.state.name}.ti2",
                required=False,
                missing_message=f".ti2 file not found for '{self.state.name}'. Ignoring.",
            ):
                return False
        else:
            if not _copy_if_exists(
                source / f"{self.state.name}.ti2",
                required=True,
                missing_message=f".ti2 file not found for '{self.state.name}'.",
            ):
                return False

        # .ti3 required for action 2 or 4
        if self.workflow_type in {"resume_measurement", "profile_from_measurement"}:
            if not _copy_if_exists(
                source / f"{self.state.name}.ti3",
                required=True,
                missing_message=f".ti3 file not found for '{self.state.name}'.",
            ):
                return False

        for f in self.state.tif_files:
            try:
                shutil.copy2(f, dest / f.name)
            except OSError:
                self.log.writeln(f"Failed to copy {f.name} to '{str(dest)}'")
                self.log.writeln("Profile folder is left as is:")
                self.log.writeln(f"'{str(dest)}'")
                return False

        return True

    def rename_files_ti1_ti2_ti3_tif(self) -> bool:
        """Rename copied files to match new profile name."""
        profile_folder = Path(self.state.profile_folder)
        old_name = Path(self.state.name)
        new_name = Path(self.state.new_name)

        # Rename ti1 and ti2 files
        extensions = ['.ti1', '.ti2']
        for ext in extensions:
            old_file = profile_folder / f"{old_name}{ext}"
            new_file = profile_folder / f"{new_name}{ext}"

            if old_file.exists():
                try:
                    old_file.rename(new_file)
                    self.log.writeln(f"Renamed: {old_file.name} -> {new_file.name}")
                except OSError as e:
                    self.log.writeln(f"Failed to rename {old_file.name}: {e}")
                    return False

        # Rename ti3 file (only for actions 2 and 4)
        if self.workflow_type in {"resume_measurement", "profile_from_measurement"}:
            old_ti3 = profile_folder / f"{old_name}.ti3"
            new_ti3 = profile_folder / f"{new_name}.ti3"
            if old_ti3.exists():
                try:
                    old_ti3.rename(new_ti3)
                    self.log.writeln(f"Renamed: {old_ti3.name} -> {new_ti3.name}")
                except OSError as e:
                    self.log.writeln(f"Failed to rename {old_ti3.name}: {e}")
                    return False

        # Rename tif files with proper suffix handling
        new_tifs = []
        for f in self.state.tif_files:
            ext = f.suffix
            base = f.stem
            suffix = ""
            m = re.search(r"_[0-9]{2}$", base)
            if m:
                suffix = m.group(0)
            new_file_name = f"{self.state.new_name}{suffix}{ext}"
            old_path = profile_folder / f.name
            new_path = profile_folder / new_file_name
            if not old_path.is_file():
                continue
            try:
                old_path.rename(new_path)
                self.log.writeln(f"Renamed: {old_path.name} -> {new_path.name}")
            except OSError as e:
                self.log.writeln(f"Failed to rename {old_path.name}: {e}")
                return False
            new_tifs.append(new_path)

        self.state.tif_files = new_tifs
        self.state.name = self.state.new_name
        self.state.desc = self.state.new_name
        return True

    def check_files_in_new_location_after_copy(self) -> bool:
        """Check that files exist after copy and rename."""
        if not self.state.profile_folder or not self.state.name:
            self.log.writeln("Required variables not set for file check")
            return False

        profile_folder = Path(self.state.profile_folder)
        missing_files = False

        # Check .ti2, applicable for actions 2 and 3
        if self.workflow_type != "profile_from_measurement":
            if not (profile_folder / f"{self.state.name}.ti2").is_file():
                self.log.writeln(f"Missing {self.state.name}.ti2 in {str(profile_folder)}")
                missing_files = True

            tif_files = _collect_matching_tifs(profile_folder, self.state.name)
            if not tif_files:
                self.log.writeln(f"No TIFF files found in {str(profile_folder)}")
                missing_files = True
            else:
                self.state.tif_files = tif_files

        # Check .ti3, applicable for actions 2 and 4
        if self.workflow_type in {"resume_measurement", "profile_from_measurement"}:
            if not (profile_folder / f"{self.state.name}.ti3").is_file():
                self.log.writeln(f"Missing {self.state.name}.ti3 in {str(profile_folder)}")
                missing_files = True

        if missing_files:
            self.log.writeln("File copy to profile location failed. Returning to main menu...")
            return False

        self.log.writeln("All files verified after copy")
        return True

    def navigate_back(self):
        """Navigate to previous step."""
        if not self.workflow_history:
            return

        # Restore Next button visibility when navigating away from install_profile
        if self.current_page == "install_profile":
            self.next_button.setVisible(True)
            self.next_button.setStyleSheet("")  # Reset style

        # Pop current page from history
        previous_page = self.workflow_history.pop()

        # Decrement step index if not going to main menu
        if previous_page != "main_menu" and self.current_step_index > 0:
            self.current_step_index -= 1
            self.update_progress_display()

        # Navigate to previous page
        if previous_page == "main_menu":
            self.show_main_menu()
        elif previous_page == "specify_name":
            self.show_specify_profile_name()
        elif previous_page == "select_instrument":
            self.show_select_instrument()
        elif previous_page == "generate_target":
            self.show_generate_target()
        elif previous_page == "measure_target":
            self.show_measure_target()
        elif previous_page == "create_profile":
            self.show_create_profile()
        elif previous_page == "sanity_check":
            self.show_sanity_check()
        elif previous_page == "install_profile":
            self.show_install_profile()
        elif previous_page == "select_ti3_file":
            self.show_select_ti3_file()
        elif previous_page == "select_ti2_file":
            self.show_select_ti2_file()

    def navigate_forward(self):
        """Navigate to next step."""
        # Add current page to history
        self.workflow_history.append(self.current_page)

        # Increment step index
        max_steps = len(self.workflow_steps)
        if self.current_step_index < max_steps - 1:
            self.current_step_index += 1
            self.update_progress_display()

        # Navigate to next page based on current page
        if self.current_page == "specify_name":
            self.show_select_instrument()
        elif self.current_page == "select_instrument":
            self.show_generate_target()
        elif self.current_page == "generate_target":
            self.show_measure_target()
        elif self.current_page == "measure_target":
            self.show_create_profile()
        elif self.current_page == "create_profile":
            # Skip sanity check for workflows 1-4, go directly to install_profile
            if self.workflow_type == "sanity_check":
                self.show_sanity_check()
            else:
                self.show_install_profile()
        elif self.current_page == "sanity_check":
            self.show_install_profile()
        elif self.current_page == "install_profile":
            self.show_completion()
        elif self.current_page == "select_ti3_file":
            # Different workflows have different next steps
            if self.workflow_type == "resume_measurement":
                self.show_measure_target()
            elif self.workflow_type == "profile_from_measurement":
                self.show_create_profile()
            elif self.workflow_type == "sanity_check":
                self.show_sanity_check()
        elif self.current_page == "select_ti2_file":
            self.show_measure_target()

    def show_main_menu(self):
        """Show the main menu."""
        self.log.writeln("")
        self.log.writeln("=== Entering Main Menu ===")
        self.log.writeln("")

        self.current_page = "main_menu"
        self.back_button.setEnabled(False)
        self.abort_button.setVisible(False)
        self.next_button.setEnabled(False)
        self.workflow_history.clear()
        self.workflow_title_label.setText("Printer Profiling - Main Menu")
        self.workflow_title_label.setVisible(True)  # Show title in main menu
        self.workflow_title_label.setStyleSheet("font-weight: bold; font-size: 18px; color: #0066cc;")
        self.progress_section.setVisible(False)  # Hide progress section in main menu
        self.nav_section.setVisible(False)  # Hide navigation buttons in main menu
        self.information_panel.setVisible(True)  # Show information panel in main menu
        self.step_header_label.setVisible(False)  # Hide step header in main menu
        self.update_progress(["Main Menu"], 0)

        # Update information panel
        self.update_information_panel("Select an action from the menu to begin.\n\n"
                                     "Options 1-5: Workflow-based printer profiling\n"
                                     "Options 6-8: Utilities and information")

        widget = QWidget()
        layout = QVBoxLayout()

        # General notes
        notes_group = QGroupBox("General Notes")
        notes_layout = QVBoxLayout()
        note1 = QLabel("1. Existing ti1/ti2/ti3/icc/icm and target image (.tif) filenames must match.")
        note1.setWordWrap(True)
        notes_layout.addWidget(note1)
        note2 = QLabel("2. If more than one target image, filenames must end with _01, _02, etc.")
        note2.setWordWrap(True)
        notes_layout.addWidget(note2)
        notes_group.setLayout(notes_layout)
        layout.addWidget(notes_group)

        # Menu options
        options_group = QGroupBox("What action do you want to perform?")
        options_layout = QVBoxLayout()

        buttons = [
            ("1: Create target chart and printer profile from scratch", "on_menu_option_1"),
            ("2: Resume or re-read an existing target chart measurement and create printer profile", "on_menu_option_2"),
            ("3: Read an existing target chart from scratch and create printer profile", "on_menu_option_3"),
            ("4: Create printer profile from an existing measurement file", "on_menu_option_4"),
            ("5: Perform sanity check on existing printer profile", "on_menu_option_5"),
            ("6: Change setup parameters", "on_menu_option_6"),
            ("7: Show tips on how to improve accuracy of a profile", "on_menu_option_7"),
            ("8: Show Delta E2000 Color Accuracy - Quick Reference", "on_menu_option_8"),
        ]

        for text, method_name in buttons:
            btn = QPushButton(text)
            btn.setStyleSheet("text-align: left; padding: 8px;")
            getattr(self, method_name)(btn)
            options_layout.addWidget(btn)

        exit_btn = QPushButton("9: Exit")
        exit_btn.setStyleSheet("text-align: left; padding: 8px;")
        exit_btn.clicked.connect(self.close)
        options_layout.addWidget(exit_btn)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        layout.addStretch()
        widget.setLayout(layout)
        self.set_content_widget(widget)

    def on_menu_option_1(self, button: QPushButton):
        """Handle menu option 1."""
        button.clicked.connect(lambda: self.start_workflow("create_from_scratch"))

    def on_menu_option_2(self, button: QPushButton):
        """Handle menu option 2."""
        button.clicked.connect(lambda: self.start_workflow("resume_measurement"))

    def on_menu_option_3(self, button: QPushButton):
        """Handle menu option 3."""
        button.clicked.connect(lambda: self.start_workflow("read_from_scratch"))

    def on_menu_option_4(self, button: QPushButton):
        """Handle menu option 4."""
        button.clicked.connect(lambda: self.start_workflow("profile_from_measurement"))

    def on_menu_option_5(self, button: QPushButton):
        """Handle menu option 5."""
        button.clicked.connect(lambda: self.start_workflow("sanity_check"))

    def on_menu_option_6(self, button: QPushButton):
        """Handle menu option 6."""
        def on_clicked():
            self.log.writeln("")
            self.log.writeln("=== Selected: Change Setup Parameters ===")
            self.log.writeln("")
            self.show_setup_parameters()
        button.clicked.connect(on_clicked)

    def on_menu_option_7(self, button: QPushButton):
        """Handle menu option 7."""
        def on_clicked():
            self.log.writeln("")
            self.log.writeln("=== Selected: Show Tips on How to Improve Accuracy ===")
            self.log.writeln("")
            self.show_improving_accuracy()
        button.clicked.connect(on_clicked)

    def on_menu_option_8(self, button: QPushButton):
        """Handle menu option 8."""
        def on_clicked():
            self.log.writeln("")
            self.log.writeln("=== Selected: Show Delta E2000 Color Accuracy - Quick Reference ===")
            self.log.writeln("")
            self.show_de_reference()
        button.clicked.connect(on_clicked)

    def start_workflow(self, workflow_type: str):
        """Start a workflow."""
        self.log.writeln("")
        self.log.writeln(f"=== Starting workflow: {workflow_type} ===")
        self.log.writeln("")

        self.workflow_type = workflow_type

        # Show workflow title and progress section for workflows 1-5
        self.workflow_title_label.setVisible(True)
        self.workflow_title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #0066cc;")
        self.progress_section.setVisible(True)  # Show progress section (now outside content group box)
        self.nav_section.setVisible(True)  # Show navigation buttons in workflow
        self.information_panel.setVisible(True)  # Show information panel in workflow

        # Clear information panel when starting workflow (remove main menu text)
        self.update_information_panel("Ready")

        if workflow_type == "create_from_scratch":
            self.workflow_title_label.setText("Create Target Chart and Printer Profile from Scratch")
            steps = [
                "Specify Profile Name",
                "Select Instrument",
                "Generate Target",
                "Measure Target",
                "Create Profile",
                "Install Profile",
            ]
            self.update_progress(steps, 0)
            self.show_specify_profile_name()

        elif workflow_type == "resume_measurement":
            self.workflow_title_label.setText("Resume or Re-read Existing Target Chart Measurement and Create Printer Profile")
            steps = [
                "Select .ti3 File",
                "Measure Target",
                "Create Profile",
                "Install Profile",
            ]
            self.update_progress(steps, 0)
            self.show_select_ti3_file()

        elif workflow_type == "read_from_scratch":
            self.workflow_title_label.setText("Read Existing Target Chart from Scratch and Create Printer Profile")
            steps = [
                "Select .ti2 File",
                "Measure Target",
                "Create Profile",
                "Install Profile",
            ]
            self.update_progress(steps, 0)
            self.show_select_ti2_file()

        elif workflow_type == "profile_from_measurement":
            self.workflow_title_label.setText("Create Printer Profile from Existing Measurement File")
            steps = [
                "Select .ti3 File",
                "Create Profile",
                "Install Profile",
            ]
            self.update_progress(steps, 0)
            self.show_select_ti3_file()

        elif workflow_type == "sanity_check":
            self.workflow_title_label.setText("Perform Sanity Check on Existing Profile")
            steps = [
                "Select .ti3 File",
                "Perform Sanity Check",
            ]
            self.update_progress(steps, 0)
            self.show_select_ti3_file()

    def show_specify_profile_name(self):
        """Show profile name specification page."""
        self.current_page = "specify_name"
        self.back_button.setEnabled(False)  # Disable back button in first step
        self.abort_button.setVisible(True)
        self.abort_button.setEnabled(True)
        self.next_button.setEnabled(False)

        # Set step header (outside content group box)
        self.step_header_label.setText("Specify Profile Description / File Name")
        self.step_header_label.setVisible(True)

        widget = QWidget()
        layout = QVBoxLayout()

        info_group = QGroupBox("Recommended Information")
        info_layout = QVBoxLayout()
        info_title = QLabel("The following is highly recommended to include:")
        info_title.setWordWrap(True)
        info_layout.addWidget(info_title)
        info_layout.addWidget(QLabel("  - Printer ID"))
        info_layout.addWidget(QLabel("  - Paper ID (Manufacturer, Product ID, Substrate Type)"))
        info_layout.addWidget(QLabel("  - Color Space"))
        info_layout.addWidget(QLabel("  - Target used for profile"))
        info_layout.addWidget(QLabel("  - Instrument/calibration type used"))
        info_layout.addWidget(QLabel("  - Date created"))
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        layout.addSpacing(20)

        # Example naming
        example_group = QGroupBox("Example File Naming Convention (select and copy)")
        example_layout = QVBoxLayout()
        example_text = self.cfg.get("EXAMPLE_FILE_NAMING", "Printer-Model-PaperType-Resolution-Date")
        example_input = QLineEdit(example_text)
        example_input.setReadOnly(True)
        example_input.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ccc; padding: 5px;")
        example_layout.addWidget(example_input)
        example_group.setLayout(example_layout)
        layout.addWidget(example_group)

        layout.addSpacing(20)

        # Description text moved below example group
        desc_text = QLabel("For simplicity, profile description and filename are made identical.\nThe profile description is what you will see in Photoshop and ColorSync Utility.")
        desc_text.setWordWrap(True)
        layout.addWidget(desc_text)

        layout.addSpacing(20)

        # Filename instruction text
        filename_instruction = QLabel("Enter a desired filename for this profile.\nIf your filename is foobar, your profile will be named foobar with extension .icc or .icm.")
        filename_instruction.setWordWrap(True)
        layout.addWidget(filename_instruction)

        layout.addSpacing(20)

        # Name input
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Profile Name:"))
        self.name_input = QLineEdit()
        self.name_input.textChanged.connect(self.on_name_changed)
        # Restore previously entered name if navigating back
        if self.state.profile_name_entered and self.state.name:
            self.name_input.setText(self.state.name)
            self.enable_and_focus_next_button()
        input_layout.addWidget(self.name_input)
        layout.addLayout(input_layout)

        validation_label = QLabel("Valid values: Letters A-Z a-z, digits 0-9, dash -, underscore _, parentheses ( ), dot .")
        validation_label.setStyleSheet("color: gray; font-size: 11px; font-style: italic;")
        layout.addWidget(validation_label)

        layout.addStretch()
        widget.setLayout(layout)
        self.set_content_widget(widget)

    def on_name_changed(self, text: str):
        """Handle name input change."""
        if not text:
            self.next_button.setEnabled(False)
            self.next_button.setStyleSheet("")  # Reset style
            self.state.name = ""
            return

        # Validate name
        if not re.fullmatch(r"[A-Za-z0-9._()\-]+", text):
            self.next_button.setEnabled(False)
            self.next_button.setStyleSheet("")  # Reset style
            self.state.name = ""
        else:
            self.enable_next_button()  # Don't set focus while typing
            self.state.name = text
            self.state.desc = text
            self.state.new_name = text

    def show_select_instrument(self):
        """Show instrument selection page."""
        self.current_page = "select_instrument"
        self.back_button.setEnabled(True)
        self.abort_button.setVisible(True)
        self.abort_button.setEnabled(True)
        self.next_button.setEnabled(False)

        # Set step header (outside content group box)
        self.step_header_label.setText("Specify Spectrophotometer Model")
        self.step_header_label.setVisible(True)

        widget = QWidget()
        layout = QVBoxLayout()

        info = QLabel("This affects how the target chart is generated.")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(20)

        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout()
        note1 = QLabel("  - A menu of target chart options will be presented next step.")
        note1.setWordWrap(True)
        notes_layout.addWidget(note1)
        note2 = QLabel("  - Option '3: ColorMunki' has a separate configurable menu from the rest.")
        note2.setWordWrap(True)
        notes_layout.addWidget(note2)
        note3 = QLabel("  - The menu option and command arguments for targen and printtarg may be edited in .ini file.")
        note3.setWordWrap(True)
        notes_layout.addWidget(note3)
        notes_group.setLayout(notes_layout)
        layout.addWidget(notes_group)

        layout.addSpacing(20)

        # Instrument selection
        instrument_group = QGroupBox("Available Instruments")
        instrument_layout = QVBoxLayout()

        instruments = [
            ("1: i1Pro", "-ii1", "i1Pro"),
            ("2: i1Pro3+", "-i3p", "i1Pro3+"),
            ("3: ColorMunki", "-iCM -h", "ColorMunki"),
            ("4: DTP20", "-i20", "DTP20"),
            ("5: DTP22", "-i22", "DTP22"),
            ("6: DTP41", "-i41", "DTP41"),
            ("7: DTP51", "-i51", "DTP51"),
            ("8: SpectroScan", "-iSS", "SpectroScan"),
        ]

        for text, arg, name in instruments:
            radio = QRadioButton(text)
            radio.setProperty("inst_arg", arg)
            radio.setProperty("inst_name", name)
            instrument_layout.addWidget(radio)

        instrument_group.setLayout(instrument_layout)
        layout.addWidget(instrument_group)

        # Enable next button when instrument is selected
        self.instrument_group = QButtonGroup()
        for i in range(instrument_layout.count()):
            child = instrument_layout.itemAt(i).widget()
            if isinstance(child, QRadioButton):
                self.instrument_group.addButton(child)
                child.toggled.connect(self.on_instrument_selected)

        # Restore previously selected instrument if navigating back
        if self.state.instrument_selected and self.state.inst_arg:
            for i in range(instrument_layout.count()):
                child = instrument_layout.itemAt(i).widget()
                if isinstance(child, QRadioButton):
                    if child.property("inst_arg") == self.state.inst_arg:
                        child.setChecked(True)
                        self.log.writeln(f"Restored instrument selection: {self.state.inst_name}")
                        self.enable_and_focus_next_button()
                        break

        layout.addStretch()
        widget.setLayout(layout)
        self.set_content_widget(widget)

    def on_instrument_selected(self, checked: bool):
        """Handle instrument selection."""
        if checked:
            # Get the selected radio button
            selected_btn = self.instrument_group.checkedButton()
            if selected_btn:
                # Save instrument selection to state
                self.state.inst_arg = selected_btn.property("inst_arg")
                self.state.inst_name = selected_btn.property("inst_name")
                self.state.instrument_selected = True  # Mark instrument as selected
                self.log.writeln(f"Selected instrument: {self.state.inst_name}")
                self.enable_and_focus_next_button()

    def show_generate_target(self):
        """Show target size selection page."""
        self.current_page = "generate_target"
        self.back_button.setEnabled(True)
        self.abort_button.setVisible(True)
        self.abort_button.setEnabled(True)
        self.next_button.setEnabled(False)

        # Set step header (outside content group box)
        self.step_header_label.setText("Select the target size")
        self.step_header_label.setVisible(True)

        widget = QWidget()
        layout = QVBoxLayout()

        # Display common settings
        info_group = QGroupBox("Common settings for targen defined in setup file:")
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel(f"      - Arguments set: {self.cfg.get('COMMON_ARGUMENTS_TARGEN', '')}"))
        info_layout.addWidget(QLabel(f"      - Ink limit -l: {self.cfg.get('INK_LIMIT', '')}"))
        info_layout.addWidget(QLabel("      - Pre-conditioning profile specified -c:"))
        info_layout.addWidget(QLabel(f"        '{self.cfg.get('PRECONDITIONING_PROFILE_PATH', '')}'"))
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Display printtarg settings
        printtarg_group = QGroupBox("Common settings for printtarg defined in setup file:")
        printtarg_layout = QVBoxLayout()
        printtarg_layout.addWidget(QLabel(f"      - Arguments set: {self.cfg.get('COMMON_ARGUMENTS_PRINTTARG', '')}"))
        printtarg_layout.addWidget(QLabel(f"      - Paper size -p: {self.cfg.get('PAPER_SIZE', '')}, Target resolution -T: {self.cfg.get('TARGET_RESOLUTION', '')} dpi"))
        printtarg_group.setLayout(printtarg_layout)
        layout.addWidget(printtarg_group)

        layout.addSpacing(20)

        # Display instrument-specific menu with integrated radio buttons
        paper_size = self.cfg.get("PAPER_SIZE", "A4")
        inst_name = self.state.inst_name
        self.target_selection_group = QButtonGroup()

        if inst_name == "ColorMunki" and paper_size in {"A4", "Letter"}:
            menu_group = QGroupBox(f"Below menu choices have been optimized for page size {paper_size} and {inst_name} instrument.")
            menu_layout = QVBoxLayout()
            for i in range(1, 7):
                pc = self.cfg.get(f"INST_CM_MENU_OPTION{i}_PATCH_COUNT_{paper_size.upper()}_f", "")
                desc = self.cfg.get(f"INST_CM_MENU_OPTION{i}_{paper_size.upper()}_DESCRIPTION", "")
                radio = QRadioButton(f"{i}: {pc} patches {desc}")
                radio.setProperty("option", str(i))
                self.target_selection_group.addButton(radio)
                menu_layout.addWidget(radio)
            menu_group.setLayout(menu_layout)
            layout.addWidget(menu_group)
        else:
            menu_group = QGroupBox("Number of created pages increase with patch count, depending on settings.")
            menu_layout = QVBoxLayout()
            for i in range(1, 7):
                pc = self.cfg.get(f"INST_OTHER_MENU_OPTION{i}_PATCH_COUNT_f", "")
                desc = self.cfg.get(f"INST_OTHER_MENU_OPTION{i}_DESCRIPTION", "")
                radio = QRadioButton(f"{i}: {pc} patches {desc}")
                radio.setProperty("option", str(i))
                self.target_selection_group.addButton(radio)
                menu_layout.addWidget(radio)
            menu_group.setLayout(menu_layout)
            layout.addWidget(menu_group)

        layout.addSpacing(20)

        # Restore previously selected target option if navigating back
        if self.state.target_option_selected:
            for button in self.target_selection_group.buttons():
                if button.property("option") == self.state.target_option_selected:
                    button.setChecked(True)
                    self.log.writeln(f"Restored target selection: option {self.state.target_option_selected}")
                    break

        # Generate button
        generate_btn = QPushButton("Generate Target Chart")
        generate_btn.clicked.connect(self.on_generate_target)
        layout.addWidget(generate_btn)

        layout.addSpacing(20)

        # Check if target was already generated
        if self.state.target_generated:
            # Update information panel with all information
            self.update_information_panel(f"Target already generated:\n{self.state.target_file_path}\n\nYou can:\n  - Press Next to continue with existing target\n  - Or select a target size and regenerate if desired", "green")
            self.enable_and_focus_next_button()  # Allow moving to next step without regenerating
        else:
            # Update information panel
            self.update_information_panel("Ready to generate target...\n\nSelect a target size and click 'Generate Target Chart' to begin.")

        layout.addStretch()
        widget.setLayout(layout)
        self.set_content_widget(widget)

        # Connect radio button selection to enable next button
        self.target_selection_group.buttonClicked.connect(self.on_target_selected)

    def on_target_selected(self, button: QRadioButton):
        """Handle target size selection."""
        self.selected_target_option = button.property("option")
        self.state.target_option_selected = self.selected_target_option  # Save to state

    def on_generate_target(self):
        """Handle target generation."""
        # Get selected target option
        if not hasattr(self, 'selected_target_option'):
            self.log.writeln("Error: No target option selected")
            return

        option = int(self.selected_target_option)
        if option < 1 or option > 6:
            self.log.writeln("Error: Invalid target option")
            return

        # Get target selection parameters
        selection = self._get_target_selection(option)
        if not selection:
            self.log.writeln("Error: Failed to get target selection parameters")
            return

        self.log.writeln(f"Selected target: {selection['label']} - {selection['patch_count']} patches")
        self.log.writeln("")

        # Update information panel
        self.update_information_panel(f"Generating target...\n\n{selection['label']}\n{selection['patch_count']} patches", "blue")

        name = self.state.name

        # Create profile folder
        created_profiles_folder = self.cfg.get("CREATED_PROFILES_FOLDER", "Created_Profiles")
        profile_folder = self.state.script_dir / created_profiles_folder / name

        try:
            profile_folder.mkdir(parents=True, exist_ok=True)
            self.state.profile_folder = str(profile_folder)
            self.state.name = name
            self.state.desc = name

            os.chdir(profile_folder)

            self.log.writeln(f"Working folder: {profile_folder}")
            self.log.writeln("")

        except Exception as e:
            self.log.writeln(f"Error creating profile folder: {e}")
            self.update_information_panel(f"Error: {e}", "red")
            return

        # Run targen command
        self.target_selection = selection  # Store selection for use in printtarg
        self.run_targen_command(selection)

    def _get_target_selection(self, option: int) -> dict[str, str]:
        """Get target selection parameters based on option."""
        paper_size = self.cfg.get("PAPER_SIZE", "A4")
        inst_name = self.state.inst_name

        if inst_name == "ColorMunki" and paper_size in {"A4", "Letter"}:
            patch_key = f"INST_CM_MENU_OPTION{option}_PATCH_COUNT_{paper_size.upper()}_f"
            patch_count = self.cfg.get(patch_key, "")
            selection = {
                "label": {1: "Small", 2: "Medium (default)", 3: "Large", 4: "XL", 5: "XXL", 6: "XXXL"}[option],
                "patch_count": patch_count,
                "white_patches": self.cfg.get(f"INST_CM_MENU_OPTION{option}_WHITE_PATCHES_e", ""),
                "black_patches": self.cfg.get(f"INST_CM_MENU_OPTION{option}_BLACK_PATCHES_B", ""),
                "gray_steps": self.cfg.get(f"INST_CM_MENU_OPTION{option}_GRAY_STEPS_g", ""),
                "multi_cube_steps": self.cfg.get(f"INST_CM_MENU_OPTION{option}_MULTI_CUBE_STEPS_m", ""),
                "multi_cube_surface_steps": self.cfg.get(f"INST_CM_MENU_OPTION{option}_MULTI_CUBE_SURFACE_STEPS_M", ""),
                "scale_patch_and_spacer": self.cfg.get(f"INST_CM_MENU_OPTION{option}_SCALE_PATCH_AND_SPACER_a", ""),
                "scale_spacer": self.cfg.get(f"INST_CM_MENU_OPTION{option}_SCALE_SPACER_A", ""),
                "layout_seed": self.cfg.get(f"INST_CM_MENU_OPTION{option}_LAYOUT_SEED_R", ""),
            }
        else:
            selection = {
                "label": {1: "Small", 2: "Medium (default)", 3: "Large", 4: "XL", 5: "XXL", 6: "XXXL"}[option],
                "patch_count": self.cfg.get(f"INST_OTHER_MENU_OPTION{option}_PATCH_COUNT_f", ""),
                "white_patches": self.cfg.get(f"INST_OTHER_MENU_OPTION{option}_WHITE_PATCHES_e", ""),
                "black_patches": self.cfg.get(f"INST_OTHER_MENU_OPTION{option}_BLACK_PATCHES_B", ""),
                "gray_steps": self.cfg.get(f"INST_OTHER_MENU_OPTION{option}_GRAY_STEPS_g", ""),
                "multi_cube_steps": self.cfg.get(f"INST_OTHER_MENU_OPTION{option}_MULTI_CUBE_STEPS_m", ""),
                "multi_cube_surface_steps": self.cfg.get(f"INST_OTHER_MENU_OPTION{option}_MULTI_CUBE_SURFACE_STEPS_M", ""),
                "scale_patch_and_spacer": self.cfg.get(f"INST_OTHER_MENU_OPTION{option}_SCALE_PATCH_AND_SPACER_a", ""),
                "scale_spacer": self.cfg.get(f"INST_OTHER_MENU_OPTION{option}_SCALE_SPACER_A", ""),
                "layout_seed": self.cfg.get(f"INST_CM_MENU_OPTION{option}_LAYOUT_SEED_R", ""),
            }

        return selection

    def run_targen_command(self, selection: dict[str, str]):
        """Run targen command to generate target."""
        name = self.state.name

        # Build targen command exactly like CLI
        args = ["targen"]

        # Add common arguments from config
        common_args = self.cfg.get("COMMON_ARGUMENTS_TARGEN", "")
        if common_args:
            args.extend(self._split_cfg_args(common_args))

        # Add ink limit if specified
        ink_limit = self.cfg.get("INK_LIMIT", "")
        if ink_limit:
            args.append(f"-l{ink_limit}")

        # Add target parameters from selection
        if selection.get("white_patches"):
            args.append(f"-e{selection['white_patches']}")
        if selection.get("black_patches"):
            args.append(f"-B{selection['black_patches']}")
        if selection.get("gray_steps"):
            args.append(f"-g{selection['gray_steps']}")
        if selection.get("multi_cube_steps"):
            args.append(f"-m{selection['multi_cube_steps']}")
        if selection.get("multi_cube_surface_steps"):
            args.append(f"-M{selection['multi_cube_surface_steps']}")
        if selection.get("patch_count"):
            args.append(f"-f{selection['patch_count']}")

        # Add pre-conditioning profile if specified
        precon_profile = self.cfg.get("PRECONDITIONING_PROFILE_PATH", "")
        if precon_profile:
            p = Path(precon_profile).expanduser()
            if p.is_file():
                args.extend(["-c", str(p.resolve())])
            else:
                self.log.writeln(f"Warning: Pre-conditioning profile not found: '{precon_profile}'")
                self.log.writeln("Skipping pre-conditioning profile in targen.")

        # Add output file name WITHOUT extension
        args.append(name)

        # Run command in thread
        self.update_information_panel("Running targen command...\n\nGenerating target color values (.ti1 file)...", "blue")
        self.log.writeln("Generating target color values (.ti1 file)...")
        self.log.writeln("")

        self.command_thread = CommandThread(args, cwd=Path(self.state.profile_folder))
        self.command_thread.output_signal.connect(self.log.write)
        self.command_thread.finished_signal.connect(self.on_targen_finished)
        self.command_thread.error_signal.connect(self.on_command_error)
        self.command_thread.start()

    def _split_cfg_args(self, args_str: str) -> list[str]:
        """Split configuration arguments string into list."""
        if not args_str:
            return []
        # Split on whitespace, handling quoted strings
        import shlex
        try:
            return shlex.split(args_str)
        except ValueError:
            # Fallback to simple split if shlex fails
            return args_str.split()

    def on_targen_finished(self, exit_code: int):
        """Handle targen completion."""
        if exit_code != 0:
            self.update_information_panel(f"targen failed with exit code {exit_code}", "red")
            return

        self.update_information_panel("targen completed successfully\n\nRunning printtarg command...", "blue")
        self.log.writeln("")
        self.log.writeln("targen completed successfully")
        self.log.writeln("")

        # Run printtarg command
        self.run_printtarg_command(self.target_selection)

    def run_printtarg_command(self, selection: dict[str, str]):
        """Run printtarg command to create TIFF."""
        name = self.state.name

        # Build printtarg command exactly like CLI
        args = ["printtarg"]

        # Add common arguments from config
        common_args = self.cfg.get("COMMON_ARGUMENTS_PRINTTARG", "")
        if common_args:
            args.extend(self._split_cfg_args(common_args))

        # Add instrument arguments
        args.extend(self._split_cfg_args(self.state.inst_arg))

        # Add layout seed if specified
        if self.cfg.get("USE_LAYOUT_SEED_FOR_TARGET", "").lower() == "true":
            layout_seed = selection.get("layout_seed", "")
            if layout_seed:
                args.append(f"-R{layout_seed}")

        # Add resolution
        resolution = self.cfg.get("TARGET_RESOLUTION", "")
        if resolution:
            args.append(f"-T{resolution}")

        # Add paper size
        paper_size = self.cfg.get("PAPER_SIZE", "")
        if paper_size:
            args.append(f"-p{paper_size}")

        # Add scale parameters from selection
        if selection.get("scale_patch_and_spacer"):
            args.append(f"-a{selection['scale_patch_and_spacer']}")
        if selection.get("scale_spacer"):
            args.append(f"-A{selection['scale_spacer']}")

        # Add input file name WITHOUT extension
        args.append(name)

        # Run command in thread
        self.update_information_panel("Running printtarg command...\n\nGenerating target(s) (.tif image(s) and .ti2 file)...", "blue")
        self.log.writeln("Generating target(s) (.tif image(s) and .ti2 file)...")
        self.log.writeln("")

        self.command_thread = CommandThread(args, cwd=Path(self.state.profile_folder))
        self.command_thread.output_signal.connect(self.log.write)
        self.command_thread.finished_signal.connect(self.on_printtarg_finished)
        self.command_thread.error_signal.connect(self.on_command_error)
        self.command_thread.start()

    def on_printtarg_finished(self, exit_code: int):
        """Handle printtarg completion."""
        if exit_code != 0:
            self.update_information_panel(f"printtarg failed with exit code {exit_code}", "red")
            return

        # Detect generated TIFFs (current working dir)
        profile_folder = Path(self.state.profile_folder)
        tif_files = _collect_matching_tifs(profile_folder, self.state.name)
        if not tif_files:
            self.log.writeln("No TIFF files were created by printtarg.")
            self.update_information_panel("Error: No TIFF files were created by printtarg.", "red")
            return
        self.state.tif_files = tif_files

        # Mark target as generated and store file path
        self.state.target_generated = True
        self.state.target_file_path = str(profile_folder / f"{self.state.name}.ti1")

        self.log.writeln("")
        self.log.writeln("Target generation completed successfully")
        self.log.writeln("")

        self.log.writeln("Test chart(s) created:")
        self.log.writeln("")
        for f in self.state.tif_files:
            self.log.writeln(f"  {f.name}")
        self.log.writeln("")

        # Update information panel
        tif_list = "\n".join([f"  {f.name}" for f in self.state.tif_files])
        self.update_information_panel(f"Target generation completed successfully!\n\nTest chart(s) created:\n{tif_list}\n\nPlease print the test chart(s) and make sure to disable color management.\n\nPress Next to continue with measuring of target...", "green")
        self.enable_and_focus_next_button()

        # Auto-open images on macOS if configured
        if self.state.PLATFORM == "macos" and self.cfg.get("ENABLE_AUTO_OPEN_IMAGES_WITH_COLOR_SYNC_MAC", "").lower() == "true":
            self.log.writeln("Please print the test chart(s) and make sure to disable color management.")
            self.log.writeln("Created Images will open automatically in ColorSync Utility.")
            self.log.writeln('In the Printer dialog set option "Colour" to "Print as Color Target".')
            app = self.cfg.get("COLOR_SYNC_UTILITY_PATH", "")
            if app:
                open_cmd = ["open", "-a", app, *[str(p) for p in self.state.tif_files]]
                self.command_thread = CommandThread(open_cmd, cwd=Path.cwd())
                self.command_thread.output_signal.connect(self.log.write)
                self.command_thread.start()
        else:
            self.log.writeln("Please print the test chart(s) and make sure to disable color management.")
            if self.state.PLATFORM == "macos":
                self.log.writeln("Use applications like ColorSync Utility, Adobe Color Print Utility or")
                self.log.writeln("Photoshop etc.")
            else:
                self.log.writeln("Use applications like Adobe Color Print Utility.")

        self.log.writeln("")
        self.log.writeln("After target(s) have been printed press Next to continuing with measuring of target...")
        self.log.writeln("")
        self.enable_and_focus_next_button()

    def on_command_error(self, error: str):
        """Handle command error."""
        # Close sanity file handle if open
        if hasattr(self, 'sanity_file_handle') and self.sanity_file_handle:
            self.sanity_file_handle.close()
            self.sanity_file_handle = None

        self.log.writeln("")
        self.log.writeln(f"Error: {error}")
        self.log.writeln("")

    def show_measure_target(self):
        """Show target measurement page."""
        self.current_page = "measure_target"
        self.back_button.setEnabled(True)
        self.abort_button.setVisible(True)
        self.abort_button.setEnabled(True)
        self.next_button.setEnabled(False)

        # Set step header (outside content group box)
        self.step_header_label.setText("Measure Target Chart")
        self.step_header_label.setVisible(True)

        widget = QWidget()
        layout = QVBoxLayout()

        # Connection confirmation
        info = QLabel("Please connect the spectrophotometer.")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(20)

        # Tips section
        tips_group = QGroupBox("Tips:")
        tips_layout = QVBoxLayout()
        tip1 = QLabel("     - Default for reading targets using ArgyllCMS is to start from column A, from the side where the column letters are, and then read to the end of the other side of the page. If not done this way, \"unexpected high deviation\" message may appear frequently.")
        tip1.setWordWrap(True)
        tips_layout.addWidget(tip1)
        tip2 = QLabel("     - Enabling bi-directional strip reading (removing -B flag and adding -b) may cause false indentification of strips when read, thus it is recommended to not enable this feature for beginners.")
        tip2.setWordWrap(True)
        tips_layout.addWidget(tip2)
        tip3 = QLabel("     - Scanning speed of more than 7 sec per strip reduces frequent re-reading due to inconsistent results, and increases quality.")
        tip3.setWordWrap(True)
        tips_layout.addWidget(tip3)
        tip4 = QLabel("     - If frequent inconsistent results try altering patch consistency tolerance parameter in setup menu (or .ini file).")
        tip4.setWordWrap(True)
        tips_layout.addWidget(tip4)
        tip5 = QLabel("     - Save progress once in a while with 'd' and then resume measuring with option 2 of main menu.")
        tip5.setWordWrap(True)
        tips_layout.addWidget(tip5)
        tips_group.setLayout(tips_layout)
        layout.addWidget(tips_group)

        layout.addSpacing(20)

        # Check if measurement was already completed
        if self.state.measurement_completed:
            # Update information panel with all information
            self.update_information_panel(f"Measurement already completed:\n{self.state.measurement_file_path}\n\nYou can:\n  - Press Next to continue with existing measurement\n  - Or start measurement again if desired", "green")
            self.enable_and_focus_next_button()  # Allow moving to next step without remeasuring
        else:
            # Update information panel
            self.update_information_panel("Ready to measure target...\n\nClick 'Start Measurement' to begin reading the printed target chart.\n\nThen follow instructions in 'Terminal Output' window.")

        # Measure button
        measure_btn = QPushButton("Start Measurement")
        measure_btn.clicked.connect(self.on_start_measurement)
        layout.addWidget(measure_btn)

        layout.addStretch()
        widget.setLayout(layout)
        self.set_content_widget(widget)

    def on_start_measurement(self):
        """Handle target measurement."""
        self.update_information_panel("Measuring target chart...\n\nStarting chart reading (read .ti2 file and generate .ti3 file)...", "blue")

        self.log.writeln("")
        self.log.writeln("Starting chart reading (read .ti2 file and generate .ti3 file)...")
        self.log.writeln("")

        name = self.state.name

        # Store mtime before chartread for all workflows that run chartread
        # This is needed to detect if chartread actually modified the file
        if self.workflow_type in {"create_from_scratch", "resume_measurement", "read_from_scratch"}:
            ti3_file = Path(self.state.profile_folder) / f"{name}.ti3"
            if ti3_file.exists():
                self.state.ti3_mtime_before = file_mtime(ti3_file)
            else:
                self.state.ti3_mtime_before = ""

        # Run chartread command
        self.run_chartread_command()

    def run_chartread_command(self):
        """Run chartread command to measure target."""
        name = self.state.name

        # Build chartread command exactly like CLI
        args = ["chartread"]

        # Add common arguments from config
        common_args = self.cfg.get("COMMON_ARGUMENTS_CHARTREAD", "")
        if common_args:
            args.extend(self._split_cfg_args(common_args))

        # Handle resume mode (action 2)
        if self.workflow_type == "resume_measurement":
            args.append("-r")

        # Add strip tolerance if specified
        strip_tol = self.cfg.get("STRIP_PATCH_CONSISTENSY_TOLERANCE", "")
        if strip_tol:
            args.append(f"-T{strip_tol}")

        # Add input file name WITHOUT extension
        args.append(name)

        # Run command in thread
        self.update_information_panel("Running chartread command...\n\nReading .ti2 file and generating .ti3 file...", "blue")
        self.log.writeln("")

        self.command_thread = CommandThread(args, cwd=Path(self.state.profile_folder))
        self.command_thread.output_signal.connect(self.log.write)
        self.command_thread.finished_signal.connect(self.on_chartread_finished)
        self.command_thread.error_signal.connect(self.on_command_error)
        self.command_thread.start()

    def on_chartread_finished(self, exit_code: int):
        """Handle chartread completion."""
        if exit_code != 0:
            self.update_information_panel(f"chartread failed with exit code {exit_code}", "red")
            self.log.writeln("")
            self.log.writeln("Chartread aborted by user.")
            self.log.writeln("")
            return

        # Verify .ti3 file was created or modified (matching original code logic)
        ti3_file = Path(self.state.profile_folder) / f"{self.state.name}.ti3"

        # For all workflows that run chartread, check if file was modified
        if self.workflow_type in {"create_from_scratch", "resume_measurement", "read_from_scratch"}:
            if self.state.ti3_mtime_before:
                # File existed before, check if it was modified
                ti3_mtime_after = file_mtime(ti3_file)
                if ti3_mtime_after == self.state.ti3_mtime_before:
                    # File was not modified - chartread failed
                    self.update_information_panel("chartread failed - no measurements stored in .ti3", "red")
                    self.log.writeln("")
                    self.log.writeln("chartread failed - no measurements stored in .ti3")
                    self.log.writeln("")
                    return
            else:
                # File didn't exist before, check if it exists now
                if not ti3_file.exists():
                    self.update_information_panel("chartread failed - .ti3 file not created", "red")
                    self.log.writeln("")
                    self.log.writeln("chartread failed - .ti3 file not created")
                    self.log.writeln("")
                    return

        self.update_information_panel(f"Measurement completed successfully!\n\nMeasurement file:\n{ti3_file}\n\nPress Next to continue with creating profile...", "green")
        self.log.writeln("")
        self.log.writeln("Chart reading completed successfully")
        self.log.writeln("")

        # Mark measurement as completed and store file path
        self.state.measurement_completed = True
        self.state.measurement_file_path = str(ti3_file)

        # Enable Next button to proceed to Create Profile step
        self.enable_and_focus_next_button()

    def run_colprof_command(self):
        """Run colprof command to create ICC/ICM profile."""
        name = self.state.name

        # Build colprof command exactly like CLI
        args = ["colprof"]

        # Add common arguments from config
        common_args = self.cfg.get("COMMON_ARGUMENTS_COLPROF", "")
        if common_args:
            args.extend(self._split_cfg_args(common_args))

        # Add ink limit if specified
        ink_limit = self.cfg.get("INK_LIMIT", "")
        if ink_limit:
            args.append(f"-l{ink_limit}")

        # Add profile smoothing
        profile_smoothing = self.cfg.get("PROFILE_SMOOTHING", "")
        if profile_smoothing:
            args.append(f"-r{profile_smoothing}")

        # Add color space profile
        icc_profile = self.cfg.get("PRINTER_ICC_PATH", "")
        if icc_profile:
            p = Path(icc_profile).expanduser()
            if p.is_file():
                args.extend(["-S", str(p.resolve())])
            else:
                self.log.writeln(f"Warning: Color space profile not found: '{icc_profile}'")
                self.log.writeln("Skipping color space profile in colprof.")

        # Add device link profile
        args.append("-D")

        # Add input file name WITHOUT extension
        args.append(name)

        # Run command in thread
        self.update_information_panel("Running colprof command...\n\nCreating ICC/ICM profile...", "blue")
        self.log.writeln("Creating ICC/ICM profile...")
        self.log.writeln("")

        self.command_thread = CommandThread(args, cwd=Path(self.state.profile_folder))
        self.command_thread.output_signal.connect(self.log.write)
        self.command_thread.finished_signal.connect(self.on_colprof_finished)
        self.command_thread.error_signal.connect(self.on_command_error)
        self.command_thread.start()

    def on_colprof_finished(self, exit_code: int):
        """Handle colprof completion."""
        if exit_code != 0:
            self.update_information_panel(f"colprof failed with exit code {exit_code}", "red")
            return

        # Determine profile extension
        icc_file = Path(self.state.profile_folder) / f"{self.state.name}.icc"
        icm_file = Path(self.state.profile_folder) / f"{self.state.name}.icm"

        if icc_file.exists():
            self.state.profile_extension = "icc"
            self.state.new_icc_path = str(icc_file)
        elif icm_file.exists():
            self.state.profile_extension = "icm"
            self.state.new_icc_path = str(icm_file)
        else:
            self.update_information_panel("colprof failed - profile file not created", "red")
            return

        self.update_information_panel(f"Profile creation completed successfully!\n\nProfile file:\n{self.state.new_icc_path}\n\nPress Next to continue with installing profile...", "green")
        self.log.writeln("")
        self.log.writeln("Profile creation completed successfully")
        self.log.writeln("")

        # Mark profile as created
        self.state.profile_created = True

        self.enable_and_focus_next_button()

    def show_create_profile(self):
        """Show profile creation page."""
        self.current_page = "create_profile"
        self.back_button.setEnabled(True)
        self.abort_button.setVisible(True)
        self.abort_button.setEnabled(True)
        self.next_button.setEnabled(False)

        # Set step header (outside content group box)
        self.step_header_label.setText("Create ICC/ICM Profile")
        self.step_header_label.setVisible(True)

        widget = QWidget()
        layout = QVBoxLayout()

        info = QLabel("The printer ICC/ICM profile will be created from the measured data.")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(20)

        # Check if profile was already created
        if self.state.profile_created and self.state.new_icc_path:
            # Update information panel with all information
            self.update_information_panel(f"Profile already created:\n{self.state.new_icc_path}\n\nYou can:\n  - Press Next to continue with existing profile\n  - Or recreate profile if desired (will overwrite existing)", "green")
            self.enable_and_focus_next_button()  # Allow moving to next step without recreating

            # Install button (only shown when profile already created)
            install_btn = QPushButton("Install Profile")
            install_btn.clicked.connect(self.on_install_profile)
            layout.addWidget(install_btn)
        else:
            # Update information panel
            self.update_information_panel("Ready to create profile...\n\nClick 'Create Profile' to create the ICC/ICM profile from the measured data.")

            # Create Profile button
            create_btn = QPushButton("Create Profile")
            create_btn.clicked.connect(self.run_colprof_command)
            layout.addWidget(create_btn)

        layout.addStretch()
        widget.setLayout(layout)
        self.set_content_widget(widget)

    def on_install_profile(self):
        """Handle profile installation."""
        self.update_information_panel("Installing profile...\n\nInstalling measured ICC/ICM profile to system profile folder...", "blue")

        self.log.writeln("")
        self.log.writeln("Installing measured ICC/ICM profile...")
        self.log.writeln("")

        # Run profile installation
        self.install_profile_to_system()

    def install_profile_to_system(self):
        """Install profile to system profile folder."""
        profile_file = Path(f"{self.state.name}.{self.state.profile_extension}")

        if not profile_file.is_file():
            self.log.writeln("")
            self.log.writeln(f"ICC/ICM profile not found: '{profile_file.name}'")
            self.log.writeln(f"Expected it in the current working directory:")
            self.log.writeln(f"  {Path.cwd()}")
            self.log.writeln("")
            self.update_information_panel("Error: Profile not found", "red")
            return

        # Get destination directory
        dest_dir = self.cfg.get("PRINTER_PROFILES_PATH", "")
        if not dest_dir:
            self.log.writeln("")
            self.log.writeln("Parameter PRINTER_PROFILES_PATH is empty. Check setup .ini file")
            self.log.writeln("")
            self.update_information_panel("Error: PRINTER_PROFILES_PATH empty", "red")
            return

        dest_dir_expanded = os.path.expandvars(dest_dir)
        dest = Path(dest_dir_expanded).expanduser()
        dest_resolved = dest.resolve() if dest.exists() else dest

        # Check if destination directory exists
        if not dest.is_dir():
            self.log.writeln("")
            self.log.writeln(f"Destination directory does not exist: '{dest_dir}'")
            self.log.writeln("Check parameter PRINTER_PROFILES_PATH in the setup .ini file")
            self.log.writeln("")
            self.update_information_panel("Error: Destination directory not found", "red")
            return

        # Check if destination is writable
        if not os.access(dest, os.W_OK):
            self.log.writeln("")
            self.log.writeln(f"Destination directory is not writable: '{dest_dir}'")
            self.log.writeln("Check folder permissions or choose a user-writable profile folder.")

            if self.state.PLATFORM == "linux":
                if dest_dir.startswith("/usr/share/") or dest_dir.startswith("/usr/local/share/"):
                    self.log.writeln("This is a system folder and typically requires administrator rights.")
                    self.log.writeln("Options:")
                    self.log.writeln("  1) Change PRINTER_PROFILES_PATH to a user folder (recommended)")
                    self.log.writeln("     e.g. '$HOME/.local/share/color/icc' (create if missing)")
                    self.log.writeln("  2) Or install to the system folder using sudo (advanced)")
                    self.log.writeln(f"     e.g. sudo cp '{profile_file.name}' '{dest_dir}/'")
            elif self.state.PLATFORM == "macos":
                self.log.writeln("Suggested macOS user profile folder:")
                self.log.writeln("  '$HOME/Library/ColorSync/Profiles'")

            self.log.writeln("")
            self.update_information_panel("Error: Destination not writable", "red")
            return

        # Copy profile to destination
        try:
            shutil.copy2(profile_file, dest / profile_file.name)
        except OSError as e:
            self.log.writeln("")
            self.log.writeln(f"Failed to copy ICC/ICM profile to '{dest_dir}'.")
            self.log.writeln("Check folder permissions or disk access. See log for details.")
            self.log.writeln("")
            self.update_information_panel(f"Error: {e}", "red")
            return

        self.log.writeln(f"Finished. '{profile_file.name}' was installed to the directory '{str(dest_resolved)}'")
        self.log.writeln("Please restart any color-managed applications before using this profile.")
        self.log.writeln(f"To print with this profile in a color-managed workflow, select '{self.state.name}' in the profile selection menu.")

        self.update_information_panel(f"Profile installed successfully!\n\nProfile installed to:\n{str(dest_resolved)}\n\nPlease restart any color-managed applications before using this profile.\n\nPress 'Go Back to Main Menu' to finish.", "green")
        self.log.writeln("")

        # Mark profile as installed
        self.state.profile_installed = True

        # Don't enable Next button - this is the last step

    def show_install_profile(self):
        """Show profile installation page."""
        self.current_page = "install_profile"
        self.back_button.setEnabled(True)
        self.abort_button.setVisible(True)
        self.abort_button.setEnabled(True)
        self.next_button.setEnabled(False)
        self.next_button.setVisible(False)  # Hide Next button (last step)

        # Set step header (outside content group box)
        self.step_header_label.setText("Install ICC/ICM Profile")
        self.step_header_label.setVisible(True)

        widget = QWidget()
        layout = QVBoxLayout()

        info = QLabel("Install the printer ICC/ICM profile to the system profile folder.")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(20)

        # Check if profile was already installed
        if self.state.profile_installed:
            # Update information panel with all information
            self.update_information_panel("Profile already installed.\n\nYou can:\n  - Press 'Go Back to Main Menu' to finish\n  - Or reinstall profile if desired", "green")
        else:
            # Update information panel
            self.update_information_panel("Ready to install profile...\n\nClick 'Install Profile' to install the ICC/ICM profile to the system profile folder.")

        # Install button
        install_btn = QPushButton("Install Profile")
        install_btn.clicked.connect(self.on_install_profile)
        layout.addWidget(install_btn)

        layout.addStretch()
        widget.setLayout(layout)
        self.set_content_widget(widget)

        # This is the last workflow step - disable back button and change abort button
        self.back_button.setEnabled(False)
        self.back_button.setStyleSheet("QPushButton:disabled { color: #808080; }")
        self.abort_button.setText("Go Back to Main Menu")
        self.abort_button.setStyleSheet("background-color: #4CAF50; color: white;")

    def show_sanity_check(self):
        """Show sanity check page."""
        self.current_page = "sanity_check"
        self.back_button.setEnabled(True)
        self.abort_button.setVisible(True)
        self.abort_button.setEnabled(True)
        self.next_button.setEnabled(False)

        # Set step header (outside content group box)
        self.step_header_label.setText("Perform Sanity Check")
        self.step_header_label.setVisible(True)

        widget = QWidget()
        layout = QVBoxLayout()

        info = QLabel("Perform a sanity check on the created profile to verify its accuracy using profcheck command.")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(20)

        # Check if sanity check was already completed
        if self.state.sanity_check_completed:
            # Update information panel with all information
            self.update_information_panel("Sanity check already completed.\n\nYou can:\n  - Press Next to continue\n  - Or perform sanity check again if desired", "green")
            self.enable_and_focus_next_button()  # Allow moving to next step without rechecking
        else:
            # Update information panel
            self.update_information_panel("Ready to perform sanity check...\n\nClick 'Perform Sanity Check' to verify the profile accuracy.")

        # Check button
        check_btn = QPushButton("Perform Sanity Check")
        check_btn.clicked.connect(self.on_sanity_check)
        layout.addWidget(check_btn)

        layout.addStretch()
        widget.setLayout(layout)
        self.set_content_widget(widget)

    def on_sanity_check(self):
        """Handle sanity check."""
        self.update_information_panel("Performing sanity check...\n\nRunning profcheck command to verify profile accuracy...", "blue")

        name = self.state.name

        # Run profcheck command
        self.run_profcheck_command()

    def run_profcheck_command(self):
        """Run profcheck command for sanity check."""
        name = self.state.name

        # Detect profile extension (.icc or .icm)
        profile_folder = Path(self.state.profile_folder)
        icc_file = profile_folder / f"{name}.icc"
        icm_file = profile_folder / f"{name}.icm"

        if icc_file.exists():
            profile_ext = "icc"
        elif icm_file.exists():
            profile_ext = "icm"
        else:
            self.log.writeln("")
            self.log.writeln(f"Error: No profile file found for '{name}'")
            self.log.writeln(f"Expected '{name}.icc' or '{name}.icm' in {profile_folder}")
            self.log.writeln("")
            self.update_information_panel("Error: Profile file not found", "red")
            return

        # Build profcheck command
        args = ["profcheck", "-v2", "-k", "-s", f"{name}.ti3", f"{name}.{profile_ext}"]

        # Run command in thread
        self.update_information_panel("Running profcheck command...\n\nPerforming sanity check (creating .txt file)...", "blue")
        self.log.writeln("Performing sanity check (creating .txt file)...")
        self.log.writeln("")

        # Show command in terminal and log
        command_str = f"Command Used: profcheck -v2 -k -s \"{name}.ti3\" \"{name}.{profile_ext}\""
        self.log.writeln(command_str)

        # Write command to sanity file
        sanity_file = Path(self.state.profile_folder) / f"{name}_sanity_check.txt"
        with open(sanity_file, "a") as f:
            f.write(f"Command Used: profcheck -v2 -k -s \"{name}.ti3\" \"{name}.{profile_ext}\"\n")
            f.write("\n\n")

        # Open sanity file for appending output
        self.sanity_file_handle = open(sanity_file, "a")

        self.command_thread = CommandThread(args, cwd=Path(self.state.profile_folder))
        self.command_thread.output_signal.connect(self.on_profcheck_output)
        self.command_thread.finished_signal.connect(self.on_profcheck_finished)
        self.command_thread.error_signal.connect(self.on_command_error)
        self.command_thread.start()

    def on_profcheck_output(self, output: str):
        """Handle profcheck output - write to log and sanity file."""
        self.log.write(output)
        if hasattr(self, 'sanity_file_handle') and self.sanity_file_handle:
            self.sanity_file_handle.write(output)
            self.sanity_file_handle.flush()

    def on_profcheck_finished(self, exit_code: int):
        """Handle profcheck completion."""
        # Close sanity file handle
        if hasattr(self, 'sanity_file_handle') and self.sanity_file_handle:
            self.sanity_file_handle.close()
            self.sanity_file_handle = None

        if exit_code != 0:
            self.update_information_panel(f"profcheck failed with exit code {exit_code}", "red")
            return

        self.update_information_panel("Analyzing delta E values...", "blue")
        self.log.writeln("")

        # Append empty lines to sanity file
        sanity_file = Path(self.state.profile_folder) / f"{self.state.name}_sanity_check.txt"
        with open(sanity_file, "a") as f:
            f.write("\n\n")

        # Perform delta E analysis
        self.perform_delta_e_analysis()

    def perform_delta_e_analysis(self):
        """Perform delta E analysis from sanity check file."""
        import math
        import re

        name = self.state.name
        sanity_file = Path(self.state.profile_folder) / f"{name}_sanity_check.txt"

        # Extract delta E values
        delta_e_values = []
        try:
            with open(sanity_file, "r") as f:
                for line in f:
                    m = re.search(r'^\[([0-9]+\.[0-9]+)\].*@', line.strip())
                    if m:
                        delta_e_values.append(float(m.group(1)))
        except FileNotFoundError:
            self.update_information_panel("Error: Sanity check file not found", "red")
            self.log.writeln("Error: Sanity check file not found")
            return

        if not delta_e_values:
            self.update_information_panel("No delta E values found in sanity check", "red")
            self.log.writeln("⚠️ No delta E values found in sanity check file")
            return

        # Since profcheck -s sorts highest to lowest
        largest = delta_e_values[0]
        smallest = delta_e_values[-1]
        range_val = largest - smallest

        total_patches = len(delta_e_values)

        # Calculate percentiles (round up)
        pos_99 = math.ceil(total_patches * 0.99)
        pos_98 = math.ceil(total_patches * 0.98)
        pos_95 = math.ceil(total_patches * 0.95)
        pos_90 = math.ceil(total_patches * 0.90)

        # Get values from end (since sorted high to low)
        def get_percentile(pos):
            if pos > 0 and pos <= total_patches:
                return delta_e_values[total_patches - pos]
            return "N/A"

        percentile_99 = get_percentile(pos_99)
        percentile_98 = get_percentile(pos_98)
        percentile_95 = get_percentile(pos_95)
        percentile_90 = get_percentile(pos_90)

        # Count <1, <2, <3
        count_lt_1 = sum(1 for v in delta_e_values if v < 1.0)
        count_lt_2 = sum(1 for v in delta_e_values if v < 2.0)
        count_lt_3 = sum(1 for v in delta_e_values if v < 3.0)

        percent_lt_1 = (count_lt_1 / total_patches) * 100
        percent_lt_2 = (count_lt_2 / total_patches) * 100
        percent_lt_3 = (count_lt_3 / total_patches) * 100

        # Display results
        self.log.writeln("")
        self.log.writeln("──────────────────────────────────────────")
        self.log.writeln("Analysis done by Argyll_Printer_Profiler")
        self.log.writeln("──────────────────────────────────────────")
        self.log.writeln("Delta E Range Analysis:")
        self.log.writeln(f"  Largest ΔE:  {largest}")
        self.log.writeln(f"  Smallest ΔE: {smallest}")
        self.log.writeln("")
        self.log.writeln("Percentile Values:")
        self.log.writeln(f"  99th percentile: {percentile_99}")
        self.log.writeln(f"  98th percentile: {percentile_98}")
        self.log.writeln(f"  95th percentile: {percentile_95}")
        self.log.writeln(f"  90th percentile: {percentile_90}")
        self.log.writeln("")
        self.log.writeln("Patch Count Analysis:")
        self.log.writeln(f"  Percent of patches with ΔE<1.0: {percent_lt_1:.1f}%")
        self.log.writeln(f"  Percent of patches with ΔE<2.0: {percent_lt_2:.1f}%")
        self.log.writeln(f"  Percent of patches with ΔE<3.0: {percent_lt_3:.1f}%")
        self.log.writeln("──────────────────────────────────────────")
        self.log.writeln("")

        # Append to file
        with open(sanity_file, "a") as f:
            f.write("\n")
            f.write("========================================\n")
            f.write("Analysis done by Argyll_Printer_Profiler\n")
            f.write("========================================\n")
            f.write("Delta E Range Analysis:\n")
            f.write(f"Largest ΔE: {largest}\n")
            f.write(f"Smallest ΔE: {smallest}\n")
            f.write("\n")
            f.write("Percentile Values:\n")
            f.write(f"99th percentile: {percentile_99}\n")
            f.write(f"98th percentile: {percentile_98}\n")
            f.write(f"95th percentile: {percentile_95}\n")
            f.write(f"90th percentile: {percentile_90}\n")
            f.write("\n")
            f.write("Patch Count Analysis:\n")
            f.write(f"Percent of patches with ΔE<1.0: {percent_lt_1:.1f}%\n")
            f.write(f"Percent of patches with ΔE<2.0: {percent_lt_2:.1f}%\n")
            f.write(f"Percent of patches with ΔE<3.0: {percent_lt_3:.1f}%\n")
            f.write("========================================\n")
            f.write("\n")

        # Run second profcheck command
        self.run_second_profcheck()

    def run_second_profcheck(self):
        """Run second profcheck command and append to sanity file."""
        name = self.state.name

        # Detect profile extension
        profile_folder = Path(self.state.profile_folder)
        icc_file = profile_folder / f"{name}.icc"
        icm_file = profile_folder / f"{name}.icm"

        if icc_file.exists():
            profile_ext = "icc"
        elif icm_file.exists():
            profile_ext = "icm"
        else:
            self.update_information_panel("Error: Profile file not found", "red")
            return

        sanity_file = Path(self.state.profile_folder) / f"{name}_sanity_check.txt"

        # Show command
        self.log.writeln(f"Command Used: profcheck -v -k \"{name}.ti3\" \"{name}.{profile_ext}\"")

        with open(sanity_file, "a") as f:
            f.write(f"Command Used: profcheck -v -k \"{name}.ti3\" \"{name}.{profile_ext}\"\n")

        # Open sanity file for appending output
        self.sanity_file_handle = open(sanity_file, "a")

        # Run command in thread
        args = ["profcheck", "-v", "-k", f"{name}.ti3", f"{name}.{profile_ext}"]
        self.command_thread = CommandThread(args, cwd=Path(self.state.profile_folder))
        self.command_thread.output_signal.connect(self.on_second_profcheck_output)
        self.command_thread.finished_signal.connect(self.on_second_profcheck_finished)
        self.command_thread.error_signal.connect(self.on_command_error)
        self.command_thread.start()

    def on_second_profcheck_output(self, output: str):
        """Handle second profcheck output - write to log and sanity file."""
        self.log.write(output)
        if hasattr(self, 'sanity_file_handle') and self.sanity_file_handle:
            self.sanity_file_handle.write(output)
            self.sanity_file_handle.flush()

    def on_second_profcheck_finished(self, exit_code: int):
        """Handle second profcheck completion."""
        # Close sanity file handle
        if hasattr(self, 'sanity_file_handle') and self.sanity_file_handle:
            self.sanity_file_handle.close()
            self.sanity_file_handle = None

        if exit_code != 0:
            self.update_information_panel(f"Second profcheck failed with exit code {exit_code}", "red")
            return

        self.update_information_panel(f"Sanity check completed successfully!\n\nResults saved to:\n{self.state.name}_sanity_check.txt\n\nPress Next to continue.", "green")
        self.log.writeln("")

        # Mark sanity check as completed
        self.state.sanity_check_completed = True

        # Show completion message
        # Set step header (outside content group box)
        self.step_header_label.setText("Sanity Check Completed Successfully!")
        self.step_header_label.setStyleSheet("font-size: 16px; font-weight: bold; color: green;")
        self.step_header_label.setVisible(True)

        widget = QWidget()
        layout = QVBoxLayout()

        layout.addSpacing(20)

        info = QLabel(f"Sanity check results saved to: {self.state.name}_sanity_check.txt")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(20)

        # Actions
        actions_layout = QHBoxLayout()

        open_folder_btn = QPushButton("Open Profile Folder")
        open_folder_btn.clicked.connect(self.on_open_profile_folder)
        actions_layout.addWidget(open_folder_btn)

        back_to_menu_btn = QPushButton("Return to Main Menu")
        back_to_menu_btn.clicked.connect(self.show_main_menu)
        actions_layout.addWidget(back_to_menu_btn)

        layout.addLayout(actions_layout)

        layout.addStretch()
        widget.setLayout(layout)
        self.set_content_widget(widget)

        self.enable_and_focus_next_button()

    def show_completion(self):
        """Show completion page."""
        self.current_page = "completion"
        self.back_button.setEnabled(False)
        self.next_button.setEnabled(False)

        # Set step header (outside content group box)
        self.step_header_label.setText("Workflow Completed Successfully!")
        self.step_header_label.setStyleSheet("font-size: 18px; font-weight: bold; color: green;")
        self.step_header_label.setVisible(True)

        widget = QWidget()
        layout = QVBoxLayout()

        layout.addSpacing(20)

        summary_group = QGroupBox("Summary")
        summary_layout = QVBoxLayout()

        name = self.state.name
        profile_folder = self.state.profile_folder
        profile_ext = self.state.profile_extension

        summary_layout.addWidget(QLabel(f"Profile Name: {name}"))
        summary_layout.addWidget(QLabel(f"Profile Folder: {profile_folder}"))
        summary_layout.addWidget(QLabel(f"Profile File: {name}.{profile_ext}"))

        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        layout.addSpacing(20)

        # Actions
        actions_layout = QHBoxLayout()

        open_folder_btn = QPushButton("Open Profile Folder")
        open_folder_btn.clicked.connect(self.on_open_profile_folder)
        actions_layout.addWidget(open_folder_btn)

        back_to_menu_btn = QPushButton("Return to Main Menu")
        back_to_menu_btn.clicked.connect(self.show_main_menu)
        actions_layout.addWidget(back_to_menu_btn)

        layout.addLayout(actions_layout)

        layout.addStretch()
        widget.setLayout(layout)
        self.set_content_widget(widget)

    def on_open_profile_folder(self):
        """Open profile folder in file manager."""
        try:
            profile_folder = Path(self.state.profile_folder)
            if self.state.PLATFORM == "windows":
                os.startfile(str(profile_folder))
            elif self.state.PLATFORM == "macos":
                subprocess.run(["open", str(profile_folder)])
            elif self.state.PLATFORM == "linux":
                subprocess.run(["xdg-open", str(profile_folder)])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open folder: {e}")

    def show_select_ti3_file(self):
        """Show .ti3 file selection page."""
        self.current_page = "select_ti3_file"
        self.back_button.setEnabled(False)  # Disable back button in first step
        self.abort_button.setVisible(True)
        self.abort_button.setEnabled(True)
        self.next_button.setEnabled(False)

        # Set step header (outside content group box)
        self.step_header_label.setText("Select .ti3 Measurement File")
        self.step_header_label.setVisible(True)

        widget = QWidget()
        layout = QVBoxLayout()

        # Dynamic info text based on workflow type
        if self.workflow_type == "resume_measurement":
            info = QLabel("Select an existing .ti3 file to re-read/resume measuring target patches.")
        elif self.workflow_type == "profile_from_measurement":
            info = QLabel("Select an existing completed .ti3 file to create .icc/.icm profile with.")
        elif self.workflow_type == "sanity_check":
            info = QLabel("Select an existing .ti3 file that has a matching .icc/.icm profile.")
        else:
            info = QLabel("Select a .ti3 measurement file to use for profile creation or sanity check.")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(20)

        # File selection
        file_btn = QPushButton("Select .ti3 File")
        file_btn.clicked.connect(self.on_select_ti3_file)
        layout.addWidget(file_btn)

        self.selected_ti3_label = QLabel("No file selected")
        self.selected_ti3_label.setWordWrap(True)
        layout.addWidget(self.selected_ti3_label)

        # Restore previously selected file if navigating back
        if self.state.ti3_file_selected and self.state.new_icc_path:
            self.selected_ti3_label.setText(f"Selected: {Path(self.state.new_icc_path).name}")
            self.enable_and_focus_next_button()

        layout.addStretch()
        widget.setLayout(layout)
        self.set_content_widget(widget)

    def on_select_ti3_file(self):
        """Handle .ti3 file selection."""
        # Use default path from original code
        initialdir = self.state.script_dir / self.cfg.get("CREATED_PROFILES_FOLDER", "Created_Profiles")

        # Dynamic dialog title based on workflow type
        if self.workflow_type == "resume_measurement":
            dialog_title = "Select an existing .ti3 file to re-read/resume measuring target patches"
        elif self.workflow_type == "profile_from_measurement":
            dialog_title = "Select an existing completed .ti3 file to create .icc/.icm profile with"
        elif self.workflow_type == "sanity_check":
            dialog_title = "Select an existing .ti3 file that has a matching .icc/.icm profile"
        else:
            dialog_title = "Select .ti3 File"

        filetypes = [("Target Information 3 data", "*.ti3"), ("All files", "*")]

        file_path = pick_file_gui(
            title=dialog_title,
            filetypes=filetypes,
            initialdir=initialdir,
            is_folder=False,
            platform=self.state.PLATFORM,
            parent=self
        )

        if file_path:
            self.state.new_icc_path = file_path
            self.state.name = Path(file_path).stem
            self.state.desc = self.state.name
            self.state.source_folder = str(Path(file_path).parent)

            self.selected_ti3_label.setText(f"Selected: {Path(file_path).name}")
            self.log.writeln(f"Selected .ti3 file: {file_path}")

            # For sanity_check workflow, set profile_folder to source_folder
            if self.workflow_type == "sanity_check":
                self.state.profile_folder = self.state.source_folder
                self.log.writeln(f"Working folder: {self.state.profile_folder}")
                self.log.writeln("")

            # Collect TIFF files for actions 2 and 3
            if self.workflow_type in {"resume_measurement", "read_from_scratch"}:
                source_folder = Path(self.state.source_folder)
                self.state.tif_files = _collect_matching_tifs(source_folder, self.state.name)

                if not self.state.tif_files:
                    self.log.writeln(f"No matching .tif target images found for '{self.state.name}'.")
                    return

                self.log.writeln("Found target image(s):")
                for f in self.state.tif_files:
                    self.log.writeln(f"  {f.name}")
                self.log.writeln("")

            # Call copy_or_overwrite_submenu for actions 2, 3, 4
            if self.workflow_type in {"resume_measurement", "read_from_scratch", "profile_from_measurement"}:
                # Reset choice state when selecting a new file
                self.state.copy_overwrite_choice_made = False
                if self.workflow_type == "read_from_scratch":
                    if not self.copy_or_overwrite_submenu(
                        overwrite_message_line_1="2: Overwrite existing (use files in their current location, ",
                        overwrite_message_line_2="   existing .ti3 and .icc/.icm files will be overwritten)"
                    ):
                        return
                elif self.workflow_type == "resume_measurement":
                    if not self.copy_or_overwrite_submenu(
                        overwrite_message_line_1="2: Overwrite existing (use files in their current location, measurement will",
                        overwrite_message_line_2="   resume using existing .ti3 and .icc/.icm file will be overwritten)"
                    ):
                        return
                elif self.workflow_type == "profile_from_measurement":
                    if not self.copy_or_overwrite_submenu(
                        overwrite_message_line_1="2: Overwrite existing (use files in their current location,"
                    ):
                        return

            self.enable_and_focus_next_button()

            # Update information panel
            self.update_information_panel("File selected.\n\nClick Next to continue...")

            # Mark .ti3 file as selected
            self.state.ti3_file_selected = True

            if self.workflow_type != "sanity_check":
                self.log.writeln(f"Working folder: {self.state.profile_folder}")
                self.log.writeln("")

    def show_select_ti2_file(self):
        """Show .ti2 file selection page."""
        self.current_page = "select_ti2_file"
        self.back_button.setEnabled(False)  # Disable back button in first step
        self.abort_button.setVisible(True)
        self.abort_button.setEnabled(True)
        self.next_button.setEnabled(False)

        # Set step header (outside content group box)
        self.step_header_label.setText("Select .ti2 Target File")
        self.step_header_label.setVisible(True)

        widget = QWidget()
        layout = QVBoxLayout()

        info = QLabel("Select an existing .ti2 file to measure target patches.")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(20)

        # File selection
        file_btn = QPushButton("Select .ti2 File")
        file_btn.clicked.connect(self.on_select_ti2_file)
        layout.addWidget(file_btn)

        self.selected_ti2_label = QLabel("No file selected")
        self.selected_ti2_label.setWordWrap(True)
        layout.addWidget(self.selected_ti2_label)

        # Restore previously selected file if navigating back
        if self.state.ti2_file_selected and self.state.new_icc_path:
            self.selected_ti2_label.setText(f"Selected: {Path(self.state.new_icc_path).name}")
            self.enable_and_focus_next_button()

        layout.addStretch()
        widget.setLayout(layout)
        self.set_content_widget(widget)

    def on_select_ti2_file(self):
        """Handle .ti2 file selection."""
        initialdir = self.state.script_dir / self.cfg.get("PRE_MADE_TARGETS_FOLDER", "Pre-made_Targets")
        dialog_title = "Select an existing .ti2 file to measure target patches"
        filetypes = [("Target Information 2 data", "*.ti2"), ("All files", "*")]

        file_path = pick_file_gui(
            title=dialog_title,
            filetypes=filetypes,
            initialdir=initialdir,
            is_folder=False,
            platform=self.state.PLATFORM,
            parent=self
        )

        if file_path:
            self.state.new_icc_path = file_path
            self.state.name = Path(file_path).stem
            self.state.desc = self.state.name
            self.state.source_folder = str(Path(file_path).parent)

            self.selected_ti2_label.setText(f"Selected: {Path(file_path).name}")
            self.log.writeln(f"Selected .ti2 file: {file_path}")

            # Collect TIFF files
            source_folder = Path(self.state.source_folder)
            self.state.tif_files = _collect_matching_tifs(source_folder, self.state.name)

            self.log.writeln("Found target image(s):")
            for f in self.state.tif_files:
                self.log.writeln(f"  {f.name}")

            # Call copy_or_overwrite_submenu for action 3 (read_from_scratch)
            if self.workflow_type == "read_from_scratch":
                # Reset choice state when selecting a new file
                self.state.copy_overwrite_choice_made = False
                if not self.copy_or_overwrite_submenu(
                    overwrite_message_line_1="2: Overwrite existing (use files in their current location, ",
                    overwrite_message_line_2="   existing .ti3 and .icc/.icm files will be overwritten)"
                ):
                    return

            self.enable_and_focus_next_button()

            # Update information panel
            self.update_information_panel("File selected.\n\nClick Next to continue...")

            # Mark .ti2 file as selected
            self.state.ti2_file_selected = True

            self.log.writeln(f"Working folder: {self.state.profile_folder}")
            self.log.writeln("")

    def show_setup_parameters(self):
        """Show setup parameters page."""
        self.current_page = "setup_parameters"
        self.back_button.setEnabled(True)
        self.abort_button.setVisible(False)
        self.next_button.setEnabled(False)

        # Show nav_section so Back button is visible
        self.nav_section.setVisible(True)

        # Hide progress section, workflow title, and information panel for this view
        self.progress_section.setVisible(False)
        self.workflow_title_label.setVisible(False)
        self.information_panel.setVisible(False)

        # Set step header (outside content group box)
        self.step_header_label.setText("Change Setup Parameters")
        self.step_header_label.setVisible(True)

        widget = QWidget()
        layout = QVBoxLayout()

        info = QLabel("In this menu some variables stored in the Argyll_Printer_Profiler_setup.ini file can be modified. Move mouse over options for more details.")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(20)

        # Parameter selection
        param_group = QGroupBox("What parameter do you want to modify?")
        param_layout = QVBoxLayout()

        # Load current values from setup file
        cfg = load_setup_file_shell_style(self.state.setup_file)
        icc_filename = cfg.get("PRINTER_ICC_PATH", "")
        precon_icc_filename = cfg.get("PRECONDITIONING_PROFILE_PATH", "")
        install_profiles_path = cfg.get("PRINTER_PROFILES_PATH", "")
        tolerance = cfg.get("STRIP_PATCH_CONSISTENSY_TOLERANCE", "")
        paper_size = cfg.get("PAPER_SIZE", "")
        ink_limit = cfg.get("INK_LIMIT", "")
        example_naming = cfg.get("EXAMPLE_FILE_NAMING", "")

        buttons = [
            ("1: Select Color Space profile (PRINTER_ICC_PATH)",
             "on_setup_param_1",
             f"Select Color Space profile to use when creating printer profile (colprof arg. -S)\n\nCurrent file specified: '{icc_filename}'"),
            ("2: Select pre-conditioning profile (PRECONDITIONING_PROFILE_PATH)",
             "on_setup_param_2",
             f"Select pre-conditioning profile to use when creating target (targen arg. -c)\n\nCurrent file specified: '{precon_icc_filename}'"),
            ("3: Select profile installation path (PRINTER_PROFILES_PATH)",
             "on_setup_param_3",
             f"Select path to where printer profiles shall be copied for use by the operating system.\n\nCurrent path specified: '{install_profiles_path}'"),
            ("4: Modify patch consistency tolerance (STRIP_PATCH_CONSISTENSY_TOLERANCE)",
             "on_setup_param_4",
             f"Modify patch consistency tolerance (chartread arg. -T)\n\nCurrent value specified: '{tolerance}'\n\nRecommended: 0.6"),
            ("5: Modify paper size (PAPER_SIZE)",
             "on_setup_param_5",
             f"Modify paper size for target generation (printtarg arg. -p).\n\nCurrent value specified: '{paper_size}'\n\nValid values: A4, Letter"),
            ("6: Modify ink limit (INK_LIMIT)",
             "on_setup_param_6",
             f"Modify ink limit (targen and colprof arg. -l).\n\nCurrent value specified: '{ink_limit}'\n\nValid values: 0 - 400 (%) or empty to disable"),
            ("7: Modify file naming convention (EXAMPLE_FILE_NAMING)",
             "on_setup_param_7",
             f"Modify file naming convention example (shown in main menu option 1).\n\nCurrent value specified:\n'{example_naming}'\n\nValid value: text"),
        ]

        for text, method_name, tooltip in buttons:
            btn = QPushButton(text)
            btn.setStyleSheet("text-align: left; padding: 8px;")
            getattr(self, method_name)(btn)
            param_layout.addWidget(btn)
            # Set tooltip after button is added to layout
            btn.setToolTip(tooltip)

        param_group.setLayout(param_layout)
        layout.addWidget(param_group)

        layout.addStretch()
        widget.setLayout(layout)
        self.set_content_widget(widget)

    def on_setup_param_1(self, button: QPushButton):
        """Handle setup parameter 1."""
        button.clicked.connect(self.select_printer_icc_path)

    def on_setup_param_2(self, button: QPushButton):
        """Handle setup parameter 2."""
        button.clicked.connect(self.select_preconditioning_profile)

    def on_setup_param_3(self, button: QPushButton):
        """Handle setup parameter 3."""
        button.clicked.connect(self.select_profile_installation_path)

    def on_setup_param_4(self, button: QPushButton):
        """Handle setup parameter 4."""
        button.clicked.connect(self.modify_patch_tolerance)

    def on_setup_param_5(self, button: QPushButton):
        """Handle setup parameter 5."""
        button.clicked.connect(self.modify_paper_size)

    def on_setup_param_6(self, button: QPushButton):
        """Handle setup parameter 6."""
        button.clicked.connect(self.modify_ink_limit)

    def on_setup_param_7(self, button: QPushButton):
        """Handle setup parameter 7."""
        button.clicked.connect(self.modify_file_naming)

    def refresh_setup_parameters(self):
        """Refresh the setup parameters page to update tooltips with new values."""
        self.show_setup_parameters()

    def select_printer_icc_path(self):
        """Select printer ICC path."""
        # Use default path from original code
        raw = (self.cfg.get("PRINTER_ICC_PATH", "") or "").strip()
        expanded = os.path.expandvars(raw)
        current_path = Path(expanded).expanduser() if expanded else Path("")
        if current_path.is_file() and current_path.parent.is_dir():
            initialdir = current_path.parent
        elif current_path.is_dir():
            initialdir = current_path
        elif current_path.parent.is_dir():
            initialdir = current_path.parent
        else:
            initialdir = self.state.script_dir

        title = "Select a new profile (.icc or .icm)"
        filetypes = [("ICC/ICM profiles", "*.icc *.icm"), ("All files", "*")]

        file_path = pick_file_gui(
            title=title,
            filetypes=filetypes,
            initialdir=initialdir,
            is_folder=False,
            platform=self.state.PLATFORM,
            parent=self
        )

        if file_path:
            update_setup_value_shell_style(self.state.setup_file, "PRINTER_ICC_PATH", file_path)
            self.cfg["PRINTER_ICC_PATH"] = file_path
            self.log.writeln(f"Updated PRINTER_ICC_PATH: {file_path}")
            QMessageBox.information(self, "Success", "PRINTER_ICC_PATH updated successfully.")
            self.refresh_setup_parameters()

    def select_preconditioning_profile(self):
        """Select pre-conditioning profile."""
        # Use default path from original code
        raw = (self.cfg.get("PRECONDITIONING_PROFILE_PATH", "") or "").strip()
        expanded = os.path.expandvars(raw)
        current_path = Path(expanded).expanduser() if expanded else Path("")

        # If PRECONDITIONING_PROFILE_PATH is empty, use PRINTER_ICC_PATH location as default
        if not current_path.is_file():
            raw_icc = (self.cfg.get("PRINTER_ICC_PATH", "") or "").strip()
            expanded_icc = os.path.expandvars(raw_icc)
            icc_path = Path(expanded_icc).expanduser() if expanded_icc else Path("")
            if icc_path.is_file() and icc_path.parent.is_dir():
                initialdir = str(icc_path.parent)
            elif icc_path.is_dir():
                initialdir = str(icc_path)
            elif icc_path.parent.is_dir():
                initialdir = str(icc_path.parent)
            else:
                initialdir = str(self.state.script_dir)
        elif current_path.is_file() and current_path.parent.is_dir():
            initialdir = str(current_path.parent)
        elif current_path.is_dir():
            initialdir = str(current_path)
        elif current_path.parent.is_dir():
            initialdir = str(current_path.parent)
        else:
            initialdir = str(self.state.script_dir)

        dialog = QDialog(self)
        dialog.setWindowTitle("Pre-conditioning Profile")
        layout = QVBoxLayout()

        layout.addWidget(QLabel("What do you want to do?"))

        select_btn = QPushButton("Choose color space profile file (.icc/.icm)")
        clear_btn = QPushButton("Clear parameter (no profile)")

        def on_select():
            title = "Select Pre-conditioning Profile"
            filetypes = [("ICC/ICM profiles", "*.icc *.icm"), ("All files", "*")]
            file_path = pick_file_gui(
                title=title,
                filetypes=filetypes,
                initialdir=Path(initialdir),
                is_folder=False,
                platform=self.state.PLATFORM,
                parent=dialog
            )
            if file_path:
                update_setup_value_shell_style(self.state.setup_file, "PRECONDITIONING_PROFILE_PATH", file_path)
                self.cfg["PRECONDITIONING_PROFILE_PATH"] = file_path
                self.log.writeln(f"Updated PRECONDITIONING_PROFILE_PATH: {file_path}")
                QMessageBox.information(dialog, "Success", "PRECONDITIONING_PROFILE_PATH updated successfully.")
                dialog.accept()
                self.refresh_setup_parameters()
            else:
                # User cancelled file selection, close dialog
                dialog.reject()

        def on_clear():
            update_setup_value_shell_style(self.state.setup_file, "PRECONDITIONING_PROFILE_PATH", "")
            self.cfg["PRECONDITIONING_PROFILE_PATH"] = ""
            self.log.writeln("Cleared PRECONDITIONING_PROFILE_PATH (no profile)")
            QMessageBox.information(dialog, "Success", "PRECONDITIONING_PROFILE_PATH cleared.")
            dialog.accept()
            self.refresh_setup_parameters()

        select_btn.clicked.connect(on_select)
        clear_btn.clicked.connect(on_clear)

        layout.addWidget(select_btn)
        layout.addWidget(clear_btn)
        dialog.setLayout(layout)
        dialog.exec()

    def select_profile_installation_path(self):
        """Select profile installation path."""
        # Use default path from original code
        raw = (self.cfg.get("PRINTER_PROFILES_PATH", "") or "").strip()
        expanded = os.path.expandvars(raw)
        current_path = Path(expanded).expanduser() if expanded else Path("")
        if current_path.is_dir():
            initialdir = current_path
        elif current_path.parent.is_dir():
            initialdir = current_path.parent
        else:
            initialdir = self.state.script_dir

        title = "Select Profile Installation Directory"

        dir_path = pick_file_gui(
            title=title,
            filetypes=[],
            initialdir=initialdir,
            is_folder=True,
            platform=self.state.PLATFORM,
            parent=self
        )

        if dir_path:
            update_setup_value_shell_style(self.state.setup_file, "PRINTER_PROFILES_PATH", dir_path)
            self.cfg["PRINTER_PROFILES_PATH"] = dir_path
            self.log.writeln(f"Updated PRINTER_PROFILES_PATH: {dir_path}")
            QMessageBox.information(self, "Success", "PRINTER_PROFILES_PATH updated successfully.")
            self.refresh_setup_parameters()

    def modify_patch_tolerance(self):
        """Modify patch tolerance."""
        current_value = self.cfg.get("STRIP_PATCH_CONSISTENSY_TOLERANCE", "0.6")

        # Create content widget
        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.addWidget(QLabel("Enter new value [0.6 recommended]:"))
        input_field = QLineEdit(current_value)
        content_layout.addWidget(input_field)
        content.setLayout(content_layout)

        def on_ok():
            value = input_field.text().strip()
            if not re.fullmatch(r'^[0-9]+(\.[0-9]+)?$', value):
                QMessageBox.warning(dialog, "Invalid Value", "Please enter a valid numeric value.")
                return

            update_setup_value_shell_style(self.state.setup_file, "STRIP_PATCH_CONSISTENSY_TOLERANCE", value)
            self.cfg["STRIP_PATCH_CONSISTENSY_TOLERANCE"] = value
            self.log.writeln(f"Updated STRIP_PATCH_CONSISTENSY_TOLERANCE to {value}")
            QMessageBox.information(dialog, "Success", "STRIP_PATCH_CONSISTENSY_TOLERANCE updated successfully.")
            dialog.accept()
            self.refresh_setup_parameters()

        dialog = create_standard_dialog(self, "Modify Patch Consistency Tolerance", content, on_ok)
        dialog.exec()

    def modify_paper_size(self):
        """Modify paper size."""
        current_value = self.cfg.get("PAPER_SIZE", "A4")

        # Create content widget
        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.addWidget(QLabel("Select paper size:"))
        combo = QComboBox()
        combo.addItems(["A4", "Letter"])
        combo.setCurrentText(current_value)
        content_layout.addWidget(combo)
        content.setLayout(content_layout)

        def on_ok():
            value = combo.currentText()
            update_setup_value_shell_style(self.state.setup_file, "PAPER_SIZE", value)
            self.cfg["PAPER_SIZE"] = value
            self.log.writeln(f"Updated PAPER_SIZE to {value}")
            QMessageBox.information(dialog, "Success", "PAPER_SIZE updated successfully.")
            dialog.accept()
            self.refresh_setup_parameters()

        dialog = create_standard_dialog(self, "Modify Paper Size", content, on_ok)
        dialog.exec()

    def modify_ink_limit(self):
        """Modify ink limit."""
        current_value = self.cfg.get("INK_LIMIT", "")

        # Create content widget
        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.addWidget(QLabel("Enter ink limit (0-400 or empty to disable):"))
        input_field = QLineEdit(current_value)
        content_layout.addWidget(input_field)
        content.setLayout(content_layout)

        def on_ok():
            value = input_field.text().strip()
            if value and (not value.isdigit() or not (0 <= int(value) <= 400)):
                QMessageBox.warning(dialog, "Invalid Value", "Please enter a value between 0 and 400.")
                return

            update_setup_value_shell_style(self.state.setup_file, "INK_LIMIT", value)
            self.cfg["INK_LIMIT"] = value
            self.log.writeln(f"Updated INK_LIMIT to '{value}'")
            QMessageBox.information(dialog, "Success", "INK_LIMIT updated successfully.")
            dialog.accept()
            self.refresh_setup_parameters()

        dialog = create_standard_dialog(self, "Modify Ink Limit", content, on_ok)
        dialog.exec()

    def modify_file_naming(self):
        """Modify file naming convention."""
        current_value = self.cfg.get("EXAMPLE_FILE_NAMING", "")

        # Create content widget
        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.addWidget(QLabel("Enter example file naming convention:"))
        input_field = QLineEdit(current_value)
        content_layout.addWidget(input_field)
        content.setLayout(content_layout)

        def on_ok():
            value = input_field.text().strip()
            if not re.fullmatch(r"[A-Za-z0-9._()\-]+", value):
                QMessageBox.warning(dialog, "Invalid Value", "Invalid file name characters. Please try again.")
                return

            update_setup_value_shell_style(self.state.setup_file, "EXAMPLE_FILE_NAMING", value)
            self.cfg["EXAMPLE_FILE_NAMING"] = value
            self.log.writeln(f"Updated EXAMPLE_FILE_NAMING to '{value}'")
            QMessageBox.information(dialog, "Success", "EXAMPLE_FILE_NAMING updated successfully.")
            dialog.accept()
            self.refresh_setup_parameters()

        dialog = create_standard_dialog(self, "Modify File Naming Convention", content, on_ok)
        dialog.exec()

    def show_improving_accuracy(self):
        """Show tips for improving accuracy."""
        self.current_page = "improving_accuracy"
        self.back_button.setEnabled(True)
        self.abort_button.setVisible(False)
        self.next_button.setEnabled(False)

        # Show nav_section so Back button is visible
        self.nav_section.setVisible(True)

        # Hide progress section, workflow title, and information panel for this view
        self.progress_section.setVisible(False)
        self.workflow_title_label.setVisible(False)
        self.information_panel.setVisible(False)

        # Set step header (outside content group box)
        self.step_header_label.setText("Tips on how to improve accuracy of a profile")
        self.step_header_label.setVisible(True)

        widget = QWidget()
        layout = QVBoxLayout()

        # Load tips from original script
        tips_text = """
  1. The top-most lines in the file '*_sanity_check.txt, created'
      after a profile is made, are the patches with highest delta E values.

  2. If delta E values are too large it is recommended to remeasure.
      - delta E > 2 is regarded as clearly visible difference and
         should be remeasured (depending on printer type, see
         Quick Reference table below or menu option 8).
      - delta E < 1 is considered visually indistinguishable.

  3. The 'Largest delta E' or 'max.' value is an indicator that some
      patches should be remeasured.

  4. When wanting to remeasure patches to improve overall profile
      quality, do the following:
      a. Open file '*_sanity_check.txt' of a created printer
         profile and identify which sheets have largest error.
         Look at patch ID and find column label on target chart.
      b. In main menu, choose option 3, then select the target used
         for your profile by selecting
         the .ti2 file (files and targets should be in the folder
         where your .icc/.icm is stored)
      c. Select option '1. Create new profile (copy files into
         new folder)'. Do not overwrite.
      d. Start reading only those strips where high error has been
         identified.
         Press 'f' to move forward, or 'b' to move back one strip
         at a time while reading.
      e. When you have read the appropriate target strips, select
         'd' to save and exit.
      f. Open the created .ti3 file, and also the original .ti3
         for your profile to be improved.
         The new .ti3 file has data for read patches below the tag
         'BEGIN_DATA', and contain only the lines you re-read.
      g. In the original .ti3 file, search for the patch IDs to
         identify the lines to replace.
         Copy one data line at a time from the new .ti3 file, and
         replace the line with same ID in the original .ti3 file.
         Then save file.
      h. Now choose option 4 in main menu. Select the updated .ti3
         file. Now a new .icc/.icm profile and sanity report is
         created. Study results and see if the profile is improved.
         """

        tips_label = QLabel(tips_text.strip())
        tips_label.setWordWrap(True)
        tips_label.setStyleSheet("font-family: Courier New, monospace; font-size: 12px;")
        layout.addWidget(tips_label)

        layout.addStretch()
        widget.setLayout(layout)
        self.set_content_widget(widget)

    def show_de_reference(self):
        """Show Delta E2000 reference."""
        self.current_page = "de_reference"
        self.back_button.setEnabled(True)
        self.abort_button.setVisible(False)
        self.next_button.setEnabled(False)

        # Show nav_section so Back button is visible
        self.nav_section.setVisible(True)

        # Hide progress section, workflow title, and information panel for this view
        self.progress_section.setVisible(False)
        self.workflow_title_label.setVisible(False)
        self.information_panel.setVisible(False)

        # Set step header (outside content group box)
        self.step_header_label.setText("Delta E 2000 (Real-World Accuracy After Profiling)")
        self.step_header_label.setVisible(True)

        widget = QWidget()
        layout = QVBoxLayout()

        # HTML table with Delta E reference
        table_html = """
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr style="background-color: #f0f0f0;">
                <th style="text-align: left;">Printer Class</th>
                <th style="text-align: center;">Typical Delta E2000</th>
                <th style="text-align: center;">Typical Substrates</th>
                <th style="text-align: left;">Typical Use Cases</th>
            </tr>
            <tr>
                <td><b>Professional Photo Inkjet</b><br>Example Models:<br>- Epson P700/P900/P9570<br>- Canon PRO-1000, HP Z9+</td>
                <td style="text-align: center;">Avg 0.5-1.5<br>95% 1.5-2.5<br>Max 3-5</td>
                <td style="text-align: center;">Gloss,<br>baryta,<br>fine art</td>
                <td>Gallery,<br>contract proofing</td>
            </tr>
            <tr>
                <td><b>Prosumer / High-End Inkjet</b><br>Example Models:<br>- Epson P600/P800<br>- Canon PRO-200/300</td>
                <td style="text-align: center;">Avg 0.8-2.0<br>95% 2.0-3.5<br>Max 4-7</td>
                <td style="text-align: center;">Premium gloss,<br>semi-gloss</td>
                <td>Serious hobby,<br>small studio</td>
            </tr>
            <tr>
                <td><b>Consumer Home Inkjet</b><br>Example Models:<br>- Canon PIXMA TS/MG<br>- Epson EcoTank/Expression</td>
                <td style="text-align: center;">Avg 1.5-3.0<br>95% 3.0-5.0<br>Max 6-10</td>
                <td style="text-align: center;">Glossy, matte,<br>plain</td>
                <td>Casual photo,<br>mixed docs</td>
            </tr>
            <tr>
                <td><b>Professional Laser / Production</b><br>Example Models:<br>- Xerox PrimeLink<br>- Canon imagePRESS<br>- Ricoh Pro C</td>
                <td style="text-align: center;">Avg 1.5-2.5<br>95% 3.0-4.0<br>Max 5-7</td>
                <td style="text-align: center;">Coated stock,<br>proof paper</td>
                <td>Corporate,<br>marketing,<br>light proof</td>
            </tr>
            <tr>
                <td><b>Office / Consumer Laser</b><br>Example Models:<br>- HP Color LaserJet Pro<br>- Brother HL/MFC<br>- Canon i-SENSYS</td>
                <td style="text-align: center;">Avg 2.5-5.0<br>95% 4.0-7.0<br>Max 7-12+</td>
                <td style="text-align: center;">Office bond,<br>coated office</td>
                <td>Business docs,<br>presentations</td>
            </tr>
        </table>
        """

        table_label = QLabel(table_html)
        table_label.setTextFormat(Qt.TextFormat.RichText)
        table_label.setWordWrap(True)
        layout.addWidget(table_label)

        # Notes section
        notes_text = """Notes:
   - Values assume proper ICC/ICM profiling and correct media settings
   - Avg = overall accuracy, 95% = typical worst case, Max = outliers
   - Lower delta E = higher color accuracy
   - delta E < 1.0 is generally considered visually indistinguishable
   - Source of these numbers: https://ChatGPT.com"""

        notes_label = QLabel(notes_text)
        notes_label.setWordWrap(True)
        notes_label.setStyleSheet("font-family: Courier New, monospace; font-size: 12px;")
        layout.addWidget(notes_label)

        layout.addStretch()
        widget.setLayout(layout)
        self.set_content_widget(widget)


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
