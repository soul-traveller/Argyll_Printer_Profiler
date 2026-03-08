"""
===============================================================================
add_argyll_path_windows.py
-------------------------------------------------------------------------------
Ensures that the ArgyllCMS binary directory is included in the Windows
USER PATH environment variable in a safe, robust, and idempotent way.

DESCRIPTION
This Python script checks whether the ArgyllCMS "bin" directory exists in the
current Windows USER PATH environment variable. If the path is missing, it is
added automatically. The script handles the following:

• Empty PATH variables
• Whitespace and trailing slashes
• Case-insensitive and normalized duplicate detection
• Malformed or empty PATH entries
• Broadcasting environment changes so new terminals recognize the updated PATH

This allows ArgyllCMS command line tools such as:

    dispcal
    colprof
    chartread
    spotread

to be executed from any command prompt or terminal without specifying the
full installation path.

The script updates the USER PATH directly via the Windows registry and
broadcasts the change, without requiring administrator rights.

IMPORTANT
You must modify the ARGYLL_INSTALLATION_PATH variable so that it matches the
actual installation directory of ArgyllCMS on your system.

Example:

    ARGYLL_INSTALLATION_PATH = r"C:\Argyll_V3.4.0\bin"

If a different version of ArgyllCMS is installed, update the version number
accordingly.

Examples:

    C:\Argyll_V3.3.0\bin
    C:\Argyll_V3.4.0\bin
    C:\Argyll_V3.5.0\bin

USAGE
Run the script using Python:

    python add_argyll_path_windows.py

The script will:

1. Detect whether it is running on Windows.
2. Normalize and inspect the current USER PATH variable.
3. Add the ArgyllCMS path if it is missing.
4. Broadcast the change so new terminals recognize the updated PATH.

If the path already exists, no changes are made.

BEHAVIOR
• If the path is missing → it will be appended to PATH.
• If the path already exists (case-insensitive, normalized) → nothing is changed.
• Handles empty PATH or malformed entries safely.
• Updates the USER PATH registry entry and broadcasts the environment change.

After running the script, newly opened terminal windows will see the updated PATH.
Existing terminals will retain their current PATH.

REQUIREMENTS
• Windows
• Python 3
• ArgyllCMS installed
• No administrator rights required

===============================================================================
"""

import platform
import winreg
import ctypes
import os

ARGYLL_INSTALLATION_PATH = r"C:\Argyll_V3.4.0\bin"


def normalize_path(p: str) -> str:
    """Normalize paths for reliable comparison."""
    return os.path.normcase(os.path.normpath(p.strip()))


def refresh_environment():
    """Notify Windows that environment variables changed."""
    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A

    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST,
        WM_SETTINGCHANGE,
        0,
        "Environment",
        0,
        100,
        None
    )


if platform.system() == "Windows":

    reg_path = r"Environment"
    path_modified = False

    normalized_target = normalize_path(ARGYLL_INSTALLATION_PATH)

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        reg_path,
        0,
        winreg.KEY_READ | winreg.KEY_WRITE
    ) as key:

        try:
            current_path, reg_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_path = ""
            reg_type = winreg.REG_EXPAND_SZ

        # Handle empty PATH
        if not current_path.strip():

            winreg.SetValueEx(
                key,
                "Path",
                0,
                reg_type,
                ARGYLL_INSTALLATION_PATH
            )

            print("PATH was empty. Added Argyll to PATH.")
            path_modified = True

        else:

            raw_paths = current_path.split(";")

            clean_paths = []
            normalized_paths = []

            for p in raw_paths:
                p = p.strip()
                if not p:
                    continue

                norm = normalize_path(p)

                clean_paths.append(p)
                normalized_paths.append(norm)

            if normalized_target not in normalized_paths:

                clean_paths.append(ARGYLL_INSTALLATION_PATH)
                new_path = ";".join(clean_paths)

                winreg.SetValueEx(
                    key,
                    "Path",
                    0,
                    reg_type,
                    new_path
                )

                print("Added Argyll to PATH")
                path_modified = True

            else:
                print("Argyll already in PATH")

    if path_modified:
        refresh_environment()
        print("Environment refreshed.")

print("Argyll path ensured in PATH.")
