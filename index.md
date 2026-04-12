# Argyll_Printer_Profiler Scripts — User Guide
**Version:** 1.3.8<br>
**Platform:** macOS, Linux (Bash script); macOS, Linux, Windows (Python script)<br>
**Based on:** Simple script by Jintak Han (https://github.com/jintakhan/AutomatedArgyllPrinter)<br>
**Author:** Knut Larsson<br>

`Argyll_Printer_Profiler` is available in two versions: a Bash script (`Argyll_Printer_Profiler.command`) and a Python script (`Argyll_Printer_Profiler.py`). Both automate a complete **ArgyllCMS printer profiling workflow** on supported platforms, from target generation to ICC installation.<br>

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
- X-Rite ColorMunki / i1Studio / i1 Pro and other instruments supported by ArgyllCMS
- Users who want:
  - Simple user-focused guidance from start to finish.
  - Reproducible, well-documented profiles without memorizing
    ArgyllCMS commands and manual procedural steps.

Make sure to read chapter on [Installation](#installation) below and follow steps in section [Getting Started](#getting-started).

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
- Builds ICC/ICM profiles
- Performs sanity checks
- Installs profiles into defined local profiles folder

**Details**

- Assists user through the whole printer profile creation process in one go: from target generation (targen+printtarg), reading (chartread), making profile (colprof) and outputting profile sanity check (profcheck+analysis).
- Configure a set of predefined targets, and select them from a menu (6 for Colormunki and 6 for other instruments) (editable from ini file)
- Configure defaults as desired for later reuse (targen, printtarg, chartread, and colprof)
- Re-measure / resume measurements on a previously incomplete / saved / interrupted measurement set
- Select pre-existing target chart to measure and create profile.
- Perform "sanity check" with extended statistics on any profile with existing ti3 file
- When creating a profile, a new folder is created with the name chosen for the profile, and needed files are copied and renamed automatically.
- Selection of ti2/3 files and icc/icm files is done through a file dialog, so that one does not have to write long path strings.
- Receive guidance on how to improve accuracy of created profile.


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
    - Check that dependencies are installed.
       - For MacOS/Linux:
          - See section [Bash Script Dependencies](#bash-script-dependencies).
       - For Windows:
          - See section[Python Script Dependencies](#python-script-dependencies).
    - Make sure environmental PATH variable for installed ArgyllCMS is present.
      This is especially important for Windows users. Use the script `add_argyll_path_windows`.
      which is supplied with the release of `Argyll\_Printer\_Profiler`.
      This script comes in two versions, use ase desired (guidance in header of file):
      1. Windows PowerShell: `add_argyll_path_windows.ps1` and
      2. Python: `add_argyll_path_windows.py`

2. Modify the setup to fit your operating system. See section [Key Parameters](#key-parameters) for understanding the most important configurable parameters. The following should be assessed/modified:

    a. Easily modified via main menu (option 6):

      - Paths, which are different for MacOS/Linux/Windows and **must be changed**
        if not valid (visible above main menu when running script):
          - ICC/ICM profile to use `PRINTER_ICC_PATH` for creation of printer
            profile (used by colprof). This affects the color gamut for
            perceptual and saturation intents created in the profile by ArgyllCMS.
            Absolute and Relative colorimetric rendering intents are not affected.
          - ICC/ICM profile to use `PRECONDITIONING_PROFILE_PATH`
            if target charts are generated to fit a particular profile (used by targen).
          - Location path `PRINTER_PROFILES_PATH` to folder where printer profiles
            are placed for operating system to use.

      - Ink limit. (keep empty to use ArgyllCMS specified default)
      - Paper size.
      - `STRIP_PATCH_CONSISTENSY_TOLERANCE`
        (tolerance for how much color patch can vary before warning by chartread)
      - `EXAMPLE_FILE_NAMING`
        (naming convention visible as guidance when specifying file name).

    b. Modified in .ini file (defaults can be used as is):

      - Common arguments to use by default (`COMMON_ARGUMENTS_*`).
        - Is `COMMON_ARGUMENTS_TARGEN` satisfactory?
        - Is `COMMON_ARGUMENTS_PRINTTARG` satisfactory?
        - Is `COMMON_ARGUMENTS_CHARTREAD` satisfactory?
        - Is `COMMON_ARGUMENTS_COLPROF` satisfactory?

      - Change menu arguments as desired (`INST_CM_MENU_*` and `INST_OTHER_MENU_*`).

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

**Note!**
Many Linux distributions have preinstalled Linux xdotool or wmctrl.
To verify if any of them is installed, open a terminal and run:

```bash
command -v xdotool >/dev/null 2>&1 && echo true || echo false
```
Outputs true if xdotool is installed, otherwise false.

```bash
command -v wmctrl >/dev/null 2>&1 && echo true || echo false
```
Outputs true if wmctrl is installed, otherwise false.


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

**Note!**
Ctrl + Right Click on the script, then Open, may work in many cases instead of running chmod command in terminal.

On modern macOS versions, a script must have the **execute bit** set.

1. Open Terminal
2. Navigate to the script folder
   (use: "cd [folder_name]" and "ls" to navigate, "cd .." to navigate one level up)
3. Run command:

```bash
chmod +x Argyll_Printer_Profiler.command
```

Verify (not strictly necessary):

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
However, the ".command" file extension is recommended to change to ".sh".
Rename file to .sh, then:

1. Open Terminal
2. Navigate to the script folder
   (use: "cd [folder_name]" and "ls" to navigate, "cd .." to navigate one level up)
3. Run command:

```bash
chmod +x Argyll_Printer_Profiler.sh
```

Verify (not strictly necessary):

```bash
ls -l Argyll_Printer_Profiler.sh
```

Expected output:

```
-rwxr-xr-x@ Argyll_Printer_Profiler.sh
```

Finally, the file manager preferences must be modified to run .sh files.

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
**For details on ArgyllCMS, the commands used by this script (targen, printtarg, chartread, colprof, profcheck), see:**
[https://www.argyllcms.com/doc/ArgyllDoc.html](https://www.argyllcms.com/doc/ArgyllDoc.html)

See `Argyll_Printer_Profiler_setup.ini` for a descriptions and list of all parameters.

- **`PRINTER_ICC_PATH`**
  Path to the RGB/CMYK colorspace profile used as reference (e.g. sRGB, AdobeRGB).

- **`PRINTER_PROFILES_PATH`**
  Destination folder for installed ICC/ICM profiles.
  Example (recommended for MacOS): `$HOME/Library/ColorSync/Profiles`

- **`STRIP_PATCH_CONSISTENSY_TOLERANCE`**
  Used by `chartread -T`
  Default recommendation: **0.6**

- **`INK_LIMIT`**
  Total ink limit used by `targen` and `colprof`

  Typical values:
  - Inkjet: 220–300
  - Laser: 180–260

- **`PAPER_SIZE`**
  `A4` or `Letter`

- **`PROFILE_SMOOTING`**
  Argument -r in `colprof` average deviation, affecting accuracy and smoothing of profile.
  Argyll-default 0.5. 1.0 makes smoother profile without much reduction in accuracy.

- **`TARGET_RESOLUTION`**
  DPI for generated TIFF targets

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

- Define profile name (used as name for created folder and files)
- Create profile folder
- Generate new targets (menu-selected from 12 optimized presets, 6 for ColorMunki, 6 for other instruments)
- Measure patches
- Create ICC/ICM profile
- Sanity check
- Install profile into specified profile folder
- Get help on how to improve profile accuracy using the sanity check results.

### 2. Resume or re-read an existing target chart measurement and create profile

- Continue from an existing `.ti3`. Useful if measurement was interrupted.
- Define profile name (used as name for created folder and files)
- Create new or overwrite existing profile `ti3`/`icc or icm`
- Create profile folder, copy needed files and rename them
- Measure patches
- Create ICC/ICM profile
- Sanity check
- Install profile into specified profile folder
- Get help on how to improve profile accuracy using the sanity check results.

### 3. Read an existing target chart from scratch and create profile

- Reuse printed targets
- Define profile name (used as name for created folder and files)
- Create new or overwrite existing profile `ti3`/`icc or icm`
- Create profile folder, copy needed files and rename them
- Measure patches
- Create ICC/ICM profile
- Sanity check
- Install profile into specified profile folder
- Get help on how to improve profile accuracy using the sanity check results.

### 4. Create printer profile from an existing measurement file

- Skip measurement
- Direct ICC/ICM generation in selected folder or create new profile folder
- Sanity check
- Install profile into specified profile folder
- Get help on how to improve profile accuracy using the sanity check results.

### 5. Perform sanity check on existing profile

- Runs `profcheck` on existing `.ti3` + `.icc or icm`
- File created is named: `profile name + _sanity_check.txt`
- Extended analysis calculations:
    - Patch count analysis (ΔE < 1.0, 2.0, 3.0)
    - Average, max, min, percentile statistics.
- If run several times, results in existing file are overwritten.
- Results are displayed in the terminal and in the created file.
- Get help on how to improve profile accuracy using the sanity check results.

### 6. Change setup parameters

- Edit selected values in the `.ini` file interactively

### 7. Show tips on how to improve accuracy of a profile

- Display important information and procedure on how to improve accuracy of created profile, using sanity check as basis. Option to show this information is also provided after creation of a profile.

### 8. Show ΔE2000 Color Accuracy — Quick Reference

- Displays ΔE2000 color difference values and their perceptual meaning
- Quick reference for evaluating profile quality
- Option to show this information is also provided after creation of a profile.

### 9. Exit script

---

## Target Generation Menu Options

The target generation menu options is available under main menu action **1**.

The script provides **6 optimized preset targets**, where patch counts and menu text are configurable in the `.ini` file.

### ColorMunki Instrument (A4/Letter Paper)
Default menu for ColorMunki instrument (User may modify/add as desired):

**A4 Paper Size:**
- **Option 1**: 210 patches  - Small  – 1 x A4 page,  quick profiling
- **Option 2**: 420 patches  - Medium – 2 x A4 pages, recommended minimum.
- **Option 3**: 630 patches  - Large  – 3 x A4 pages, better accuracy
- **Option 4**: 840 patches  - XL     – 4 x A4 pages, high quality
- **Option 5**: 1050 patches - XXL    – 5 x A4 pages, very high quality
- **Option 6**: 1260 patches - XXXL   – 6 x A4 pages, maximum quality

**Letter Paper Size:**
- **Option 1**: 196 patches  - Small  - 1 x Letter page,  quick profiling
- **Option 2**: 392 patches  - Medium - 2 x Letter pages, recommended minimum
- **Option 3**: 588 patches  - Large  - 3 x Letter pages, better accuracy
- **Option 4**: 784 patches  - XL     - 4 x Letter pages, high quality
- **Option 5**: 980 patches  - XXL    - 5 x Letter pages, very high quality
- **Option 6**: 1176 patches - XXXL   - 6 x Letter pages, maximum quality

The Colormunki menu above has separate options for A4 and Letter, shown according to the current setting of paper size, which can be chosen in main menu option 6.

### Other Instruments (Same for All Paper Sizes)
Default menu for other instruments (User may modify/add as desired):

- **Option 1**: 480 patches  - i1Pro Small  – 1 x A4 page,     quick profiling
- **Option 2**: 480 patches  - i1Pro Small  – 1 x Letter page, quick profiling
- **Option 3**: 957 patches  - i1Pro Medium – 1 x A4 page,     recommended default
- **Option 4**: 957 patches  - i1Pro Medium – 1 x Letter page, recommended default
- **Option 5**: 2250 patches - i1Pro Large  - 3 x A4 pages, better accuracy
- **Option 6**: 2250 patches - i1Pro Large  - 3 x Letter pages, better accuracy

The menu for Other Instruments is the same regardless of paper size. This means that, if options differentiate between A4 and Letter size, then the page size must first be set in main menu option 6.

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

- `.icc or .icm` file is copied to `PRINTER_PROFILES_PATH`
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

**If you require more detailed debugging information:
**In the .ini file, locate the common parameters for the command you want to debug:
- **`COMMON_ARGUMENTS_TARGEN`**.
- **`COMMON_ARGUMENTS_PRINTTARG`**.
- **`COMMON_ARGUMENTS_CHARTREAD`**.
- **`COMMON_ARGUMENTS_COLPROF`**

Change the **`-v`** argument on any of the parameters to **`-v2`**.
Now terminal output and log file will show detailed debug output from ArgyllCMS commands.

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

For .command script on Linux or MacOS:

   - Ensure execute bit is set (`chmod +x`). See sections:
      - [Execution Permissions for MacOS (Important)](#execution-permissions-for-macos-important)
      - [Execution Permissions for Linux (Important)](#execution-permissions-for-linux-important)
   - macOS Gatekeeper may require Ctrl+right-click → Open.
   - The .command script cannot run on Windows.

### Script does not find ArgyllCMS installation

Make sure ArgyllCMS is properly installed. Under chapter [Installation](#installation) see sections:

   - [Getting Started](#getting-started).
   - [Bash Script Dependencies](#bash-script-dependencies).
   - [Python Script Dependencies](#python-script-dependencies).

### Path warnings above main menu

- Ensure all path variables are set correctly according to your operating system (platform).
- Default when downloading `Argyll_Printer_Profiler` paths are for MacOS.
- User main menu option 6 to set all the path variables.
- `PRECONDITIONING_PROFILE_PATH` is allowed to be empty.

### ICC/ICM not copied

- Ensure `PRINTER_PROFILES_PATH` is an absolute path
- Do not use `~` unless expanded to `$HOME`

### Strip read recognised as other strip

If reading strips of a chart frequently gives warning that the strip is recognised as another strip, this is an imperfection caused by the random distribution of patches by the ArgyllCMS printtarg command. If many warnings occur it may indicate that the expected values in the .ti2 are not to be relied on (far from the values actually being measured), or the sequence of patches for each strip are distributed in a way that one strip is similar to another. Both cases can also be true at the same time.

To turn off all "wrong strip" and "unexpected value" warnings make sure the argument `-S` is added to parameter `COMMON_ARGUMENTS_CHARTREAD` in the .ini file.

**If you intend to perfect a generated chart then make note of the following:**  
Each generated chart has a seed number at the bottom, determining the random sequence. the "-R number" argument can be used with printtarg to make sure to use the same seed number every time, to reproduce a known good patch distribution.

Many charts deliverd with this script have not been verified, thus there is a chance this type of error may occur, given that argument `-S` is not used for ArgyllCMS chartread command. For this reason the command used to generate most targets have been provided (look in the folder of pre-made targets), so that the user can re-generate a target with a new random distribution. When a good working patch sequence is found, which does not give lots of "strip recognised as another strip" type error, then use the -R argument to make sure to keep the seed number. In some cases this seed number can then also be used on other similar targets.

### colprof gray-axis errors

Try the following:

- Check measurement quality
- Reduce profile quality (`-qm`)
- Increase target size
- Re-measure gray patches

---

End of documentation.
