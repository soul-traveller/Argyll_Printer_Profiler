# Argyll_Printer_Profiler.command — User Guide
**Version:** 1.0<br>
**Platform:** macOS<br>
**Based on:** Simple script by Jintak Han (https://github.com/jintakhan/AutomatedArgyllPrinter)<br>
**Author:** Knut Larsson<br>

Argyll_Printer_Profiler.command is an interactive Bash script that automates a complete **ArgyllCMS printer profiling workflow** on macOS, from target generation to ICC installation.<br>

---

## 📑 Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Installation on macOS](#installation-on-macos)
  - [ArgyllCMS Installation](#argyllcms-installation)
  - [Script Placement](#script-placement)
  - [Execution Permissions (Important)](#execution-permissions-important)
- [Setup File: Argyll_Printer_Profiler_setup.ini](#setup-file-Argyll_Printer_Profiler_setupini)
- [General Workflow](#general-workflow)
- [Main Menu Actions Explained](#main-menu-actions-explained)
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

The script:

- Generates optimized color targets
- Assists with printing targets correctly
- Reads measurements
- Builds ICC profiles
- Performs sanity checks
- Installs profiles into macOS local profiles folder

---

## Requirements

- macOS 10.13 or later (Intel or Apple Silicon)
- ArgyllCMS installed and available in Terminal (checked by script)
- Supported measurement device (ColorMunki, i1Pro, etc.)
- Terminal access
- ColorSync Utility (included with macOS)

---

## Installation on macOS

### ArgyllCMS Installation

The recommended way is Homebrew:

```bash
brew install argyll-cms
```

Verify installation:

```bash
targen -?
```

---

### Script Placement

You may place `Argyll_Printer_Profiler.command` **in any folder**:

- Desktop
- Documents
- External drive
- Project-specific folder

All generated files are stored **relative to the script’s location**.

---

### Execution Permissions (Important)

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

---

## Setup File: Argyll_Printer_Profiler_setup.ini

The setup file **must be located in the same folder as the script**:

```
Argyll_Printer_Profiler.command
Argyll_Printer_Profiler_setup.ini
```

### Key Parameters

- `PRINTER_ICC_PATH`
  Path to the RGB/CMYK colorspace profile used as reference (e.g. sRGB, AdobeRGB).

- `PRINTER_PROFILES_PATH`
  Destination folder for installed ICC profiles
  Example (recommended):
  ```$HOME/Library/ColorSync/Profiles```

- `STRIP_PATCH_CONSISTENSY_TOLERANCE`
  Used by `chartread -T`
  Default recommendation: **0.6**

- `INK_LIMIT`
  Total ink limit used by `targen` and `colprof`

  Typical values:
  - Inkjet: 220–300
  - Laser: 180–260

- `PAPER_SIZE`
  `A4` or `Letter`

- `PROFILE_SMOOTING`
  Argument -r in `colprof` average deviation, affecting accuracy and smooting of profile. Argyll-default 0.5. 1.0 makes smoother profile without much reduction in accuracy.

- `TARGET_RESOLUTION`
  DPI for generated TIFF targets

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

### 1. Create printer profile from scratch

- Define profile name
- Generate new targets (menu-selected)
- Measure patches
- Create ICC profile
- Sanity check
- Install profile into local profile folder

### 2. Re-read or resume partly read chart

- Continue from an existing `.ti3`. Useful if measurement was interrupted
- Measure patches
- Create new or overwrite existing profile `ti3`/`icc`
- Sanity check
- Install profile into local profile folder

### 3. Create profile from existing `.ti2`

- Reuse printed targets
- Measure again
- Create new or overwrite existing profile `ti3`/`icc`
- Sanity check
- Install profile into local profile folder

### 4. Create profile from existing `.ti3`

- Skip measurement
- Direct ICC generation in selected folder
    - Make sure `.ti3` file selected has unique name.
    - Overwrites existing `.icc` with same name, if exists
- Sanity check
- Install profile into local profile folder

### 5. Perform sanity check only

- Runs `profcheck` on existing `.ti3` + `.icc`
- File created is named: `profile name + _sanity_check.txt`
- If run several times, results are appended into same file.

### 6. Change setup parameters

- Edit selected values in the `.ini` file interactively

---

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
        └── Argyll_Printer_Profiler_YYYYMMDD_HHMMSS.log
```

All work is performed inside this folder once created.

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
- Optimized for ColorMunki/i1Studio

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
- Typically:
  ```
  ~/Library/ColorSync/Profiles
  ```

macOS applications must be **restarted** to see the new profile.

---

## Logs and Debugging

- A timestamped log file is created at script start
- Log is automatically moved into the profile folder
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
