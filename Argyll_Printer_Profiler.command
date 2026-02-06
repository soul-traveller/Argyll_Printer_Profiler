#!/usr/bin/env bash


# Version 1.0.1

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

# --- OS detection -------------------------------------------------
OS_TYPE="$(uname -s)"

case "$OS_TYPE" in
  Darwin)
    PLATFORM="macos"
    ;;
  Linux)
    PLATFORM="linux"
    ;;
  *)
    echo "❌ Unsupported operating system: $OS_TYPE"
    exit 1
    ;;
esac

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
echo "Automated ArgyllCMS script for calibrating printers on MacOS and Linux."
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

# Try to create/truncate the log file explicitly
if ! : >"$TEMP_LOG" 2>/dev/null; then
  echo "❌ Cannot create log file at '$TEMP_LOG'."
  echo "   Check folder permissions or disk access."
else
  # Only if creation succeeded, hook up tee-based logging
  exec > >(tee -a "$TEMP_LOG") 2>&1
fi

echo
echo "File path: ${SCRIPT_DIR}"
echo "Script executed: ${SCRIPT_NAME}"
echo "Log file: ${TEMP_LOG}"
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

# --- Required command detection --------------------------------------
REQUIRED_CMDS=(
    targen
    chartread
    colprof
    printtarg
    profcheck
    dispcal
)

if [[ "$PLATFORM" == "linux" ]]; then
    REQUIRED_CMDS+=(
        zenity
    )
fi
for cmd in "${REQUIRED_CMDS[@]}"; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "❌ ArgyllCMS not found (missing command: $cmd)"
    echo
    if [[ "$PLATFORM" == "macos" ]]; then
        echo "Install it using Homebrew:"
        echo "  brew install argyll-cms"
    else
        echo "Install required dependabilities from your distribution's package manager or from argyllcms.com"
        echo "Example:"
        echo "   sudo apt install argyll zenity"
    fi
    echo
    exit 1
  fi
done

# Portable sed -i helper (required for Linux)
sed_inplace() {
    local pattern="$1"
    local file="$2"

    if [[ "$PLATFORM" == "macos" ]]; then
        # macOS: BSD sed needs -i '' for in-place editing without backup
        sed -i '' "$pattern" "$file"
    else
        # Linux: GNU sed
        sed -i "$pattern" "$file"
    fi
}

# --- Extract Argyll version --------------------------------------------------
ARGYLL_VERSION_LINE=$(dispcal 2>&1 | head -n 1)
ARGYLL_VERSION=$(echo "$ARGYLL_VERSION_LINE" | sed -n 's/.*Version \([0-9.]*\).*/\1/p')
echo "✅ ArgyllCMS detected"
echo "   Version: $ARGYLL_VERSION"
echo

# --- Functions --------------------------------------------------
move_log() {
    # Move log to profile folder
    if [ ! -f "$TEMP_LOG" ]; then
        echo "❌ Log file '$TEMP_LOG' does not exist; cannot move."
        return 1
    fi

    if [ ! -d "$PROFILE_FOLDER" ]; then
        echo "❌ Profile folder '$PROFILE_FOLDER' does not exist; cannot move log."
        return 1
    fi

    if mv "$TEMP_LOG" "$PROFILE_FOLDER/"; then
        TEMP_LOG="${PROFILE_FOLDER}/$(basename "$TEMP_LOG")"
    else
        echo "❌ Could not move log '$TEMP_LOG' to '$PROFILE_FOLDER/'"
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
    while true; do
        echo
        echo 'When specifying a profile description/filename the following is highly recommended to include:'
        echo '  - Printer ID'
        echo '  - Paper ID'
        echo '  - Color Space'
        echo '  - Target used for profile'
        echo '  - Instrument/calibration type used'
        echo '  - Date created'
        echo "Example file naming convention (select and copy):"
        echo "${EXAMPLE_FILE_NAMING}"
        echo
        echo 'For simplicity, profile description and filename are made identical.'
        echo 'The profile description is what you will see in Photoshop and ColorSync Utility.'
        echo
        echo 'Enter a desired filename for this profile.'
        echo 'If your filename is foobar, your profile will be named foobar.icc.'
        echo
        echo 'Valid values: Letters A–Z a–z, digits 0–9, dash -, underscore _, parentheses ( ), dot .'
        echo 'Press Enter without typing anything to cancel and return to previous menu.'
        echo

        read -e -p 'Enter filename: ' name

        # If user pressed Enter without typing anything → cancel
        if [[ -z "$name" ]]; then
            echo "⏎ Input cancelled. Returning to previous menu..."
            return 1
        fi

        if [[ ! "$name" =~ ^[A-Za-z0-9._()\-]+$ ]]; then
            echo "❌ Invalid file name characters. Please try again."
            continue
        fi

        # Valid input → exit loop
        break
    done

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
    echo "Select a new ICC/ICM profile to use"
    echo

    # Extract folder and current file from PRINTER_ICC_PATH
    local current_file
    local folder
    current_file="$(basename "$PRINTER_ICC_PATH")"
    folder="$(dirname "$PRINTER_ICC_PATH")"

    # Open AppleScript file chooser dialog

    if [[ "$PLATFORM" == "macos" ]]; then
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
    else    # linux
        # Open Zenity file chooser dialog (Linux)
        new_icc_path=$(zenity --file-selection \
            --title="Select a new ICC/ICM profile (.icc or .icm)" \
            --filename="${folder}/" \
            --file-filter="ICC/ICM profiles | *.icc *.icm")
    fi

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

    echo "Selected profile: $new_icc_path"
}

set_icc_profile_parameter() {
    # Update the setup file
    if [ ! -f "$SETUP_FILE" ]; then
        echo "❌ Setup file not found. Cannot save new ICC/ICM profile."
        return 1
    fi

    # Escape slashes for sed
    local escaped_path
    escaped_path=$(printf '%s\n' "$new_icc_path" | sed 's/[\/&]/\\&/g')

    # Replace the line starting with PRINTER_ICC_PATH=
    sed_inplace "s|^PRINTER_ICC_PATH=.*|PRINTER_ICC_PATH=\"${escaped_path}\"|" "$SETUP_FILE"

    echo "✅ Updated PRINTER_ICC_PATH in setup file:"
    echo "   $SETUP_FILE"
    echo "   New path: $new_icc_path"
    echo
}

set_precond_profile_parameter() {
    # Update the setup file
    if [ ! -f "$SETUP_FILE" ]; then
        echo "❌ Setup file not found. Cannot save new ICC/ICM profile."
        return 1
    fi

    # Escape slashes for sed
    local escaped_path
    escaped_path=$(printf '%s\n' "$new_icc_path" | sed 's/[\/&]/\\&/g')

    # Replace the line starting with PRECONDITIONING_PROFILE_PATH=
    sed_inplace "s|^PRECONDITIONING_PROFILE_PATH=.*|PRECONDITIONING_PROFILE_PATH=\"${escaped_path}\"|" "$SETUP_FILE"

    echo "✅ Updated PRECONDITIONING_PROFILE_PATH in setup file:"
    echo "   $SETUP_FILE"
    echo "   New path: $new_icc_path"
    echo
}

