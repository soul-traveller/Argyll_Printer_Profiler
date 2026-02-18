#!/usr/bin/env python3
"""Argyll Printer Profiler — Python Port

This is a fully functional Python port of the original Bash script
`Argyll_Printer_Profiler.command`, providing cross-platform support for automated
printer ICC profiling using ArgyllCMS.

Supported Platforms:
- Windows 10 and 11+
- macOS 10.6+
- Linux (Ubuntu/Debian and similar distributions)

Main Functionality:
- Create color target charts and measure them with supported spectrophotometers
- Generate ICC/ICM printer profiles using ArgyllCMS tools
- Resume interrupted measurements
- Create profiles from existing .ti3 measurement files
- Perform sanity checks on profiles with detailed ΔE analysis
- Interactive setup parameter editing
- Tips and reference guides for profile accuracy improvement
- Uses configurable .ini file for setup parameters

Key Features:
- Preserves the original workflow, menus, and error handling
- Cross-platform file selection dialogs using tkinter
- Unified logging to terminal and daily log files
- Compatible with existing shell-style setup file (Argyll_Printer_Profiler_setup.ini)
- Supports all ArgyllCMS spectrophotometers (i1Pro, ColorMunki, etc.)

Usage:
1. Ensure Python 3.x is installed with tkinter (usually included).
2. Install ArgyllCMS: Download from https://www.argyllcms.com/ or use package managers.
3. Run: python Argyll_Printer_Profiler.py
4. Follow the interactive menus to create profiles or perform checks.

Dependencies:
- Python 3.x with tkinter
- ArgyllCMS tools (targen, chartread, colprof, etc.) available from terminal
- Spectrophotometer connected for measurement workflows

This port replaces Bash-specific mechanisms (e.g., tee redirection, sed in-place edits,
osascript/zenity dialogs) with Python equivalents for full Windows compatibility.
"""

from __future__ import annotations

# Standard library imports
import datetime as dt  # Date and time handling
import getpass  # User name retrieval
import os  # Operating system interface
import platform  # Platform detection
import re  # Regular expressions
import shutil  # High-level file operations
import shlex  # Shell-like syntax parsing
import subprocess  # Subprocess management
import sys  # System-specific parameters and functions
from dataclasses import dataclass, field  # Data class definitions
from pathlib import Path  # Object-oriented filesystem paths
from typing import Optional  # Type hints


def getch() -> str:
    """Read a single character from stdin without echoing or waiting for enter."""
    try:
        # Windows
        import msvcrt
        return msvcrt.getch().decode('utf-8', errors='ignore')
    except ImportError:
        # Unix-like
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


VERSION = "1.3.0"


@dataclass
class AppState:
    """Holds script state and mirrors the Bash global variables."""

    script_dir: Path  # Directory where the script is located
    script_name: str  # Name of the script file
    temp_log: Path  # Path to the daily log file
    setup_file: Path  # Path to the setup configuration file
    PLATFORM: str  # Detected operating system ('windows', 'macos', 'linux')

    # Mirrors Bash globals (cleared on each main menu iteration)
    source_folder: str = ""  # Folder containing selected target files
    dialog_title: str = ""  # Title for file selection dialogs
    name: str = ""  # Base name of selected files (without extension)
    desc: str = ""  # Description for profile (usually same as name)
    action: str = ""  # Current action code from main menu
    profile_folder: str = ""  # Folder where profile is created/saved
    new_name: str = ""  # New name for renamed files/profiles
    ti3_mtime_before: str = ""  # Modification time before resuming measurement
    ti3_mtime_after: str = ""  # Modification time after measurement
    tif_files: list[Path] = field(default_factory=list)  # List of TIFF target images
    new_icc_path: str = ""  # Path to newly selected ICC profile

    # Additional globals used by the ported workflow
    inst_arg: str = ""  # Instrument argument for Argyll commands
    inst_name: str = ""  # Human-readable instrument name



class TeeLogger:
    """Simple terminal + file logger.

    This replaces Bash `exec > >(tee -a ...) 2>&1`.

    Important:
    - Prefer using `log.writeln()` instead of `print()` so output is captured.
    - For external command output, use `run_cmd()` which streams output to log.
    """

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path  # Path to the log file to write to

    def write(self, text: str) -> None:
        # Write text to stdout and flush immediately
        sys.stdout.write(text)
        sys.stdout.flush()
        # Append text to the log file (create if needed)
        with self.log_path.open("a", encoding="utf-8", errors="replace") as f:
            f.write(text)

    def writeln(self, text: str = "") -> None:
        # Write a line with newline
        self.write(text + "\n")

    def log_only(self, text: str = "") -> None:
        # Write to log file only, not to stdout
        with self.log_path.open("a", encoding="utf-8", errors="replace") as f:
            f.write(text + "\n")


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


def session_separator(state: AppState, log: TeeLogger) -> None:
    """Write a large session separator to the log file only."""

    now = dt.datetime.now().astimezone()
    lines = [
        "",
        "",
        "",
        "=" * 80,
        "NEW SCRIPT SESSION STARTED",
        f"Date & Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z (%z)')}",
        f"Platform: {state.PLATFORM}",
        f"User: {getpass.getuser()}",
        f"Working Directory: {os.getcwd()}",
        f"Script: {state.script_name}",
        f"Log File: {str(state.temp_log)}",
        f"Process ID: {os.getpid()}",
        "=" * 80,
        "",
        "",
        "",
    ]
    for line in lines:
        log.log_only(line)


_SETUP_ASSIGN_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<val>.*)$")


def load_setup_file_shell_style(setup_path: Path) -> dict[str, str]:
    """Load setup variables from a shell-style setup file.

    The Bash version uses `source "$setup_file"`, meaning the file is expected
    to contain simple KEY='value' assignments.

    This function parses those assignments and returns a dict with the same
    variable names.
    """

    if not setup_path.exists():
        raise FileNotFoundError(f"Setup file not found: {setup_path}")

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
    """Update or append KEY='value' in the shell-style setup file."""

    lines = setup_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=False)
    out: list[str] = []
    found = False
    key_prefix = f"{key}="

    for line in lines:
        if line.strip().startswith(key_prefix):
            out.append(f"{key}='{value}'")
            found = True
        else:
            out.append(line)

    if not found:
        out.append(f"{key}='{value}'")

    setup_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def check_required_commands(required_cmds: list[str], log: TeeLogger, PLATFORM: str) -> None:
    """Check that required external commands are available on PATH."""

    missing = [cmd for cmd in required_cmds if shutil.which(cmd) is None]
    if missing:
        log.writeln(f"❌ Missing required commands: {', '.join(missing)}")
        for cmd in missing:
            if cmd in ["targen", "chartread", "colprof", "printtarg", "profcheck", "dispcal"]:
                if PLATFORM == "linux":
                    log.writeln("On Linux, install ArgyllCMS with: sudo apt update && sudo apt install argyll")
                elif PLATFORM == "macos":
                    log.writeln("On macOS, install ArgyllCMS with: brew install argyllcms")
                elif PLATFORM == "windows":
                    log.writeln("On Windows, download and install ArgyllCMS from https://www.argyllcms.com/")
                break  # Only show once for Argyll tools
        raise SystemExit(1)


