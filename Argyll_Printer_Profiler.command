#!/usr/bin/env bash

# Version 1.0

# Argyll_Printer_Profiler
# Uses ArgyllCMS version that is installed and checks if commands are availeble in terminal.
# Files are stored in folder where script is run from.
#
# Important: To make script run in later MacOS versions, it is not enough to have
# Read and Write permission to execute a command script. One must have the execute (x) bit set.
# In Terminal run command "chmod +x Argyll_Printer_Profiler.command"
# To verify run command "ls -l Argyll_Printer_Profiler.command"
# The output should be similar to "-rwxr-xr-x@  Argyll_Printer_Profiler.command"
# Based on simple script by Jintak Han, https://github.com/jintakhan/AutomatedArgyllPrinter
# Redesigned by Knut Larsson, https://github.com/soul-traveller/Argyll_Printer_Profiler
# Based on instructions at https://rawtherapee.com/mirror/dcamprof/argyll-print.html

shopt -s nullglob

echo "=============================================================="
echo "    ___        _                        _           _ _       "
echo "   / _ \ _   _| |_ ___  _ __ ___   __ _| |_ ___  __| | |      "
echo "  | | | | | | | __/ _ \| '_ \` _ \ / _\` | __/ _ \/ _\` | |   "
echo "  | |_| | |_| | || (_) | | | | | | (_| | ||  __/ (_| | |      "
echo "   \___/ \__,_|\__\___/|_| |_| |_|\__,_|\__\___|\__,_|_|      "
echo "                                                              "
echo "        Argyll Printer Profiler (Automated Workflow)          "
echo "          Color Target Generation & ICC Profiling             "
echo "=============================================================="
echo
echo
echo "Automated ArgyllCMS script for calibrating printers on MacOS."
echo "Targets are adapted for use with X-Rite Colormunki Photo / i1Studio."
echo
echo "Author: Knut Larsson"
echo
echo
echo
# --- Set location and script name -------------------------------------------------
cd "$(dirname "$0")"
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
SCRIPT_NAME="$(basename -- "$0")"
TEMP_LOG="${SCRIPT_DIR}/Argyll_Printer_Profiler_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$TEMP_LOG") 2>&1
echo
echo "File path: ${SCRIPT_DIR}"
echo "Script executed: ${SCRIPT_NAME}"
echo

# --- Load setup file -------------------------------------------------
SETUP_FILE="${SCRIPT_DIR}/Argyll_Printer_Profiler_setup.ini"

if [ ! -f "$SETUP_FILE" ]; then
  echo "❌ Setup file not found:"
  echo "   The setup ini file must be located in folder together with script ${SCRIPT_NAME}."
  exit 1
fi

# Load variables
# shellcheck source=/dev/null
source "$SETUP_FILE"

# Check if setup parameters exist
for var in STRIP_PATCH_CONSISTENSY_TOLERANCE PRINTER_ICC_PATH COLOR_SYNC_UTILITY_PATH PRINTER_PROFILES_PATH PROFILE_SMOOTING TARGET_RESOLUTION; do
  if [ -z "${!var:-}" ]; then
    echo "❌ Variable $var not set. Check setup file."
    exit 1
  fi
done

# --- ArgyllCMS detection ---------------------------------------------
REQUIRED_CMDS=(targen chartread colprof printtarg profcheck dispcal)

for cmd in "${REQUIRED_CMDS[@]}"; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "❌ ArgyllCMS not found (missing command: $cmd)"
    echo
    echo "Install it using Homebrew:"
    echo "  brew install argyll-cms"
    echo
    exit 1
  fi
done

# --- Extract Argyll version --------------------------------------------------
ARGYLL_VERSION_LINE=$(dispcal 2>&1 | head -n 1)
ARGYLL_VERSION=$(echo "$ARGYLL_VERSION_LINE" | sed -n 's/.*Version \([0-9.]*\).*/\1/p')
echo "✅ ArgyllCMS detected"
echo "   Version: $ARGYLL_VERSION"
echo

# --- Functions --------------------------------------------------
move_log() {
    # Move log to profile folder
    if mv "$TEMP_LOG" "$PROFILE_FOLDER/" 2>/dev/null; then
        TEMP_LOG="${PROFILE_FOLDER}/$(basename "$TEMP_LOG")"
    else
        echo "⚠ Could not move log to profile folder"
        return 1
    fi
    exec > >(tee -a "$TEMP_LOG") 2>&1
}

prepare_profile_folder() {

    # Default fallback
    new_name="$name"

    # Do only if action 2 or 3 (ti2 or ti3 selection)
    if [[ "$action" == "2" || "$action" == "3" ]]; then
        echo
        echo 'Enter/modify filename for this new profile.'
        echo 'If your filename is foobar, your profile will be named foobar.icc.'
        echo "Previous name: $name"
        echo
        read -e -p "Enter filename (leave empty to keep previous): " new_name
        echo

        if [ -z "$new_name" ]; then
            # User pressed Enter → keep previous name untouched
            new_name="$name"
        else
            # User entered something → sanitize trailing junk
            # Remove trailing spaces, tabs, CR, LF, and any POSIX whitespace
            new_name="$(printf '%s' "$new_name" | sed 's/[[:space:]]*$//')"
        fi
    fi

    PROFILE_FOLDER="${SCRIPT_DIR}/${CREATED_PROFILES_FOLDER}/${new_name}"

    mkdir -p "$PROFILE_FOLDER" || {
        echo "❌ Failed to create profile folder: $PROFILE_FOLDER"
        return 1
    }

    # Move log to profile folder
    move_log

    echo "✅ Working folder for profile:"
    echo "$PROFILE_FOLDER"

    cd "$PROFILE_FOLDER" || {
        echo "❌ Failed to change directory to $PROFILE_FOLDER"
        return 1
    }

    desc="$new_name"
}