select_instrument() {
    echo
    echo 'Creating a test chart...'
    echo
    echo 'Please choose a spectrophotometer model. This effects how target is generated.'
    echo '1: i1Pro'
    echo '2: i1Pro3+'
    echo '3: ColorMunki (Default)'
    echo '4: DTP20'
    echo '5: DTP22'
    echo '6: DTP41'
    echo '7: DTP51'
    echo '8: SpectroScan'
    echo "9: Abort printing target."
    echo
    echo "When choosing '3: Colormunki' a menu of target options will be presented at next step."
    echo 'For all other choices command arguments may be edited for targen and printtarg.'
    echo
    read -r -n 1 -p 'Enter your choice [1–9]: ' answer
    echo
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
      9)
        echo
        echo 'Aborting printing target.'
        return 1
        ;;
      *)
        inst_arg="-iCM -h"
        inst_name='ColorMunki'
        echo
        echo 'No valid selection made. Using default instrument...'
        ;;
    esac
    echo
    echo "Selected instrument: ${inst_name}"
    echo
}

specify_and_generate_target() {
    precon_icc_filename="${PRECONDITIONING_PROFILE_PATH##*/}"

    menu_info_common_settings() {
        echo "Common settings for targen defined in setup file: "
        echo "      - Arguments set: $COMMON_ARGUMENTS_TARGEN"
        echo "      - Ink limit -l: $INK_LIMIT"
        echo '      - Pre-conditioning profile specified -c:'
        echo "        '${PRECONDITIONING_PROFILE_PATH}'"
        echo "Common settings for printtarg defined in setup file: "
        echo "      - Arguments set: $COMMON_ARGUMENTS_PRINTTARG"
        echo "      - Paper size -p: $PAPER_SIZE, Target resolution -T: $TARGET_RESOLUTION dpi"
        echo "Common settings for chartread defined in setup file: "
        echo "      - Arguments set: $COMMON_ARGUMENTS_CHARTREAD"
        echo "      - Patch consistency tolerance per strip -T: $STRIP_PATCH_CONSISTENSY_TOLERANCE"
        echo "Common settings for coprof defined in setup file: "
        echo "      - Arguments set: $COMMON_ARGUMENTS_COLPROF"
        echo "      - Average deviation/smooting -r: $PROFILE_SMOOTING"
        echo '      - Color space profile specified, gamut mapping -S:'
        echo "        '${PRINTER_ICC_PATH}'"
    }
    menu_info_other_instruments() {
        echo "1: $INST_OTHER_MENU_OPTION1_PATCH_COUNT_f patches $INST_OTHER_MENU_OPTION1_DESCRIPTION"
        echo "2: $INST_OTHER_MENU_OPTION2_PATCH_COUNT_f patches $INST_OTHER_MENU_OPTION2_DESCRIPTION"
        echo "3: $INST_OTHER_MENU_OPTION3_PATCH_COUNT_f patches $INST_OTHER_MENU_OPTION3_DESCRIPTION"
        echo "4: $INST_OTHER_MENU_OPTION4_PATCH_COUNT_f patches $INST_OTHER_MENU_OPTION4_DESCRIPTION"
        echo "5: $INST_OTHER_MENU_OPTION5_PATCH_COUNT_f patches $INST_OTHER_MENU_OPTION5_DESCRIPTION"
        echo "6: $INST_OTHER_MENU_OPTION6_PATCH_COUNT_f patches $INST_OTHER_MENU_OPTION6_DESCRIPTION"
        echo "7: Custom – Specify arugments independend of setup parameters"
        echo "8: Abort printing target."
    }

    menu_option_custom_target() {
        label='Custom'
        # Clear parameters
        patch_count=''
        white_patches=''
        black_patches=''
        gray_steps=''
        multi_cube_steps=''
        multi_cube_surface_steps=''
        scale_patch_and_spacer=''
        scale_spacer=''
        layout_seed=''
        inst_arg=''

        while true; do
            echo
            echo
            echo 'Specify targen command arguments:'
            echo "Default value specified:"
            echo "'${DEFAULT_TARGEN_COMMAND_CUSTOM}'"
            echo
            echo 'Notes: - Arguments -l and -c are programatically selected'
            echo '         (unless empty '' in setup) and should not be specified below.'
            if [ -n "$PRECONDITIONING_PROFILE_PATH" ]; then
                echo '       - Current pre-conditioning profile specified -c:'
                echo "         '${PRECONDITIONING_PROFILE_PATH}'"
                precon_icc="${PRECONDITIONING_PROFILE_PATH}"
            else
                echo '       - Pre-conditioning profile is currently not specified in setup.'
            fi
            echo "       - Current ink limit specified -l: '${INK_LIMIT}'"
            echo
            echo 'Valid values: Letters A–Z a–z, digits 0–9, dash -, underscore _, '
            echo '              parentheses ( ), forward slash /, space, dot .'
            read -e -p "Enter/modify arguments or enter to use default: " targen_command_custom

            # Use default if user pressed Enter
            if [[ -z "$targen_command_custom" ]]; then
                targen_command_custom="${DEFAULT_TARGEN_COMMAND_CUSTOM}"
                break
            fi

            if [[ ! "$targen_command_custom" =~ ^[A-Za-z0-9._()\/\-[:space:]]+$ ]]; then
                echo "❌ Invalid characters. Please try again."
                continue
            fi

            # Valid input → exit loop
            break
        done
        while true; do
            echo
            echo
            echo 'Specify printtarg command arguments:'
            echo "Default value specified:"
            echo "'${DEFAULT_PRINTTARG_COMMAND_CUSTOM}'"
            echo
            echo "Note: - Previsouly selected instrument (-i), resolution (-T) "
            echo "        and page size (-p) must be specified again if desired."
            echo
            echo 'Valid values: Letters A–Z a–z, digits 0–9, dash -, underscore _, '
            echo '              parentheses ( ), forward slash /, space, dot .'
            read -e -p "Enter/modify arguments or enter to use default: " printtarg_command_custom

            # Use default if user pressed Enter
            if [[ -z "$printtarg_command_custom" ]]; then
                printtarg_command_custom="${DEFAULT_PRINTTARG_COMMAND_CUSTOM}"
                break
            fi

            if [[ ! "$printtarg_command_custom" =~ ^[A-Za-z0-9._()\/\-[:space:]]+$ ]]; then
                echo "❌ Invalid characters. Please try again."
                continue
            fi

            # Valid input → exit loop
            break
        done
    }

    default_target() {
        label='Medium (default)'
        # If any of these parameters are set to empty ("") the argument in targen/printarg is omitted.
        if [ "$inst_name" = "ColorMunki" ]; then
            if [ "$PAPER_SIZE" = "A4" ]; then
                patch_count="$INST_CM_MENU_OPTION2_PATCH_COUNT_A4_f"
            elif [ "$PAPER_SIZE" = "Letter" ]; then
                patch_count="$INST_CM_MENU_OPTION2_PATCH_COUNT_LETTER_f"
            else
                patch_count="$INST_OTHER_MENU_OPTION2_PATCH_COUNT_f"
            fi

            if [[ "$PAPER_SIZE" = "A4" || "$PAPER_SIZE" = "Letter" ]]; then
                white_patches="$INST_CM_MENU_OPTION2_WHITE_PATCHES_e"
                black_patches="$INST_CM_MENU_OPTION2_BLACK_PATCHES_B"
                gray_steps="$INST_CM_MENU_OPTION2_GRAY_STEPS_g"
                multi_cube_steps="$INST_CM_MENU_OPTION2_MULTI_CUBE_STEPS_m"
                multi_cube_surface_steps="$INST_CM_MENU_OPTION2_MULTI_CUBE_SURFACE_STEPS_M"
                scale_patch_and_spacer="$INST_CM_MENU_OPTION2_SCALE_PATCH_AND_SPACER_a"
                scale_spacer="$INST_CM_MENU_OPTION2_SCALE_SPACER_A"
            else
                white_patches="$INST_OTHER_MENU_OPTION2_WHITE_PATCHES_e"
                black_patches="$INST_OTHER_MENU_OPTION2_BLACK_PATCHES_B"
                gray_steps="$INST_OTHER_MENU_OPTION2_GRAY_STEPS_g"
                multi_cube_steps="$INST_OTHER_MENU_OPTION2_MULTI_CUBE_STEPS_m"
                multi_cube_surface_steps="$INST_OTHER_MENU_OPTION2_MULTI_CUBE_SURFACE_STEPS_M"
                scale_patch_and_spacer="$INST_OTHER_MENU_OPTION2_SCALE_PATCH_AND_SPACER_a"
                scale_spacer="$INST_OTHER_MENU_OPTION2_SCALE_SPACER_A"
            fi
        else
            patch_count="$INST_OTHER_MENU_OPTION2_PATCH_COUNT_f"
            white_patches="$INST_OTHER_MENU_OPTION2_WHITE_PATCHES_e"
            black_patches="$INST_OTHER_MENU_OPTION2_BLACK_PATCHES_B"
            gray_steps="$INST_OTHER_MENU_OPTION2_GRAY_STEPS_g"
            multi_cube_steps="$INST_OTHER_MENU_OPTION2_MULTI_CUBE_STEPS_m"
            multi_cube_surface_steps="$INST_OTHER_MENU_OPTION2_MULTI_CUBE_SURFACE_STEPS_M"
            scale_patch_and_spacer="$INST_OTHER_MENU_OPTION2_SCALE_PATCH_AND_SPACER_a"
            scale_spacer="$INST_OTHER_MENU_OPTION2_SCALE_SPACER_A"
        fi
        layout_seed="$INST_CM_MENU_OPTION2_LAYOUT_SEED_R"
    }

    while true; do
        if [ "$inst_name" = "ColorMunki" ]; then
            # Display menu depending on paper size
            if [ "$PAPER_SIZE" = "A4" ]; then
                echo
                echo "Below menu choices have been optimized for page size $PAPER_SIZE and $inst_name instrument."
                menu_info_common_settings
                echo
                echo 'Select the target size:'
                echo
                echo "1: $INST_CM_MENU_OPTION1_PATCH_COUNT_A4_f patches $INST_CM_MENU_OPTION1_A4_DESCRIPTION"
                echo "2: $INST_CM_MENU_OPTION2_PATCH_COUNT_A4_f patches $INST_CM_MENU_OPTION2_A4_DESCRIPTION"
                echo "3: $INST_CM_MENU_OPTION3_PATCH_COUNT_A4_f patches $INST_CM_MENU_OPTION3_A4_DESCRIPTION"
                echo "4: $INST_CM_MENU_OPTION4_PATCH_COUNT_A4_f patches $INST_CM_MENU_OPTION4_A4_DESCRIPTION"
                echo "5: $INST_CM_MENU_OPTION5_PATCH_COUNT_A4_f patches $INST_CM_MENU_OPTION5_A4_DESCRIPTION"
                echo "6: $INST_CM_MENU_OPTION6_PATCH_COUNT_A4_f patches $INST_CM_MENU_OPTION6_A4_DESCRIPTION"
                echo "7: Custom – Specify arugments independend of setup parameters"
                echo "8: Abort printing target."
            elif [ "$PAPER_SIZE" = "Letter" ]; then
                echo
                echo "Below menu choices have been optimized for page size $PAPER_SIZE and $inst_name instrument."
                menu_info_common_settings
                echo
                echo 'Select the target size:'
                echo
                echo "1: $INST_CM_MENU_OPTION1_PATCH_COUNT_LETTER_f patches $INST_CM_MENU_OPTION1_LETTER_DESCRIPTION"
                echo "2: $INST_CM_MENU_OPTION2_PATCH_COUNT_LETTER_f patches $INST_CM_MENU_OPTION2_LETTER_DESCRIPTION"
                echo "3: $INST_CM_MENU_OPTION3_PATCH_COUNT_LETTER_f patches $INST_CM_MENU_OPTION3_LETTER_DESCRIPTION"
                echo "4: $INST_CM_MENU_OPTION4_PATCH_COUNT_LETTER_f patches $INST_CM_MENU_OPTION4_LETTER_DESCRIPTION"
                echo "5: $INST_CM_MENU_OPTION5_PATCH_COUNT_LETTER_f patches $INST_CM_MENU_OPTION5_LETTER_DESCRIPTION"
                echo "6: $INST_CM_MENU_OPTION6_PATCH_COUNT_LETTER_f patches $INST_CM_MENU_OPTION6_LETTER_DESCRIPTION"
                echo "7: Custom – Specify arugments independend of setup parameters"
                echo "8: Abort printing target."
            else
                # PAPER_SIZE A4 or any other value than Letter
                echo
                echo "⚠️ Non-standard printer paper size: PAPER_SIZE \"$PAPER_SIZE\"."
                echo 'USING INSTRUMENT/PAGE INDEPENDENT MENU-PARAMETERS (STARTING WITH INST_OTHER_*).'
                echo
                echo 'Number of created pages increase with patch count, depending on settings.'
                menu_info_common_settings
                echo
                echo 'Select the target size:'
                echo
                menu_info_other_instruments
            fi
        else
            # Display menu for other instruments
            echo
            echo 'Number of created pages increase with patch count, depending on settings.'
            menu_info_common_settings
            echo
            echo 'Select the target size:'
            echo
            menu_info_other_instruments
        fi

        echo
        # Prompt user after menu
        read -r -n 1 -p 'Enter your choice [1–8]: ' patch_choice
        echo
        case "$patch_choice" in
        1)
            label='Small'
            # If any of these parameters are set to empty ("") the argument in targen/printarg is omitted.
            if [ "$inst_name" = "ColorMunki" ]; then
                if [ "$PAPER_SIZE" = "A4" ]; then
                    patch_count="$INST_CM_MENU_OPTION1_PATCH_COUNT_A4_f"
                elif [ "$PAPER_SIZE" = "Letter" ]; then
                    patch_count="$INST_CM_MENU_OPTION1_PATCH_COUNT_LETTER_f"
                else
                    patch_count="$INST_OTHER_MENU_OPTION1_PATCH_COUNT_f"
                fi

                if [[ "$PAPER_SIZE" = "A4" || "$PAPER_SIZE" = "Letter" ]]; then
                    white_patches="$INST_CM_MENU_OPTION1_WHITE_PATCHES_e"
                    black_patches="$INST_CM_MENU_OPTION1_BLACK_PATCHES_B"
                    gray_steps="$INST_CM_MENU_OPTION1_GRAY_STEPS_g"
                    multi_cube_steps="$INST_CM_MENU_OPTION1_MULTI_CUBE_STEPS_m"
                    multi_cube_surface_steps="$INST_CM_MENU_OPTION1_MULTI_CUBE_SURFACE_STEPS_M"
                    scale_patch_and_spacer="$INST_CM_MENU_OPTION1_SCALE_PATCH_AND_SPACER_a"
                    scale_spacer="$INST_CM_MENU_OPTION1_SCALE_SPACER_A"
                else
                    white_patches="$INST_OTHER_MENU_OPTION1_WHITE_PATCHES_e"
                    black_patches="$INST_OTHER_MENU_OPTION1_BLACK_PATCHES_B"
                    gray_steps="$INST_OTHER_MENU_OPTION1_GRAY_STEPS_g"
                    multi_cube_steps="$INST_OTHER_MENU_OPTION1_MULTI_CUBE_STEPS_m"
                    multi_cube_surface_steps="$INST_OTHER_MENU_OPTION1_MULTI_CUBE_SURFACE_STEPS_M"
                    scale_patch_and_spacer="$INST_OTHER_MENU_OPTION1_SCALE_PATCH_AND_SPACER_a"
                    scale_spacer="$INST_OTHER_MENU_OPTION1_SCALE_SPACER_A"
                fi
            else
                patch_count="$INST_OTHER_MENU_OPTION1_PATCH_COUNT_f"
                white_patches="$INST_OTHER_MENU_OPTION1_WHITE_PATCHES_e"
                black_patches="$INST_OTHER_MENU_OPTION1_BLACK_PATCHES_B"
                gray_steps="$INST_OTHER_MENU_OPTION1_GRAY_STEPS_g"
                multi_cube_steps="$INST_OTHER_MENU_OPTION1_MULTI_CUBE_STEPS_m"
                multi_cube_surface_steps="$INST_OTHER_MENU_OPTION1_MULTI_CUBE_SURFACE_STEPS_M"
                scale_patch_and_spacer="$INST_OTHER_MENU_OPTION1_SCALE_PATCH_AND_SPACER_a"
                scale_spacer="$INST_OTHER_MENU_OPTION1_SCALE_SPACER_A"
            fi
            layout_seed="$INST_CM_MENU_OPTION1_LAYOUT_SEED_R"
            ;;
        2)
            default_target
            ;;
        3)
            label='Large'
            # If any of these parameters are set to empty ("") the argument in targen/printarg is omitted.
            if [ "$inst_name" = "ColorMunki" ]; then
                if [ "$PAPER_SIZE" = "A4" ]; then
                    patch_count="$INST_CM_MENU_OPTION3_PATCH_COUNT_A4_f"
                elif [ "$PAPER_SIZE" = "Letter" ]; then
                    patch_count="$INST_CM_MENU_OPTION3_PATCH_COUNT_LETTER_f"
                else
                    patch_count="$INST_OTHER_MENU_OPTION3_PATCH_COUNT_f"
                fi

                if [[ "$PAPER_SIZE" = "A4" || "$PAPER_SIZE" = "Letter" ]]; then
                    white_patches="$INST_CM_MENU_OPTION3_WHITE_PATCHES_e"
                    black_patches="$INST_CM_MENU_OPTION3_BLACK_PATCHES_B"
                    gray_steps="$INST_CM_MENU_OPTION3_GRAY_STEPS_g"
                    multi_cube_steps="$INST_CM_MENU_OPTION3_MULTI_CUBE_STEPS_m"
                    multi_cube_surface_steps="$INST_CM_MENU_OPTION3_MULTI_CUBE_SURFACE_STEPS_M"
                    scale_patch_and_spacer="$INST_CM_MENU_OPTION3_SCALE_PATCH_AND_SPACER_a"
                    scale_spacer="$INST_CM_MENU_OPTION3_SCALE_SPACER_A"
                else
                    white_patches="$INST_OTHER_MENU_OPTION3_WHITE_PATCHES_e"
                    black_patches="$INST_OTHER_MENU_OPTION3_BLACK_PATCHES_B"
                    gray_steps="$INST_OTHER_MENU_OPTION3_GRAY_STEPS_g"
                    multi_cube_steps="$INST_OTHER_MENU_OPTION3_MULTI_CUBE_STEPS_m"
                    multi_cube_surface_steps="$INST_OTHER_MENU_OPTION3_MULTI_CUBE_SURFACE_STEPS_M"
                    scale_patch_and_spacer="$INST_OTHER_MENU_OPTION3_SCALE_PATCH_AND_SPACER_a"
                    scale_spacer="$INST_OTHER_MENU_OPTION3_SCALE_SPACER_A"
                fi
            else
                patch_count="$INST_OTHER_MENU_OPTION3_PATCH_COUNT_f"
                white_patches="$INST_OTHER_MENU_OPTION3_WHITE_PATCHES_e"
                black_patches="$INST_OTHER_MENU_OPTION3_BLACK_PATCHES_B"
                gray_steps="$INST_OTHER_MENU_OPTION3_GRAY_STEPS_g"
                multi_cube_steps="$INST_OTHER_MENU_OPTION3_MULTI_CUBE_STEPS_m"
                multi_cube_surface_steps="$INST_OTHER_MENU_OPTION3_MULTI_CUBE_SURFACE_STEPS_M"
                scale_patch_and_spacer="$INST_OTHER_MENU_OPTION3_SCALE_PATCH_AND_SPACER_a"
                scale_spacer="$INST_OTHER_MENU_OPTION3_SCALE_SPACER_A"
            fi
            layout_seed="$INST_CM_MENU_OPTION3_LAYOUT_SEED_R"
            ;;
        4)
            label='XL'
            # If any of these parameters are set to empty ("") the argument in targen/printarg is omitted.
            if [ "$inst_name" = "ColorMunki" ]; then
                if [ "$PAPER_SIZE" = "A4" ]; then
                    patch_count="$INST_CM_MENU_OPTION4_PATCH_COUNT_A4_f"
                elif [ "$PAPER_SIZE" = "Letter" ]; then
                    patch_count="$INST_CM_MENU_OPTION4_PATCH_COUNT_LETTER_f"
                else
                    patch_count="$INST_OTHER_MENU_OPTION4_PATCH_COUNT_f"
                fi

                if [[ "$PAPER_SIZE" = "A4" || "$PAPER_SIZE" = "Letter" ]]; then
                    white_patches="$INST_CM_MENU_OPTION4_WHITE_PATCHES_e"
                    black_patches="$INST_CM_MENU_OPTION4_BLACK_PATCHES_B"
                    gray_steps="$INST_CM_MENU_OPTION4_GRAY_STEPS_g"
                    multi_cube_steps="$INST_CM_MENU_OPTION4_MULTI_CUBE_STEPS_m"
                    multi_cube_surface_steps="$INST_CM_MENU_OPTION4_MULTI_CUBE_SURFACE_STEPS_M"
                    scale_patch_and_spacer="$INST_CM_MENU_OPTION4_SCALE_PATCH_AND_SPACER_a"
                    scale_spacer="$INST_CM_MENU_OPTION4_SCALE_SPACER_A"
                else
                    white_patches="$INST_OTHER_MENU_OPTION4_WHITE_PATCHES_e"
                    black_patches="$INST_OTHER_MENU_OPTION4_BLACK_PATCHES_B"
                    gray_steps="$INST_OTHER_MENU_OPTION4_GRAY_STEPS_g"
                    multi_cube_steps="$INST_OTHER_MENU_OPTION4_MULTI_CUBE_STEPS_m"
                    multi_cube_surface_steps="$INST_OTHER_MENU_OPTION4_MULTI_CUBE_SURFACE_STEPS_M"
                    scale_patch_and_spacer="$INST_OTHER_MENU_OPTION4_SCALE_PATCH_AND_SPACER_a"
                    scale_spacer="$INST_OTHER_MENU_OPTION4_SCALE_SPACER_A"
                fi
            else
                patch_count="$INST_OTHER_MENU_OPTION4_PATCH_COUNT_f"
                white_patches="$INST_OTHER_MENU_OPTION4_WHITE_PATCHES_e"
                black_patches="$INST_OTHER_MENU_OPTION4_BLACK_PATCHES_B"
                gray_steps="$INST_OTHER_MENU_OPTION4_GRAY_STEPS_g"
                multi_cube_steps="$INST_OTHER_MENU_OPTION4_MULTI_CUBE_STEPS_m"
                multi_cube_surface_steps="$INST_OTHER_MENU_OPTION4_MULTI_CUBE_SURFACE_STEPS_M"
                scale_patch_and_spacer="$INST_OTHER_MENU_OPTION4_SCALE_PATCH_AND_SPACER_a"
                scale_spacer="$INST_OTHER_MENU_OPTION4_SCALE_SPACER_A"
            fi
            layout_seed="$INST_CM_MENU_OPTION4_LAYOUT_SEED_R"
            ;;
        5)
            label='XXL'
            # If any of these parameters are set to empty ("") the argument in targen/printarg is omitted.
            if [ "$inst_name" = "ColorMunki" ]; then
                if [ "$PAPER_SIZE" = "A4" ]; then
                    patch_count="$INST_CM_MENU_OPTION5_PATCH_COUNT_A4_f"
                elif [ "$PAPER_SIZE" = "Letter" ]; then
                    patch_count="$INST_CM_MENU_OPTION5_PATCH_COUNT_LETTER_f"
                else
                    patch_count="$INST_OTHER_MENU_OPTION5_PATCH_COUNT_f"
                fi

                if [[ "$PAPER_SIZE" = "A4" || "$PAPER_SIZE" = "Letter" ]]; then
                    white_patches="$INST_CM_MENU_OPTION5_WHITE_PATCHES_e"
                    black_patches="$INST_CM_MENU_OPTION5_BLACK_PATCHES_B"
                    gray_steps="$INST_CM_MENU_OPTION5_GRAY_STEPS_g"
                    multi_cube_steps="$INST_CM_MENU_OPTION5_MULTI_CUBE_STEPS_m"
                    multi_cube_surface_steps="$INST_CM_MENU_OPTION5_MULTI_CUBE_SURFACE_STEPS_M"
                    scale_patch_and_spacer="$INST_CM_MENU_OPTION5_SCALE_PATCH_AND_SPACER_a"
                    scale_spacer="$INST_CM_MENU_OPTION5_SCALE_SPACER_A"

                else
                    white_patches="$INST_OTHER_MENU_OPTION5_WHITE_PATCHES_e"
                    black_patches="$INST_OTHER_MENU_OPTION5_BLACK_PATCHES_B"
                    gray_steps="$INST_OTHER_MENU_OPTION5_GRAY_STEPS_g"
                    multi_cube_steps="$INST_OTHER_MENU_OPTION5_MULTI_CUBE_STEPS_m"
                    multi_cube_surface_steps="$INST_OTHER_MENU_OPTION5_MULTI_CUBE_SURFACE_STEPS_M"
                    scale_patch_and_spacer="$INST_OTHER_MENU_OPTION5_SCALE_PATCH_AND_SPACER_a"
                    scale_spacer="$INST_OTHER_MENU_OPTION5_SCALE_SPACER_A"
                fi
            else
                patch_count="$INST_OTHER_MENU_OPTION5_PATCH_COUNT_f"
                white_patches="$INST_OTHER_MENU_OPTION5_WHITE_PATCHES_e"
                black_patches="$INST_OTHER_MENU_OPTION5_BLACK_PATCHES_B"
                gray_steps="$INST_OTHER_MENU_OPTION5_GRAY_STEPS_g"
                multi_cube_steps="$INST_OTHER_MENU_OPTION5_MULTI_CUBE_STEPS_m"
                multi_cube_surface_steps="$INST_OTHER_MENU_OPTION5_MULTI_CUBE_SURFACE_STEPS_M"
                scale_patch_and_spacer="$INST_OTHER_MENU_OPTION5_SCALE_PATCH_AND_SPACER_a"
                scale_spacer="$INST_OTHER_MENU_OPTION5_SCALE_SPACER_A"
            fi
            layout_seed="$INST_CM_MENU_OPTION5_LAYOUT_SEED_R"
            ;;
        6)
            label='XXXL'
            # If any of the targen/printarg relevant argument-parameters are set to empty ("") the argument is omitted at execution.
            if [ "$inst_name" = "ColorMunki" ]; then
                if [ "$PAPER_SIZE" = "A4" ]; then
                    patch_count="$INST_CM_MENU_OPTION6_PATCH_COUNT_A4_f"
                elif [ "$PAPER_SIZE" = "Letter" ]; then
                    patch_count="$INST_CM_MENU_OPTION6_PATCH_COUNT_LETTER_f"
                else
                    patch_count="$INST_OTHER_MENU_OPTION6_PATCH_COUNT_f"
                fi

                if [[ "$PAPER_SIZE" = "A4" || "$PAPER_SIZE" = "Letter" ]]; then
                    white_patches="$INST_CM_MENU_OPTION6_WHITE_PATCHES_e"
                    black_patches="$INST_CM_MENU_OPTION6_BLACK_PATCHES_B"
                    gray_steps="$INST_CM_MENU_OPTION6_GRAY_STEPS_g"
                    multi_cube_steps="$INST_CM_MENU_OPTION6_MULTI_CUBE_STEPS_m"
                    multi_cube_surface_steps="$INST_CM_MENU_OPTION6_MULTI_CUBE_SURFACE_STEPS_M"
                    scale_patch_and_spacer="$INST_CM_MENU_OPTION6_SCALE_PATCH_AND_SPACER_a"
                    scale_spacer="$INST_CM_MENU_OPTION6_SCALE_SPACER_A"
                else
                    white_patches="$INST_OTHER_MENU_OPTION6_WHITE_PATCHES_e"
                    black_patches="$INST_OTHER_MENU_OPTION6_BLACK_PATCHES_B"
                    gray_steps="$INST_OTHER_MENU_OPTION6_GRAY_STEPS_g"
                    multi_cube_steps="$INST_OTHER_MENU_OPTION6_MULTI_CUBE_STEPS_m"
                    multi_cube_surface_steps="$INST_OTHER_MENU_OPTION6_MULTI_CUBE_SURFACE_STEPS_M"
                    scale_patch_and_spacer="$INST_OTHER_MENU_OPTION6_SCALE_PATCH_AND_SPACER_a"
                    scale_spacer="$INST_OTHER_MENU_OPTION6_SCALE_SPACER_A"
                fi
            else
                patch_count="$INST_OTHER_MENU_OPTION6_PATCH_COUNT_f"
                white_patches="$INST_OTHER_MENU_OPTION6_WHITE_PATCHES_e"
                black_patches="$INST_OTHER_MENU_OPTION6_BLACK_PATCHES_B"
                gray_steps="$INST_OTHER_MENU_OPTION6_GRAY_STEPS_g"
                multi_cube_steps="$INST_OTHER_MENU_OPTION6_MULTI_CUBE_STEPS_m"
                multi_cube_surface_steps="$INST_OTHER_MENU_OPTION6_MULTI_CUBE_SURFACE_STEPS_M"
                scale_patch_and_spacer="$INST_OTHER_MENU_OPTION6_SCALE_PATCH_AND_SPACER_a"
                scale_spacer="$INST_OTHER_MENU_OPTION6_SCALE_SPACER_A"
            fi
            layout_seed="$INST_CM_MENU_OPTION6_LAYOUT_SEED_R"
            ;;
        7)
            menu_option_custom_target
            ;;
        8)
            echo 'Aborting printing target.'
            return 1
            ;;
        *)
            default_target
            echo 'Invalid selection. Using default.'
            ;;
        esac

        echo
        if [ ! "$label" = "Custom" ]; then      # When menu choice other than Custom
            echo "Selected target: ${label} – ${patch_count} patches"
        else
            targen_c=''        # pre-conditioning profile path with filename
            if [ -n "$PRECONDITIONING_PROFILE_PATH" ]; then
                targen_c=(" -c \"$PRECONDITIONING_PROFILE_PATH\"")
            fi
            targen_l=''        # ink limit
            if [ -n "$INK_LIMIT" ]; then
                targen_l=" -l${INK_LIMIT}"
            fi
            echo "Selected target: - ${label}"
            echo "                 - targen arguments: ${targen_command_custom}${targen_l}${targen_c}"
            echo "                 - printtarg arguments: ${printtarg_command_custom}"
        fi

        while true; do
            read -r -n 1 -p 'Do you want to continue with select target? [y/n]: ' again
            echo
            case "$again" in
            [yY]|[yY][eE][sS])
                echo 'Continuing with selected target...'
                break 2  # Exit both loops (confirmation and target selection)
                ;;
            [nN]|[nN][oO])
                echo 'Repeating target selection...'
                break  # Exit confirmation loop, stay in target selection loop
                ;;
            *)
                echo 'Invalid input. Please enter y/yes or n/no.'
                ;;
            esac
        done
    done

    # --- Build targen arguments conditionally ---------------------------

    # For targen, if any variable for each argument is empty, then remove argument in command (empty parameter)
   targen_l=''        # ink limit
   if [ -n "$INK_LIMIT" ]; then
       targen_l="-l${INK_LIMIT}"
   fi
    targen_e=''        # white patches
    if [ -n "$white_patches" ]; then
        targen_e="-e${white_patches}"
    fi
    targen_B=''        # black patches
    if [ -n "$black_patches" ]; then
        targen_B="-B${black_patches}"
    fi
    targen_g=''        # gray steps
    if [ -n "$gray_steps" ]; then
        targen_g="-g${gray_steps}"
    fi
    targen_m=''        # multi cube steps
    if [ -n "$multi_cube_steps" ]; then
        targen_m="-m${multi_cube_steps}"
    fi
    targen_M=''        # multi cube surface steps
    if [ -n "$multi_cube_surface_steps" ]; then
        targen_M="-M${multi_cube_surface_steps}"
    fi
    targen_a=''        # multi cube surface steps
    if [ -n "$scale_patch_and_spacer" ]; then
        targen_a="-a${scale_patch_and_spacer}"
    fi
    targen_A=''        # multi cube surface steps
    if [ -n "$scale_spacer" ]; then
        targen_A="-A${scale_spacer}"
    fi
    targen_f=''        # patch count
    if [ -n "$patch_count" ]; then
        targen_f="-f${patch_count}"
    fi
    targen_c=()        # pre-conditioning profile path with filename
    if [ -n "$PRECONDITIONING_PROFILE_PATH" ]; then
       targen_c+=("-c" "$PRECONDITIONING_PROFILE_PATH")
    fi

    # --- Build printtarg arguments conditionally -------------------------

    # For printtarg, if any variable for each argument is empty, then remove argument in command (empty parameter)
    printtarg_T=''     # target resolution
    if [ -n "$TARGET_RESOLUTION" ]; then
        printtarg_T="-T${TARGET_RESOLUTION}"
    fi
    printtarg_p=''     # paper size
    if [ -n "$PAPER_SIZE" ]; then
        printtarg_p="-p${PAPER_SIZE}"
    fi
    ## Removed defined layout seed for printtarg if not used
    printtarg_R=''        # layour seed
    if [ "$USE_LAYOUT_SEED_FOR_TARGET" = "true" ]; then
        if [ -n "$layout_seed" ]; then
            printtarg_R="-R${layout_seed}"
        fi
    fi

    if [ ! "$label" = "Custom" ]; then      # When menu choice other than Custom
        echo
        echo 'Generating target color values (.ti1 file)...'
        echo "Command Used: targen ${COMMON_ARGUMENTS_TARGEN} ${targen_l} ${targen_e} ${targen_B} ${targen_g} ${targen_m} ${targen_M} ${targen_f} "${targen_c[@]}" "${name}""
        # --- Generate target ONLY ONCE, after confirmation ---
        targen ${COMMON_ARGUMENTS_TARGEN} ${targen_l} ${targen_e} ${targen_B} ${targen_g} ${targen_m} ${targen_M} ${targen_f} "${targen_c[@]}" "${name}" || {
            echo "❌ targen failed. See log for details."
            return 1
        }

        echo
        echo 'Generating target(s) (.tif image(es) and .ti2 file)...'
        echo "Command Used: printtarg ${COMMON_ARGUMENTS_PRINTTARG} ${inst_arg} ${printtarg_R} ${printtarg_T} ${printtarg_p} ${targen_a} ${targen_A} "${name}""
        # Common printtarg command
        printtarg ${COMMON_ARGUMENTS_PRINTTARG} ${inst_arg} ${printtarg_R} ${printtarg_T} ${printtarg_p} ${targen_a} ${targen_A} "${name}" || {
            echo "❌ printtarg failed. See log for details."
            return 1
        }
        echo
    else      # When menu choice is Custom
        echo
        echo 'Generating target color values (.ti1 file)...'
        # --- Generate target ONLY ONCE, after confirmation ---
        echo "Command Used: targen ${targen_command_custom} ${targen_l} "${targen_c[@]}" "${name}""
        targen ${targen_command_custom} ${targen_l} "${targen_c[@]}" "${name}" || {
            echo "❌ targen failed. See log for details."
            return 1
        }

        echo
        echo 'Generating target(s) (.tif image(es) and .ti2 file)...'
        echo "Command Used: printtarg ${printtarg_command_custom} "${name}""
        # Common printtarg command
        printtarg ${printtarg_command_custom} "${name}" || {
            echo "❌ printtarg failed. See log for details."
            return 1
        }
        echo
    fi

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

    if [[ "$PLATFORM" == "macos" ]]; then
        echo 'Please print the test chart(s) using ColorSync Utility (opens automatically).'
        echo 'In the Printer dialog set option "Colour" to "Print as Color Target".'
        echo 'This will print without color management.'
        echo 'Tip: It might be beneficial to print targets with 88-90% scaling to prevent the rubber'
        echo '     taps underneath the Colormunki to interfere with reading of the first patches.'
        open -a "$COLOR_SYNC_UTILITY_PATH" "${tif_files[@]}"
    else
        echo 'Please print the test chart(s) created and make sure to disable color management.'
        echo 'Tip: It might be beneficial to print targets with 88-90% scaling to prevent the rubber'
        echo '     taps underneath the Colormunki to interfere with reading of the first patches.'
    fi

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
    if [[ "$PLATFORM" == "macos" ]]; then
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
    else    # linux
        # Open Zenity file chooser dialog (Linux)
        ti2_path=$(zenity --file-selection \
            --title="Select a .ti2 file" \
            --filename="${SCRIPT_DIR}/${CREATED_PROFILES_FOLDER}/" \
            --file-filter="Target Information 2 data | *.ti2")
    fi

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
    if [[ "$PLATFORM" == "macos" ]]; then
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
    else    # linux
        # Open Zenity file chooser dialog (Linux)
        ti3_path=$(zenity --file-selection \
            --title="Select a .ti3 file" \
            --filename="${SCRIPT_DIR}/${CREATED_PROFILES_FOLDER}/" \
            --file-filter="Target Information 3 data | *.ti3")
    fi

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
    if [[ "$PLATFORM" == "macos" ]]; then
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
    else    # linux
        # Open Zenity file chooser dialog (Linux)
        ti3_path=$(zenity --file-selection \
            --title="Select a .ti3 file" \
            --filename="${SCRIPT_DIR}/${CREATED_PROFILES_FOLDER}/" \
            --file-filter="Target Information 3 data | *.ti3")
    fi

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
    echo "Command Used: profcheck -v2 -k -s "${name}.ti3" "${name}.icc" 2>&1 >> "${name}_sanity_check.txt""
    echo
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

