<#
===============================================================================
add_argyll_path_windows.ps1
-------------------------------------------------------------------------------
Adds the ArgyllCMS binary folder to the Windows USER PATH environment variable.

DESCRIPTION
This PowerShell script ensures that the ArgyllCMS "bin" directory is present
in the user's PATH environment variable so that ArgyllCMS command line tools
(such as dispcal, colprof, chartread, etc.) can be executed from any terminal.

The script checks whether the specified ArgyllCMS path already exists in the
current USER PATH. If the path is missing, it is appended safely. If the path
is already present, the script does nothing.

The modification affects the USER environment PATH only and does not require
administrator privileges.

IMPORTANT
You must modify the ARGYLL_INSTALLATION_PATH parameter so that it matches the
actual installation directory of ArgyllCMS on your system, including the
correct version number.

Example installation path:

    C:\Argyll_V3.4.0\bin

If you installed a different version of ArgyllCMS, adjust the version number
accordingly.

Example:

    C:\Argyll_V3.3.0\bin
    C:\Argyll_V3.5.0\bin

USAGE
Run the script from PowerShell:

    powershell -ExecutionPolicy Bypass -File add_argyll_path_windows.ps1

You may also pass the installation path as a parameter:

    powershell -ExecutionPolicy Bypass -File add_argyll_path_windows.ps1 `
        -ARGYLL_INSTALLATION_PATH "C:\Argyll_V3.4.0\bin"

BEHAVIOR
• If the path is not in PATH → it will be added.
• If the path already exists → nothing is changed.

After running the script, newly opened terminals will be able to run ArgyllCMS
commands directly.

NOTE
The updated PATH will only appear in NEW terminals opened after running the
script.

REQUIREMENTS
• Windows
• PowerShell
• ArgyllCMS installed

===============================================================================
param(
    [string]$ARGYLL_INSTALLATION_PATH = "C:\Argyll_V3.4.0\bin"
)

# Get current user PATH
$p = [Environment]::GetEnvironmentVariable("Path", "User")

# If PATH is empty or null, initialize it
if ([string]::IsNullOrWhiteSpace($p)) {
    [Environment]::SetEnvironmentVariable(
        "Path",
        $ARGYLL_INSTALLATION_PATH,
        "User"
    )
    Write-Host "PATH was empty. Added Argyll to PATH."
    return
}

# Split PATH into entries and trim whitespace
$paths = $p.Split(';') | ForEach-Object { $_.Trim() }

# Check for exact match
if ($paths -notcontains $ARGYLL_INSTALLATION_PATH) {

    $newPath = ($paths + $ARGYLL_INSTALLATION_PATH) -join ';'

    [Environment]::SetEnvironmentVariable(
        "Path",
        $newPath,
        "User"
    )

    Write-Host "Added Argyll to PATH"
}
else {
    Write-Host "Argyll already in PATH"
}