rename_files() {
    echo "Renaming files to match new profile name…"
    local f base suffix ext newfile i

    # Rename files
    mv "${name}.ti1" "${new_name}.ti1" || {
        echo "❌ Failed to rename ${name}.ti1 → ${new_name}.ti1"
        return 1
    }
    mv "${name}.ti2" "${new_name}.ti2" || {
        echo "❌ Failed to rename ${name}.ti2 → ${new_name}.ti2"
        return 1
    }

    # Do only if action 2 (ti3 selection)
    if [ "$action" == "2" ]; then
        mv "${name}.ti3" "${new_name}.ti3" || {
            echo "❌ Failed to rename ${name}.ti3 → ${new_name}.ti3"
            return 1
        }
    fi

    # DEBUG!!!
    #echo
    #echo "name: ${name}"
    #echo "new_name: ${new_name}"
    #echo

    # Rename tif files, except trailing numbering.
    for i in "${!tif_files[@]}"; do
        f="${tif_files[$i]}"
        [ -f "$f" ] || continue

        # Extract extension
        ext=".${f##*.}"

        # Extract suffix (_01, _02, etc.)
        if [[ "$(basename "$f" "$ext")" =~ _[0-9]{2}$ ]]; then
            suffix="${BASH_REMATCH[0]}"
        else
            suffix=""
        fi

        # Build new filename. Profile folder must have had 'cd' performed.
        #newfile="${PROFILE_FOLDER}/${new_name}${suffix}${ext}"
        newfile="${new_name}${suffix}${ext}"

        # Rename file
        mv "$(basename "$f")" "$newfile" || {
            echo "❌ Failed to rename $(basename "$f") → $(basename "$newfile")"
            return 1
        }

        # DEBUG!!!
        #echo
        #echo "ext: $ext"
        #echo "suffix: $suffix"
        #echo "basename f: $(basename "$f")"
        #echo "basename newfile: $(basename "$newfile")"
        #echo

        # Update array immediately
        tif_files[$i]="$newfile"
    done

    # Update logical variables
    name="$new_name"
    desc="$new_name"
}

specify_profile_name() {
    echo
    echo 'When specifying a profile description/filename the following is highly recommended to include:'
    echo '  - Printer ID'
    echo '  - Paper ID'
    echo '  - Target used for profile'
    echo '  - Instrument/calibration type used'
    echo '  - Date'
    echo "Example filename: ${EXAMPLE_FILE_NAMING}"
    echo 'For simplicity, profile description and filename are made identical.'
    echo 'The profile description is what you will see in Photoshop and ColorSync Utility.'
    echo
    echo 'Enter a desired filename for this profile.'
    echo 'If your filename is foobar, your profile will be named foobar.icc.'
    echo
    read -e -p 'Enter filename: ' name

    prepare_profile_folder || {
        echo "Profile preparation failed..."
        return 1
    }
    echo
}

select_icc_profile() {
    # Opens a file selection dialog starting from the folder in PRINTER_ICC_PATH
    # Allows selecting a new .icc file
    # Updates the .ini setup file to store the new path
    # If cancelled, nothing is changed and it returns to main_menu

    echo
    echo "Select a new ICC profile to use"

    # Extract folder and current file from PRINTER_ICC_PATH
    local current_file
    local folder
    current_file="$(basename "$PRINTER_ICC_PATH")"
    folder="$(dirname "$PRINTER_ICC_PATH")"

    # Open AppleScript file chooser dialog
    local new_icc_path
    new_icc_path=$(osascript <<EOF
try
    tell application "Finder"
        activate
        set f to choose file with prompt "Select a new ICC profile (.icc or .icm)" of type {"icc", "icm"} default location POSIX file "${folder}"
        POSIX path of f
    end tell
on error
    return ""
end try
EOF
)

    # Check if user cancelled
    if [ -z "$new_icc_path" ]; then
        echo "Selection cancelled."
        echo
        return 1
    fi

    # Validate file extension
    local ext="${new_icc_path##*.}"
    if [[ "$ext" != "icc" && "$ext" != "icm" ]]; then
        echo "❌ Selected file is not a .icc or .icm file."
        return 1
    fi

    echo "Selected ICC profile: $new_icc_path"

    # Update the setup file
    if [ ! -f "$SETUP_FILE" ]; then
        echo "❌ Setup file not found. Cannot save new ICC profile."
        return 1
    fi

    # Escape slashes for sed
    local escaped_path
    escaped_path=$(printf '%s\n' "$new_icc_path" | sed 's/[\/&]/\\&/g')

    # Replace the line starting with PRINTER_ICC_PATH=
    sed -i.bak "s|^PRINTER_ICC_PATH=.*|PRINTER_ICC_PATH=\"${escaped_path}\"|" "$SETUP_FILE"

    echo "✅ Updated PRINTER_ICC_PATH in setup file:"
    echo "   $SETUP_FILE"
    echo "   New path: $new_icc_path"
    echo
}

