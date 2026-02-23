# Argyll_Printer_Profiler Scripts — User Guide
**Version:** 1.3.0<br>
**Platform:** macOS, Linux (Bash script); macOS, Linux, Windows (Python script)<br>
**Based on:** Simple script by Jintak Han (https://github.com/jintakhan/AutomatedArgyllPrinter)<br>
**Author:** Knut Larsson<br>

Argyll_Printer_Profiler is available in two versions: a Bash script (`Argyll_Printer_Profiler.command`) and a Python script (`Argyll_Printer_Profiler.py`). Both automate a complete **ArgyllCMS printer profiling workflow** on supported platforms, from target generation to ICC installation.<br>

---

## 📑 Table of Contents

- [Overview](#overview)
- [Scripts and Platforms](#scripts-and-platforms)
- [Features](#features)
- [Installation](#installation)
  - [Getting Started](#getting-started)
  - [Bash Script Dependencies](#bash-script-dependencies)
      - [macOS](#macos)
      - [Linux](#linux)
  - [Python Script Dependencies](#python-script-dependencies)
      - [macOS](#macos-1)
      - [Linux](#linux-1)
      - [Windows](#windows)
  - [Script Placement](#script-placement)
  - [Execution Permissions for MacOS (Important)](#execution-permissions-for-macos-important)
  - [Execution Permissions for Linux (Important)](#execution-permissions-for-linux-important)
  - [Key Parameters](#key-parameters)
- [General Workflow](#general-workflow)
- [Main Menu Actions Explained](#main-menu-actions-explained)
- [Target Generation Menu Options](#target-generation-menu-options)
- [Custom Target Generation](#custom-target-generation)
- [Files and Folder Structure](#files-and-folder-structure)
- [ArgyllCMS Commands and Defaults](#argyllcms-commands-and-defaults)
- [ICC Profile Installation](#icc-profile-installation)
- [Logs and Debugging](#logs-and-debugging)
- [Important Notes and Best Practices](#important-notes-and-best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

This script provides a **guided, menu-driven interface** for creating printer ICC profiles using ArgyllCMS.
It is designed for:

- Inkjet and laser printers
- X-Rite ColorMunki / i1Studio and compatible instruments
- Users who want reproducible, well-documented profiles without memorizing ArgyllCMS commands

---

## Scripts and Platforms

The Argyll_Printer_Profiler project provides two script versions to accommodate different user preferences and platform requirements.

### Bash Script (`Argyll_Printer_Profiler.command`)

- **Platforms:** macOS, Linux
- **Requirements:**
  - macOS 10.13 or later (Intel or Apple Silicon), or a modern Linux distribution
  - ArgyllCMS installed and available in Terminal
  - On Linux: `zenity` for graphical file pickers, `wmctrl` or `xdotool` for window management
  - Supported measurement device (ColorMunki, i1Pro, etc.)
  - Terminal access
- **How to use:**
  - On macOS: Double-click the script in Finder after setting execute permissions
  - On Linux: Run `./Argyll_Printer_Profiler.command` in terminal after setting permissions

### Python Script (Argyll_Printer_Profiler.py)

- **Platforms:** macOS, Linux, Windows
- **Requirements:**
  - Python 3.x with tkinter (usually included)
  - ArgyllCMS tools available from terminal
  - Spectrophotometer connected for measurement workflows
  - Supported platforms: Windows 10+, macOS 10.6+, Linux (Ubuntu/Debian and similar)
  - On Linux: `wmctrl` or `xdotool` for window management and focus return
- **How to use:**
  - Run `python3 Argyll_Printer_Profiler.py` in terminal or command prompt

Both scripts use the same setup file (`Argyll_Printer_Profiler_setup.ini`) and provide identical functionality and user experience.

---

## Features
**General**

- Generates optimized color targets
- Reads measurements
- Builds ICC profiles
- Performs sanity checks
- Installs profiles into defined local profiles folder

**Details**

- Assists user through the whole printer profile creation process in one go: from target generation (targen+printtarg), reading (charread), making profile (colprof) and outputing proifle sanity check.
- Configure a set of predefined targets, and select them from a menu (6 for Colormunki and 6 for other instruments) (editable from ini file)
- Configure defaults as desired for later reuse (targen, printtarg, chartread, and colprof)
- Re-measure / resume measurements on a previously incomplete / saved / interupted measurement set
- Select pre-existing target chart to measure and create profile.
- Perform "sanity check" with extended statistics on any profile with existing ti3 file
- When creting a profile, a new folder is created with the name chosen for the profile, and needed files are copied and renamed automatically.
- Selection of ti2/3 files and icc files are done through a file dialog, so that one does not have to write long path strings.


### Advanced Delta E Analysis
- Percentile calculations (99th, 98th, 95th, 90th)
- Patch count analysis below specific thresholds
- Range statistics and outlier identification
 
### Robust Error Handling
- Variable validation in all functions
- Dependency checking with clear error messages
- Directory verification and automatic recovery
 
### User Interface
- Simple interactive terminal prompt

---

## Installation
### Getting Started

1. Prepare for the script to run:   
    - Place script folder in a desired location. See section [Script Placement](#script-placement).
    - Check that dependencies are installed. See section [Bash Script Dependencies](#bash-script-dependencies).

2. Modify the setup to fit your operating system. See section [Key Parameters](#key-parameters) for understanding the most important configurable parameters. The following should be assesed/modified:

	a. Easily modified via main menu (option 6):   
	
       - ICC profile to use (`PRECONDITIONING_PROFILE_PATH` and `PRINTER_ICC_PATH`).  
       - Ink limit.  
       - Paper size.  

	b. Modified in .ini file:   
	
       - `PRINTER_PROFILES_PATH` (different for MacOS/Linux/Windows).  
       - Common arguments to use by default (`COMMON_ARGUMENTS_*`).  
       - Is `STRIP_PATCH_CONSISTENSY_TOLERANCE` satisfactory?   
       - `EXAMPLE_FILE_NAMING` (file naming convention).  
       - Is `DEFAULT_TARGEN_COMMAND_NON_COLORMUNKI` satisfactory?   
       - Is `DEFAULT_PRINTTARG_COMMAND_NON_COLORMUNKI` satisfactory?   

3. Run the script

   For the Bash script (`Argyll_Printer_Profiler.command`), see the Execution Permissions for MacOS or Linux sections below for setting permissions and running.

   For the Python script (`Argyll_Printer_Profiler.py`), open a terminal or command prompt, navigate to the script folder, and run:

   ```bash
   python3 Argyll_Printer_Profiler.py
   ```

   On Windows, use `python` instead of `python3`.


### Bash Script Dependencies

#### macOS

The recommended way is Homebrew:

```bash
brew install argyll-cms
```

Verify ArgyllCMS installation:

```bash
targen -?
```

#### Linux

The recommended way is apt:

```bash
sudo apt install argyll zenity xdotool
or
sudo apt install argyll zenity wmctrl
```

Verify ArgyllCMS installation:

```bash
targen -?
```

### Python Script Dependencies

#### macOS

Install Python 3 with tkinter support:

```bash
brew install python3 python-tk
```

Install ArgyllCMS:

```bash
brew install argyll-cms
```

Verify installations:

```bash
python3 --version
python3 -c "import tkinter; print('tkinter available')"
targen -?
```

#### Linux

Install Python 3 with tkinter support (if not already installed):

```bash
sudo apt install python3 python3-tk
```

Install ArgyllCMS and window management tools:

```bash
sudo apt install argyll xdotool
or
sudo apt install argyll wmctrl
```

Verify installations:

```bash
python3 --version
python3 -c "import tkinter; print('tkinter available')"
targen -?
```

#### Windows

Download and install Python 3.x from https://www.python.org/downloads/ (ensure tkinter is selected during installation).

Download and install ArgyllCMS from https://www.argyllcms.com/.

Verify installations:

```bash
python --version
python -c "import tkinter; print('tkinter available')"
targen -?
```

### Script Placement

You may place any of the scripts **in any folder**:

- Desktop
- Documents
- External drive
- Project-specific folder

All generated files are stored **relative to the script’s location**.

**Setup File: Argyll\_Printer\_Profiler\_setup.ini**.  
The setup file **must be located in the same folder as the script**:

```
Argyll_Printer_Profiler.command
or
Argyll_Printer_Profiler.py

Argyll_Printer_Profiler_setup.ini
```

### Execution Permissions for MacOS (Important)

On modern macOS versions, a script must have the **execute bit** set.

1. Open Terminal
2. Navigate to the script folder
3. Run:

```bash
chmod +x Argyll_Printer_Profiler.command
```

Verify:

```bash
ls -l Argyll_Printer_Profiler.command
```

Expected output:

```
-rwxr-xr-x@ Argyll_Printer_Profiler.command
```

You can now run the script by:
- Double-clicking it in Finder
- Or running `./Argyll_Printer_Profiler.command` from Terminal

### Execution Permissions for Linux (Important)

As for macOS, Linux scripts must have the **execute bit** set.
However, the .command file extension is mac only.
Rename file to .sh, then:

1. Open Terminal
2. Navigate to the script folder
3. Run:

```bash
chmod +x Argyll_Printer_Profiler.sh
```

Verify:

```bash
ls -l Argyll_Printer_Profiler.sh
```

Expected output:

```
-rwxr-xr-x@ Argyll_Printer_Profiler.sh
```

Finnaly, the file manager preferences must be modified to run .sh files.

For Files / Nautilus (Ubuntu, Fedora)

1. Open Files
2. Menu → Preferences
3. Executable Text Files
4. Select:
 - ✅ Ask what to do
 - or Run them

Now double-click will prompt or run.
You can now run the script by:
- Double-clicking it in your file manager (e.g. Files/Nautilus).
- Or running `./Argyll_Printer_Profiler.sh` from Terminal

### Key Parameters
**For details on ArgyllCMS and the commands used by this script (targen, printtarg, chartread, colprof, profcheck), see:**   
[https://www.argyllcms.com/doc/ArgyllDoc.html](https://www.argyllcms.com/doc/ArgyllDoc.html)


See `Argyll_Printer_Profiler_setup.ini` for a descriptions and list of all parameters.

- **`PRINTER_ICC_PATH`**
  Path to the RGB/CMYK colorspace profile used as reference (e.g. sRGB, AdobeRGB).

- **`PRINTER_PROFILES_PATH`**
  Destination folder for installed ICC profiles
  Example (recommended):
  ```$HOME/Library/ColorSync/Profiles```

- **`STRIP_PATCH_CONSISTENSY_TOLERANCE`**
  Used by `chartread -T`
  Default recommendation: **0.6**

- **`INK_LIMIT`**
  Total ink limit used by `targen` and `colprof`

  Typical values:
  - Inkjet: 220–300
  - Laser: 180–260

- **`PAPER_SIZE`**
  `A4` or `Letter`. Any other sizes requires the use of Option 7: Custom Target Generation, after selecting main menu option 1.

- **`PROFILE_SMOOTING`**
  Argument -r in `colprof` average deviation, affecting accuracy and smooting of profile. Argyll-default 0.5. 1.0 makes smoother profile without much reduction in accuracy.

- **`TARGET_RESOLUTION`**
  DPI for generated TIFF targets

- **`DEFAULT_TARGEN_COMMAND_CUSTOM`**: Custom targen arguments template
- **`DEFAULT_PRINTTARG_COMMAND_CUSTOM`**: Custom printtarg arguments template

#### Instrument-Specific Parameters
- **`INST_CM_*`**: ColorMunki-optimized parameters (A4/Letter paper sizes)
- **`INST_OTHER_*`**: Other instrument parameters (paper size independent)

#### Target Generation Parameters
- **`*_PATCH_COUNT_*`**: Number of patches per option
- **`*_WHITE_PATCHES_e`**: White patch count (`targen -e`)
- **`*_BLACK_PATCHES_B`**: Black patch count (`targen -B`)
- **`*_GRAY_STEPS_g`**: Gray ramp steps (`targen -g`)
- **`*_DESCRIPTION`**: Menu display descriptions

The script validates that all required parameters exist before running.

---

## General Workflow

1. Choose an action from the main menu
2. Specify or select a profile name
3. Generate or reuse color targets
4. Print targets with **no color management**
5. Measure patches with the instrument
6. Create ICC profile
7. Perform sanity check
8. Install profile into local profiles folder

---

## Main Menu Actions Explained

### 1. Create target chart and printer profile from scratch

- Define profile name
- Create profile folder
- Generate new targets (menu-selected from 12 optimized presets or custom, 6 for ColorMunki, 6 for other instruments)
- Measure patches
- Create ICC profile
- Sanity check
- Install profile into specified profile folder

### 2. Resume or re-read an existing target chart measurement and create profile

- Continue from an existing `.ti3`. Useful if measurement was interrupted.
- Define profile name
- Create new or overwrite existing profile `ti3`/`icc`
- Create profile folder, copy needed files and rename them
- Measure patches
- Create new or overwrite existing profile `ti3`/`icc`
- Sanity check
- Install profile into specified profile folder

### 3. Read an existing target chart from scratch and create profile

- Reuse printed targets
- Define profile name
- Create new or overwrite existing profile `ti3`/`icc`
- Create profile folder, copy needed files and rename them
- Measure patches
- Sanity check
- Install profile into specified profile folder

### 4. Create printer profile from an existing measurement file

- Skip measurement
- Direct ICC generation in selected folder or create new profile folder
- Sanity check
- Install profile into specified profile folder

### 5. Perform sanity check on existing profile

- Runs `profcheck` on existing `.ti3` + `.icc`
- File created is named: `profile name + _sanity_check.txt`
- Extended analysis calculations:
    - Patch count analysis (ΔE < 1.0, 2.0, 3.0)
    - Average, max, min, percentile statistics.
- If run several times, results existing file are overwritten.
- Results are displayed in the terminal and in the created file.
- Get help on how to improve profile accuracy using the sanity check results.

### 6. Change setup parameters

- Edit selected values in the `.ini` file interactively

### 7. Show tips on how to improve accuracy of a profile

- Display important information and procedure on how to improve accuracy of created profile, using sanity check as basis.

### 8. Show ΔE2000 Color Accuracy — Quick Reference

- Displays ΔE2000 color difference values and their perceptual meaning
- Quick reference for evaluating profile quality

### 9. Exit script

---

## Target Generation Menu Options

The target generation menu options is available under main menu action **1**.

The script provides **6 optimized preset targets** plus a **custom option**, where patch counts and menu text are configurable in the `.ini` file.

### ColorMunki Instrument (A4/Letter Paper)
Default menu for ColorMunki instrument:

**A4 Paper Size:**  
- **Option 1**: Small – 210 patches – 1 × A4 page, quick profiling.  
- **Option 2**: Medium – 420 patches – 2 × A4 pages, recommended default.  
- **Option 3**: Large – 630 patches – 3 × A4 pages, better accuracy.  
- **Option 4**: XL – 840 patches – 4 × A4 pages, high quality.  
- **Option 5**: XXL – 1050 patches – 5 × A4 pages, very high quality.  
- **Option 6**: XXXL – 1260 patches – 6 × A4 pages, maximum quality.  

**Letter Paper Size:**  
- **Option 1**: Small – 196 patches – 1 × Letter page, quick profiling.  
- **Option 2**: Medium – 392 patches – 2 × Letter pages, recommended default.  
- **Option 3**: Large – 588 patches – 3 × Letter pages, better accuracy.  
- **Option 4**: XL – 784 patches – 4 × Letter pages, high quality.  
- **Option 5**: XXL – 980 patches – 5 × Letter pages, very high quality.  
- **Option 6**: XXXL – 1176 patches – 6 × Letter pages, maximum quality.  

The Colormunki menu above has separate options for A4 and Letter, shown according to the current setting of paper size, which can be chosen in main menu option 6.

### Other Instruments (Same for All Paper Sizes)
Default menu for other instruments is only partially specified. User may modify/add as desired:

- **Option 1**: Small – 480 patches – quick profiling.  
- **Option 2**: Medium – 960 patches – recommended default.  
- **Options 3-6**: Options Not defined (specify in the `.ini` file).  

The menu for Other Instruments is the same regardless of paper size. This means that, if options differntiate between A4 and Letter size, then the page size must first be set in main menu option 6.

### Option 7: Custom Target Generation
Allows advanced users to specify custom `targen` and `printtarg` arguments independent of setup parameters.

## Custom Target Generation

**Menu Option 7**, under main menu action **1**, provides advanced users with direct control over ArgyllCMS parameters. Refer to [https://www.argyllcms.com/doc/ArgyllDoc.html](https://www.argyllcms.com/doc/ArgyllDoc.html) for command attributes.

### Features:
- **Independent Parameters**: Bypasses all preset configurations
- **Direct Argument Control**: Specify exact `targen` and `printtarg` arguments
- **Default Templates**: Pre-populated with sensible defaults that can be edited
- **Expert Control**: Full access to all ArgyllCMS capabilities

### Usage:
1. Select option 7 from any target generation menu
2. Review and edit `targen` arguments (patch count, ink limits, etc.)
3. Review and edit `printtarg` arguments (resolution, paper size, scaling)
4. Confirm to generate custom target

### Default Templates:
- **targen**: `-v -d2 -G -e8 -B8 -g128 -f954`
- **printtarg**: `-v -ii1 -a0.75 -A0.5 -M2 -T300 -P -p210x297`

These defaults can be modified in the `.ini` file via:
- `DEFAULT_TARGEN_COMMAND_CUSTOM`
- `DEFAULT_PRINTTARG_COMMAND_CUSTOM`

## Files and Folder Structure

For each profile, a dedicated folder is created:

Folder `Created_Profiles` is created if missing.

```
Script_Location
└── Created_Profiles/
    └── ProfileName/
        ├── ProfileName.ti1
        ├── ProfileName.ti2
        ├── ProfileName.ti3
        ├── ProfileName.tif / _01.tif / _02.tif
        ├── ProfileName.icc
        ├── ProfileName_sanity_check.txt
└── Pre-made_Targets/
    ├── Patch Width 8-11mm - Expert (Use rig-guide-ruler)/
    ├── Patch Width 12-15mm - Intermediate (Easy with ruler)
    └── Patch Width 16-30mm - Easy (Freehand possible)
└── Argyll_Printer_Profiler_YYYYMMDD.log
└── Argyll_Printer_Profiler.py
└── Argyll_Printer_Profiler.command
└── Argyll_Printer_Profiler.ini
```

The script will create a new folder for each profile, named after the profile name.
A selection of targets is provided in the `Pre-made_Targets` folder, grouped by patch width and ease of use.

- **`Created_Profiles`**: Auto-generated profiles and associated files
- **`Pre-made_Targets`**: Target files for reuse.

---

## ArgyllCMS Commands and Defaults

### targen

Used to generate color values:

- Device class: Printer (`-d2`)
- Includes gray ramp, black & white patches
- Ink limit from setup file
- Patch count selected interactively

### printtarg

- Instrument-specific layout
- User-selected paper size
- Resolution from setup file

### chartread

- Strip reading mode
- Consistency tolerance: `-T`
- Resume supported

### colprof

- High quality (`-qh`)
- PCS reference profile via `-S`
- Perceptual intent (`-dpp`)
- Uses measurement-defined ink limit

### profcheck

- Generates human-readable sanity check
- Flags excessive ΔE values

---

## ICC Profile Installation

After successful creation:

- `.icc` file is copied to `PRINTER_PROFILES_PATH`
- Typical paths:   
   - macOS: 
      - `$HOME/Library/ColorSync/Profiles/` (user) or 
      - `/Library/ColorSync/Profiles/` (system)
   - Windows: 
      - `C:\Windows\System32\spool\drivers\color\` or 
      - `%USERPROFILE%\AppData\Local\Microsoft\Windows\spool\drivers\color\`
   - Linux: 
      - `/usr/share/color/icc/` or 
      - `/var/lib/colord/icc/` or 
      - `$HOME/.color/icc/`

macOS applications must be **restarted** to see the new profile.

---

## Logs and Debugging

- A daily log file is created: `Argyll_Printer_Profiler_YYYYMMDD.log`
- Multiple script executions on same day append to same log
- Log remains in script directory throughout session
- All stdout/stderr is captured

Log files are essential for:
- Diagnosing ArgyllCMS errors
- Reproducing command lines
- Support requests

---

## Important Notes and Best Practices

- Always print targets with **Color Management disabled**
- Use consistent paper, ink, and printer settings
- Use same basename for all files, as script does.
- Keep profile names free of trailing whitespace
- Large targets improve neutrality and gray accuracy

---

## Troubleshooting

### Script won’t run

- Ensure execute bit is set (`chmod +x`)
- macOS Gatekeeper may require right-click → Open

### ICC not copied

- Ensure `PRINTER_PROFILES_PATH` is an absolute path
- Do not use `~` unless expanded to `$HOME`

### colprof gray-axis errors

- Check measurement quality
- Reduce profile quality (`-qm`)
- Increase target size
- Re-measure gray patches

---

End of documentation.