def run_cmd(args: list[str], log: TeeLogger, cwd: Optional[Path] = None) -> int:
    """Run external command and stream combined stdout/stderr to logger."""

    log.writeln("")
    log.writeln(f"Command Used: {' '.join(args)}")

    # Stream output line-by-line so it goes to both terminal and log.
    try:
        proc = subprocess.Popen(
            args,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        log.writeln(f"❌ Command not found: {args[0]}")
        return 127

    assert proc.stdout is not None
    for line in proc.stdout:
        log.write(line)

    proc.wait()
    return int(proc.returncode)


def _split_cfg_args(cfg_value: str) -> list[str]:
    """Split a shell-like argument string from the setup file.

    The Bash version stores command argument groups as strings like "-v -d2 -G".
    We parse them using shlex so quoting (if present) is preserved.
    """

    s = (cfg_value or "").strip()
    if not s:
        return []
    return shlex.split(s)


def pick_file_gui(title: str, filetypes: list[tuple[str, str]], initialdir: Optional[Path] = None) -> Optional[str]:
    """GUI file picker using tkinter. Returns path or None if cancelled.

    tkinter is a required dependency for this port (no console fallback).
    """

    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as e:
        raise RuntimeError(
            "tkinter is required for file selection dialogs but is not available in this Python installation."
        ) from e

    root = tk.Tk()
    root.geometry("1x1+0+0")  # Place off-screen to avoid visible window

    try:
        # Try to place dialog on top and ensure focus
        root.wm_attributes("-topmost", 1)
    except Exception:
        pass

    root.lift()  # Bring to front
    root.focus_force()  # Force focus

    import time
    time.sleep(0.1)  # Short delay to ensure focus takes effect

    kwargs: dict[str, object] = {
        "title": title,
        "filetypes": filetypes,
        "parent": root,  # Set root as parent to ensure dialog inherits focus
    }
    if initialdir is not None:
        kwargs["initialdir"] = str(initialdir)

    path = filedialog.askopenfilename(**kwargs)
    try:
        root.destroy()
    except Exception:
        pass

    return path or None


def _collect_matching_tifs(source_folder: Path, name: str) -> list[Path]:
    """Return matching .tif files for a base name.

    Mirrors Bash behavior:
    - single-page: <name>.tif
    - multi-page:  <name>_01.tif, <name>_02.tif, ... (pattern _??.tif)
    """

    single = source_folder / f"{name}.tif"
    if single.is_file():
        return [single]

    files = sorted(source_folder.glob(f"{name}_??.tif"))
    return [p for p in files if p.is_file()]


def _copy_or_overwrite_submenu(
    state: AppState,
    cfg: dict[str, str],
    log: TeeLogger,
    overwrite_message_line_1: str,
    overwrite_message_line_2: Optional[str],
) -> bool:
    """Show the copy/overwrite/abort submenu used by select_ti2_file/select_ti3_file/select_ti3_file_only.

    This is a direct port of the Bash submenu text and behavior.
    """

    _ = (cfg,)
    while True:
        log.writeln("")
        log.writeln("")
        log.writeln("Do you want to:")
        log.writeln("")
        log.writeln("1: Create new profile (copy files into new folder)")
        log.writeln(overwrite_message_line_1)
        if overwrite_message_line_2 is not None:
            log.writeln(overwrite_message_line_2)
        log.writeln("3: Abort operation")
        log.writeln("")

        print("Enter your choice [1-3]: ", end='', flush=True)
        copy_choice = getch()
        print(copy_choice, flush=True)
        log.writeln("")

        if copy_choice == "1":
            if not prepare_profile_folder(state, cfg, log):
                log.writeln("Profile preparation failed...")
                return False

            if not copy_files_ti1_ti2_ti3_tif(state, cfg, log):
                log.writeln("File copy failed...")
                return False

            if not rename_files_ti1_ti2_ti3_tif(state, cfg, log):
                log.writeln("File renaming failed...")
                return False

            if not check_files_in_new_location_after_copy(state, cfg, log):
                log.writeln("File check after copy failed...")
                return False
            return True

        if copy_choice == "2":
            state.profile_folder = state.source_folder
            log.writeln("✅ Working folder for profile:")
            log.writeln(state.profile_folder)
            try:
                os.chdir(state.profile_folder)
            except OSError:
                log.writeln(f"❌ Failed to change directory to '{state.profile_folder}'")
                return False
            return True

        if copy_choice == "3":
            log.writeln("User chose to abort.")
            return False

        log.writeln("Invalid selection. Please choose 1 or 2.")


def select_file(state: AppState, cfg: dict[str, str], log: TeeLogger) -> bool:
    """Unified file selection function driven by state.action.

    This merges the logic of:
    - select_ti2_file (main menu action 3)
    - select_ti3_file (main menu action 2)
    - select_ti3_file_only (main menu actions 4 and 5)
    - select_icc_profile (setup menu action 6)

    The goal is to preserve messages, validation rules, and submenu timing.
    """

    if state.action == "6":
        log.writeln("")
        log.writeln("Select a new ICC/ICM profile to use")
        log.writeln("")

        current_path = Path(cfg.get("PRINTER_ICC_PATH", "") or "")
        initialdir = current_path.parent if str(current_path) else Path.cwd()
        title = "Select a new profile (.icc or .icm)"
        filetypes = [("ICC/ICM profiles", "*.icc *.icm"), ("All files", "*")]
        allowed_suffixes = {".icc", ".icm"}
        invalid_suffix_message = "❌ Selected file is not a .icc or .icm file."
    elif state.action == "3":
        initialdir = state.script_dir / cfg.get("PRE_MADE_TARGETS_FOLDER", "Pre-made_Targets")
        title = state.dialog_title
        filetypes = [("Target Information 2 data", "*.ti2"), ("All files", "*")]
        allowed_suffixes = {".ti2"}
        invalid_suffix_message = "❌ Selected file is not a .ti2 file."
    elif state.action in {"2", "4", "5"}:
        initialdir = state.script_dir / cfg.get("CREATED_PROFILES_FOLDER", "Created_Profiles")
        title = state.dialog_title
        filetypes = [("Target Information 3 data", "*.ti3"), ("All files", "*")]
        allowed_suffixes = {".ti3"}
        invalid_suffix_message = "❌ Selected file is not a .ti3 file."
    else:
        log.writeln(f"❌ Unsupported action for file selection: {state.action}")
        return False

    # Capture the ID of the currently active window (terminal) for later focus return on Linux
    term_win_id = None
    if state.PLATFORM == "linux":
        # Try xdotool first for getting active window
        if shutil.which("xdotool"):
            try:
                result = subprocess.run(["xdotool", "getactivewindow"], capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    term_win_id = result.stdout.strip()
            except subprocess.TimeoutExpired:
                pass
        # Fallback to xprop if xdotool not available
        elif shutil.which("xprop"):
            try:
                result = subprocess.run(["xprop", "-root", "_NET_ACTIVE_WINDOW"], capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    term_win_id = result.stdout.split()[-1].strip()
            except subprocess.TimeoutExpired:
                pass

    try:
        selected = pick_file_gui(
            title=title,
            filetypes=filetypes,
            initialdir=initialdir,
        )
    except RuntimeError as e:
        log.writeln(f"❌ {e}")
        return False

    # Bring focus back to terminal after dialog closes (for cancel/exit and successful selection)
    if state.PLATFORM == "macos":
        # Use osascript to activate Terminal and set frontmost
        subprocess.run(["osascript", "-e", 'tell application "Terminal" to activate', "-e", 'tell application "System Events" to set frontmost of process "Terminal" to true'], check=False)
    elif state.PLATFORM == "windows":
        # Use Windows API to set console window as foreground
        import ctypes
        ctypes.windll.user32.SetForegroundWindow(ctypes.windll.kernel32.GetConsoleWindow())
    elif state.PLATFORM == "linux":
        # Use xdotool or wmctrl to activate the captured window
        if term_win_id:
            if shutil.which("xdotool"):
                subprocess.run(["xdotool", "windowactivate", term_win_id], check=False)
            elif shutil.which("wmctrl"):
                subprocess.run(["wmctrl", "-ia", term_win_id], check=False)

    if not selected:
        log.writeln("Selection cancelled.")
        log.writeln("")
        return False

    p = Path(selected).expanduser().resolve()
    if p.suffix.lower() not in allowed_suffixes:
        log.writeln(invalid_suffix_message)
        return False

    if state.action == "6":
        state.new_icc_path = str(p)
        log.writeln(f"Selected profile: {state.new_icc_path}")
        return True

    state.name = p.stem
    state.desc = state.name
    state.source_folder = str(p.parent)

    if state.action == "3":
        log.writeln(f"Selected .ti2 file: {str(p)}")
    else:
        log.writeln(f"Selected .ti3 file: {str(p)}")

    source_folder_path = Path(state.source_folder)

    # select_ti3_file: require matching .ti2
    if state.action == "2":
        ti2_path = source_folder_path / f"{state.name}.ti2"
        if not ti2_path.is_file():
            log.writeln(f"❌ Matching .ti2 file not found for '{state.name}'.")
            return False

    # select_ti3_file_only (action 5): require matching .icc
    if state.action == "5":
        icc_path = source_folder_path / f"{state.name}.icc"
        if not icc_path.is_file():
            log.writeln(f"❌ Matching .icc file not found for '{state.name}'.")
            return False

    # select_ti2_file and select_ti3_file: require matching TIFF targets
    if state.action in {"2", "3"}:
        tif_files = _collect_matching_tifs(source_folder_path, state.name)
        if not tif_files:
            log.writeln(f"❌ No matching .tif target images found for '{state.name}'.")
            return False
        state.tif_files = tif_files

        log.writeln("Found target image(s):")
        log.writeln("")
        for f in state.tif_files:
            log.writeln(f"  {f.name}")

    # select_ti3_file_only: set working folder immediately
    if state.action in {"4", "5"}:
        state.profile_folder = state.source_folder
        log.writeln("✅ Working folder for profile:")
        log.writeln(state.profile_folder)
        try:
            os.chdir(state.profile_folder)
        except OSError:
            log.writeln(f"❌ Failed to change directory to '{state.profile_folder}'")
            return False

    # Submenu timing differences:
    # - select_ti2_file: always show submenu
    # - select_ti3_file: always show submenu
    # - select_ti3_file_only: show submenu only for action 4
    if state.action == "3":
        return _copy_or_overwrite_submenu(
            state,
            cfg,
            log,
            overwrite_message_line_1="2: Overwrite existing (use files in their current location, ",
            overwrite_message_line_2="   existing .ti3 and .icc/icm files will be overwritten)",
        )

    if state.action == "2":
        return _copy_or_overwrite_submenu(
            state,
            cfg,
            log,
            overwrite_message_line_1="2: Overwrite existing (use files in their current location, measurement will",
            overwrite_message_line_2="   resume using existing .ti3 and .icc/icm file will be overwritten)",
        )

    if state.action == "4":
        return _copy_or_overwrite_submenu(
            state,
            cfg,
            log,
            overwrite_message_line_1="2: Overwrite existing (use files in their current location,",
            overwrite_message_line_2="   existing .icc/icm file will be overwritten)",
        )

    return True


# ------------------- Ported function stubs (to be filled) -------------------


def print_profile_name_menu(log: TeeLogger, cfg: dict[str, str], last_line: str, current_name: str | None = None, show_example: bool = True, current_display: str | None = None) -> None:
    example = cfg.get("EXAMPLE_FILE_NAMING", "")
    log.writeln("")
    log.writeln("")
    log.writeln("")
    log.writeln("─────────────────────────────────────────────────────────────────────")
    log.writeln("Specify Profile Description / File Name")
    log.writeln("─────────────────────────────────────────────────────────────────────")
    log.writeln("")
    log.writeln("The following is highly recommended to include:")
    log.writeln("  - Printer ID")
    log.writeln("  - Paper ID")
    log.writeln("  - Color Space")
    log.writeln("  - Target used for profile")
    log.writeln("  - Instrument/calibration type used")
    log.writeln("  - Date created")
    log.writeln("")
    if show_example:
        log.writeln("Example file naming convention (select and copy):")
        if example:
            log.writeln(f"{example}")
        log.writeln("")
        log.writeln("For simplicity, profile description and filename are made identical.")
        log.writeln("The profile description is what you will see in Photoshop and ColorSync Utility.")
        log.writeln("")
        log.writeln("Enter a desired filename for this profile.")
        log.writeln("If your filename is foobar, your profile will be named foobar.icc.")
        log.writeln("")
    if not current_display and current_name:
        current_display = f"Current name: {current_name}"
    if current_display:
        log.writeln(current_display)
        log.writeln("")
    log.writeln("Valid values: Letters A–Z a–z, digits 0–9, dash -, underscore _, parentheses ( ), dot .")
    log.writeln(last_line)
    log.writeln("")


def prepare_profile_folder(state: AppState, cfg: dict[str, str], log: TeeLogger) -> bool:
    """Create/select profile folder (port of Bash prepare_profile_folder)."""

    if not state.name:
        log.writeln("❌ name variable not set")
        return False

    if not state.action:
        log.writeln("❌ action variable not set")
        return False

    created_profiles_folder = cfg.get("CREATED_PROFILES_FOLDER", "Created_Profiles")

    # Default fallback
    state.new_name = state.name

    # Do only if action 2 or 3 or 4
    if state.action in {"2", "3", "4"}:
        if state.action == "4":
            allow_empty = False
            prompt = "Enter filename: "
            last_line = "Leave empty to cancel."
        else:
            allow_empty = True
            prompt = "Enter filename (leave empty to keep current): "
            last_line = "Leave empty to keep current name."

        print_profile_name_menu(log, cfg, last_line, state.name)

        while True:
            name = input(prompt).strip()

            if not name:
                if allow_empty:
                    state.new_name = state.name
                    break
                else:
                    log.writeln("⏎ Input cancelled. Returning to previous menu...")
                    return False

            if not re.fullmatch(r"[A-Za-z0-9._()\-]+", name):
                log.writeln("❌ Invalid file name characters. Please try again.")
                continue

            state.new_name = name
            break

    while True:
        profile_folder = state.script_dir / created_profiles_folder / state.new_name

        if profile_folder.is_dir():
            log.writeln("")
            log.writeln(f"⚠️ Profile folder already exists: '{str(profile_folder)}'")
            log.writeln("")
            log.writeln("Contents:")
            try:
                for p in sorted(profile_folder.iterdir()):
                    log.writeln(f"  {p.name}")
            except OSError:
                log.writeln("  (Unable to list contents of '{str(profile_folder)}')")
            log.writeln("")
            log.writeln("Choose an option:")
            log.writeln("  1) Use existing folder (delete existing files)")
            log.writeln("  2) Enter a different name")
            log.writeln("  3) Cancel operation")
            log.writeln("")
            while True:
                print("Enter choice [1-3]: ", end='', flush=True)
                choice = getch()
                print(choice, flush=True)
                log.writeln("")
                if choice == "1":
                    log.writeln("")
                    log.writeln(f"Using existing folder: '{str(profile_folder)}'")
                    # Delete existing contents to avoid leftover files from previous runs
                    for item in profile_folder.iterdir():
                        try:
                            if item.is_file() or item.is_symlink():
                                item.unlink()
                            elif item.is_dir():
                                shutil.rmtree(item)
                        except OSError as e:
                            log.writeln(f"⚠️ Warning: Failed to delete {item.name}: {e}")
                    break
                if choice == "2":
                    # Show the menu again for re-entering name
                    allow_empty = False
                    prompt = "Enter filename: "
                    last_line = "Leave empty to cancel."
                    print_profile_name_menu(log, cfg, last_line, state.name)

                    while True:
                        name = input(prompt).strip()

                        if not name:
                            log.writeln("⏎ Input cancelled. Returning to previous menu...")
                            return False

                        if not re.fullmatch(r"[A-Za-z0-9._()\-]+", name):
                            log.writeln("❌ Invalid file name characters. Please try again.")
                            continue

                        state.new_name = name
                        break
                    profile_folder = state.script_dir / created_profiles_folder / state.new_name
                    break
                if choice == "3":
                    log.writeln("")
                    log.writeln("Creating profile folder cancelled.")
                    return False
                log.writeln("❌ Invalid choice. Please enter 1, 2, or 3.")

            if choice == "2":
                continue
        break

    try:
        profile_folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        log.writeln(f"❌ Failed to create profile folder: '{str(profile_folder)}'")
        return False

    log.writeln("✅ Working folder for profile:")
    log.writeln(f"'{str(profile_folder)}'")
    try:
        os.chdir(profile_folder)
    except OSError:
        log.writeln(f"❌ Failed to change directory to '{str(profile_folder)}'")
        return False

    state.profile_folder = str(profile_folder)
    state.desc = state.new_name
    return True


def copy_files_ti1_ti2_ti3_tif(state: AppState, cfg: dict[str, str], log: TeeLogger) -> bool:
    """Copy relevant .ti1/.ti2/.ti3/.tif files into working folder."""

    _ = (cfg,)
    if not state.source_folder or not state.profile_folder:
        return False

    source = Path(state.source_folder)
    dest = Path(state.profile_folder)

    def _copy_if_exists(path: Path, required: bool, missing_message: str) -> bool:
        if not state.name or not path.is_file():
            if required:
                log.writeln(missing_message)
                return False
            if missing_message:
                log.writeln(missing_message)
            return True
        if path.parent == dest:
            return True
        try:
            shutil.copy2(path, dest / path.name)
        except OSError:
            log.writeln(f"❌ Failed to copy {path.name} to directory '{str(dest)}'")
            log.writeln("Profile folder is left as is:")
            log.writeln(f"'{str(dest)}'")
            return False
        return True

    # .ti1 is optional
    if not _copy_if_exists(
        source / f"{state.name}.ti1",
        required=False,
        missing_message=f"⚠️ .ti1 file not found for '{state.name}'. Ignoring.",
    ):
        return False

    # .ti2 required unless action 4
    if state.action == "4":
        if not _copy_if_exists(
            source / f"{state.name}.ti2",
            required=False,
            missing_message=f"⚠️ .ti2 file not found for '{state.name}'. Ignoring.",
        ):
            return False
    else:
        if not _copy_if_exists(
            source / f"{state.name}.ti2",
            required=True,
            missing_message=f"❌ .ti2 file not found for '{state.name}'.",
        ):
            return False

    # .ti3 required for action 2 or 4
    if state.action in {"2", "4"}:
        if not _copy_if_exists(
            source / f"{state.name}.ti3",
            required=True,
            missing_message=f"❌ .ti3 file not found for '{state.name}'.",
        ):
            return False

    for f in state.tif_files:
        if f.parent == dest:
            continue
        try:
            shutil.copy2(f, dest / f.name)
        except OSError:
            log.writeln(f"❌ Failed to copy {f.name} to '{str(dest)}'")
            log.writeln("Profile folder is left as is:")
            log.writeln(f"'{str(dest)}'")
            return False

    return True


def rename_files_ti1_ti2_ti3_tif(state: AppState, cfg: dict[str, str], log: TeeLogger) -> bool:
    """Rename files to new basename (port of Bash rename_files_ti1_ti2_ti3_tif)."""

    _ = (cfg,)
    if not state.profile_folder:
        return False

    profile_folder = Path(state.profile_folder)
    if Path.cwd().resolve() != profile_folder.resolve():
        log.writeln(f"⚠️ Not in profile folder. Current: {Path.cwd()}")
        log.writeln(f"🔄 Attempting to change to profile folder: '{str(profile_folder)}'")
        try:
            os.chdir(profile_folder)
            log.writeln("✅ Successfully changed to profile folder")
        except OSError:
            log.writeln("❌ Failed to change to profile folder.")
            log.writeln("Existing files are left in profile folder:")
            log.writeln(f"'{str(profile_folder)}'")
            return False

    log.writeln("Renaming files to match new profile name…")

    def _rename_if_exists(old: Path, new: Path, error_msg: str) -> bool:
        if not old.is_file():
            return True
        try:
            old.rename(new)
        except OSError:
            log.writeln(error_msg)
            log.writeln("Existing files are left in profile folder:")
            log.writeln(f"'{str(profile_folder)}'")
            return False
        return True

    if not _rename_if_exists(
        profile_folder / f"{state.name}.ti1",
        profile_folder / f"{state.new_name}.ti1",
        f"❌ Failed to rename {state.name}.ti1 → {state.new_name}.ti1",
    ):
        return False

    if not _rename_if_exists(
        profile_folder / f"{state.name}.ti2",
        profile_folder / f"{state.new_name}.ti2",
        f"❌ Failed to rename {state.name}.ti2 → {state.new_name}.ti2",
    ):
        return False

    if state.action in {"2", "4"}:
        if not _rename_if_exists(
            profile_folder / f"{state.name}.ti3",
            profile_folder / f"{state.new_name}.ti3",
            f"❌ Failed to rename {state.name}.ti3 → {state.new_name}.ti3",
        ):
            return False

    new_tifs: list[Path] = []
    for f in state.tif_files:
        ext = f.suffix
        base = f.stem
        suffix = ""
        m = re.search(r"_[0-9]{2}$", base)
        if m:
            suffix = m.group(0)
        new_name = f"{state.new_name}{suffix}{ext}"
        old_path = profile_folder / f.name
        new_path = profile_folder / new_name
        if not old_path.is_file():
            continue
        try:
            old_path.rename(new_path)
        except OSError:
            log.writeln(f"❌ Failed to rename {old_path.name} → {new_path.name}")
            log.writeln("Existing files are left in profile folder:")
            log.writeln(f"'{str(profile_folder)}'")
            return False
        new_tifs.append(new_path)

    state.tif_files = new_tifs
    state.name = state.new_name
    state.desc = state.new_name
    return True


def specify_profile_name(state: AppState, cfg: dict[str, str], log: TeeLogger) -> bool:
    """Prompt for profile name (port of Bash specify_profile_name)."""

    while True:
        print_profile_name_menu(log, cfg, "Leave empty to cancel and return to previous menu.")

        name = input("Enter filename: ").strip()

        if not name:
            log.writeln("⏎ Input cancelled. Returning to previous menu...")
            return False

        if not re.fullmatch(r"[A-Za-z0-9._()\-]+", name):
            log.writeln("❌ Invalid file name characters. Please try again.")
            continue

        break

    state.name = name
    state.new_name = name
    state.desc = name

    if not prepare_profile_folder(state, cfg, log):
        log.writeln("Profile preparation failed...")
        return False

    log.writeln("")
    return True


def select_instrument(state: AppState, cfg: dict[str, str], log: TeeLogger) -> bool:
    """Select instrument menu (port of Bash select_instrument)."""

    _ = (cfg,)
    while True:
        log.writeln("")
        log.writeln("")
        log.writeln("─────────────────────────────────────────────────────────────────────")
        log.writeln("Specify Spectrophotometer Model")
        log.writeln("─────────────────────────────────────────────────────────────────────")
        log.writeln("")
        log.writeln("This affects how the target chart is generated.")
        log.writeln("")
        log.writeln("1: i1Pro")
        log.writeln("2: i1Pro3+")
        log.writeln("3: ColorMunki")
        log.writeln("4: DTP20")
        log.writeln("5: DTP22")
        log.writeln("6: DTP41")
        log.writeln("7: DTP51")
        log.writeln("8: SpectroScan")
        log.writeln("9: Abort creating target.")
        log.writeln("")
        log.writeln("Notes:")
        log.writeln("  - A menu of target chart options will be presented next step.")
        log.writeln("  - Option '3: ColorMunki' has a separate configurable menu from the rest.")
        log.writeln("  - The menu option and command arguments for targen and printtarg may be")
        log.writeln("    edited in .ini file.")
        log.writeln("")
        log.writeln("─────────────────────────────────────────────────────────────────────")
        log.writeln("")

        print('Enter your choice [1-9]: ', end='', flush=True)
        answer = getch()
        print(answer, flush=True)

        if not re.fullmatch(r"[1-9]", answer or ""):
            log.writeln("")
            log.writeln("❌ Invalid choice. Please enter a number from 1 to 9.")
            log.writeln("")
            continue

        if answer == "1":
            state.inst_arg = "-ii1"
            state.inst_name = "i1Pro"
            break
        if answer == "2":
            state.inst_arg = "-i3p"
            state.inst_name = "i1Pro3+"
            break
        if answer == "3":
            state.inst_arg = "-iCM -h"
            state.inst_name = "ColorMunki"
            break
        if answer == "4":
            state.inst_arg = "-i20"
            state.inst_name = "DTP20"
            break
        if answer == "5":
            state.inst_arg = "-i22"
            state.inst_name = "DTP22"
            break
        if answer == "6":
            state.inst_arg = "-i41"
            state.inst_name = "DTP41"
            break
        if answer == "7":
            state.inst_arg = "-i51"
            state.inst_name = "DTP51"
            break
        if answer == "8":
            state.inst_arg = "-iSS"
            state.inst_name = "SpectroScan"
            break

        log.writeln("")
        log.writeln("Aborting creating target.")
        return False

    log.writeln("")
    log.writeln(f"Selected instrument: {state.inst_name}")
    log.writeln("")
    return True


def specify_and_generate_target(state: AppState, cfg: dict[str, str], log: TeeLogger) -> bool:
    """Target generation menu and targen/printtarg execution."""

    def menu_info_common_settings() -> None:
        log.writeln("Common settings for targen defined in setup file: ")
        log.writeln(f"      - Arguments set: {cfg.get('COMMON_ARGUMENTS_TARGEN', '')}")
        log.writeln(f"      - Ink limit -l: {cfg.get('INK_LIMIT', '')}")
        log.writeln("      - Pre-conditioning profile specified -c:")
        log.writeln(f"        '{cfg.get('PRECONDITIONING_PROFILE_PATH', '')}'")
        log.writeln("Common settings for printtarg defined in setup file: ")
        log.writeln(f"      - Arguments set: {cfg.get('COMMON_ARGUMENTS_PRINTTARG', '')}")
        log.writeln(
            f"      - Paper size -p: {cfg.get('PAPER_SIZE', '')}, Target resolution -T: {cfg.get('TARGET_RESOLUTION', '')} dpi"
        )
        log.writeln("Common settings for chartread defined in setup file: ")
        log.writeln(f"      - Arguments set: {cfg.get('COMMON_ARGUMENTS_CHARTREAD', '')}")
        log.writeln(
            f"      - Patch consistency tolerance per strip -T: {cfg.get('STRIP_PATCH_CONSISTENSY_TOLERANCE', '')}"
        )
        log.writeln("Common settings for coprof defined in setup file: ")
        log.writeln(f"      - Arguments set: {cfg.get('COMMON_ARGUMENTS_COLPROF', '')}")
        log.writeln(f"      - Average deviation/smooting -r: {cfg.get('PROFILE_SMOOTING', '')}")
        log.writeln("      - Color space profile specified, gamut mapping -S:")
        log.writeln(f"        '{cfg.get('PRINTER_ICC_PATH', '')}'")
        log.writeln("")
        log.writeln("Notes on generating target charts:")
        log.writeln("")
        log.writeln(
            "  When making targets with argyllcms targen, often two very light coloured patches"
        )
        log.writeln(
            "  come next to each other (especially if there are multiple white patches), and targen"
        )
        log.writeln(
            "  leaves the spacer between them also white (not black as it should be), which then"
        )
        log.writeln("  results in error “Not enough few patches” during reading of chart.")
        log.writeln(
            "  To prevent this, review the targets before printing to see if any light colored patches"
        )
        log.writeln(
            "  are next to each other, and if the spacer is close in color. If there are, re-generate"
        )
        log.writeln(
            "  the targets until it is acceptable. If this situation persists, this may be reason to"
        )
        log.writeln(
            "  choose a pre-made target (option 3. in main menu)."
        )
        log.writeln("")

    def menu_info_other_instruments() -> None:
        for i in range(1, 7):
            pc = cfg.get(f"INST_OTHER_MENU_OPTION{i}_PATCH_COUNT_f", "")
            desc = cfg.get(f"INST_OTHER_MENU_OPTION{i}_DESCRIPTION", "")
            log.writeln(f"{i}: {pc} patches {desc}")
        log.writeln("7: Custom – Specify arugments independend of setup parameters")
        log.writeln("8: Abort printing target.")

    def default_target() -> dict[str, str]:
        # This function ports the default_target() selection logic.
        paper = cfg.get("PAPER_SIZE", "")
        inst_name = state.inst_name

        if inst_name == "ColorMunki":
            if paper == "A4":
                patch_count = cfg.get("INST_CM_MENU_OPTION2_PATCH_COUNT_A4_f", "")
            elif paper == "Letter":
                patch_count = cfg.get("INST_CM_MENU_OPTION2_PATCH_COUNT_LETTER_f", "")
            else:
                patch_count = cfg.get("INST_OTHER_MENU_OPTION2_PATCH_COUNT_f", "")

            if paper in {"A4", "Letter"}:
                suffix = "A4" if paper == "A4" else "LETTER"
                return {
                    "label": "Medium (default)",
                    "patch_count": patch_count,
                    "white_patches": cfg.get(f"INST_CM_MENU_OPTION2_WHITE_PATCHES_e", ""),
                    "black_patches": cfg.get(f"INST_CM_MENU_OPTION2_BLACK_PATCHES_B", ""),
                    "gray_steps": cfg.get(f"INST_CM_MENU_OPTION2_GRAY_STEPS_g", ""),
                    "multi_cube_steps": cfg.get(f"INST_CM_MENU_OPTION2_MULTI_CUBE_STEPS_m", ""),
                    "multi_cube_surface_steps": cfg.get(f"INST_CM_MENU_OPTION2_MULTI_CUBE_SURFACE_STEPS_M", ""),
                    "scale_patch_and_spacer": cfg.get(f"INST_CM_MENU_OPTION2_SCALE_PATCH_AND_SPACER_a", ""),
                    "scale_spacer": cfg.get(f"INST_CM_MENU_OPTION2_SCALE_SPACER_A", ""),
                    "layout_seed": cfg.get(f"INST_CM_MENU_OPTION2_LAYOUT_SEED_R", ""),
                }
            return {
                "label": "Medium (default)",
                "patch_count": patch_count,
                "white_patches": cfg.get("INST_OTHER_MENU_OPTION2_WHITE_PATCHES_e", ""),
                "black_patches": cfg.get("INST_OTHER_MENU_OPTION2_BLACK_PATCHES_B", ""),
                "gray_steps": cfg.get("INST_OTHER_MENU_OPTION2_GRAY_STEPS_g", ""),
                "multi_cube_steps": cfg.get("INST_OTHER_MENU_OPTION2_MULTI_CUBE_STEPS_m", ""),
                "multi_cube_surface_steps": cfg.get("INST_OTHER_MENU_OPTION2_MULTI_CUBE_SURFACE_STEPS_M", ""),
                "scale_patch_and_spacer": cfg.get("INST_OTHER_MENU_OPTION2_SCALE_PATCH_AND_SPACER_a", ""),
                "scale_spacer": cfg.get("INST_OTHER_MENU_OPTION2_SCALE_SPACER_A", ""),
                "layout_seed": cfg.get("INST_CM_MENU_OPTION2_LAYOUT_SEED_R", ""),
            }

        return {
            "label": "Medium (default)",
            "patch_count": cfg.get("INST_OTHER_MENU_OPTION2_PATCH_COUNT_f", ""),
            "white_patches": cfg.get("INST_OTHER_MENU_OPTION2_WHITE_PATCHES_e", ""),
            "black_patches": cfg.get("INST_OTHER_MENU_OPTION2_BLACK_PATCHES_B", ""),
            "gray_steps": cfg.get("INST_OTHER_MENU_OPTION2_GRAY_STEPS_g", ""),
            "multi_cube_steps": cfg.get("INST_OTHER_MENU_OPTION2_MULTI_CUBE_STEPS_m", ""),
            "multi_cube_surface_steps": cfg.get("INST_OTHER_MENU_OPTION2_MULTI_CUBE_SURFACE_STEPS_M", ""),
            "scale_patch_and_spacer": cfg.get("INST_OTHER_MENU_OPTION2_SCALE_PATCH_AND_SPACER_a", ""),
            "scale_spacer": cfg.get("INST_OTHER_MENU_OPTION2_SCALE_SPACER_A", ""),
            "layout_seed": cfg.get("INST_CM_MENU_OPTION2_LAYOUT_SEED_R", ""),
        }

    def _targen_args_from_selection(sel: dict[str, str], targen_command_custom: str, is_custom: bool) -> list[str]:
        if is_custom:
            args = _split_cfg_args(targen_command_custom)
        else:
            args = _split_cfg_args(cfg.get("COMMON_ARGUMENTS_TARGEN", ""))

            ink_limit = cfg.get("INK_LIMIT", "")
            if ink_limit:
                args.append(f"-l{ink_limit}")

            def _add_flag(flag: str, key: str) -> None:
                v = sel.get(key, "")
                if v:
                    args.append(f"-{flag}{v}")

            _add_flag("e", "white_patches")
            _add_flag("B", "black_patches")
            _add_flag("g", "gray_steps")
            _add_flag("m", "multi_cube_steps")
            _add_flag("M", "multi_cube_surface_steps")
            if sel.get("patch_count", ""):
                args.append(f"-f{sel['patch_count']}")

        precon = cfg.get("PRECONDITIONING_PROFILE_PATH", "")
        if precon:
            p = Path(precon).expanduser()
            if not p.is_file():
                log.writeln(f"⚠️ Warning: Pre-conditioning profile not found: '{precon}'")
                log.writeln("   Skipping pre-conditioning profile in targen.")
            else:
                args.extend(["-c", str(p.resolve())])

        args.append(state.name)
        return ["targen", *args]

    def _printtarg_args_from_selection(sel: dict[str, str], printtarg_command_custom: str, is_custom: bool) -> list[str]:
        if is_custom:
            args = _split_cfg_args(printtarg_command_custom)
            args.append(state.name)
            return ["printtarg", *args]

        args = _split_cfg_args(cfg.get("COMMON_ARGUMENTS_PRINTTARG", ""))
        args.extend(_split_cfg_args(state.inst_arg))

        if cfg.get("USE_LAYOUT_SEED_FOR_TARGET", "").lower() == "true":
            layout_seed = sel.get("layout_seed", "")
            if layout_seed:
                args.append(f"-R{layout_seed}")

        target_res = cfg.get("TARGET_RESOLUTION", "")
        if target_res:
            args.append(f"-T{target_res}")

        paper = cfg.get("PAPER_SIZE", "")
        if paper:
            args.append(f"-p{paper}")

        if sel.get("scale_patch_and_spacer", ""):
            args.append(f"-a{sel['scale_patch_and_spacer']}")
        if sel.get("scale_spacer", ""):
            args.append(f"-A{sel['scale_spacer']}")

        args.append(state.name)
        return ["printtarg", *args]

    # ----------------------------- Target selection menu -----------------------------
    label = ""
    targen_command_custom = cfg.get("DEFAULT_TARGEN_COMMAND_CUSTOM", "")
    printtarg_command_custom = cfg.get("DEFAULT_PRINTTARG_COMMAND_CUSTOM", "")
    selection: dict[str, str] = {}
    is_custom = False

    while True:
        paper = cfg.get("PAPER_SIZE", "")
        if state.inst_name == "ColorMunki":
            if paper == "A4":
                log.writeln("")
                log.writeln(
                    f"Below menu choices have been optimized for page size {paper} and {state.inst_name} instrument."
                )
                menu_info_common_settings()
                log.writeln("")
                log.writeln("Select the target size:")
                log.writeln("")
                for i in range(1, 7):
                    pc = cfg.get(f"INST_CM_MENU_OPTION{i}_PATCH_COUNT_A4_f", "")
                    desc = cfg.get(f"INST_CM_MENU_OPTION{i}_A4_DESCRIPTION", "")
                    log.writeln(f"{i}: {pc} patches {desc}")
                log.writeln("7: Custom – Specify arugments independend of setup parameters")
                log.writeln("8: Abort printing target.")
            elif paper == "Letter":
                log.writeln("")
                log.writeln(
                    f"Below menu choices have been optimized for page size {paper} and {state.inst_name} instrument."
                )
                menu_info_common_settings()
                log.writeln("")
                log.writeln("Select the target size:")
                log.writeln("")
                for i in range(1, 7):
                    pc = cfg.get(f"INST_CM_MENU_OPTION{i}_PATCH_COUNT_LETTER_f", "")
                    desc = cfg.get(f"INST_CM_MENU_OPTION{i}_LETTER_DESCRIPTION", "")
                    log.writeln(f"{i}: {pc} patches {desc}")
                log.writeln("7: Custom – Specify arugments independend of setup parameters")
                log.writeln("8: Abort printing target.")
            else:
                log.writeln("")
                log.writeln(f"⚠️ Non-standard printer paper size: PAPER_SIZE \"{paper}\".")
                log.writeln(
                    "USING INSTRUMENT/PAGE INDEPENDENT MENU-PARAMETERS (STARTING WITH INST_OTHER_*)."
                )
                log.writeln("")
                log.writeln("Number of created pages increase with patch count, depending on settings.")
                menu_info_common_settings()
                log.writeln("")
                log.writeln("Select the target size:")
                log.writeln("")
                menu_info_other_instruments()
        else:
            log.writeln("")
            log.writeln("Number of created pages increase with patch count, depending on settings.")
            menu_info_common_settings()
            log.writeln("")
            log.writeln("Select the target size:")
            log.writeln("")
            menu_info_other_instruments()

        log.writeln("")
        print("Enter your choice [1–8]: ", end='', flush=True)
        patch_choice = getch()
        print(patch_choice, flush=True)

        if patch_choice == "8":
            log.writeln("Aborting printing target.")
            return False

        if patch_choice == "7":
            # Custom arguments
            is_custom = True

            while True:
                log.writeln("")
                log.writeln("")
                log.writeln("Specify targen command arguments:")
                log.writeln("Default value specified:")
                log.writeln(f"'{cfg.get('DEFAULT_TARGEN_COMMAND_CUSTOM', '')}'")
                log.writeln("")
                log.writeln(
                    "Notes: - Arguments -l and -c are programatically selected"
                )
                log.writeln(
                    "         (unless empty '' in setup) and should not be specified below."
                )
                precon = cfg.get("PRECONDITIONING_PROFILE_PATH", "")
                if precon:
                    log.writeln("       - Current pre-conditioning profile specified -c:")
                    log.writeln(f"         '{precon}'")
                else:
                    log.writeln("       - Pre-conditioning profile is currently not specified in setup.")
                log.writeln(f"       - Current ink limit specified -l: '{cfg.get('INK_LIMIT', '')}'")
                log.writeln("       - For more information on targen arguments, see argyllcms manual.")
                log.writeln("")
                log.writeln(
                    "Valid values: Letters A–Z a–z, digits 0–9, dash -, underscore _, "
                )
                log.writeln(
                    "              parentheses ( ), forward slash /, space, dot ."
                )
                entered = input("Enter/modify arguments or enter to use default: ")
                if not entered:
                    targen_command_custom = cfg.get("DEFAULT_TARGEN_COMMAND_CUSTOM", "")
                    break
                if not re.fullmatch(r"[A-Za-z0-9._()\/\-\s]+", entered):
                    log.writeln("❌ Invalid characters. Please try again.")
                    continue
                targen_command_custom = entered
                break

            while True:
                log.writeln("")
                log.writeln("")
                log.writeln("Specify printtarg command arguments:")
                log.writeln("Default value specified:")
                log.writeln(f"'{cfg.get('DEFAULT_PRINTTARG_COMMAND_CUSTOM', '')}'")
                log.writeln("")
                log.writeln(
                    "Note: - Previously selected instrument (-i), resolution (-T) "
                )
                log.writeln(
                    "        and page size (-p) must be specified again if desired."
                )
                log.writeln("      - For more information on printtarg arguments, see argyllcms manual.")
                log.writeln("")
                log.writeln(
                    "Valid values: Letters A–Z a–z, digits 0–9, dash -, underscore _, "
                )
                log.writeln(
                    "              parentheses ( ), forward slash /, space, dot ."
                )
                entered = input("Enter/modify arguments or enter to use default: ")
                if not entered:
                    printtarg_command_custom = cfg.get("DEFAULT_PRINTTARG_COMMAND_CUSTOM", "")
                    break
                if not re.fullmatch(r"[A-Za-z0-9._()\/\-\s]+", entered):
                    log.writeln("❌ Invalid characters. Please try again.")
                    continue
                printtarg_command_custom = entered
                break

            label = "Custom"
            selection = {}
        else:
            is_custom = False

            if patch_choice not in {"1", "2", "3", "4", "5", "6"}:
                selection = default_target()
                label = selection["label"]
                log.writeln("Invalid selection. Using default.")
            else:
                i = int(patch_choice)
                # Use instrument-specific or other-instrument keys
                if state.inst_name == "ColorMunki" and cfg.get("PAPER_SIZE", "") in {"A4", "Letter"}:
                    patch_key = f"INST_CM_MENU_OPTION{i}_PATCH_COUNT_{cfg.get('PAPER_SIZE', '').upper()}_f"
                    patch_count = cfg.get(patch_key, "")
                    selection = {
                        "label": {1: "Small", 2: "Medium (default)", 3: "Large", 4: "XL", 5: "XXL", 6: "XXXL"}[i],
                        "patch_count": patch_count,
                        "white_patches": cfg.get(f"INST_CM_MENU_OPTION{i}_WHITE_PATCHES_e", ""),
                        "black_patches": cfg.get(f"INST_CM_MENU_OPTION{i}_BLACK_PATCHES_B", ""),
                        "gray_steps": cfg.get(f"INST_CM_MENU_OPTION{i}_GRAY_STEPS_g", ""),
                        "multi_cube_steps": cfg.get(f"INST_CM_MENU_OPTION{i}_MULTI_CUBE_STEPS_m", ""),
                        "multi_cube_surface_steps": cfg.get(f"INST_CM_MENU_OPTION{i}_MULTI_CUBE_SURFACE_STEPS_M", ""),
                        "scale_patch_and_spacer": cfg.get(f"INST_CM_MENU_OPTION{i}_SCALE_PATCH_AND_SPACER_a", ""),
                        "scale_spacer": cfg.get(f"INST_CM_MENU_OPTION{i}_SCALE_SPACER_A", ""),
                        "layout_seed": cfg.get(f"INST_CM_MENU_OPTION{i}_LAYOUT_SEED_R", ""),
                    }
                else:
                    selection = {
                        "label": {1: "Small", 2: "Medium (default)", 3: "Large", 4: "XL", 5: "XXL", 6: "XXXL"}[i],
                        "patch_count": cfg.get(f"INST_OTHER_MENU_OPTION{i}_PATCH_COUNT_f", ""),
                        "white_patches": cfg.get(f"INST_OTHER_MENU_OPTION{i}_WHITE_PATCHES_e", ""),
                        "black_patches": cfg.get(f"INST_OTHER_MENU_OPTION{i}_BLACK_PATCHES_B", ""),
                        "gray_steps": cfg.get(f"INST_OTHER_MENU_OPTION{i}_GRAY_STEPS_g", ""),
                        "multi_cube_steps": cfg.get(f"INST_OTHER_MENU_OPTION{i}_MULTI_CUBE_STEPS_m", ""),
                        "multi_cube_surface_steps": cfg.get(f"INST_OTHER_MENU_OPTION{i}_MULTI_CUBE_SURFACE_STEPS_M", ""),
                        "scale_patch_and_spacer": cfg.get(f"INST_OTHER_MENU_OPTION{i}_SCALE_PATCH_AND_SPACER_a", ""),
                        "scale_spacer": cfg.get(f"INST_OTHER_MENU_OPTION{i}_SCALE_SPACER_A", ""),
                        "layout_seed": cfg.get(f"INST_CM_MENU_OPTION{i}_LAYOUT_SEED_R", ""),
                    }
                label = selection["label"]

        log.writeln("")
        if label != "Custom":
            log.writeln(f"Selected target: {label} – {selection.get('patch_count', '')} patches")
        else:
            precon = cfg.get("PRECONDITIONING_PROFILE_PATH", "")
            targen_l = f" -l{cfg.get('INK_LIMIT', '')}" if cfg.get("INK_LIMIT", "") else ""
            targen_c = f" -c \"{precon}\"" if precon else ""
            log.writeln("Selected target: - Custom")
            log.writeln(f"                 - targen arguments: {targen_command_custom}{targen_l}{targen_c}")
            log.writeln(f"                 - printtarg arguments: {printtarg_command_custom}")

        while True:
            log.writeln("")
            print("Do you want to continue with selected target? [y/n]: ", end='', flush=True)
            again = getch()
            print(again, flush=True)
            if again.lower() == "y":
                log.writeln("")
                log.writeln("Continuing with selected target...")
                break
            if again.lower() == "n":
                log.writeln("")
                log.writeln("Repeating target selection...")
                break
            log.writeln("")
            log.writeln("Invalid input. Please enter y or n.")
        if again.lower() == "y":
            break

    # --- Execute targen/printtarg -------------------------------------------------
    log.writeln("")
    log.writeln("Generating target color values (.ti1 file)...")

    targen_cmd = _targen_args_from_selection(selection, targen_command_custom, is_custom=is_custom)
    if run_cmd(targen_cmd, log) != 0:
        log.writeln("❌ targen failed. See log for details.")
        return False

    log.writeln("")
    log.writeln("Generating target(s) (.tif image(es) and .ti2 file)...")
    printtarg_cmd = _printtarg_args_from_selection(selection, printtarg_command_custom, is_custom=is_custom)
    if run_cmd(printtarg_cmd, log) != 0:
        log.writeln("❌ printtarg failed. See log for details.")
        return False
    log.writeln("")

    # Detect generated TIFFs (current working dir)
    tif_files = _collect_matching_tifs(Path.cwd(), state.name)
    if not tif_files:
        log.writeln("❌ No TIFF files were created by printtarg.")
        return False
    state.tif_files = tif_files

    log.writeln("Test chart(s) created:")
    log.writeln("")
    for f in state.tif_files:
        log.writeln(f"  {f.name}")
    log.writeln("")

    if state.PLATFORM == "macos" and cfg.get("ENABLE_AUTO_OPEN_IMAGES_WITH_COLOR_SYNC_MAC", "").lower() == "true":
        log.writeln("Please print the test chart(s) and make sure to disable color management.")
        log.writeln("Created Images will open automatically in ColorSync Utility.")
        log.writeln('In the Printer dialog set option "Colour" to "Print as Color Target".')
        app = cfg.get("COLOR_SYNC_UTILITY_PATH", "")
        if app:
            open_cmd = ["open", "-a", app, *[str(p) for p in state.tif_files]]
            run_cmd(open_cmd, log)
    else:
        log.writeln("Please print the test chart(s) and make sure to disable color management.")
        if state.PLATFORM == "macos":
            log.writeln("Use applications like ColorSync Utility, Adobe Color Print Utility or")
            log.writeln("Photoshop etc.")
        else:
            log.writeln("Use applications like ColorSync Utility or Adobe Color Print Utility.")

    log.writeln("")
    log.writeln("")
    log.writeln("After target(s) have been printed...")
    log.writeln("")
    while True:
        print("Do you want to continue with measuring of target? [y/n]: ", end='', flush=True)
        again = getch()
        print(again, flush=True)
        if again.lower() == "y":
            log.writeln("")
            log.writeln("Continuing with measuring of target...")
            break
        if again.lower() == "n":
            log.writeln("")
            log.writeln("Aborting measuring of target...")
            return False
        log.writeln("")
        log.writeln("Invalid input. Please enter y or n.")

    return True


def check_files_in_new_location_after_copy(state: AppState, cfg: dict[str, str], log: TeeLogger) -> bool:
    """Verify copied files (port of Bash check_files_in_new_location_after_copy)."""

    _ = (cfg,)
    if not state.profile_folder or not state.name:
        log.writeln("❌ Required variables not set for file check")
        return False

    profile_folder = Path(state.profile_folder)
    missing_files = False

    # Check .ti2, applicable for action 2+3
    if state.action != "4":
        if not (profile_folder / f"{state.name}.ti2").is_file():
            log.writeln(f"❌ Missing {state.name}.ti2 in {str(profile_folder)}")
            missing_files = True

        tif_files = _collect_matching_tifs(profile_folder, state.name)
        if not tif_files:
            log.writeln(f"❌ No TIFF files found in {str(profile_folder)}")
            missing_files = True
        else:
            state.tif_files = tif_files

    if state.action in {"2", "4"}:
        if not (profile_folder / f"{state.name}.ti3").is_file():
            log.writeln(f"❌ Missing {state.name}.ti3 in {str(profile_folder)}")
            missing_files = True

    if missing_files:
        log.writeln("❌ File copy to profile location failed. Returning to main menu...")
        return False
    return True


def show_de_reference(state: AppState, cfg: dict[str, str], log: TeeLogger) -> None:
    """Print ΔE reference table (port of Bash show_de_reference)."""

    _ = (state, cfg)
    log.writeln("Delta E 2000 (Real-World Accuracy After Profiling)")
    log.writeln("──────────────────────────────────────────────────────────────────────────────")
    log.writeln("                             Typical       Typical          Typical")
    log.writeln("Printer Class                ΔE2000        Substrates       Use Cases")
    log.writeln("──────────────────────────────────────────────────────────────────────────────")
    log.writeln("Professional Photo Inkjet    Avg 0.5-1.5   Gloss,           Gallery,")
    log.writeln("  Example Models:            95% 1.5-2.5   baryta,          contract proofing")
    log.writeln("  Epson P700/P900/P9570,     Max 3-5       fine art")
    log.writeln("  Canon PRO-1000, HP Z9+")
    log.writeln("")
    log.writeln("Prosumer / High-End Inkjet   Avg 0.8-2.0   Premium gloss,   Serious hobby,")
    log.writeln("  Example Models:            95% 2.0-3.5   semi-gloss,      small studio")
    log.writeln("  Epson P600/P800,           Max 4-7")
    log.writeln("  Canon PRO-200/300")
    log.writeln("")
    log.writeln("Consumer Home Inkjet         Avg 1.5-3.0   Glossy, matte,   Casual photo,")
    log.writeln("  Example Models:            95% 3.0-5.0   plain            mixed docs")
    log.writeln("  Canon PIXMA TS/MG,         Max 6-10")
    log.writeln("  Epson EcoTank/Expression")
    log.writeln("")
    log.writeln("Professional Laser /         Avg 1.5-2.5   Coated stock,    Corporate,")
    log.writeln("Production                   95% 3.0-4.0   proof paper      marketing,")
    log.writeln("  Example Models:            Max 5-7                        light proof")
    log.writeln("  Xerox PrimeLink,")
    log.writeln("  Canon imagePRESS")
    log.writeln("  Ricoh Pro C")
    log.writeln("")
    log.writeln("Office / Consumer Laser      Avg 2.5-5.0   Office bond,     Business docs,")
    log.writeln("  Example Models:            95% 4.0-7.0   coated office    presentations")
    log.writeln("  HP Color LaserJet Pro,     Max 7-12+")
    log.writeln("  Brother HL/MFC")
    log.writeln("  Canon i-SENSYS")
    log.writeln("")
    log.writeln("──────────────────────────────────────────────────────────────────────────────")
    log.writeln("")
    log.writeln("Notes:")
    log.writeln("   • Values assume proper ICC profiling and correct media settings")
    log.writeln("   • Avg = overall accuracy, 95% = typical worst case, Max = outliers")
    log.writeln("   • Lower ΔE = higher color accuracy")
    log.writeln("   • ΔE < 1.0 is generally considered visually indistinguishable")
    log.writeln("   • Source of these numbers: https://ChatGPT.com")
    log.writeln("")


def improving_accuracy(state: AppState, cfg: dict[str, str], log: TeeLogger) -> None:
    """Print accuracy improvement tips (port of Bash improving_accuracy)."""

    _ = (state, cfg)
    log.writeln("")
    log.writeln("")
    log.writeln("")
    log.writeln("────────────────────────────────────────────────────────────────")
    log.writeln("Tips on how to improve accuracy of a profile")
    log.writeln("────────────────────────────────────────────────────────────────")
    log.writeln("")
    log.writeln("  1. The top-most lines in the file '*_sanity_check.txt, created'")
    log.writeln("     after a profile is made, are the patches with higest ΔE values.")
    log.writeln("")
    log.writeln("  2. If ΔE values are too large it is recommended to remeasure.")
    log.writeln("      - ΔE > 2 is regarded as clearly visible difference and")
    log.writeln("         should be remeasured (depending on printer type, see")
    log.writeln("         Quick Reference table below or menu option 8).")
    log.writeln("      - ΔE < 1 is considered visually indistinguishable.")
    log.writeln("")
    log.writeln("  3. The 'Largest ΔE' or 'max.' value is an indicator that some")
    log.writeln("     patches should be remeasured.")
    log.writeln("")
    log.writeln("  4. When wanting to remeasure patches to improve overall profile")
    log.writeln("     quality, do the following: ")
    log.writeln("      a. Open file '*_sanity_check.txt' of a created printer")
    log.writeln("         profile and identify which sheets have largest error.")
    log.writeln("         Look at patch ID and find column label on target chart.")
    log.writeln("      b. In main menu, chose option 3, then select the target used")
    log.writeln("         for your profile by selecting")
    log.writeln("         the .ti2 file (files and targets should be in the folder")
    log.writeln("         where your .icc is stored)")
    log.writeln("      c. Select option '1. Create new profile (copy files into")
    log.writeln("         new folder)'. Do not overwrite.")
    log.writeln("      d. Start reading only those strips where high error has been")
    log.writeln("         identified. ")
    log.writeln("         Press 'f' to move forward, or 'b' to move back one strip")
    log.writeln("         at a time while reading.")
    log.writeln("      e. When you have read the appropriate target strips, select")
    log.writeln("         ‘d’ to save and exit.")
    log.writeln("      f. Open the created .ti3 file, and also the original .ti3")
    log.writeln("         for your profile to be improved.")
    log.writeln("         The new .ti3 file has data for read patches below the tag")
    log.writeln("         'BEGIN_DATA', and contain only the lines you re-read.")
    log.writeln("      g. In the original .ti3 file, search for the patch IDs to")
    log.writeln("         identify the lines to replace.")
    log.writeln("         Copy one data line at a time from the new .ti3 file, and")
    log.writeln("         replace the line with same ID in the original .ti3 file.")
    log.writeln("         Then save file.")
    log.writeln("      h. Now choose option 4 in main menu. Select the updated .ti3")
    log.writeln("         file. Now a new .icc profile and and sanity report is")
    log.writeln("         created. Study results and see if the profile is improved.")
    log.writeln("")
    log.writeln("────────────────────────────────────────────────────────────────")
    log.writeln("")


def sanity_check(state: AppState, cfg: dict[str, str], log: TeeLogger) -> bool:
    """Run profcheck and generate sanity report (port of Bash sanity_check)."""

    _ = (cfg,)
    sanity_file = Path(f"{state.name}_sanity_check.txt")

    log.writeln("")
    log.writeln("Performing sanity check (creating .txt file)...")
    log.writeln("")

    log.writeln("Command Used: profcheck -v2 -k -s")
    # Run profcheck and redirect to file
    import subprocess
    with open(sanity_file, "w") as f:
        proc = subprocess.run(
            ["profcheck", "-v2", "-k", "-s", f"{state.name}.ti3", f"{state.name}.icc"],
            stdout=f,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if proc.returncode != 0:
        log.writeln("")
        log.writeln("❌ profcheck failed. See log for details.")
        log.writeln("")
        return False

    # Append empty lines
    with open(sanity_file, "a") as f:
        f.write("\n\n")

    # Extract delta E values
    delta_e_values = []
    with open(sanity_file, "r") as f:
        for line in f:
            m = re.search(r'^\[([0-9]+\.[0-9]+)\].*@', line.strip())
            if m:
                delta_e_values.append(float(m.group(1)))

    if not delta_e_values:
        log.writeln("⚠️ No delta E values found in sanity check file")
        return False

    # Since profcheck -s sorts highest to lowest
    largest = delta_e_values[0]
    smallest = delta_e_values[-1]
    range_val = largest - smallest

    total_patches = len(delta_e_values)

    # Calculate percentiles (round up)
    import math
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
    log.writeln("")
    log.writeln("Delta E Range Analysis:")
    log.writeln(f"  Largest ΔE:  {largest}")
    log.writeln(f"  Smallest ΔE: {smallest}")
    log.writeln("")
    log.writeln("Percentile Values:")
    log.writeln(f"  99th percentile: {percentile_99}")
    log.writeln(f"  98th percentile: {percentile_98}")
    log.writeln(f"  95th percentile: {percentile_95}")
    log.writeln(f"  90th percentile: {percentile_90}")
    log.writeln("")
    log.writeln("Patch Count Analysis:")
    log.writeln(f"  Percent of patches with ΔE<1.0: {percent_lt_1:.1f}%")
    log.writeln(f"  Percent of patches with ΔE<2.0: {percent_lt_2:.1f}%")
    log.writeln(f"  Percent of patches with ΔE<3.0: {percent_lt_3:.1f}%")
    log.writeln("")

    # Append to file
    with open(sanity_file, "a") as f:
        f.write("\n")
        f.write("=== Delta E Range Analysis ===\n")
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
        f.write("================================\n")
        f.write("\n")

    # Run another profcheck and append
    log.writeln("Command Used: profcheck -v -k")
    with open(sanity_file, "a") as f:
        proc2 = subprocess.run(
            ["profcheck", "-v", "-k", f"{state.name}.ti3", f"{state.name}.icc"],
            stdout=f,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if proc2.returncode != 0:
        log.writeln("")
        log.writeln("❌ profcheck failed. See log for details.")
        log.writeln("")
        return False

    log.writeln("")
    log.writeln("Sanity Check Complete")
    log.writeln(f"Detailed sanity check stored in:")
    log.writeln(f"'{sanity_file}'.")
    log.writeln("")

    # Submenu
    while True:
        log.writeln("")
        log.writeln("")
        log.writeln("─────────────────────────────────────────────────────────────────────────")
        log.writeln("What would you like to do?")
        log.writeln("─────────────────────────────────────────────────────────────────────────")
        log.writeln("")
        log.writeln("1) Show tips on how to improve accuracy of a profile")
        log.writeln("2) Show ΔE2000 Color Accuracy — Quick Reference")
        log.writeln("3) Return to main menu")
        log.writeln("")
        log.writeln("─────────────────────────────────────────────────────────────────────────")
        log.writeln("")

        print("Enter your choice [1-3]: ", end='', flush=True)
        choice = getch()
        print(choice, flush=True)

        if choice == "1":
            log.writeln("")
            improving_accuracy(state, cfg, log)
            log.writeln("")
            input("Press enter to continue...")
        elif choice == "2":
            log.writeln("")
            show_de_reference(state, cfg, log)
            log.writeln("")
            input("Press enter to continue...")
        elif choice == "3":
            log.writeln("")
            log.writeln("Returning to main menu...")
            break
        else:
            log.writeln("")
            log.writeln("❌ Invalid choice. Please enter 1, 2, or 3.")
    return True


def file_mtime(path: Path) -> int:
    """Get modification time as integer seconds since epoch."""

    return int(path.stat().st_mtime)


def perform_measurement_and_profile_creation(state: AppState, cfg: dict[str, str], log: TeeLogger) -> bool:
    """Run chartread + colprof (port of Bash perform_measurement_and_profile_creation)."""

    # --- Build chartread arguments conditionally ---------------------------
    chartread_T = ""
    strip_tol = cfg.get("STRIP_PATCH_CONSISTENSY_TOLERANCE", "")
    if strip_tol:
        chartread_T = f"-T{strip_tol}"

    log.writeln("")
    log.writeln("")
    log.writeln("Please connect the spectrophotometer.")
    log.writeln("")
    while True:
        print("Continue? [y/n]: ", end='', flush=True)
        again = getch()
        print(again, flush=True)
        if again.lower() == "y":
            log.writeln("")
            log.writeln("Starting chart reading (read .ti2 file and generate .ti3 file)...")
            break
        if again.lower() == "n":
            log.writeln("")
            log.writeln("Aborting measuring of target...")
            return False
        log.writeln("")
        log.writeln("Invalid input. Please enter y or n.")

    log.writeln("")
    log.writeln("")
    log.writeln("")

    def common_text_tips() -> None:
        log.writeln("Tips:")
        log.writeln("     - Default for reading targets using ArgyllCMS is to start from")
        log.writeln("       column A, from the side where the column letters are, and then")
        log.writeln("       read to the end of the other side of the page.")
        log.writeln("       If not done this way, “unexpected high deviation” message may")
        log.writeln("       appear frequently.")
        log.writeln("     - Enabling bi-directional strip reading (removing -B flag and")
        log.writeln("       adding -b) may cause false indentification of strips when read,")
        log.writeln("       thus it is recommended to not enable this feature for beginners.")
        log.writeln("     - Scanning speed of more than 7 sec per strip reduces frequent")
        log.writeln("       re-reading due to inconsistent results, and increases quality.")
        log.writeln("     - If frequent inconsistent results try altering patch consistency")
        log.writeln("       tolerance parameter in setup (or .ini file).")
        log.writeln("     - Save progress once in a while with 'd' and then")
        log.writeln("       resume measuring with option 2 of main menu.")

    ti3_file = Path(f"{state.name}.ti3")

    # Resume mode (action 2): detect abort by unchanged mtime
    ti3_mtime_before: Optional[int] = None
    if state.action == "2" and ti3_file.exists():
        ti3_mtime_before = file_mtime(ti3_file)

    log.writeln("")
    common_text_tips()
    log.writeln("")

    chartread_args = ["chartread", *_split_cfg_args(cfg.get("COMMON_ARGUMENTS_CHARTREAD", ""))]
    if state.action == "2":
        # Bash: chartread ${COMMON_ARGUMENTS_CHARTREAD} -r${chartread_T} "${name}"
        # where chartread_T is built as " -T<value>" (leading space) => becomes: -r -T<value>
        chartread_args.append("-r")
        if chartread_T:
            chartread_args.append(chartread_T)
    else:
        if chartread_T:
            chartread_args.append(chartread_T)

    chartread_args.append(state.name)

    if run_cmd(chartread_args, log) != 0:
        log.writeln("")
        log.writeln("❌ chartread failed. See log for details.")
        log.writeln("")
        return False

    if state.action == "2":
        if not ti3_file.exists() or ti3_mtime_before is None:
            # If file didn't exist before, fallback to existence check
            if not ti3_file.exists():
                log.writeln("")
                log.writeln("⚠️️ Chartread aborted by user.")
                log.writeln("")
                return False
        else:
            ti3_mtime_after = file_mtime(ti3_file)
            if ti3_mtime_after == ti3_mtime_before:
                log.writeln("")
                log.writeln("⚠️️ Chartread aborted by user (no new measurements written).")
                log.writeln("")
                return False
    else:
        if not ti3_file.exists():
            log.writeln("")
            log.writeln("⚠️️ Chartread aborted by user.")
            log.writeln("")
            return False

    # --- Build colprof arguments conditionally ---------------------------
    colprof_args = ["colprof", *_split_cfg_args(cfg.get("COMMON_ARGUMENTS_COLPROF", ""))]
    ink_limit = cfg.get("INK_LIMIT", "")
    if ink_limit:
        colprof_args.append(f"-l{ink_limit}")
    smoothing = cfg.get("PROFILE_SMOOTING", "")
    if smoothing:
        colprof_args.append(f"-r{smoothing}")
    printer_icc = cfg.get("PRINTER_ICC_PATH", "")
    if printer_icc:
        p = Path(printer_icc).expanduser()
        if not p.is_file():
            log.writeln(f"⚠️ Warning: Printer ICC profile not found: '{printer_icc}'")
            log.writeln("   Skipping printer ICC profile in colprof.")
        else:
            colprof_args.extend(["-S", str(p.resolve())])

    log.writeln("")
    print("Do you want to continue creating profile with resulting ti3 file? [y/n]: ", end='', flush=True)
    cont = getch()
    print(cont, flush=True)
    if cont.lower() != "y":
        log.writeln("")
        log.writeln("Profile creation aborted by user...")
        log.writeln("")
        return False

    log.writeln("")
    log.writeln("")
    log.writeln("Starting profile creation (read .ti3 file and generate .icc file)...")
    colprof_args.extend(["-D", state.desc, state.name])

    if run_cmd(colprof_args, log) != 0:
        log.writeln("")
        log.writeln("❌ colprof failed. See log for details.")
        log.writeln("")
        return False

    log.writeln("")
    log.writeln("Profile created.")
    log.writeln("")

    if not sanity_check(state, cfg, log):
        return False
    return True


def create_profile_from_existing(state: AppState, cfg: dict[str, str], log: TeeLogger) -> bool:
    """Create ICC from existing .ti3 (port of Bash create_profile_from_existing)."""

    # --- Build colprof arguments conditionally ---------------------------
    colprof_args = ["colprof", *_split_cfg_args(cfg.get("COMMON_ARGUMENTS_COLPROF", ""))]
    ink_limit = cfg.get("INK_LIMIT", "")
    if ink_limit:
        colprof_args.append(f"-l{ink_limit}")
    smoothing = cfg.get("PROFILE_SMOOTING", "")
    if smoothing:
        colprof_args.append(f"-r{smoothing}")
    printer_icc = cfg.get("PRINTER_ICC_PATH", "")
    if printer_icc:
        p = Path(printer_icc).expanduser()
        if not p.is_file():
            log.writeln(f"⚠️ Warning: Printer ICC profile not found: '{printer_icc}'")
            log.writeln("   Skipping printer ICC profile in colprof.")
        else:
            colprof_args.extend(["-S", str(p.resolve())])

    log.writeln("")
    log.writeln("")
    log.writeln("Starting profile creation (read .ti3 file and generate .icc file)...")
    log.writeln(f"Command Used: {' '.join(colprof_args)} -D \"{state.desc}\" \"{state.name}\"")
    colprof_args.extend(["-D", state.desc, state.name])

    if run_cmd(colprof_args, log) != 0:
        log.writeln("")
        log.writeln("❌ colprof failed. See log for details.")
        log.writeln("")
        return False

    log.writeln("")
    log.writeln("Profile created.")
    log.writeln("")

    if not sanity_check(state, cfg, log):
        return False
    return True


def install_profile_and_save_data(state: AppState, cfg: dict[str, str], log: TeeLogger) -> bool:
    """Copy ICC into PRINTER_PROFILES_PATH (port of Bash install_profile_and_save_data)."""

    _ = (cfg,)
    log.writeln("Installing measured ICC profile...")

    src = Path(f"{state.name}.icc")
    if not src.is_file():
        log.writeln("")
        log.writeln(f"❌ ICC profile not found: '{src.name}'")
        log.writeln("   Expected it in the current working directory:")
        log.writeln(f"   {Path.cwd()}")
        log.writeln("")
        return False

    dest_dir = cfg.get("PRINTER_PROFILES_PATH", "")
    if not dest_dir:
        log.writeln("")
        log.writeln("❌ PRINTER_PROFILES_PATH is empty. Check setup file.")
        log.writeln("")
        return False

    dest = Path(dest_dir).expanduser()
    if not dest.is_dir():
        log.writeln("")
        log.writeln(f"❌ Destination directory does not exist: '{dest_dir}'")
        log.writeln("   Check PRINTER_PROFILES_PATH in the setup file.")
        log.writeln("")
        return False

    if not os.access(dest, os.W_OK):
        log.writeln("")
        log.writeln(f"❌ Destination directory is not writable: '{dest_dir}'")
        log.writeln("   Check folder permissions or choose a user-writable profile folder.")
        log.writeln("")
        if state.PLATFORM == "linux":
            if dest_dir.startswith("/usr/share/") or dest_dir.startswith("/usr/local/share/"):
                log.writeln("   This is a system folder and typically requires administrator rights.")
                log.writeln("   Options:")
                log.writeln("     1) Change PRINTER_PROFILES_PATH to a user folder (recommended)")
                log.writeln("        e.g. '$HOME/.local/share/color/icc' (create if missing)")
                log.writeln("     2) Or install to the system folder using sudo (advanced)")
                log.writeln(f"        e.g. sudo cp '{src.name}' '{dest_dir}/'")
            log.writeln("")
            log.writeln("   Current permissions:")
            try:
                st = dest.stat()
                log.writeln(f"   mode: {oct(st.st_mode)}")
            except OSError:
                pass
        else:
            log.writeln("   Suggested macOS user profile folder:")
            log.writeln("     '$HOME/Library/ColorSync/Profiles'")
        log.writeln("")
        return False

    try:
        shutil.copy2(src, dest / src.name)
    except OSError:
        log.writeln("")
        log.writeln(f"❌ Failed to copy ICC profile to '{dest_dir}'.")
        log.writeln("   Check folder permissions or disk access. See log for details.")
        log.writeln("")
        return False

    log.writeln(f"Finished. '{src.name}' was installed to the directory '{dest_dir}'")
    log.writeln("Please restart any color-managed applications before using this profile.")
    log.writeln(
        f"To print with this profile in a color-managed workflow, select '{state.desc}' in the profile selection menu."
    )
    return True



def edit_setup_parameters(state: AppState, cfg: dict[str, str], log: TeeLogger) -> None:
    """Interactive edit of setup parameters (port of Bash edit_setup_parameters)."""

    cfg = load_setup_file_shell_style(state.setup_file)
    validate_cfg_paths(cfg, log)

    while True:
        icc_filename = Path(cfg.get("PRINTER_ICC_PATH", "")).name
        precon_icc_filename = Path(cfg.get("PRECONDITIONING_PROFILE_PATH", "")).name

        log.writeln("")
        log.writeln("")
        log.writeln("")
        log.writeln("─────────────────────────────────────────────────────────────────────")
        log.writeln("Change Setup Parameters - Sub-Menu ")
        log.writeln("─────────────────────────────────────────────────────────────────────")
        log.writeln("")
        log.writeln("In this menu some variables stored in the $setup_file file ")
        log.writeln("can be modified. For other parameters modify the file in a text editor.")
        log.writeln("")
        log.writeln("What parameter do you want to modify?")
        log.writeln("")
        log.writeln("1: Select Color Space profile to use when creating printer profile.")
        log.writeln("   (gamut mapping to output profile)")
        log.writeln(f"   Current file specified: '{icc_filename}'")
        log.writeln("")
        log.writeln("2: Select pre-conditioning profile to use when creating target.")
        log.writeln(f"   Current file specified: '{precon_icc_filename}'")
        log.writeln("")
        log.writeln("3: Modify patch consistency tolerance (chartread arg. -T)")
        log.writeln(f"   Current value specified: '{cfg.get('STRIP_PATCH_CONSISTENSY_TOLERANCE', '')}'")
        log.writeln("")
        log.writeln("4: Modify paper size for target generation (printtarg -p). Valid values: A4, Letter.")
        log.writeln(f"   Current value specified: '{cfg.get('PAPER_SIZE', '')}'")
        log.writeln("")
        log.writeln("5: Modify ink limit (targen and colprof -l). Valid values: 0 – 400 (%) or empty to disable.")
        log.writeln(f"   Current value specified: '{cfg.get('INK_LIMIT', '')}'")
        log.writeln("")
        log.writeln("6: Modify file naming convention example (shown in main menu option 1). Valid value: text.")
        log.writeln("   Current value specified:")
        log.writeln(f"   '{cfg.get('EXAMPLE_FILE_NAMING', '')}'")
        log.writeln("")
        log.writeln("7: Go back to main menu.")
        log.writeln("")
        log.writeln("─────────────────────────────────────────────────────────────────────")
        log.writeln("")

        print("Enter your choice [1–7]: ", end='', flush=True)
        answer = getch()
        print(answer, flush=True)

        if answer == "1":
            state.action = "6"
            if select_file(state, cfg, log):
                new_path = state.new_icc_path
                update_setup_value_shell_style(state.setup_file, "PRINTER_ICC_PATH", new_path)
                cfg["PRINTER_ICC_PATH"] = new_path
                log.writeln("✅ Updated PRINTER_ICC_PATH")
            else:
                log.writeln("Selection cancelled.")
            continue

        elif answer == "2":
            state.action = "6"
            if select_file(state, cfg, log):
                new_path = state.new_icc_path
                update_setup_value_shell_style(state.setup_file, "PRECONDITIONING_PROFILE_PATH", new_path)
                cfg["PRECONDITIONING_PROFILE_PATH"] = new_path
                log.writeln("✅ Updated PRECONDITIONING_PROFILE_PATH")
            else:
                log.writeln("Selection cancelled.")
            continue

        elif answer == "3":
            value = input("Enter new value [0.6 recommended]: ").strip()
            if not re.fullmatch(r'^[0-9]+(\.[0-9]+)?$', value):
                log.writeln("❌ Invalid numeric value.")
                continue
            update_setup_value_shell_style(state.setup_file, "STRIP_PATCH_CONSISTENSY_TOLERANCE", value)
            cfg["STRIP_PATCH_CONSISTENSY_TOLERANCE"] = value
            log.writeln(f"✅ Updated STRIP_PATCH_CONSISTENSY_TOLERANCE to {value}")
            continue

        elif answer == "4":
            value = input("Enter paper size [A4 or Letter]: ").strip()
            if value not in ["A4", "Letter"]:
                log.writeln("❌ Invalid paper size.")
                continue
            update_setup_value_shell_style(state.setup_file, "PAPER_SIZE", value)
            cfg["PAPER_SIZE"] = value
            log.writeln(f"✅ Updated PAPER_SIZE to {value}")
            continue

        elif answer == "5":
            value = input("Enter ink limit (0–400 or empty to disable): ").strip()
            if value and (not value.isdigit() or not (0 <= int(value) <= 400)):
                log.writeln("❌ Invalid ink limit.")
                continue
            update_setup_value_shell_style(state.setup_file, "INK_LIMIT", value)
            cfg["INK_LIMIT"] = value
            log.writeln(f"✅ Updated INK_LIMIT to '{value}'")
            continue

        elif answer == "6":
            # Show the menu
            print_profile_name_menu(log, cfg, "", show_example=False, current_display=f"Current value specified:\n'{cfg.get('EXAMPLE_FILE_NAMING', '')}'")
            value = input("Enter example file naming convention: ").strip()
            if not re.fullmatch(r"[A-Za-z0-9._()\-]+", value):
                log.writeln("❌ Invalid file name characters. Please try again.")
                continue
            update_setup_value_shell_style(state.setup_file, "EXAMPLE_FILE_NAMING", value)
            cfg["EXAMPLE_FILE_NAMING"] = value
            log.writeln("")
            log.writeln("✅ Updated file naming convention example to:")
            log.writeln(value)
            log.writeln("")
            continue

        elif answer == "7":
            log.writeln("")
            log.writeln("Returning to main menu...")
            return

        else:
            log.writeln("")
            log.writeln("No valid selection made. Reloading setup menu...")
            continue


def print_banner(log: TeeLogger) -> None:
    """Print the ASCII banner similar to the Bash version."""

    log.writeln("==============================================================")
    log.writeln("    ___        _                        _           _ _       ")
    log.writeln("   / _ \\ _   _| |_ ___  _ __ ___   __ _| |_ ___  __| | |      ")
    log.writeln("  | | | | | | | __/ _ \\| '_ ` _ \\ / _` | __/ _ \\/ _` | |   ")
    log.writeln("  | |_| | |_| | || (_) | | | | | | (_| | ||  __/ (_| | |      ")
    log.writeln("   \\___/ \\__,_|\\__\\___/|_| |_| |_|\\__,_|\\__\\___|\\__,_|_|      ")
    log.writeln("                                                              ")
    log.writeln("        Argyll Printer Profiler (Automated Workflow)          ")
    log.writeln("          Color Target Generation & ICC Profiling             ")
    log.writeln("==============================================================")
    log.writeln("")
    log.writeln("Automated ArgyllCMS script for calibrating printers on Windows, macOS and Linux.")
    log.writeln("Targets are adapted for use with X-Rite Colormunki Photo / i1Studio.")
    log.writeln("")
    log.writeln("Author:  Knut Larsson")
    log.writeln(f"Version: {VERSION}")
    log.writeln("")


def validate_cfg_paths(cfg: dict[str, str], log: TeeLogger) -> None:
    """Validate paths in cfg for existence and validity, logging warnings if issues."""

    # PRINTER_PROFILES_PATH: should be a directory
    path_str = cfg.get("PRINTER_PROFILES_PATH", "").strip()
    if not path_str:
        log.writeln("⚠️ Warning: PRINTER_PROFILES_PATH is not specified in setup file.")
    else:
        path_str = os.path.expandvars(path_str)
        p = Path(path_str).expanduser()
        if not p.exists():
            log.writeln(f"⚠️ Warning: PRINTER_PROFILES_PATH directory does not exist: '{path_str}'")
        elif not p.is_dir():
            log.writeln(f"⚠️ Warning: PRINTER_PROFILES_PATH is not a directory: '{path_str}'")

    # PRECONDITIONING_PROFILE_PATH: should be a file
    path_str = cfg.get("PRECONDITIONING_PROFILE_PATH", "").strip()
    if path_str:
        path_str = os.path.expandvars(path_str)
        p = Path(path_str).expanduser()
        if not p.exists():
            log.writeln(f"⚠️ Warning: PRECONDITIONING_PROFILE_PATH file does not exist: '{path_str}'")
        elif not p.is_file():
            log.writeln(f"⚠️ Warning: PRECONDITIONING_PROFILE_PATH is not a file: '{path_str}'")
    # else:
        # Do nothing: accepted that path is empty

    # PRINTER_ICC_PATH: should be a file
    path_str = cfg.get("PRINTER_ICC_PATH", "").strip()
    if not path_str:
        log.writeln("⚠️ Warning: PRINTER_ICC_PATH is not specified in setup file.")
    else:
        path_str = os.path.expandvars(path_str)
        p = Path(path_str).expanduser()
        if not p.exists():
            log.writeln(f"⚠️ Warning: PRINTER_ICC_PATH file does not exist: '{path_str}'")
        elif not p.is_file():
            log.writeln(f"⚠️ Warning: PRINTER_ICC_PATH is not a file: '{path_str}'")

    # Check required non-path variables
    required_vars = [
        "STRIP_PATCH_CONSISTENSY_TOLERANCE",
        "COLOR_SYNC_UTILITY_PATH",
        "PROFILE_SMOOTING",
        "TARGET_RESOLUTION",
    ]

    for var in required_vars:
        if not cfg.get(var, "").strip():
            log.writeln(f"⚠️ Warning: Variable {var} not set. Check setup file.")



def main_menu(state: AppState, cfg: dict[str, str], log: TeeLogger) -> None:
    """Main menu loop (port of Bash main_menu)."""

    while True:
        cfg = load_setup_file_shell_style(state.setup_file)

        validate_cfg_paths(cfg, log)

        # Clear variables each loop to mirror Bash behavior
        state.source_folder = ""
        state.dialog_title = ""
        state.name = ""
        state.desc = ""
        state.action = ""
        state.profile_folder = ""
        state.new_name = ""
        state.ti3_mtime_before = ""
        state.ti3_mtime_after = ""

        log.writeln("")
        log.writeln("")
        log.writeln("─────────────────────────────────────────────────────────────────────────")
        log.writeln("Printer Profiling — Main Menu")
        log.writeln("─────────────────────────────────────────────────────────────────────────")
        log.writeln("General Notes:")
        log.writeln("   1. Existing ti1/ti2/ti3/icc and target image (.tif) filenames must match.")
        log.writeln("   2. If more than one target image, filenames must end with _01, _02, etc.")
        log.writeln("")
        log.writeln("")
        log.writeln("What action do you want to perform?")
        log.writeln("")
        log.writeln("1: Create target chart and printer profile from scratch")
        log.writeln("    └─ Specify name → Generate targets → Measure target patches")
        log.writeln("       → Create profile → Sanity check → Copy to profile folder")
        log.writeln("       (Cancel after generating targets if only target chart is needed)")
        log.writeln("")
        log.writeln("2: Resume or re-read an existing target chart measurement and create profile")
        log.writeln("    └─ Specify .ti3 file → Measure target patches")
        log.writeln("       → Create profile → Sanity check → Copy to profile folder")
        log.writeln("")
        log.writeln("3: Read an existing target chart from scratch and create profile")
        log.writeln("    └─ Specify .ti2 file → Measure target patches")
        log.writeln("       → Create profile → Sanity check → Copy to profile folder")
        log.writeln("")
        log.writeln("4: Create printer profile from an existing measurement file")
        log.writeln("    └─ Specify .ti3 file → Create profile → Sanity check")
        log.writeln("       → Copy to profile folder")
        log.writeln("")
        log.writeln("5: Perform sanity check on existing profile")
        log.writeln("    └─ Specify .ti3 file → Check profile against test chart data")
        log.writeln("       → Create report")
        log.writeln("")
        log.writeln("6: Change setup parameters")
        log.writeln("")
        log.writeln("7: Show tips on how to improve accuracy of a profile")
        log.writeln("")
        log.writeln("8: Show ΔE2000 Color Accuracy — Quick Reference")
        log.writeln("")
        log.writeln("9: Exit script")
        log.writeln("─────────────────────────────────────────────────────────────────────────")
        log.writeln("")

        print("Enter your choice [1–9]: ", end='', flush=True)
        answer = getch()
        print(answer, flush=True)

        if answer == "1":
            state.action = "1"
            if not specify_profile_name(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue
            if not select_instrument(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue
            if not specify_and_generate_target(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue
            if not perform_measurement_and_profile_creation(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue
            if not install_profile_and_save_data(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue

        elif answer == "2":
            state.action = "2"
            state.dialog_title = "Select an existing .ti3 file to re-read/resume measuring target patches."
            log.writeln(state.dialog_title)
            if not select_file(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue
            if not perform_measurement_and_profile_creation(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue
            if not install_profile_and_save_data(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue

        elif answer == "3":
            state.action = "3"
            state.dialog_title = "Select an existing .ti2 file to measure target patches."
            log.writeln(state.dialog_title)
            if not select_file(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue
            if not perform_measurement_and_profile_creation(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue
            if not install_profile_and_save_data(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue

        elif answer == "4":
            state.action = "4"
            state.dialog_title = "Select an existing completed .ti3 file to create .icc profile with."
            log.writeln(state.dialog_title)
            if not select_file(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue
            if not create_profile_from_existing(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue
            if not install_profile_and_save_data(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue

        elif answer == "5":
            state.action = "5"
            state.dialog_title = "Select an existing .ti3 file that has a matching .icc profile."
            log.writeln(state.dialog_title)
            if not select_file(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue
            if not sanity_check(state, cfg, log):
                log.writeln("")
                log.writeln("Operation aborted.")
                input("Press enter to return to main menu...")
                continue

        elif answer == "6":
            state.action = "6"
            edit_setup_parameters(state, cfg, log)

        elif answer == "7":
            state.action = "7"
            improving_accuracy(state, cfg, log)
            input("Press enter to return to main menu...")

        elif answer == "8":
            state.action = "8"
            show_de_reference(state, cfg, log)
            input("Press enter to return to main menu...")

        elif answer == "9":
            state.action = "9"
            log.writeln("")
            log.writeln("Exiting script...")
            raise SystemExit(0)

        else:
            log.writeln("")
            log.writeln("No valid selection made. Returning to main menu...")
            continue


def main() -> None:
    # Detect the operating system platform
    PLATFORM = detect_platform()

    # Get script path and derive directories
    script_path = Path(__file__).resolve()
    script_dir = script_path.parent
    script_name = script_path.name

    # Create log file path with today's date
    today = dt.date.today().strftime("%Y%m%d")
    temp_log = script_dir / f"Argyll_Printer_Profiler_{today}.log"
    setup_file = script_dir / "Argyll_Printer_Profiler_setup.ini"

    # Ensure the log file exists and is writable
    try:
        temp_log.parent.mkdir(parents=True, exist_ok=True)
        temp_log.touch(exist_ok=True)
    except OSError as e:
        print(f"❌ Cannot create log file at '{temp_log}': {e}")
        raise SystemExit(1)

    # Create logger that writes to both terminal and log file
    log = TeeLogger(temp_log)

    # Create application state object
    state = AppState(
        script_dir=script_dir,
        script_name=script_name,
        temp_log=temp_log,
        setup_file=setup_file,
        PLATFORM=PLATFORM,
    )

    # Print banner to terminal + log
    print_banner(log)

    # Add session separator to log only
    session_separator(state, log)

    # Load setup configuration from file
    if not setup_file.exists():
        log.writeln("❌ Setup file not found:")
        log.writeln(f"   {setup_file}")
        raise SystemExit(1)

    cfg = load_setup_file_shell_style(setup_file)

    # Check that required Argyll commands are available
    required_cmds = ["targen", "chartread", "colprof", "printtarg", "profcheck", "dispcal"]
    check_required_commands(required_cmds, log, PLATFORM)

    # Check tkinter availability for file dialogs
    try:
        import tkinter
    except ImportError:
        log.writeln("❌ tkinter is required for file selection dialogs but is not available in this Python installation.")
        if PLATFORM == "linux":
            log.writeln("On Linux, install tkinter with: sudo apt update && sudo apt install python3-tk")
        elif PLATFORM == "macos":
            log.writeln("On macOS, tkinter is usually included with Python. Try reinstalling Python from python.org or use Homebrew: brew install python-tk")
        elif PLATFORM == "windows":
            log.writeln("On Windows, tkinter is included with Python installations from python.org. Download and install Python again, ensuring tkinter is selected during installation.")
        raise SystemExit(1)

    # Check Linux window management tools for focus return
    if PLATFORM == "linux":
        if not shutil.which("xdotool") and not shutil.which("wmctrl"):
            log.writeln("❌ On Linux, window management tools are required for file dialog focus return but neither xdotool nor wmctrl is available.")
            log.writeln("Install xdotool with: sudo apt update && sudo apt install xdotool")
            log.writeln("Or install wmctrl with: sudo apt update && sudo apt install wmctrl")
            raise SystemExit(1)

    # Extract Argyll version for logging
    try:
        result = subprocess.run(["dispcal"], capture_output=True, text=True)
        argyll_version_line = (result.stdout + result.stderr).split('\n')[0]
        match = re.search(r'Version ([0-9.]+)', argyll_version_line)
        argyll_version = match.group(1) if match else "unknown"
    except (subprocess.SubprocessError, AttributeError):
        argyll_version = "unknown"
    log.writeln("✅ ArgyllCMS detected")
    log.writeln(f"   Version: {argyll_version}")
    log.writeln("")
    log.writeln("🖥️  Recommended Terminal Window Size: 100 columns x 50 rows")
    log.writeln("")

    # Start the main menu loop
    main_menu(state, cfg, log)


if __name__ == "__main__":
    main()