select_instrument() {
    echo
    echo 'Creating a test chart...'
    echo 'Please choose a spectrophotometer model. This effects how target is generated.'
    echo '1: i1Pro'
    echo '2: i1Pro3+'
    echo '3: ColorMunki (Default)'
    echo '4: DTP20'
    echo '5: DTP22'
    echo '6: DTP41'
    echo '7: DTP51'
    echo '8: SpectroScan'
    echo
    read -r -n 1 -p 'Enter your choice [1–8]: ' answer
    case $answer in
      1)
        inst_arg='-ii1'
        inst_name='i1Pro'
        ;;
      2)
        inst_arg='-i3p'
        inst_name='i1Pro3+'
        ;;
      3)
        inst_arg="-iCM -h"
        inst_name='ColorMunki'
        ;;
      4)
        inst_arg='-i20'
        inst_name='DTP20'
        ;;
      5)
        inst_arg='-i22'
        inst_name='DTP22'
        ;;
      6)
        inst_arg='-i41'
        inst_name='DTP41'
        ;;
      7)
        inst_arg='-i51'
        inst_name='DTP51'
        ;;
      8)
        inst_arg='-iSS'
        inst_name='SpectroScan'
        ;;
      *)
        inst_arg="-iCM -h"
        inst_name='ColorMunki'
        echo 'No valid selection made. Using default instrument...'
        ;;
    esac
    echo
    echo "Selected instrument: ${inst_name}"
    echo
}

