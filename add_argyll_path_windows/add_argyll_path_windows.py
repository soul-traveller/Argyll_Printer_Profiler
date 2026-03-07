"""
===============================================================================
add_argyll_path_windows.py
-------------------------------------------------------------------------------
Ensures that the ArgyllCMS binary directory is included in the Windows
USER PATH environment variable.

DESCRIPTION
This Python script checks whether the ArgyllCMS "bin" directory exists in the
current Windows USER PATH environment variable. If the path is missing, it is
added automatically.

This allows ArgyllCMS command line tools such as:

    dispcal
    colprof
    chartread
    spotread

to be executed from any command prompt or terminal without specifying the
full installation path.

The script uses PowerShell internally to modify the Windows environment
variables safely without truncating long PATH values.

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
2. Check if the ArgyllCMS path already exists in the USER PATH variable.
3. Add the path if it is missing.

If the path already exists, no changes are made.

BEHAVIOR
• If the path is missing → it will be appended to PATH.
• If the path already exists → nothing is changed.

After running the script, open a new terminal window to use the updated PATH.

NOTE
Changes to environment variables only apply to newly opened terminals.

REQUIREMENTS
• Windows
• Python 3
• PowerShell available (standard on Windows)
• ArgyllCMS installed

===============================================================================
"""

import subprocess
import platform

ARGYLL_INSTALLATION_PATH = r"C:\Argyll_V3.4.0\bin"

if platform.system() == "Windows":
    ps_command = rf"""
$p=[Environment]::GetEnvironmentVariable('Path','User');
if($p -notlike '*{ARGYLL_INSTALLATION_PATH}*'){{
    [Environment]::SetEnvironmentVariable(
        'Path',
        $p + ';{ARGYLL_INSTALLATION_PATH}',
        'User'
    )
}}
"""

    subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
        check=True
    )

print("Argyll path ensured in PATH.")