# Helper for stat command differences (Linux vs macOS)
file_mtime() {
  if stat -f "%m" "$1" >/dev/null 2>&1; then
    stat -f "%m" "$1"
  else
    stat -c "%Y" "$1"
  fi
}

perform_measurement_and_profile_creation() {
    echo
    echo "Starting chart reading (read .ti2 file and generate .ti3 file)..."
    echo

    # --- Build chartread arguments conditionally ---------------------------
    # For chartread, if any variable for each argument is empty, then remove argument in command (empty parameter)
    chartread_T=''        # patch strip consistency
    if [ -n "$STRIP_PATCH_CONSISTENSY_TOLERANCE" ]; then
        chartread_T="-T${STRIP_PATCH_CONSISTENSY_TOLERANCE}"
    fi

    local ti3_file="${name}.ti3"
    if [ "$action" = "2" ]; then    # re-read or resume partly read chart
        # Capture modification time state before chartread
        local ti3_mtime_before=""
        if [ -f "$ti3_file" ]; then
            ti3_mtime_before=$(file_mtime "$ti3_file")
        fi

        echo "Command Used: chartread ${COMMON_ARGUMENTS_CHARTREAD} -r ${chartread_T} "${name}""
        echo
        echo "Tips:"
        echo "     - Reading speed to more than 7 sec per strip reduces"
        echo "       frequent re-reading due to inconsistent results."
        echo "     - If frequent inconsistent results try altering"
        echo "       patch consistency tolerance."
        echo "     - Save progress once in a while with 'd' and then"
        echo "       resume measuring with option 2 of main manu."
        echo
        chartread ${COMMON_ARGUMENTS_CHARTREAD} -r ${chartread_T} "${name}" || {
            echo
            echo "❌ chartread failed. See log for details."
            echo
            return 1
        }

        # Detect abort after chartread
        # Resume mode: Check if file modified, if not user abored
        local ti3_mtime_after
        ti3_mtime_after=$(file_mtime "$ti3_file")

        if [[ "$ti3_mtime_after" == "$ti3_mtime_before" ]]; then
            echo
            echo "⚠️️ Chartread aborted by user (no new measurements written)."
            echo
            return 1
        fi

    else # Normal chartread
        echo "Command Used: chartread ${COMMON_ARGUMENTS_CHARTREAD} ${chartread_T} "${name}""
        echo
        echo "Tips:"
        echo "     - Reading speed to more than 7 sec per strip reduces"
        echo "       frequent re-reading due to inconsistent results."
        echo "     - If frequent inconsistent results try altering"
        echo "       patch consistency tolerance."
        echo "     - Save progress once in a while with 'd' and then"
        echo "       resume measuring with option 2 of main manu."
        echo
        chartread ${COMMON_ARGUMENTS_CHARTREAD} ${chartread_T} "${name}" || {
            echo
            echo "❌ chartread failed. See log for details."
            echo
            return 1
        }

        # Detect abort after chartread
        # Fresh read: file must exist
        if [ ! -f "$ti3_file" ]; then
            echo
            echo "⚠️️ Chartread aborted by user."
            echo
            return 1
        fi
    fi

    # --- Build colprof arguments conditionally ---------------------------
    # For colprof, if any variable for each argument is empty, then remove argument in command (empty parameter)
    colprof_S=()        # printer icc profile
    if [ -n "$PRINTER_ICC_PATH" ]; then
       colprof_S+=("-S" "$PRINTER_ICC_PATH")
    fi
    colprof_l=''        # ink limit
    if [ -n "$INK_LIMIT" ]; then
        colprof_l="-l${INK_LIMIT}"
    fi
    colprof_r=''        # Average deviation / smooting
    if [ -n "$PROFILE_SMOOTING" ]; then
        colprof_r="-r${PROFILE_SMOOTING}"
    fi

    echo
    read -r -n 1 -p 'Do you want to continue creating profile with resulting ti3 file? [y/n]: ' continue
    echo
    case "$continue" in
    [yY]|[yY][eE][sS])
        echo
        echo
        echo "Starting profile creation (read .ti3 file and generate .icc file)..."
        echo "Command Used: colprof ${COMMON_ARGUMENTS_COLPROF} ${colprof_l} ${colprof_r} "${colprof_S[@]}" -D"${desc}" "${name}""
        colprof ${COMMON_ARGUMENTS_COLPROF} ${colprof_l} ${colprof_r} "${colprof_S[@]}" -D"${desc}" "${name}" || {
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
    # --- Build colprof arguments conditionally ---------------------------
    # For colprof, if any variable for each argument is empty, then remove argument in command (empty parameter)
    colprof_S=()        # printer icc profile
    if [ -n "$PRINTER_ICC_PATH" ]; then
       colprof_S+=("-S" "$PRINTER_ICC_PATH")
    fi
    colprof_l=''        # ink limit
    if [ -n "$INK_LIMIT" ]; then
        colprof_l="-l${INK_LIMIT}"
    fi
    colprof_r=''        # Average deviation / smooting
    if [ -n "$PROFILE_SMOOTING" ]; then
        colprof_r="-r${PROFILE_SMOOTING}"
    fi

    echo
    echo
    echo "Starting profile creation (read .ti3 file and generate .icc file)..."
    echo "Command Used: colprof ${COMMON_ARGUMENTS_COLPROF} ${colprof_l} ${colprof_r} "${colprof_S[@]}" -D"${desc}" "${name}""
    colprof ${COMMON_ARGUMENTS_COLPROF} ${colprof_l} ${colprof_r} "${colprof_S[@]}" -D"${desc}" "${name}" || {
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
        precon_icc_filename="${PRECONDITIONING_PROFILE_PATH##*/}"

        echo
        echo
        echo "In this menu some variables stored in the $SETUP_FILE file can be modified."
        echo "For other parameters modify the file in a text editor."
        echo
        echo "What parameter do you want to modify?"
        echo
        echo "1: Select Color Space profile to use when creating printer profile."
        echo "   (gamut mapping to output profile)"
        echo "   Current file specified: '${icc_filename}'"
        echo
        echo "2: Select pre-conditioning profile to use when creating target."
        echo "   Current file specified: '${precon_icc_filename}'"
        echo
        echo "3: Modify patch consistency tolerance (chartread arg. -T)"
        echo "   Current value specified: '${STRIP_PATCH_CONSISTENSY_TOLERANCE}'"
        echo
        echo "4: Modify paper size for target generation (printtarg -p). Valid values: A4, Letter."
        echo "   Current value specified: '${PAPER_SIZE}'"
        echo
        echo "5: Modify ink limit (targen and colprof -l). Valid values: 0 – 400 (%)."
        echo "   Current value specified: '${INK_LIMIT}'"
        echo
        echo "6: Modify file naming convention example (shown in main menu option 1). Valid value: text."
        echo "   Current value specified:"
        echo "   '${EXAMPLE_FILE_NAMING}'"
        echo
        echo "7: Go back to main menu."
        echo

        read -r -n 1 -p "Enter your choice [1–7]: " answer
        echo

        case $answer in
            1)
                select_icc_profile || {
                    echo "Returning to setup menu..."
                }
                set_icc_profile_parameter || {
                    echo "Returning to setup menu..."
                }
                source "$SETUP_FILE"
                continue
                ;;

            2)
                select_icc_profile || {
                    echo "Returning to setup menu..."
                }
                set_precond_profile_parameter || {
                    echo "Returning to setup menu..."
                }
                source "$SETUP_FILE"
                continue
                echo
                ;;

            3)
                echo
                read -r -p "Enter new value [0.6 recommended]: " value

                if [[ ! "$value" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
                    echo "❌ Invalid numeric value."
                    continue
                fi

                sed_inplace "s|^STRIP_PATCH_CONSISTENSY_TOLERANCE=.*|STRIP_PATCH_CONSISTENSY_TOLERANCE='${value}'|" "$SETUP_FILE"

                echo "✅ Updated STRIP_PATCH_CONSISTENSY_TOLERANCE to $value"
                source "$SETUP_FILE"
                echo
                continue
                ;;

            4)
                echo
                read -r -p "Enter paper size [A4 or Letter]: " value
                echo

                case "$value" in
                    A4|Letter)
                        sed_inplace "s|^PAPER_SIZE=.*|PAPER_SIZE='${value}'|" "$SETUP_FILE"
                        echo "✅ Updated PAPER_SIZE to $value"
                        source "$SETUP_FILE"
                        ;;
                    *)
                        echo "❌ Invalid paper size."
                        ;;
                esac
                echo
                continue
                ;;

            5)
                echo
                read -r -p "Enter ink limit (0–400): " value

                if [[ ! "$value" =~ ^[0-9]+$ ]] || (( value < 0 || value > 400 )); then
                    echo "❌ Invalid ink limit."
                    continue
                fi

                sed_inplace "s|^INK_LIMIT=.*|INK_LIMIT='${value}'|" "$SETUP_FILE"

                echo "✅ Updated INK_LIMIT to $value"
                source "$SETUP_FILE"
                echo
                continue
                ;;

            6)
                while true; do
                    echo
                    echo 'When specifying a profile description/filename the following is highly recommended to include:'
                    echo '  - Printer ID'
                    echo '  - Paper ID'
                    echo '  - Color Space'
                    echo '  - Target used for profile'
                    echo '  - Instrument/calibration type used'
                    echo '  - Date created'
                    echo
                    echo "Current value specified:"
                    echo "'${EXAMPLE_FILE_NAMING}'"
                    echo
                    echo 'Valid values: Letters A–Z a–z, digits 0–9, dash -, underscore _, parentheses ( ), dot .'
                    echo
                    read -e -p "Enter example file naming convention: " value

                    if [[ ! "$value" =~ ^[A-Za-z0-9._()\-]+$ ]]; then
                        echo "❌ Invalid file name characters. Please try again."
                        continue
                    fi

                    # Valid input → exit loop
                    break
                done

                sed_inplace "s|^EXAMPLE_FILE_NAMING=.*|EXAMPLE_FILE_NAMING='${value}'|" "$SETUP_FILE"

                echo "✅ Updated file naming convention example to:"
                echo "$value"
                echo
                source "$SETUP_FILE"
                continue
                ;;

            7)
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
        echo
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
            if [[ "$PLATFORM" == "macos" ]]; then
                osascript -e 'tell application "Terminal" to close front window' & exit 0
            else
                exit 0
            fi
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