specify_and_generate_target() {
    default_target() {
      if [ "$PAPER_SIZE" = "Letter" ]; then
        patch_count='392'
      else
        patch_count='420'
      fi
      label='Medium (default)'
      white_patches='5'
      black_patches='5'
      gray_steps='64'
      multi_cube_steps='5'
      multi_cube_surface_steps='4'
      layout_seed='-R2'
    }

    while true; do
        # Display menu depending on paper size
        if [ "$PAPER_SIZE" = "A4" ]; then
            echo 'Select the target size:'
            echo '1: Small  – 210 patches  - 1 x A4 page  (quick, lower accuracy)'
            echo '2: Medium – 420 patches  - 2 x A4 pages (recommended default)'
            echo '3: Large  – 630 patches  - 3 x A4 pages (better accuracy)'
            echo '4: XL     – 840 patches  - 4 x A4 pages'
            echo '5: XXL    – 1050 patches - 5 x A4 pages'
            echo '6: XXXL   – 1260 patches - 6 x A4 pages (maximum quality)'

        elif [ "$PAPER_SIZE" = "Letter" ]; then
            echo 'Select the target size:'
            echo '1: Small  – 196 patches  - 1 x Letter page  (quick, lower accuracy)'
            echo '2: Medium – 392 patches  - 2 x Letter pages (recommended default)'
            echo '3: Large  – 588 patches  - 3 x Letter pages (better accuracy)'
            echo '4: XL     – 784 patches  - 4 x Letter pages'
            echo '5: XXL    – 980 patches  - 5 x Letter pages'
            echo '6: XXXL   – 1176 patches - 6 x Letter pages (maximum quality)'
        else
            # PAPER_SIZE A4 or any other value than Letter
            echo "⚠ Unknown PAPER_SIZE \"$PAPER_SIZE\", reverting to A4."
            PAPER_SIZE="A4"
            echo 'Select the target size:'
            echo '1: Small  – 210 patches  - 1 x A4 page  (quick, lower accuracy)'
            echo '2: Medium – 420 patches  - 2 x A4 pages (recommended default)'
            echo '3: Large  – 630 patches  - 3 x A4 pages (better accuracy)'
            echo '4: XL     – 840 patches  - 4 x A4 pages'
            echo '5: XXL    – 1050 patches - 5 x A4 pages'
            echo '6: XXXL   – 1260 patches - 6 x A4 pages (maximum quality)'
        fi

        echo
        # Prompt user after menu
        read -r -n 1 -p 'Enter your choice [1–6]: ' patch_choice
        case "$patch_choice" in
        1)
          if [ "$PAPER_SIZE" = "Letter" ]; then
            patch_count='196'
          else
            patch_count='210'
          fi
          label='Small'
          white_patches='4'
          black_patches='4'
          gray_steps='32'
          multi_cube_steps='3'
          multi_cube_surface_steps='3'
          layout_seed='-R1'
          ;;
        2)
          default_target
          ;;
        3)
          if [ "$PAPER_SIZE" = "Letter" ]; then
            patch_count='588'
          else
            patch_count='630'
          fi
          label='Large'
          white_patches='6'
          black_patches='6'
          gray_steps='64'
          multi_cube_steps='6'
          multi_cube_surface_steps='6'
          layout_seed='-R3'
          ;;
        4)
          if [ "$PAPER_SIZE" = "Letter" ]; then
            patch_count='784'
          else
            patch_count='840'
          fi
          label='XL'
          white_patches='7'
          black_patches='7'
          gray_steps='128'
          multi_cube_steps='7'
          multi_cube_surface_steps='7'
          layout_seed='-R4'
          ;;
        5)
          if [ "$PAPER_SIZE" = "Letter" ]; then
            patch_count='980'
          else
            patch_count='1050'
          fi
          label='XXL'
          white_patches='8'
          black_patches='8'
          gray_steps='128'
          multi_cube_steps='8'
          multi_cube_surface_steps='8'
          layout_seed='-R5'
          ;;
        6)
          if [ "$PAPER_SIZE" = "Letter" ]; then
            patch_count='1176'
          else
            patch_count='1260'
          fi
          label='XXXL'
          white_patches='8'
          black_patches='8'
          gray_steps='128'
          multi_cube_steps='8'
          multi_cube_surface_steps='8'
          layout_seed='-R6'
          ;;
        *)
          default_target
          echo 'Invalid selection. Using default.'
          ;;
        esac

        echo
        echo "Selected target: ${label} – ${patch_count} patches"

        read -r -n 1 -p 'Do you want to continue with select target? [y/n]: ' again
        case "$again" in
        [yY]|[yY][eE][sS])
          echo 'Continuing with selected target...'
          break
          ;;
        *)
          echo 'Repeating target selection...'
          ;;
        esac
    done

    ## Removed defined layout seed for printtarg if not used
    if [ "$USE_LAYOUT_SEED_FOR_TARGET" = "false" ]; then
        layout_seed=''
    fi

    echo
    echo 'Generating target color values (.ti1 file)...'
    echo "Command Used: targen ${COMMON_ARGUMENTS_TARGEN} -l${INK_LIMIT} -e${white_patches} -B${black_patches} -g${gray_steps} -m${multi_cube_steps} -M${multi_cube_surface_steps} -f${patch_count} "${name}""
    # --- Generate target ONLY ONCE, after confirmation ---
    targen ${COMMON_ARGUMENTS_TARGEN} -e${white_patches} -B${black_patches} -g${gray_steps} -m${multi_cube_steps} -f${patch_count} "${name}" || {
        echo "❌ targen failed. See log for details."
        return 1
    }

    echo
    echo 'Generating target(s) (.tif image(es) and .ti2 file)...'
    echo "Command Used: printtarg ${COMMON_ARGUMENTS_PRINTTARG} ${inst_arg} -b ${layout_seed} -r${PROFILE_SMOOTING} -T${TARGET_RESOLUTION} -p${PAPER_SIZE} "${name}""
    # Common printtarg command
    printtarg ${COMMON_ARGUMENTS_PRINTTARG} ${inst_arg} -b ${layout_seed} -r${PROFILE_SMOOTING} -T${TARGET_RESOLUTION} -p${PAPER_SIZE} "${name}" || {
        echo "❌ printtarg failed. See log for details."
        return 1
    }
    echo

    # Detect generated TIFF files (single-page or multi-page)
    tif_files=()
    # Check if single-page file exists
    [ -f "${name}.tif" ] && tif_files+=("${name}.tif")

    # Check for multi-page files with _XX suffix
    for f in "${name}"_??.tif; do
        [ -f "$f" ] && tif_files+=("$f")
    done

    if [ ${#tif_files[@]} -eq 0 ]; then
        echo "❌ No TIFF files were created by printtarg."
        return 1
    fi

    echo "Test chart(s) created:"
    for f in "${tif_files[@]}"; do
        echo "  $f"
    done

    echo 'Please print the test chart(s) using ColorSync Utility (opens automatically).'
    echo 'In the Printer dialog set option "Colour" to "Print as Color Target".'
    echo 'This will print without color management.'
    echo 'Tip: It might be beneficial to print targets with 88-90% scaling to prevent the rubber'
    echo '     taps underneath the Colormunki to interfere with reading of the first patches.'

    # Open all created TIFFs in ColorSync Utility
    for f in "${tif_files[@]}"; do
        open -a "${COLOR_SYNC_UTILITY_PATH}" "$f"
    done

    echo
    read -p 'After target(s) have been printed, press enter to continue...'
    echo
    echo 'Please connect the spectrophotometer.'
    read -p 'Press enter to continue...'
    echo
}

check_files_in_new_location_after_copy() {
    local missing_files=0
    # Check .ti2, applicable for both ti2 and ti3 selection
    if [ ! -f "${PROFILE_FOLDER}/${name}.ti2" ]; then
        echo "❌ Missing ${name}.ti2 in $PROFILE_FOLDER"
        missing_files=1
    fi

    # Check .ti3 if exists (only for ti3 selection)
    if [ "$action" = "2" ]; then
        if [ ! -f "${PROFILE_FOLDER}/${name}.ti3" ]; then
            echo "❌ Missing ${name}.ti3 in $PROFILE_FOLDER"
            missing_files=1
        fi
    fi

    # Check TIFFs
    tif_files=()
    if [ -f "${PROFILE_FOLDER}/${name}.tif" ]; then
        tif_files+=("${PROFILE_FOLDER}/${name}.tif")
    fi
    for f in "${PROFILE_FOLDER}/${name}"_??.tif; do
        [ -f "$f" ] && tif_files+=("$f")
    done

    if [ ${#tif_files[@]} -eq 0 ]; then
        echo "❌ No TIFF files found in $PROFILE_FOLDER"
        missing_files=1
    fi

    # If any missing, abort
    if [ "$missing_files" -eq 1 ]; then
        echo "❌ File copy to profile location failed. Returning to main menu..."
        return 1
    fi
}


select_ti2_file() {
    # Open dialog to select .ti2 file, starting from folder where script is located (SCRIPT_DIR).
    # Verify that selected file has .tif images with same name. If more than one image, filenames must end with _01, _02, ..., _03, etc.
    # Set found filenames to parameter tif_files[@]
    # Set filename selected to parameter ${name} and ${desc}
    echo

    local ti2_path
    ti2_path=$(osascript <<EOF
try
    tell application "Finder"
        activate
        set f to choose file with prompt "Select a .ti2 file" of type {"ti2"} default location POSIX file "${SCRIPT_DIR}/${CREATED_PROFILES_FOLDER}"
        POSIX path of f
    end tell
on error
    return ""
end try
EOF
)

    # User cancelled → return to main menu
    if [ -z "$ti2_path" ]; then
        echo "Selection cancelled."
        echo
        return 1
    fi

    if [[ "${ti2_path##*.}" != "ti2" ]]; then
        echo "❌ Selected file is not a .ti2 file."
        return 1
    fi

    name="$(basename "$ti2_path" .ti2)"
    desc="$name"
    # Folder where the selected file resides
    SOURCE_FOLDER="$(dirname "$ti2_path")"

    echo "Selected .ti2 file: $ti2_path"

    # Check TIFF targets
    tif_files=()

    # Single-page
    if [ -f "${SOURCE_FOLDER}/${name}.tif" ]; then
        tif_files+=("${SOURCE_FOLDER}/${name}.tif")
    else
        # Multi-page
        for f in "${SOURCE_FOLDER}/${name}"_??.tif; do
            [ -f "$f" ] && tif_files+=("$f")
        done
    fi

    if [ ${#tif_files[@]} -eq 0 ]; then
        echo "❌ No matching .tif target images found for '${name}'."
        return 1
    fi

    echo "Found target image(s):"
    for f in "${tif_files[@]}"; do
        echo "  $(basename "$f")"
    done

    while true; do
        echo
        echo "Do you want to:"
        echo "1: Create new profile (copy files into new folder)"
        echo "2: Overwrite existing (use files in their current location)"
        echo "3: Abort operation"
        echo
        read -r -n 1 -p 'Enter your choice [1-3]: ' copy_choice
        echo

        case "$copy_choice" in
          1)
            # Create new folder
            prepare_profile_folder || {
                echo "Profile preparation failed..."
                return 1
            }
            # Copy existing files into new folder
            cp "${SOURCE_FOLDER}/${name}.ti1" "$PROFILE_FOLDER/" || {
                echo "❌ Failed to copy ${name}.ti1 to directory to $PROFILE_FOLDER"
            }
            cp "${SOURCE_FOLDER}/${name}.ti2" "$PROFILE_FOLDER/" || {
                echo "❌ Failed to copy ${name}.ti2 to directory to $PROFILE_FOLDER"
            }
            # Copy all TIFFs from tif_files array
            for f in "${tif_files[@]}"; do
                cp "$f" "$PROFILE_FOLDER/" || {
                    echo "❌ Failed to copy $(basename "$f") to $PROFILE_FOLDER"
                }
            done

            rename_files || {
                echo "File renaming failed..."
                return 1
            }

            check_files_in_new_location_after_copy || {
                echo "File check after copy failed..."
                return 1
            }
            break  # exit submenu loop
            ;;
          2)
            # Overwrite existing
            # Update PROFILE_FOLDER to folder of selected .ti2 file
            PROFILE_FOLDER="$SOURCE_FOLDER"

            # Move log to profile folder
            move_log

            echo "✅ Working folder for profile:"
            echo "$PROFILE_FOLDER"
            # Change working directory
            cd "$PROFILE_FOLDER" || {
                echo "❌ Failed to change directory to $PROFILE_FOLDER"
                return 1
            }
            break  # exit submenu loop
            ;;
          3)
            echo "User chose to abort."
            return 1
            ;;
          *)
            echo "Invalid selection. Please choose 1 or 2."
            ;;
        esac
    done
}

select_ti3_file() {
    # Open dialog to select .ti3 file, starting from folder where script is located (SCRIPT_DIR).
    # Verify that selected file has .ti2 file and .tif images with same name. If more than one image, filenames must end with _01, _02, ..., _03, etc.
    # Set found filenames to parameter tif_files[@]
    # Set filename selected to parameter ${name} and ${desc}
    echo

    local ti3_path
    ti3_path=$(osascript <<EOF
try
    tell application "Finder"
        activate
        set f to choose file with prompt "Select a .ti3 file" of type {"ti3"} default location POSIX file "${SCRIPT_DIR}/${CREATED_PROFILES_FOLDER}"
        POSIX path of f
    end tell
on error
    return ""
end try
EOF
)

    # User cancelled → return to main menu
    if [ -z "$ti3_path" ]; then
        echo "Selection cancelled."
        echo
        return 1
    fi

    if [[ "${ti3_path##*.}" != "ti3" ]]; then
        echo "❌ Selected file is not a .ti3 file."
        return 1
    fi

    name="$(basename "$ti3_path" .ti3)"
    desc="$name"
    # Folder where the selected file resides
    SOURCE_FOLDER="$(dirname "$ti3_path")"

    echo "Selected .ti3 file: $ti3_path"

    # Verify .ti2 exists
    if [ ! -f "${SOURCE_FOLDER}/${name}.ti2" ]; then
        echo "❌ Matching .ti2 file not found for '${name}'."
        return 1
    fi

    # Check TIFF targets
    tif_files=()

    # Single-page
    if [ -f "${SOURCE_FOLDER}/${name}.tif" ]; then
        tif_files+=("${SOURCE_FOLDER}/${name}.tif")
    else
        # Multi-page
        for f in "${SOURCE_FOLDER}/${name}"_??.tif; do
            [ -f "$f" ] && tif_files+=("$f")
        done
    fi

    if [ ${#tif_files[@]} -eq 0 ]; then
        echo "❌ No matching .tif target images found for '${name}'."
        return 1
    fi

    echo "Found target image(s):"
    for f in "${tif_files[@]}"; do
        echo "  $(basename "$f")"
    done

    while true; do
        echo
        echo "Do you want to:"
        echo "1: Create new profile (copy files into new folder)"
        echo "2: Overwrite existing (use files in their current location)"
        echo "3: Abort operation"
        echo
        read -r -n 1 -p 'Enter your choice [1-3]: ' copy_choice
        echo

        case "$copy_choice" in
          1)
            # Create new folder
            prepare_profile_folder || {
                echo "Profile preparation failed..."
                return 1
            }
            # Copy existing files into new folder
            cp "${SOURCE_FOLDER}/${name}.ti1" "$PROFILE_FOLDER/" || {
                echo "❌ Failed to copy ${name}.ti1 to directory to $PROFILE_FOLDER"
            }
            cp "${SOURCE_FOLDER}/${name}.ti2" "$PROFILE_FOLDER/" || {
                echo "❌ Failed to copy ${name}.ti2 to directory to $PROFILE_FOLDER"
            }
            cp "${SOURCE_FOLDER}/${name}.ti3" "$PROFILE_FOLDER/" || {
                echo "❌ Failed to copy ${name}.ti3 to directory to $PROFILE_FOLDER"
            }
            # Copy all TIFFs from tif_files array
            for f in "${tif_files[@]}"; do
                cp "$f" "$PROFILE_FOLDER/" || {
                    echo "❌ Failed to copy $(basename "$f") to $PROFILE_FOLDER"
                }
            done

            rename_files || {
                echo "File renaming failed..."
                return 1
            }

            check_files_in_new_location_after_copy || {
                echo "File check after copy failed..."
                return 1
            }
            break  # exit submenu loop
            ;;
          2)
            # Overwrite existing
            # Update PROFILE_FOLDER to folder of selected .ti3 file
            PROFILE_FOLDER="$SOURCE_FOLDER"

            # Move log to profile folder
            move_log

            echo "✅ Working folder for profile:"
            echo "$PROFILE_FOLDER"
            # Change working directory
            cd "$PROFILE_FOLDER" || {
                echo "❌ Failed to change directory to $PROFILE_FOLDER"
                return 1
            }
            break  # exit submenu loop
            ;;
          3)
            echo "User chose to abort."
            return 1
            ;;
          *)
            echo "Invalid selection. Please choose 1 or 2."
            ;;
        esac
    done
}

