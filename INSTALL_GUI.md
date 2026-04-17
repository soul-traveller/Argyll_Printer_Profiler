# Argyll Printer Profiler GUI - Installation Guide

## Prerequisites

### 1. Python Installation
- Python 3.8 or higher required
- Download from https://www.python.org/downloads/
- During installation on Windows, ensure "Add Python to PATH" is checked

### 2. ArgyllCMS Installation
ArgyllCMS must be installed and available in your system PATH.

#### Windows
1. Download from https://www.argyllcms.com/
2. Run the installer
3. Add ArgyllCMS to your PATH (usually C:\Program Files\ArgyllCMS\bin)

#### macOS
```bash
brew install argyll-cms
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install argyll
```

### 3. PyQt6 Installation
Install PyQt6 for the GUI framework:

```bash
pip install -r requirements.txt
```

Or install directly:
```bash
pip install PyQt6
```

## Running the GUI

### Windows
```bash
python Argyll_Printer_Profiler_GUI.py
```

Or create a batch file `run_gui.bat`:
```batch
@echo off
python Argyll_Printer_Profiler_GUI.py
pause
```

### macOS
```bash
python3 Argyll_Printer_Profiler_GUI.py
```

### Linux
```bash
python3 Argyll_Printer_Profiler_GUI.py
```

## First Run

When you first run the GUI, it will:

1. Check for required ArgyllCMS commands (targen, chartread, colprof, printtarg, profcheck)
2. Verify setup file exists (Argyll_Printer_Profiler_setup.ini)
3. Display the main menu with all available options

## Configuration

The GUI uses the same setup file as the CLI version:
- `Argyll_Printer_Profiler_setup.ini`

You can modify parameters through the GUI (Menu option 6) or edit the file directly.

## Troubleshooting

### "Command not found" errors
- Ensure ArgyllCMS is installed and in your PATH
- Test by running `targen --version` in terminal

### GUI won't start
- Check Python version (3.8+)
- Verify PyQt6 is installed: `pip list | grep PyQt6`
- Check terminal output for error messages

### File dialogs don't work on Linux
- Install window management tools:
  ```bash
  sudo apt install xdotool
  # or
  sudo apt install wmctrl
  ```

## Features

- **Graphical Interface**: Modern PyQt6-based GUI
- **Step-by-Step Navigation**: Next/Back buttons for workflow control
- **Progress Tracking**: Visual progress bar showing workflow steps
- **Terminal Output**: Real-time command execution output
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Error Handling**: Comprehensive error messages and validation
- **File Selection**: Native file dialogs for all file operations

## Workflow Steps

The GUI supports all workflows from the CLI version:

1. **Create from Scratch**: Generate targets, measure, create profile, sanity check, install
2. **Resume Measurement**: Re-read existing .ti3 files and continue
3. **Read from Scratch**: Measure new .ti2 files
4. **Profile from Measurement**: Create profile from existing .ti3
5. **Sanity Check**: Analyze existing profiles

Each workflow shows a progress bar at the top with step indicators.

## Logging

All operations are logged to:
- Daily log file: `Argyll_Printer_Profiler_GUI_YYYYMMDD.log`
- Terminal output panel in the GUI

Logs include:
- All user actions
- Command executions
- Error messages
- Timestamps

## Support

For issues or questions:
- Check the main documentation: https://soul-traveller.github.io/Argyll_Printer_Profiler/
- Review log files for error details
- Ensure ArgyllCMS is properly installed

## License

Same as the original Argyll_Printer_Profiler project.