select_ti3_file_only() {
    # Open dialog to select .ti3 file, starting from folder where script is located (SCRIPT_DIR).
    # Verify that selected file has .ti3 file
    # Set found filenames to parameter tif_files[@]
    # Set filename selected to parameter ${name} and ${desc}
    echo

    local ti3_path
    ti3_path=$(osascript <<EOF
try
    tell application "Finder"
        activate
        set f to choose file with prompt "Select a .ti3 file" of type {"ti3"} default location POSIX file "${SCRIPT_DIR}/${CREATED_PROFILES_FOLDER}"
        POSIX path of f
    end tell
on error
    return ""
end try
EOF
)

    # User cancelled → return to main menu
    if [ -z "$ti3_path" ]; then
        echo "Selection cancelled."
        echo
        return 1
    fi

    if [[ "${ti3_path##*.}" != "ti3" ]]; then
        echo "❌ Selected file is not a .ti3 file."
        return 1
    fi

    name="$(basename "$ti3_path" .ti3)"
    desc="$name"
    # Folder where the selected file resides
    SOURCE_FOLDER="$(dirname "$ti3_path")"

    # only for action 5 (perform sanity check)
    if [ "$action" = "5" ]; then
        # Verify .icc exists
        if [ ! -f "${SOURCE_FOLDER}/${name}.icc" ]; then
            echo "❌ Matching .icc file not found for '${name}'."
            return 1
        fi
    fi

    echo "Selected .ti3 file: $ti3_path"

    # Overwrite existing
    # Update PROFILE_FOLDER to folder of selected .ti3 file
    PROFILE_FOLDER="$SOURCE_FOLDER"

    # Move log to profile folder
    move_log

    echo "✅ Working folder for profile:"
    echo "$PROFILE_FOLDER"
    # Change working directory
    cd "$PROFILE_FOLDER" || {
        echo "❌ Failed to change directory to $PROFILE_FOLDER"
        return 1
    }
}

sanity_check() {
    echo
    echo 'Performing sanity check (creating .txt file)...'
    echo
    echo "Command Used: profcheck -k "${name}.ti3" "${name}.icc" | tee -a "${name}_sanity_check.txt""
    echo
    echo "and,"
    echo
    echo "Command Used: profcheck -v2 -k -s "${name}.ti3" "${name}.icc" 2>&1 >> "${name}_sanity_check.txt""
    echo
    profcheck -k "${name}.ti3" "${name}.icc" | tee -a "${name}_sanity_check.txt" || {
        echo
        echo "❌ profcheck failed. See log for details."
        echo
        return 1
    }
    profcheck -v2 -k -s "${name}.ti3" "${name}.icc" 2>&1 >> "${name}_sanity_check.txt" || {
        echo
        echo "❌ profcheck failed. See log for details."
        echo
        return 1
    }
    echo
    echo "Detailed sanity check stored in '${name}_sanity_check.txt'."
    echo 'Sanity check complete.'
    echo
    echo
    echo "If any of the profile values in the sanity check exceed 2.0"
    echo "it is recommended to remeasure patches or whole target."
    echo
    echo
}

perform_measurement_and_profile_creation() {
    echo
    echo "Starting chart reading (read .ti2 file and generate .ti3 file)..."
    echo

    if [ "$action" = "2" ]; then    # re-read or resume partly read chart
        # Capture modification time state before chartread
        local ti3_file="${name}.ti3"
        local ti3_mtime_before=""
        if [ -f "$ti3_file" ]; then
            ti3_mtime_before=$(stat -f "%m" "$ti3_file")
        fi

        echo "Command Used: chartread ${COMMON_ARGUMENTS_CHARTREAD} -r -T"${STRIP_PATCH_CONSISTENSY_TOLERANCE}" "${name}""
        echo
        echo "Tips:"
        echo "     - Reading speed to more than 7 sec per strip reduces"
        echo "       frequent re-reading due to inconsistent results."
        echo "     - If frequent inconsistent results try altering"
        echo "       patch consistency tolerance."
        echo "     - Save progress once in a while with 'd' and then"
        echo "       resume measuring with option 2 of main manu."
        echo
        chartread ${COMMON_ARGUMENTS_CHARTREAD} -r -T"${STRIP_PATCH_CONSISTENSY_TOLERANCE}" "${name}" || {
            echo
            echo "❌ chartread failed. See log for details."
            echo
            return 1
        }

        # Detect abort after chartread
        # Resume mode: Check if file modified, if not user abored
        local ti3_mtime_after
        ti3_mtime_after=$(stat -f "%m" "$ti3_file")

        if [[ "$ti3_mtime_after" == "$ti3_mtime_before" ]]; then
            echo
            echo "⚠️ Chartread aborted by user (no new measurements written)."
            echo
            return 1
        fi

    else # Normal chartread
        echo "Command Used: chartread ${COMMON_ARGUMENTS_CHARTREAD} -T"${STRIP_PATCH_CONSISTENSY_TOLERANCE}" "${name}""
        echo
        echo "Tips:"
        echo "     - Reading speed to more than 7 sec per strip reduces"
        echo "       frequent re-reading due to inconsistent results."
        echo "     - If frequent inconsistent results try altering"
        echo "       patch consistency tolerance."
        echo "     - Save progress once in a while with 'd' and then"
        echo "       resume measuring with option 2 of main manu."
        echo
        chartread ${COMMON_ARGUMENTS_CHARTREAD} -T"${STRIP_PATCH_CONSISTENSY_TOLERANCE}" "${name}" || {
            echo
            echo "❌ chartread failed. See log for details."
            echo
            return 1
        }

        # Detect abort after chartread
        # Fresh read: file must exist
        if [ ! -f "$ti3_file" ]; then
            echo
            echo "⚠️ Chartread aborted by user."
            echo
            return 1
        fi
    fi

    echo
    read -r -n 1 -p 'Do you want to continue creating profile with resulting ti3 file? [y/n]: ' continue
    case "$continue" in
    [yY]|[yY][eE][sS])
        echo
        echo
        echo "Starting profile creation (read .ti3 file and generate .icc file)..."
        echo "Command Used: colprof ${COMMON_ARGUMENTS_COLPROF} -S \"${PRINTER_ICC_PATH}\" -D"${desc}" "${name}""
        colprof ${COMMON_ARGUMENTS_COLPROF} -l${INK_LIMIT} -S "${PRINTER_ICC_PATH}" -D"${desc}" "${name}" || {
            echo
            echo "❌ colprof failed. See log for details."
            echo
            return 1
        }
        echo
        echo 'Profile created.'
        echo
        ;;
    *)
        echo
        echo 'Profile creation aborted by user...'
        echo
        return 1
        ;;
    esac
    sanity_check || {
        return 1
    }
}

create_profile_from_existing() {
    echo
    echo
    echo "Starting profile creation (read .ti3 file and generate .icc file)..."
    echo "Command Used: colprof ${COMMON_ARGUMENTS_COLPROF} -S \"${PRINTER_ICC_PATH}\" -D"${desc}" "${name}""
    colprof ${COMMON_ARGUMENTS_COLPROF} -l${INK_LIMIT} -S "${PRINTER_ICC_PATH}" -D"${desc}" "${name}" || {
        echo
        echo "❌ colprof failed. See log for details."
        echo
        return 1
    }
    echo
    echo 'Profile created.'
    echo
    sanity_check || {
        return 1
    }
}

install_profile_and_save_data() {
    echo 'Installing measured ICC profile...'
    cp "${name}.icc" "${PRINTER_PROFILES_PATH}" || {
        echo "❌ Failed to copy ICC profile to ${PRINTER_PROFILES_PATH}. See log for details."
        return 1
    }
    echo "Finished. '${name}.icc' was installed to the directory '${PRINTER_PROFILES_PATH}'"
    echo "Please restart any color-managed applications before using this profile."
    echo "To print with this profile in a color-managed workflow, select "'${desc}'" in the profile selection menu."
}

edit_setup_parameters() {
    while true; do
        icc_filename="${PRINTER_ICC_PATH##*/}"

        echo
        echo
        echo "In this menu some variables stored in the $SETUP_FILE file can be modified."
        echo "For other parameters modify the file in a text editor."
        echo
        echo "What parameter do you want to modify?"
        echo
        echo "1: Select Color Space profile to use when creating printer profile."
        echo "   Current file specified: '${icc_filename}'"
        echo
        echo "2: Modify patch consistency tolerance (chartread arg. -T)"
        echo "   Current value specified: '${STRIP_PATCH_CONSISTENSY_TOLERANCE}'"
        echo
        echo "3: Modify paper size for target generation. Valid values: A4, Letter."
        echo "   Current value specified: '${PAPER_SIZE}'"
        echo
        echo "4: Modify ink limit. Valid values: 0 – 400 (%)."
        echo "   Current value specified: '${INK_LIMIT}'"
        echo
        echo "5: Go back to main menu."
        echo

        read -r -n 1 -p "Enter your choice [1–5]: " answer
        echo

        case $answer in
            1)
                select_icc_profile || {
                    echo "Returning to setup menu..."
                }
                source "$SETUP_FILE"
                continue
                ;;

            2)
                echo
                read -r -p "Enter new value [0.6 recommended]: " value

                if [[ ! "$value" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
                    echo "❌ Invalid numeric value."
                    continue
                fi

                sed -i.bak "s|^STRIP_PATCH_CONSISTENSY_TOLERANCE=.*|STRIP_PATCH_CONSISTENSY_TOLERANCE=${value}|" "$SETUP_FILE"

                echo "✅ Updated STRIP_PATCH_CONSISTENSY_TOLERANCE to $value"
                source "$SETUP_FILE"
                continue
                ;;

            3)
                echo
                read -r -p "Enter paper size [A4 or Letter]: " value

                case "$value" in
                    A4|Letter)
                        sed -i.bak "s|^PAPER_SIZE=.*|PAPER_SIZE=${value}|" "$SETUP_FILE"
                        echo "✅ Updated PAPER_SIZE to $value"
                        source "$SETUP_FILE"
                        ;;
                    *)
                        echo "❌ Invalid paper size."
                        ;;
                esac
                continue
                ;;

            4)
                echo
                read -r -p "Enter ink limit (0–400): " value

                if [[ ! "$value" =~ ^[0-9]+$ ]] || (( value < 0 || value > 400 )); then
                    echo "❌ Invalid ink limit."
                    continue
                fi

                sed -i.bak "s|^INK_LIMIT=.*|INK_LIMIT=${value}|" "$SETUP_FILE"

                echo "✅ Updated INK_LIMIT to $value"
                source "$SETUP_FILE"
                continue
                ;;

            5)
                echo "Returning to main menu..."
                return 0
                ;;

            *)
                echo "No valid selection made. Reloading setup menu..."
                continue
                ;;
        esac
    done
    echo
}

# --- Main --------------------------------------------------
main_menu() {
    while true; do
        echo
        echo
        echo 'What action do you want to perform?'
        echo
        echo '1: Create printer profile from scratch (default).'
        echo '   Specify name → Generate targets → Measure target patches'
        echo '    → Create profile → Sanity check → Copy to profile folder'
        echo
        echo '2: Re-read or resume partly read chart, then create printer profile.'
        echo '   Specify .ti3 file → Continue measuring target patches'
        echo '    → Create profile → Sanity check → Copy to profile folder'
        echo
        echo '   Note: Existing .ti3, .ti2 and target image filenames must be same.'
        echo '         If more than one target image, filenames end with _01, _02, etc.'
        echo
        echo '3: Select an existing target with .ti2 file to create profile:'
        echo '   Specify .ti2 file → Measure target patches'
        echo '    → Create profile → Sanity check → Copy to profile folder'
        echo
        echo '   Note: Existing .ti2 and target image filenames must be same.'
        echo '         If more than one target image, filenames end with _01, _02, etc.'
        echo
        echo '4: Create printer profile from an existing .ti3.'
        echo '   Specify .ti3 file → Create profile → Sanity check → Copy to profile folder'
        echo
        echo '5: Perform sanity check on existing .ti3 and .icc file pair.'
        echo
        echo '   Note: Existing .ti3 and .icc filenames must be same.'
        echo
        echo '6: Change setup parameters.'
        echo
        echo '7: Exit script'
        echo
        read -r -n 1 -p 'Enter your choice [1–7]: ' answer
        case $answer in
          1)
            action='1'
            # Call functions
            echo
            echo
            specify_profile_name || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            select_instrument || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            specify_and_generate_target || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            perform_measurement_and_profile_creation || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            install_profile_and_save_data || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            continue   # <-- go back to menu
            ;;
          2)
            action='2'
            # Call functions
            echo
            echo
            echo "Select an existing .ti3 file"
            echo
            select_ti3_file || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            perform_measurement_and_profile_creation || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            install_profile_and_save_data || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            continue   # <-- go back to menu
            ;;
          3)
            action='3'
            # Call functions
            echo
            echo
            echo "Select an existing .ti2 file"
            echo
            select_ti2_file || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            perform_measurement_and_profile_creation || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            install_profile_and_save_data || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            continue   # <-- go back to menu
            ;;
          4)
            action='4'
            # Call functions
            echo
            echo
            echo "Select an existing .ti3 file to create .icc profile with. The .ti3 file must be complete."
            echo "Warning: existing .icc profile with same name will be overwritten!"
            echo "         Make sure selected .ti3 file has unique name to prevent overwriting."
            echo
            select_ti3_file_only || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            create_profile_from_existing || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            install_profile_and_save_data || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            continue   # <-- go back to menu
            ;;
          5)
            action='5'
            # Call functions
            echo
            echo
            echo "Select an existing .ti3 file that has a matching .icc with same name."
            select_ti3_file_only || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            sanity_check || {
                echo "Operation aborted. Returning to main menu..."
                continue   # <-- go back to menu
            }
            continue   # <-- go back to menu
            ;;
          6)
            action='6'
            edit_setup_parameters
            continue   # <-- go back to menu
            ;;
          7)
            action='7'
            echo
            echo "Closing Terminal..."
            osascript -e 'tell application "Terminal" to close front window' & exit 0
            ;;
          *)
            action='1'
            echo
            echo 'No valid selection made. Returning to main menu...'
            continue   # <-- go back to menu
            ;;
        esac
        echo
    done
    echo
}

main_menu

