#!/usr/bin/env bash

version="1.3.0"
# Version 1.3.0

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
    echo
    read -p 'Press enter to quit...'
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
echo "Author:  Knut Larsson"
echo "Version: $version"
echo
echo
# --- Set location and script name -------------------------------------------------
cd "$(dirname "$0")"
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
script_name="$(basename -- "$0")"
temp_log="${script_dir}/Argyll_Printer_Profiler_$(date +%Y%m%d).log"

session_separator() {
    # Add session separator to log file only
    {
        echo
        echo
        echo
        echo "================================================================================"
        echo "🆕 NEW SCRIPT SESSION STARTED"
        echo "📅 Date & Time: $(date '+%Y-%m-%d %H:%M:%S %Z (%z)')"
        echo "🖥️  Platform: $PLATFORM"
        echo "👤 User: $(whoami)"
        echo "📂 Working Directory: $(pwd)"
        echo "📜 Script: $script_name"
        echo "📊 Log File: $temp_log"
        echo "⚡ Process ID: $$"
        echo "================================================================================"
        echo
        echo
        echo
    } >> "$temp_log"
}

# Check if log file for today already exists
if [ -f "$temp_log" ]; then
    echo "⚠️ Log file already exists for today."
    echo "🔄 Appending to existing daily log."
    # Hook up tee-based logging for existing file
    exec > >(tee -a "$temp_log") 2>&1
    # Add session separator to log file only
    session_separator
else
    # Try to create/truncate the log file explicitly
    if ! : >"$temp_log" 2>/dev/null; then
        echo "❌ Cannot create log file at '$temp_log'."
        echo "   Check folder permissions or disk access."
        echo
        read -p 'Press enter to quit...'
        exit 1  # Exit if we can't create log file
    else
        # Only if creation succeeded, hook up tee-based logging
        exec > >(tee -a "$temp_log") 2>&1
        # Add session separator to log file only
        session_separator
    fi
fi

echo

# --- Load setup file -------------------------------------------------
setup_file="${script_dir}/Argyll_Printer_Profiler_setup.ini"

if [ ! -f "$setup_file" ]; then
  echo "❌ Setup file not found:"
  echo "   The setup ini file must be located in folder together with script ${script_name}."
  echo
  read -p 'Press enter to quit...'
  exit 1
fi

# Load variables
# shellcheck source=/dev/null
source "$setup_file"

# --- Required command detection --------------------------------------
REQUIRED_CMDS=(
    targen
    chartread
    colprof
    printtarg
    profcheck
    dispcal
)

# Platform-specific requirements
if [[ "$PLATFORM" == "linux" ]]; then
    REQUIRED_CMDS+=(
        zenity
    )
fi

# Check core ArgyllCMS commands
missing_argyll=()
missing_linux_tools=()

for cmd in "${REQUIRED_CMDS[@]}"; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    # Check if it's an ArgyllCMS command or Linux tool
    case "$cmd" in
        targen|chartread|colprof|printtarg|profcheck|dispcal)
            missing_argyll+=("$cmd")
            ;;
        zenity)
            missing_linux_tools+=("$cmd")
            ;;
    esac
  fi
done

# Check Linux window management tools (optional but recommended)
if [[ "$PLATFORM" == "linux" ]]; then
    if ! command -v wmctrl >/dev/null 2>&1 && ! command -v xdotool >/dev/null 2>&1; then
        missing_linux_tools+=("wmctrl or xdotool")
    fi
fi

# Report missing dependencies
if [ ${#missing_argyll[@]} -gt 0 ]; then
    echo "❌ ArgyllCMS not found (missing commands: ${missing_argyll[*]})"
    echo
    if [[ "$PLATFORM" == "macos" ]]; then
        echo "Install ArgyllCMS using desired package manager (e.g. Homebrew):"
        echo "  brew install argyll-cms"
    else
        echo "Install ArgyllCMS from your distribution's package manager or from argyllcms.com"
        echo "Example:"
        echo "   sudo apt install argyll-cms"
    fi
    echo
    read -p 'Press enter to quit...'
    exit 1
fi
 
if [ ${#missing_linux_tools[@]} -gt 0 ]; then
    echo "❌ Missing required Linux tools: ${missing_linux_tools[*]}"
    echo
    echo "Install with your package manager:"
    echo "   sudo apt install ${missing_linux_tools[*]}"
    echo
    echo "These tools are required for the script to function properly:"
    if [[ " ${missing_linux_tools[*]} " =~ " zenity " ]]; then
        echo "  • zenity: Required for file selection dialogs"
    fi
    if [[ " ${missing_linux_tools[*]} " =~ " wmctrl or xdotool " ]]; then
        echo "  • wmctrl or xdotool: Required for terminal focus management"
    fi
    echo
    echo "Please install the missing dependencies and try again."
    echo
    read -p 'Press enter to quit...'
    exit 1
fi
 
echo "✅ All required dependencies found"
echo

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
echo "🖥️  Recommeded Terminal Window Size: 100 columns x 50 rows"
echo

# --- Functions --------------------------------------------------
prepare_profile_folder() {
    # Validate required variables
    # ${name:-} If $name is unset or empty, use "" (empty string)
    if [ -z "${name:-}" ]; then
        echo "❌ name variable not set"
        return 1
    fi
    
    # ${action:-} If $action is unset or empty, use "" (empty string)
    if [ -z "${action:-}" ]; then
        echo "❌ action variable not set"
        return 1
    fi

    # Default fallback
    new_name="$name"

    # Do only if action 2 or 3 or 4 (ti2 or ti3 selection)
    if [[ "$action" == "2" || "$action" == "3"  || "$action" == "4" ]]; then
        print_profile_name_menu "Leave empty to keep current name." "$name"

        read -e -p "Enter filename (leave empty to keep current): " new_name
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

    while true; do  # ← Outer loop for retry logic
        profile_folder="${script_dir}/${CREATED_PROFILES_FOLDER}/${new_name}"

        # Check if profile folder already exists
        if [ -d "$profile_folder" ]; then
            echo
            echo "⚠️ Profile folder already exists: '$profile_folder'"
            echo
            echo "Contents:"
            ls -l -1 "$profile_folder" 2>/dev/null || echo "  (Unable to list contents)"
            echo
            echo "Choose an option:"
            echo "  1) Use existing folder (delete existing files)"
            echo "  2) Enter a different name"
            echo "  3) Cancel operation"
            echo
            while true; do
                read -r -n 1 -p "Enter choice [1-3]: " choice
                echo
                case "$choice" in
                    1)
                        echo
                        echo "Using existing folder: '$profile_folder'"
                        # Delete existing contents to avoid leftover files from previous runs
                        rm -rf "$profile_folder"/* 2>/dev/null || true
                        break 2     # Exit both loops
                        ;;
                    2)
                        echo
                        # Re-show the menu for re-entering name
                        print_profile_name_menu "Leave empty to cancel." "$name"
                        while true; do
                            read -e -p "Enter filename: " new_name
                            if [ -z "$new_name" ]; then
                                echo
                                echo "Creating profile folder cancelled."
                                return 1
                            fi
                            # Sanitize input
                            new_name="$(printf '%s' "$new_name" | sed 's/[[:space:]]*$//')"
                            if [[ ! "$new_name" =~ ^[A-Za-z0-9._()\-]+$ ]]; then
                                echo "❌ Invalid file name characters. Please try again."
                                continue
                            fi
                            profile_folder="${script_dir}/${CREATED_PROFILES_FOLDER}/${new_name}"
                            break
                        done
                        # Restart check with new name
                        break 1     # Exit inner loop only
                        ;;
                    3)
                        echo
                        echo "Creating profile folder cancelled."
                        return 1
                        ;;
                    *)
                        echo "❌ Invalid choice. Please enter 1, 2, or 3."
                        ;;
                esac
            done
        else
            # Folder doesn't exist, break outer loop
            break
        fi
    done  # ← Close outer loop
    
    # DEBUG!!!
    #echo
    #echo "In function prepare_profile_folder:"
    #echo "Defined Folder before mkdir: $profile_folder"
    #echo "new_name: ${new_name}"
    #echo

    # Create profile folder
    mkdir -p "$profile_folder" || {
        echo "❌ Failed to create profile folder: '$profile_folder'"
        return 1
    }

    echo "✅ Working folder for profile:"
    echo "'$profile_folder'"

    cd "$profile_folder" || {
        echo "❌ Failed to change directory to '$profile_folder'"
        return 1
    }

    desc="$new_name"
}

copy_files_ti1_ti2_ti3_tif() {
    # Copy existing files into new folder
    # Verify file exists
    if [ ! -n "$name" ] || [ ! -f "${source_folder}/${name}.ti1" ]; then
        echo "⚠️ .ti1 file not found for '${name}'. Ignoring."
    else
        if [ "$source_folder" != "$profile_folder" ]; then
            cp "${source_folder}/${name}.ti1" "$profile_folder/" || {
                echo "❌ Failed to copy ${name}.ti1 to directory '$profile_folder'"
                echo "Profile folder is left as is:"
                echo "'${profile_folder}'"
                return 1
            }
        fi
    fi

    if [[ "$action" == "4" ]]; then
        if [ ! -n "$name" ] || [ ! -f "${source_folder}/${name}.ti2" ]; then
            echo "⚠️ .ti2 file not found for '${name}'. Ignoring."
        else
            if [ "$source_folder" != "$profile_folder" ]; then
                cp "${source_folder}/${name}.ti2" "$profile_folder/" || {
                    echo "❌ Failed to copy ${name}.ti2 to directory '$profile_folder'"
                    echo "Profile folder is left as is:"
                    echo "'${profile_folder}'"
                    return 1
                }
            fi
        fi
    else    # must exist for action 2 + 3
        if [ ! -n "$name" ] || [ ! -f "${source_folder}/${name}.ti2" ]; then
            echo "❌ .ti2 file not found for '${name}'."
            return 1
        else
            if [ "$source_folder" != "$profile_folder" ]; then
                cp "${source_folder}/${name}.ti2" "$profile_folder/" || {
                    echo "❌ Failed to copy ${name}.ti2 to directory '$profile_folder'"
                    echo "Profile folder is left as is:"
                    echo "'${profile_folder}'"
                    return 1
                }
            fi
        fi
    fi

    # Do only if action 2 or 4 (ti3 selection)
    if [[ "$action" == "2" || "$action" == "4" ]]; then
        if [ ! -n "$name" ] || [ ! -f "${source_folder}/${name}.ti3" ]; then
            echo "❌ .ti3 file not found for '${name}'."
            return 1
        else
            if [ "$source_folder" != "$profile_folder" ]; then
                cp "${source_folder}/${name}.ti3" "$profile_folder/" || {
                    echo "❌ Failed to copy ${name}.ti3 to directory '$profile_folder'"
                    echo "Profile folder is left as is:"
                    echo "'${profile_folder}'"
                    return 1
                }
            fi
        fi
    fi

    if (( ${#tif_files[@]} > 0 )); then
        # Copy all TIFFs from tif_files array
        for f in "${tif_files[@]}"; do
            if [ "$(dirname "$f")" != "$profile_folder" ]; then
                cp "$f" "$profile_folder/" || {
                    echo "❌ Failed to copy $(basename "$f") to '$profile_folder'"
                    echo "Profile folder is left as is:"
                    echo "'${profile_folder}'"
                    return 1
                }
            fi
        done
    fi
}

rename_files_ti1_ti2_ti3_tif() {
    # Before calling this function, make sure:
    #  - $name and $new_name are set.
    #  - $profile_folder is set.
    #  - $tif_files is set.
    #  - $action is set.
    #  - directory $profile_folder exists.
    #  - directory has been cd'ed into.

    # Verify we're in the correct directory
    if [ "$(pwd)" != "$profile_folder" ]; then
        echo "⚠️ Not in profile folder. Current: $(pwd)"
        echo "🔄 Attempting to change to profile folder: '$profile_folder'"
            
        if cd "$profile_folder" 2>/dev/null; then
            echo "✅ Successfully changed to profile folder"
        else
            echo "❌ Failed to change to profile folder."
            echo "Existing files are left in profile folder:"
            echo "'${profile_folder}'"
            return 1
        fi
    fi
    echo "Renaming files to match new profile name…"
    local f base suffix ext newfile i

    # Rename files
    if [ -f "${profile_folder}/${name}.ti1" ]; then
        mv "${name}.ti1" "${new_name}.ti1" || {
            echo "❌ Failed to rename ${name}.ti1 → ${new_name}.ti1"
            echo "Existing files are left in profile folder:"
            echo "'${profile_folder}'"
            return 1
        }
    fi

    if [ -f "${profile_folder}/${name}.ti2" ]; then
        mv "${name}.ti2" "${new_name}.ti2" || {
            echo "❌ Failed to rename ${name}.ti2 → ${new_name}.ti2"
            echo "Existing files are left in profile folder:"
            echo "'${profile_folder}'"
            return 1
        }
    fi

    # Do only if action 2 (ti3 selection)
    if [[ "$action" == "2" || "$action" == "4" ]]; then
        if [ -f "${profile_folder}/${name}.ti3" ]; then
            mv "${name}.ti3" "${new_name}.ti3" || {
                echo "❌ Failed to rename ${name}.ti3 → ${new_name}.ti3"
                echo "Existing files are left in profile folder:"
                echo "'${profile_folder}'"
                return 1
            }
        fi
    fi

    # DEBUG!!!
    #echo
    #echo "In function rename_files_ti1_ti2_ti3_tif:"
    #echo "new_name: ${new_name}"
    #echo "tif_files: ${tif_files[@]}"
    #echo
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
        newfile="${new_name}${suffix}${ext}"

        # Rename file
        mv "$(basename "$f")" "$newfile" || {
            echo "❌ Failed to rename $(basename "$f") → $(basename "$newfile")"
            echo "Existing files are left in profile folder:"
            echo "'${profile_folder}'"
            return 1
        }

        # DEBUG!!!
        #echo
        #echo "In function rename_files_ti1_ti2_ti3_tif:"
        #echo "newfile: ${newfile}"
        #echo "f: $f"
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

# Reusable function to print the profile name menu with customizable elements
print_profile_name_menu() {
    local last_line="$1"
    local current_name="$2"
    local show_example="${3:-true}"  # Default true
    local current_display="$4"

    echo
    echo
    echo
    echo "─────────────────────────────────────────────────────────────────────"
    echo "Specify Profile Description / File Name"
    echo "─────────────────────────────────────────────────────────────────────"
    echo
    echo "The following is highly recommended to include:"
    echo "  - Printer ID"
    echo "  - Paper ID"
    echo "  - Color Space"
    echo "  - Target used for profile"
    echo "  - Instrument/calibration type used"
    echo "  - Date created"
    echo
    if [ "$show_example" = "true" ]; then
        echo "Example file naming convention (select and copy):"
        echo "${EXAMPLE_FILE_NAMING}"
        echo
        echo "For simplicity, profile description and filename are made identical."
        echo "The profile description is what you will see in Photoshop and ColorSync Utility."
        echo
        echo "Enter a desired filename for this profile."
        echo "If your filename is foobar, your profile will be named foobar.icc."
        echo
    fi
    if [ -n "$current_display" ]; then
        echo "$current_display"
        echo
    elif [ -n "$current_name" ]; then
        echo "Current name: $current_name"
        echo
    fi
    echo "Valid values: Letters A–Z a–z, digits 0–9, dash -, underscore _, parentheses (), dot ."
    echo "$last_line"
    echo
}

specify_profile_name() {
    while true; do
        print_profile_name_menu "Leave empty to cancel and return to previous menu."
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


set_icc_profile_parameter() {
    # Update the setup file
    if [ ! -f "$setup_file" ]; then
        echo "❌ Setup file not found. Cannot save new ICC/ICM profile."
        return 1
    fi

    if [ -z "${new_icc_path:-}" ]; then
        echo "⚠️ No new ICC/ICM profile selected. Keeping existing PRINTER_ICC_PATH."
        return 1
    fi

    # Escape slashes for sed
    local escaped_path
    escaped_path=$(printf '%s\n' "$new_icc_path" | sed 's/[\/&]/\\&/g')

    # Replace the line starting with PRINTER_ICC_PATH=
    sed_inplace "s|^PRINTER_ICC_PATH=.*|PRINTER_ICC_PATH=\"${escaped_path}\"|" "$setup_file"

    echo "✅ Updated PRINTER_ICC_PATH in setup file:"
    echo "   $setup_file"
    echo "   New path: $new_icc_path"
    echo
}

set_precond_profile_parameter() {
    # Update the setup file
    if [ ! -f "$setup_file" ]; then
        echo "❌ Setup file not found. Cannot save new ICC/ICM profile."
        return 1
    fi

    if [ -z "${new_icc_path:-}" ]; then
        echo "⚠️ No new ICC/ICM profile selected. Keeping existing PRECONDITIONING_PROFILE_PATH."
        return 1
    fi

    # Escape slashes for sed
    local escaped_path
    escaped_path=$(printf '%s\n' "$new_icc_path" | sed 's/[\/&]/\\&/g')

    # Replace the line starting with PRECONDITIONING_PROFILE_PATH=
    sed_inplace "s|^PRECONDITIONING_PROFILE_PATH=.*|PRECONDITIONING_PROFILE_PATH=\"${escaped_path}\"|" "$setup_file"

    echo "✅ Updated PRECONDITIONING_PROFILE_PATH in setup file:"
    echo "   $setup_file"
    echo "   New path: $new_icc_path"
    echo
}

select_instrument() {
    while true; do
        echo
        echo
        echo "─────────────────────────────────────────────────────────────────────"
        echo 'Specify Spectrophotometer Model'
        echo "─────────────────────────────────────────────────────────────────────"
        echo
        echo 'This affects how the target chart is generated.'
        echo
        echo '1: i1Pro'
        echo '2: i1Pro3+'
        echo '3: ColorMunki'
        echo '4: DTP20'
        echo '5: DTP22'
        echo '6: DTP41'
        echo '7: DTP51'
        echo '8: SpectroScan'
        echo "9: Abort creating target."
        echo
        echo 'Notes:'
        echo "  - A menu of target chart options will be presented next step."
        echo "  - Option '3: ColorMunki' has a separate configurable menu from the rest."
        echo "  - The menu option and command arguments for targen and printtarg may be"
        echo "    edited in .ini file."
        echo
        echo "─────────────────────────────────────────────────────────────────────"
        echo
        read -r -n 1 -p 'Enter your choice [1-9]: ' answer
        echo
        
        # Validate input
        if [[ ! "$answer" =~ ^[1-9]$ ]]; then
            echo
            echo "❌ Invalid choice. Please enter a number from 1 to 9."
            echo
            continue
        fi
        
        case $answer in
            1)
                inst_arg=' -ii1'
                inst_name='i1Pro'
                break
                ;;
            2)
                inst_arg=' -i3p'
                inst_name='i1Pro3+'
                break
                ;;
            3)
                inst_arg=' -iCM -h'
                inst_name='ColorMunki'
                break
                ;;
            4)
                inst_arg=' -i20'
                inst_name='DTP20'
                break
                ;;
            5)
                inst_arg=' -i22'
                inst_name='DTP22'
                break
                ;;
            6)
                inst_arg=' -i41'
                inst_name='DTP41'
                break
                ;;
            7)
                inst_arg=' -i51'
                inst_name='DTP51'
                break
                ;;
            8)
                inst_arg=' -iSS'
                inst_name='SpectroScan'
                break
                ;;
            9)
                echo
                echo 'Aborting creating target.'
                return 1
                ;;
        esac
    done
    
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
        echo
        echo "Notes on generating target charts:"
        echo
        echo '  When making targets with argyllcms targen, often two very light coloured patches'
        echo '  come next to each other (especially if there are multiple white patches), and targen'
        echo '  leaves the spacer between them also white (not black as it should be), which then'
        echo '  results in error “Not enough few patches” during reading of chart.'
        echo '  To prevent this, review the targets before printing to see if any light colored patches'
        echo '  are next to each other, and if the spacer is close in color. If there are, re-generate'
        echo '  the targets until it is acceptable. If this situation persists, this may be reason to'
        echo '  choose a pre-made target (option 3. in main menu).'
        echo
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
            echo "       - For more information on targen arguments, see argyllcms manual."
            echo
            echo 'Valid values: Letters A–Z a–z, digits 0–9, dash -, underscore _, '
            echo '              parentheses (), forward slash /, space, dot .'
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
            echo "Note: - Previously selected instrument (-i), resolution (-T) "
            echo "        and page size (-p) must be specified again if desired."
            echo "      - For more information on printtarg arguments, see argyllcms manual."
            echo
            echo 'Valid values: Letters A–Z a–z, digits 0–9, dash -, underscore _, '
            echo '              parentheses (), forward slash /, space, dot .'
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
            echo
            read -r -n 1 -p 'Do you want to continue with selected target? [y/n]: ' again
            echo
            case "$again" in
            [yY]|[yY][eE][sS])
                echo
                echo 'Continuing with selected target...'
                break 2  # Exit both loops (confirmation and target selection)
                ;;
            [nN]|[nN][oO])
                echo
                echo 'Repeating target selection...'
                break  # Exit confirmation loop, stay in target selection loop
                ;;
            *)
                echo
                echo 'Invalid input. Please enter y/yes or n/no.'
                ;;
            esac
        done
    done

    # --- Build targen arguments conditionally ---------------------------

    # For targen, if any variable for each argument is empty, then remove argument in command (empty parameter)
   targen_l=''        # ink limit
   if [ -n "$INK_LIMIT" ]; then
       targen_l=" -l${INK_LIMIT}"
   fi
    targen_e=''        # white patches
    if [ -n "$white_patches" ]; then
        targen_e=" -e${white_patches}"
    fi
    targen_B=''        # black patches
    if [ -n "$black_patches" ]; then
        targen_B=" -B${black_patches}"
    fi
    targen_g=''        # gray steps
    if [ -n "$gray_steps" ]; then
        targen_g=" -g${gray_steps}"
    fi
    targen_m=''        # multi cube steps
    if [ -n "$multi_cube_steps" ]; then
        targen_m=" -m${multi_cube_steps}"
    fi
    targen_M=''        # multi cube surface steps
    if [ -n "$multi_cube_surface_steps" ]; then
        targen_M=" -M${multi_cube_surface_steps}"
    fi
    targen_f=''        # patch count
    if [ -n "$patch_count" ]; then
        targen_f=" -f${patch_count}"
    fi
    targen_c=()        # pre-conditioning profile path with filename
    if [ -n "$PRECONDITIONING_PROFILE_PATH" ]; then
       if [ -f "$PRECONDITIONING_PROFILE_PATH" ]; then
          targen_c+=("-c" "$PRECONDITIONING_PROFILE_PATH")
       else
          echo "⚠️ Warning: Pre-conditioning profile not found: '$PRECONDITIONING_PROFILE_PATH'"
          echo "   Skipping pre-conditioning profile in targen."
       fi
    fi

    # --- Build printtarg arguments conditionally -------------------------

    # For printtarg, if any variable for each argument is empty, then remove argument in command (empty parameter)
    printtarg_T=''     # target resolution
    if [ -n "$TARGET_RESOLUTION" ]; then
        printtarg_T=" -T${TARGET_RESOLUTION}"
    fi
    printtarg_p=''     # paper size
    if [ -n "$PAPER_SIZE" ]; then
        printtarg_p=" -p${PAPER_SIZE}"
    fi
    printtarg_a=''        # multi cube surface steps
    if [ -n "$scale_patch_and_spacer" ]; then
        printtarg_a=" -a${scale_patch_and_spacer}"
    fi
    printtarg_A=''        # multi cube surface steps
    if [ -n "$scale_spacer" ]; then
        printtarg_A=" -A${scale_spacer}"
    fi
    ## Removed defined layout seed for printtarg if not used
    printtarg_R=''        # layour seed
    if [ "$USE_LAYOUT_SEED_FOR_TARGET" = "true" ]; then
        if [ -n "$layout_seed" ]; then
            printtarg_R=" -R${layout_seed}"
        fi
    fi

    if [ ! "$label" = "Custom" ]; then      # When menu choice other than Custom
        echo
        echo 'Generating target color values (.ti1 file)...'
        echo "Command Used: targen ${COMMON_ARGUMENTS_TARGEN}${targen_l}${targen_e}${targen_B}${targen_g}${targen_m}${targen_M}${targen_f} "${targen_c[@]}" "${name}""
        # --- Generate target ONLY ONCE, after confirmation ---
        targen ${COMMON_ARGUMENTS_TARGEN}${targen_l}${targen_e}${targen_B}${targen_g}${targen_m}${targen_M}${targen_f} "${targen_c[@]}" "${name}" || {
            echo "❌ targen failed."
            return 1
        }

        echo
        echo 'Generating target(s) (.tif image(es) and .ti2 file)...'
        echo "Command Used: printtarg ${COMMON_ARGUMENTS_PRINTTARG}${inst_arg}${printtarg_R}${printtarg_T}${printtarg_p}${printtarg_a}${printtarg_A} "${name}""
        # Common printtarg command
        printtarg ${COMMON_ARGUMENTS_PRINTTARG}${inst_arg}${printtarg_R}${printtarg_T}${printtarg_p}${printtarg_a}${printtarg_A} "${name}" || {
            echo "❌ printtarg failed."
            return 1
        }
        echo
    else      # When menu choice is Custom
        echo
        echo 'Generating target color values (.ti1 file)...'
        # --- Generate target ONLY ONCE, after confirmation ---
        echo "Command Used: targen ${targen_command_custom}${targen_l} "${targen_c[@]}" "${name}""
        targen ${targen_command_custom}${targen_l} "${targen_c[@]}" "${name}" || {
            echo "❌ targen failed."
            return 1
        }

        echo
        echo 'Generating target(s) (.tif image(s) and .ti2 file)...'
        echo "Command Used: printtarg ${printtarg_command_custom} "${name}""
        # Common printtarg command
        printtarg ${printtarg_command_custom} "${name}" || {
            echo "❌ printtarg failed."
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
    echo
    for f in "${tif_files[@]}"; do
        echo "  $f"
    done
    echo

    if [[ "$PLATFORM" == "macos" ]]; then
        if [[ "$ENABLE_AUTO_OPEN_IMAGES_WITH_COLOR_SYNC_MAC" == "true" ]]; then
            echo 'Please print the test chart(s) and make sure to disable color management.'
            echo 'Created Images will open automatically in ColorSync Utility.'
            echo 'In the Printer dialog set option "Colour" to "Print as Color Target".'
            open -a "$COLOR_SYNC_UTILITY_PATH" "${tif_files[@]}"
        else
            echo 'Please print the test chart(s) and make sure to disable color management.'
            echo 'Use applications like ColorSync Utility, Adobe Color Print Utility or'
            echo 'Photoshop etc.'
            echo
            echo 'If you want ColorSync Utility to automatically open all created test'
            echo 'charts, open .ini file and set parameter'
            echo "ENABLE_AUTO_OPEN_IMAGES_WITH_COLOR_SYNC_MAC to 'true'."
        fi
    else
        echo 'Please print the test chart(s) and make sure to disable color management.'
        echo 'Use applications like ColorSync Utility or Adobe Color Print Utility.'
    fi

    echo
    echo
    echo 'After target(s) have been printed...'
    echo
    while true; do
        read -r -n 1 -p 'Do you want to continue with measuring of target? [y/n]: ' again
        echo
        case "$again" in
        [yY]|[yY][eE][sS])
            echo
            echo 'Continuing with measuring of target...'
            break  # Exit loop
            ;;
        [nN]|[nN][oO])
            echo
            echo 'Aborting measuring of target...'
            return 1    # jumps out of loop and function immediately
            ;;
        *)
            echo
            echo 'Invalid input. Please enter y/yes or n/no.'
            ;;
        esac
    done
}

check_files_in_new_location_after_copy() {
    local missing_files=0
    # Check .ti2, applicable for action 2+3
    if [[ ! "$action" == "4" ]]; then
        if [ ! -f "${profile_folder}/${name}.ti2" ]; then
            echo "❌ Missing ${name}.ti2 in $profile_folder"
            missing_files=1
        fi
    fi

    # Check .ti3 if exists (only for ti3 selection)
    if [[ "$action" == "2" || "$action" == "4" ]]; then
        if [ ! -f "${profile_folder}/${name}.ti3" ]; then
            echo "❌ Missing ${name}.ti3 in $profile_folder"
            missing_files=1
        fi
    fi

    # Check tif only if not action 4.
    if [[ ! "$action" == "4" ]]; then
        # Check TIFFs
        tif_files=()
        if [ -f "${profile_folder}/${name}.tif" ]; then
            tif_files+=("${profile_folder}/${name}.tif")
        fi
        for f in "${profile_folder}/${name}"_??.tif; do
            [ -f "$f" ] && tif_files+=("$f")
        done

        if [ ${#tif_files[@]} -eq 0 ]; then
            echo "❌ No TIFF files found in $profile_folder"
            missing_files=1
        fi
    fi
    # If any missing, abort
    if [ "$missing_files" -eq 1 ]; then
        echo "❌ File copy to profile location failed. Returning to main menu..."
        return 1
    fi
}

copy_or_overwrite_submenu() {
    local line1="$1"
    local line2="$2"
    while true; do
        echo
        echo
        echo "Do you want to:"
        echo
        echo "1: Create new profile (copy files into new folder)"
        if [ -n "$line2" ]; then
            echo "2: Overwrite existing ($line1"
            echo "   $line2)"
        else
            echo "2: Overwrite existing ($line1)"
        fi
        echo "3: Abort operation"
        echo
        read -r -n 1 -p 'Enter your choice [1-3]: ' copy_choice
        echo
        case "$copy_choice" in
          1)
            prepare_profile_folder || {
                echo "Profile preparation failed..."
                return 1
            }
            copy_files_ti1_ti2_ti3_tif || {
                echo "File copy failed..."
                return 1
            }
            rename_files_ti1_ti2_ti3_tif || {
                echo "File renaming failed..."
                return 1
            }
            check_files_in_new_location_after_copy || {
                echo "File check after copy failed..."
                return 1
            }
            break
            ;;
          2)
            profile_folder="$source_folder"
            echo "✅ Working folder for profile:"
            echo "$profile_folder"
            cd "$profile_folder" || {
                echo "❌ Failed to change directory to $profile_folder"
                return 1
            }
            break
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

select_file() {
    local ext="$1"
    local title="$2"
    local type="$3"
    
    echo

    local file_path
    local default_location
    local filter
    
    case "$type" in
        ti2)
            default_location="${script_dir}/${PRE_MADE_TARGETS_FOLDER}"
            filter="Target Information 2 data | *.ti2"
            ;;
        ti3|ti3_only)
            default_location="${script_dir}/${CREATED_PROFILES_FOLDER}"
            filter="Target Information 3 data | *.ti3"
            ;;
        icc)
            local current_file
            local folder
            current_file="$(basename "$PRINTER_ICC_PATH")"
            folder="$(dirname "$PRINTER_ICC_PATH")"
            default_location="$folder"
            filter="ICC/ICM profiles | *.icc *.icm"
            ;;
    esac

    if [[ "$PLATFORM" == "macos" ]]; then
        local of_type
        if [[ "$type" == "icc" ]]; then
            of_type="{\"icc\", \"icm\"}"
        else
            of_type="{\"${ext}\"}"
        fi
        
        file_path=$(osascript <<EOF
try
    tell application "Finder"
        activate
        set f to choose file with prompt "$title" of type ${of_type} default location POSIX file "$default_location"
        set resultPath to POSIX path of f
    end tell
    tell application "Terminal" to activate
    tell application "System Events" to set frontmost of process "Terminal" to true
    return resultPath
on error
    tell application "Terminal" to activate
    tell application "System Events" to set frontmost of process "Terminal" to true
    return ""
end try
EOF
)

    else    # linux
        local term_win_id=""
        if command -v xdotool >/dev/null 2>&1; then
            term_win_id="$(xdotool getactivewindow 2>/dev/null)"
        elif command -v xprop >/dev/null 2>&1; then
            term_win_id="$(xprop -root _NET_ACTIVE_WINDOW 2>/dev/null | awk '{print $NF}')"
        fi
        # Open Zenity file chooser dialog (Linux)
        file_path=$(zenity --file-selection \
            --title="$title" \
            --filename="$default_location/" \
            --file-filter="$filter")

        # Return focus to terminal after file selection
        if [ -n "$term_win_id" ] && command -v xdotool >/dev/null 2>&1; then
            xdotool windowactivate "$term_win_id" 2>/dev/null || true
        elif [ -n "$term_win_id" ] && command -v wmctrl >/dev/null 2>&1; then
            wmctrl -ia "$term_win_id" 2>/dev/null || true
        else
            echo "⚠️ Warning: Could not return focus to terminal (install wmctrl or xdotool)"
        fi
    fi

    # User cancelled → return to main menu
    if [ -z "$file_path" ]; then
        echo "Selection cancelled."
        echo
        return 1
    fi

    if [[ "$type" == "icc" ]]; then
        # Validate file extension
        local file_ext="${file_path##*.}"
        if [[ "$file_ext" != "icc" && "$file_ext" != "icm" ]]; then
            echo "❌ Selected file is not a .icc or .icm file."
            return 1
        fi
        new_icc_path="$file_path"
        echo "Selected profile: $new_icc_path"
    else
        # For profiling files
        if [[ "${file_path##*.}" != "$ext" ]]; then
            echo "❌ Selected file is not a .$ext file."
            return 1
        fi
        
        name="$(basename "$file_path" .$ext)"
        desc="$name"
        source_folder="$(dirname "$file_path")"
        
        echo "Selected .$ext file: $file_path"
        
        if [[ "$type" == "ti2" ]]; then
            # Check TIFF targets
            tif_files=()
            
            # Single-page
            if [ -f "${source_folder}/${name}.tif" ]; then
                tif_files+=("${source_folder}/${name}.tif")
            else
                # Multi-page
                for f in "${source_folder}/${name}"_??.tif; do
                    [ -f "$f" ] && tif_files+=("$f")
                done
            fi
            
            if [ ${#tif_files[@]} -eq 0 ]; then
                echo "❌ No matching .tif target images found for '${name}'."
                return 1
            fi
            
            echo "Found target image(s):"
            echo
            for f in "${tif_files[@]}"; do
                echo "  $(basename "$f")"
            done
            
            copy_or_overwrite_submenu "use files in their current location, " "existing .ti3 and .icc/icm files will be overwritten"
        elif [[ "$type" == "ti3" ]]; then
            # Verify .ti2 exists
            if [ ! -n "$name" ] || [ ! -f "${source_folder}/${name}.ti2" ]; then
                echo "❌ Matching .ti2 file not found for '${name}'."
                return 1
            fi
            
            # Check TIFF targets
            tif_files=()
            
            # Single-page
            if [ -f "${source_folder}/${name}.tif" ]; then
                tif_files+=("${source_folder}/${name}.tif")
            else
                # Multi-page
                for f in "${source_folder}/${name}"_??.tif; do
                    [ -f "$f" ] && tif_files+=("$f")
                done
            fi
            
            if [ ${#tif_files[@]} -eq 0 ]; then
                echo "❌ No matching .tif target images found for '${name}'."
                return 1
            fi
            
            echo "Found target image(s):"
            echo
            for f in "${tif_files[@]}"; do
                echo "  $(basename "$f")"
            done
            
            copy_or_overwrite_submenu "measurement will" "resume using existing .ti3 and .icc/icm file will be overwritten"
        elif [[ "$type" == "ti3_only" ]]; then
            # only for action 5 (perform sanity check)
            if [ "$action" = "5" ]; then
                # Verify .icc exists
                if [ ! -n "$name" ] || [ ! -f "${source_folder}/${name}.icc" ]; then
                    echo "❌ Matching .icc file not found for '${name}'."
                    return 1
                fi
            fi

            # Overwrite existing
            # Update profile_folder to folder of selected .ti3 file
            profile_folder="$source_folder"

            echo "✅ Working folder for profile:"
            echo "$profile_folder"
            # Change working directory
            cd "$profile_folder" || {
                echo "❌ Failed to change directory to $profile_folder"
                return 1
            }

            # only for action 4 (Create printer profile from an existing measurement file)
            if [ "$action" = "4" ]; then
                copy_or_overwrite_submenu "existing .icc/icm file will be overwritten" ""
            fi
        fi
    fi
}

show_de_reference() {
    echo
    echo
    echo
    echo "Below is an overview of expected accuracy of profiles."
    echo
    echo "──────────────────────────────────────────────────────────────────────────────"
    echo "Delta E 2000 (Real-World Accuracy After Profiling)"
    echo "──────────────────────────────────────────────────────────────────────────────"
    echo "                             Typical       Typical          Typical"
    echo "Printer Class                ΔE2000        Substrates       Use Cases"
    echo "──────────────────────────────────────────────────────────────────────────────"
    echo "Professional Photo Inkjet    Avg 0.5-1.5   Gloss,           Gallery,"
    echo "  Example Models:            95% 1.5-2.5   baryta,          contract proofing"
    echo "  Epson P700/P900/P9570,     Max 3-5       fine art"
    echo "  Canon PRO-1000, HP Z9+"
    echo
    echo "Prosumer / High-End Inkjet   Avg 0.8-2.0   Premium gloss,   Serious hobby,"
    echo "  Example Models:            95% 2.0-3.5   semi-gloss,      small studio"
    echo "  Epson P600/P800,           Max 4-7"
    echo "  Canon PRO-200/300"
    echo
    echo "Consumer Home Inkjet         Avg 1.5-3.0   Glossy, matte,   Casual photo,"
    echo "  Example Models:            95% 3.0-5.0   plain            mixed docs"
    echo "  Canon PIXMA TS/MG,         Max 6-10"
    echo "  Epson EcoTank/Expression"
    echo
    echo "Professional Laser /         Avg 1.5-2.5   Coated stock,    Corporate,"
    echo "Production                   95% 3.0-4.0   proof paper      marketing,"
    echo "  Example Models:            Max 5-7                        light proof"
    echo "  Xerox PrimeLink,"
    echo "  Canon imagePRESS"
    echo "  Ricoh Pro C"
    echo
    echo "Office / Consumer Laser      Avg 2.5-5.0   Office bond,     Business docs,"
    echo "  Example Models:            95% 4.0-7.0   coated office    presentations"
    echo "  HP Color LaserJet Pro,     Max 7-12+"
    echo "  Brother HL/MFC"
    echo "  Canon i-SENSYS"
    echo
    echo "──────────────────────────────────────────────────────────────────────────────"
    echo
    echo "Notes:"
    echo "   • Values assume proper ICC profiling and correct media settings"
    echo "   • Avg = overall accuracy, 95% = typical worst case, Max = outliers"
    echo "   • Lower ΔE = higher color accuracy"
    echo "   • ΔE < 1.0 is generally considered visually indistinguishable"
    echo "   • Source of these numbers: https://ChatGPT.com"
    echo
}

improving_accuracy() {
    echo
    echo
    echo
    echo "────────────────────────────────────────────────────────────────"
    echo "Tips on how to improve accuracy of a profile"
    echo "────────────────────────────────────────────────────────────────"
    echo
    echo "  1. The top-most lines in the file '*_sanity_check.txt, created'"
    echo "     after a profile is made, are the patches with higest ΔE values."
    echo
    echo "  2. If ΔE values are too large it is recommended to remeasure."
    echo "      - ΔE > 2 is regarded as clearly visible difference and"
    echo "         should be remeasured (depending on printer type, see"
    echo "         Quick Reference table below or menu option 8)."
    echo "      - ΔE < 1 is considered visually indistinguishable."
    echo
    echo "  3. The 'Largest ΔE' or 'max.' value is an indicator that some"
    echo "     patches should be remeasured."
    echo
    echo "  4. When wanting to remeasure patches to improve overall profile"
    echo "     quality, do the following: "
    echo "      a. Open file '*_sanity_check.txt' of a created printer"
    echo "         profile and identify which sheets have largest error."
    echo "         Look at patch ID and find column label on target chart."
    echo "      b. In main menu, chose option 3, then select the target used"
    echo "         for your profile by selecting"
    echo "         the .ti2 file (files and targets should be in the folder"
    echo "         where your .icc is stored)"
    echo "      c. Select option '1. Create new profile (copy files into"
    echo "         new folder)'. Do not overwrite."
    echo "      d. Start reading only those strips where high error has been"
    echo "         identified. "
    echo "         Press 'f' to move forward, or 'b' to move back one strip"
    echo "         at a time while reading."
    echo "      e. When you have read the appropriate target strips, select"
    echo "         ‘d’ to save and exit."
    echo "      f. Open the created .ti3 file, and also the original .ti3"
    echo "         for your profile to be improved."
    echo "         The new .ti3 file has data for read patches below the tag"
    echo "         'BEGIN_DATA', and contain only the lines you re-read."
    echo "      g. In the original .ti3 file, search for the patch IDs to"
    echo "         identify the lines to replace."
    echo "         Copy one data line at a time from the new .ti3 file, and"
    echo "         replace the line with same ID in the original .ti3 file."
    echo "         Then save file."
    echo "      h. Now choose option 4 in main menu. Select the updated .ti3"
    echo "         file. Now a new .icc profile and and sanity report is"
    echo "         created. Study results and see if the profile is improved."
    echo
    echo "────────────────────────────────────────────────────────────────"
    echo
}
sanity_check() {
    echo
    echo 'Performing sanity check (creating .txt file)...'
    echo
    echo "Command Used: profcheck -v -k -s" 2>&1 > "${name}_sanity_check.txt"
    profcheck -v2 -k -s "${name}.ti3" "${name}.icc" 2>&1 >> "${name}_sanity_check.txt" || {
        echo
        echo "❌ profcheck failed."
        echo
        return 1
    }
    # Append to sanity check file
    {
        echo
        echo
    } >> "${name}_sanity_check.txt"

    # Extract delta E values from lines starting with "["
    local -a delta_e_values=()
    local largest smallest range total_patches index array_length
    local pos_99 pos_98 pos_95 pos_90
    local percentile_99 percentile_98 percentile_95 percentile_90
    local count_lt_1 count_lt_2 count_lt_3
    local percent_lt_1 percent_lt_2 percent_lt_3

    while IFS= read -r line; do
        # match lines that start with [decimal] followed by space and @
        if [[ "$line" =~ ^\[([0-9]+\.[0-9]+)\].*@ ]]; then
            delta_e_values+=("${BASH_REMATCH[1]}")
        fi
    done < "${name}_sanity_check.txt"

    if [ ${#delta_e_values[@]} -eq 0 ]; then
        echo "⚠️ No delta E values found in sanity check file"
        return 1
    fi

    # DEBUG!!: show first few values
    #echo "Found ${#delta_e_values[@]} delta E values"
    #echo "First few values: ${delta_e_values[@]:0:5}"

    # Since profcheck -s already sorts from highest to lowest:
    # First element is largest, last element is smallest
    largest="${delta_e_values[0]}"

    # Get last element safely
    last_index=$((${#delta_e_values[@]} - 1))
    smallest="${delta_e_values[$last_index]}"

    # Calculate range using awk (more reliable than bc)
    range=$(awk "BEGIN {printf \"%.6f\", $largest - $smallest}")

    # Calculate percentiles based on position in sorted array
    total_patches=${#delta_e_values[@]}

    # Calculate positions (round up to nearest integer)
    pos_99=$(awk "BEGIN {printf \"%.0f\", $total_patches * 0.99}")
    pos_98=$(awk "BEGIN {printf \"%.0f\", $total_patches * 0.98}")
    pos_95=$(awk "BEGIN {printf \"%.0f\", $total_patches * 0.95}")
    pos_90=$(awk "BEGIN {printf \"%.0f\", $total_patches * 0.90}")

    # Get values at these positions from the end of array (since sorted highest to lowest)
    # 99th percentile should be near smallest values, so access from end
    array_length=${#delta_e_values[@]}

    index=$(( total_patches - pos_99 ))
    if (( index >= 0 && index < array_length )); then
        percentile_99="${delta_e_values[index]}"
    else
        percentile_99="N/A"
    fi
    index=$(( total_patches - pos_98 ))
    if (( index >= 0 && index < array_length )); then
        percentile_98="${delta_e_values[index]}"
    else
        percentile_98="N/A"
    fi
    index=$(( total_patches - pos_95 ))
    if (( index >= 0 && index < array_length )); then
        percentile_95="${delta_e_values[index]}"
    else
        percentile_95="N/A"
    fi
    index=$(( total_patches - pos_90 ))
    if (( index >= 0 && index < array_length )); then
        percentile_90="${delta_e_values[index]}"
    else
        percentile_90="N/A"
    fi

    # Count values below thresholds
    count_lt_1=0
    count_lt_2=0
    count_lt_3=0

    for value in "${delta_e_values[@]}"; do
        # Compare using awk for floating point comparison
        if (( $(awk "BEGIN {print ($value < 1.0)}") )); then
            ((count_lt_1++))
        fi
        if (( $(awk "BEGIN {print ($value < 2.0)}") )); then
            ((count_lt_2++))
        fi
        if (( $(awk "BEGIN {print ($value < 3.0)}") )); then
            ((count_lt_3++))
        fi
    done

    # Calculate percentages
    percent_lt_1=$(awk "BEGIN {printf \"%.1f\", ($count_lt_1 / $total_patches) * 100}")
    percent_lt_2=$(awk "BEGIN {printf \"%.1f\", ($count_lt_2 / $total_patches) * 100}")
    percent_lt_3=$(awk "BEGIN {printf \"%.1f\", ($count_lt_3 / $total_patches) * 100}")

    # Display results
    echo
    echo "Delta E Range Analysis:"
    echo "  Largest ΔE:  $largest"
    echo "  Smallest ΔE: $smallest"
    echo
    echo "Percentile Values:"
    echo "  99th percentile: $percentile_99"
    echo "  98th percentile: $percentile_98"
    echo "  95th percentile: $percentile_95"
    echo "  90th percentile: $percentile_90"
    echo
    echo "Patch Count Analysis:"
    echo "  Percent of patches with ΔE<1.0: ${percent_lt_1}%"
    echo "  Percent of patches with ΔE<2.0: ${percent_lt_2}%"
    echo "  Percent of patches with ΔE<3.0: ${percent_lt_3}%"
    echo

    # Append results to sanity check file
    {
        echo
        echo "=== Delta E Range Analysis ==="
        echo "Largest ΔE: $largest"
        echo "Smallest ΔE: $smallest"
        echo
        echo "Percentile Values:"
        echo "99th percentile: $percentile_99"
        echo "98th percentile: $percentile_98"
        echo "95th percentile: $percentile_95"
        echo "90th percentile: $percentile_90"
        echo
        echo "Patch Count Analysis:"
        echo "Percent of patches with ΔE<1.0: ${percent_lt_1}%"
        echo "Percent of patches with ΔE<2.0: ${percent_lt_2}%"
        echo "Percent of patches with ΔE<3.0: ${percent_lt_3}%"
        echo "================================"
        echo
    } >> "${name}_sanity_check.txt"

    profcheck -v -k "${name}.ti3" "${name}.icc" || {
        echo
        echo "❌ profcheck failed."
        echo
        return 1
    }
    profcheck -v -k "${name}.ti3" "${name}.icc" 2>&1 >> "${name}_sanity_check.txt" || {
        echo
        echo "❌ profcheck failed."
        echo
        return 1
    }

    echo
    echo "Sanity Check Complete"
    echo "Detailed sanity check stored in:"
    echo "'${name}_sanity_check.txt'."
    echo
    while true; do
        echo
        echo
        echo "─────────────────────────────────────────────────────────────────────────"
        echo "What would you like to do?"
        echo "─────────────────────────────────────────────────────────────────────────"
        echo
        echo "1) Show tips on how to improve accuracy of a profile"
        echo "2) Show ΔE2000 Color Accuracy — Quick Reference"
        echo "3) Return to main menu"
        echo
        echo "─────────────────────────────────────────────────────────────────────────"
        echo
        read -r -n 1 -p 'Enter your choice [1-3]: ' choice
        echo
        
        case "$choice" in
            1)
                echo
                improving_accuracy
                echo
                read -p 'Press enter to continue...'
                ;;
            2)
                echo
                show_de_reference
                echo
                read -p 'Press enter to continue...'
                ;;
            3)
                echo
                echo "Returning to main menu..."
                break
                ;;
            *)
                echo
                echo "❌ Invalid choice. Please enter 1, 2, or 3."
                ;;
        esac
    done
}

# Helper for stat command differences (Linux vs macOS)
file_mtime() {
  if stat -f "%m" "$1" >/dev/null 2>&1; then
    stat -f "%m" "$1"
  else
    stat -c "%Y" "$1"
  fi
}

common_text_tips() {
    echo "Tips:"
    echo "     - Default for reading targets using ArgyllCMS is to start from"
    echo "       column A, from the side where the column letters are, and then"
    echo "       read to the end of the other side of the page."
    echo "       If not done this way, 'unexpected high deviation' message may"
    echo "       appear frequently."
    echo "     - Enabling bi-directional strip reading (removing -B flag and"
    echo "       adding -b) may cause false indentification of strips when read,"
    echo "       thus it is recommended to not enable this feature for beginners."
    echo "     - Scanning speed of more than 7 sec per strip reduces frequent"
    echo "       re-reading due to inconsistent results, and increases quality."
    echo "     - If frequent inconsistent results try altering patch consistency"
    echo "       tolerance parameter in setup (or .ini file)."
    echo "     - Save progress once in a while with 'd' and then"
    echo "       resume measuring with option 2 of main menu."
}


perform_measurement_and_profile_creation() {
    # --- Build chartread arguments conditionally ---------------------------
    # For chartread, if any variable for each argument is empty, then remove argument in command (empty parameter)
    chartread_T=''        # patch strip consistency
    if [ -n "$STRIP_PATCH_CONSISTENSY_TOLERANCE" ]; then
        chartread_T=" -T${STRIP_PATCH_CONSISTENSY_TOLERANCE}"
    fi

    echo
    echo
    echo 'Please connect the spectrophotometer.'
    echo
    while true; do
        read -r -n 1 -p 'Continue? [y/n]: ' again
        echo
        case "$again" in
        [yY]|[yY][eE][sS])
            echo
            echo "Starting chart reading (read .ti2 file and generate .ti3 file)..."
            break  # Exit loop
            ;;
        [nN]|[nN][oO])
            echo
            echo 'Aborting measuring of target...'
            return 1    # jumps out of loop and function immediately
            ;;
        *)
            echo
            echo 'Invalid input. Please enter y/yes or n/no.'
            ;;
        esac
    done
    echo
    echo
    echo

    local ti3_file="${name}.ti3"
    if [ "$action" = "2" ]; then    # re-read or resume partly read chart
        # Capture modification time state before chartread
        local ti3_mtime_before=""
        if [ -f "$ti3_file" ]; then
            ti3_mtime_before=$(file_mtime "$ti3_file")
        fi

        echo
        common_text_tips
        echo
        echo "Command Used: chartread ${COMMON_ARGUMENTS_CHARTREAD} -r${chartread_T} "${name}""
        chartread ${COMMON_ARGUMENTS_CHARTREAD} -r${chartread_T} "${name}" || {
            echo
            echo "❌ chartread failed."
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
        echo
        common_text_tips
        echo
        echo "Command Used: chartread ${COMMON_ARGUMENTS_CHARTREAD}${chartread_T} "${name}""
        chartread ${COMMON_ARGUMENTS_CHARTREAD}${chartread_T} "${name}" || {
            echo
            echo "❌ chartread failed."
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
    if [ -n "$PRINTER_ICC_PATH" ] && [ -f "$PRINTER_ICC_PATH" ]; then
       colprof_S+=("-S" "$PRINTER_ICC_PATH")
    else
       echo "⚠️ Warning: Printer ICC profile not found: '$PRINTER_ICC_PATH'"
       echo "   Skipping printer ICC profile in colprof."
    fi
    colprof_l=''        # ink limit
    if [ -n "$INK_LIMIT" ]; then
        colprof_l=" -l${INK_LIMIT}"
    fi
    colprof_r=''        # Average deviation / smooting
    if [ -n "$PROFILE_SMOOTING" ]; then
        colprof_r=" -r${PROFILE_SMOOTING}"
    fi

    echo
    read -r -n 1 -p 'Do you want to continue creating profile with resulting ti3 file? [y/n]: ' continue
    echo
    case "$continue" in
    [yY]|[yY][eE][sS])
        echo
        echo
        echo "Starting profile creation (read .ti3 file and generate .icc file)..."
        echo "Command Used: colprof ${COMMON_ARGUMENTS_COLPROF}${colprof_l}${colprof_r} "${colprof_S[@]}" -D "${desc}" "${name}""
        colprof ${COMMON_ARGUMENTS_COLPROF}${colprof_l}${colprof_r} "${colprof_S[@]}" -D "${desc}" "${name}" || {
            echo
            echo "❌ colprof failed."
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
    if [ -n "$PRINTER_ICC_PATH" ] && [ -f "$PRINTER_ICC_PATH" ]; then
       colprof_S+=("-S" "$PRINTER_ICC_PATH")
    else
       echo "⚠️ Warning: Printer ICC profile not found: '$PRINTER_ICC_PATH'"
       echo "   Skipping printer ICC profile in colprof."
    fi
    colprof_l=''        # ink limit
    if [ -n "$INK_LIMIT" ]; then
        colprof_l=" -l${INK_LIMIT}"
    fi
    colprof_r=''        # Average deviation / smooting
    if [ -n "$PROFILE_SMOOTING" ]; then
        colprof_r=" -r${PROFILE_SMOOTING}"
    fi

    echo
    echo
    echo "Starting profile creation (read .ti3 file and generate .icc file)..."
    echo "Command Used: colprof ${COMMON_ARGUMENTS_COLPROF}${colprof_l}${colprof_r} "${colprof_S[@]}" -D "${desc}" "${name}""
    colprof ${COMMON_ARGUMENTS_COLPROF}${colprof_l}${colprof_r} "${colprof_S[@]}" -D "${desc}" "${name}" || {
        echo
        echo "❌ colprof failed."
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

    # Verify source ICC exists
    if [ ! -f "${name}.icc" ]; then
        echo
        echo "❌ ICC profile not found: '${name}.icc'"
        echo "   Expected it in the current working directory:"
        echo "   $(pwd)"
        echo
        return 1
    fi

    # Verify destination exists
    if [ -z "${PRINTER_PROFILES_PATH:-}" ]; then
        echo
        echo "❌ PRINTER_PROFILES_PATH is empty. Check setup file."
        echo
        return 1
    fi

    if [ ! -d "${PRINTER_PROFILES_PATH}" ]; then
        echo
        echo "❌ Destination directory does not exist: '${PRINTER_PROFILES_PATH}'"
        echo "   Check PRINTER_PROFILES_PATH in the setup file."
        echo
        return 1
    fi

    # Verify destination is writable
    if [ ! -w "${PRINTER_PROFILES_PATH}" ]; then
        echo
        echo "❌ Destination directory is not writable: '${PRINTER_PROFILES_PATH}'"
        echo "   Check folder permissions or choose a user-writable profile folder."
        echo
        if [[ "$PLATFORM" == "linux" ]]; then
            if [[ "${PRINTER_PROFILES_PATH}" == /usr/share/* || "${PRINTER_PROFILES_PATH}" == /usr/local/share/* ]]; then
                echo "   This is a system folder and typically requires administrator rights."
                echo "   Options:"
                echo "     1) Change PRINTER_PROFILES_PATH to a user folder (recommended)"
                echo "        e.g. '$HOME/.local/share/color/icc' (create if missing)"
                echo "     2) Or install to the system folder using sudo (advanced)"
                echo "        e.g. sudo cp '${name}.icc' '${PRINTER_PROFILES_PATH}/'"
            fi
            echo
            echo "   Current permissions:"
            ls -ld "${PRINTER_PROFILES_PATH}" 2>/dev/null || true
        else
            echo "   Suggested macOS user profile folder:"
            echo "     '$HOME/Library/ColorSync/Profiles'"
        fi
        echo
        return 1
    fi

    cp "${name}.icc" "${PRINTER_PROFILES_PATH}" || {
        echo
        echo "❌ Failed to copy ICC profile to '${PRINTER_PROFILES_PATH}'."
        echo "   Check folder permissions or disk access."
        echo
        return 1
    }

    echo "Finished. '${name}.icc' was installed to the directory '${PRINTER_PROFILES_PATH}'"
    echo "Please restart any color-managed applications before using this profile."
    echo "To print with this profile in a color-managed workflow, select "'${desc}'" in the profile selection menu."
}

edit_setup_parameters() {
    source "$setup_file"
    validate_cfg_paths
    while true; do
        icc_filename="${PRINTER_ICC_PATH##*/}"
        precon_icc_filename="${PRECONDITIONING_PROFILE_PATH##*/}"

        echo
        echo
        echo
        echo "─────────────────────────────────────────────────────────────────────"
        echo "Change Setup Parameters - Sub-Menu "
        echo "─────────────────────────────────────────────────────────────────────"
        echo
        echo "In this menu some variables stored in the $setup_file file "
        echo "can be modified. For other parameters modify the file in a text editor."
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
        echo "5: Modify ink limit (targen and colprof -l). Valid values: 0 – 400 (%) or empty to disable."
        echo "   Current value specified: '${INK_LIMIT}'"
        echo
        echo "6: Modify file naming convention example (shown in main menu option 1). Valid value: text."
        echo "   Current value specified:"
        echo "   '${EXAMPLE_FILE_NAMING}'"
        echo
        echo "7: Go back to main menu."
        echo
        echo "─────────────────────────────────────────────────────────────────────"
        echo

        read -r -n 1 -p "Enter your choice [1–7]: " answer
        echo

        case $answer in
            1)
                if select_file "icc" "Select a new profile (.icc or .icm)" "icc"; then
                    set_icc_profile_parameter || {
                        echo "Returning to setup menu..."
                    }
                    source "$setup_file"
                else
                    echo "Returning to setup menu..."
                fi
                continue
                ;;

            2)
                if select_file "icc" "Select a new pre-conditioning profile (.icc or .icm)" "icc"; then
                    set_precond_profile_parameter || {
                        echo "Returning to setup menu..."
                    }
                    source "$setup_file"
                else
                    echo "Returning to setup menu..."
                fi
                continue
                ;;

            3)
                echo
                read -r -p "Enter new value [0.6 recommended]: " value

                if [[ ! "$value" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
                    echo "❌ Invalid numeric value."
                    continue
                fi

                sed_inplace "s|^STRIP_PATCH_CONSISTENSY_TOLERANCE=.*|STRIP_PATCH_CONSISTENSY_TOLERANCE='${value}'|" "$setup_file"

                echo "✅ Updated STRIP_PATCH_CONSISTENSY_TOLERANCE to $value"
                source "$setup_file"
                echo
                continue
                ;;

            4)
                echo
                read -r -p "Enter paper size [A4 or Letter]: " value
                echo

                case "$value" in
                    A4|Letter)
                        sed_inplace "s|^PAPER_SIZE=.*|PAPER_SIZE='${value}'|" "$setup_file"
                        echo "✅ Updated PAPER_SIZE to $value"
                        source "$setup_file"
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
                read -r -p "Enter ink limit (0–400 or empty to disable): " value

                if [[ "$value" != "" ]] && ([[ ! "$value" =~ ^[0-9]+$ ]] || (( value < 0 || value > 400 ))); then
                    echo "❌ Invalid ink limit."
                    continue
                fi

                sed_inplace "s|^INK_LIMIT=.*|INK_LIMIT='${value}'|" "$setup_file"

                echo "✅ Updated INK_LIMIT to '${value}'"
                source "$setup_file"
                echo
                continue
                ;;

            6)
                while true; do
                    echo
                    echo
                    echo
                    echo "─────────────────────────────────────────────────────────────────────"
                    echo "Specify Profile Description / File Name"
                    echo "─────────────────────────────────────────────────────────────────────"
                    echo
                    echo 'The following is highly recommended to include:'
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
                    echo 'Valid values: '
                    echo 'Letters A–Z a–z, digits 0–9, dash -, underscore _, parentheses (), dot .'
                    echo
                    echo "─────────────────────────────────────────────────────────────────────"
                    echo
                    read -e -p "Enter example file naming convention: " value
                    echo

                    if [[ ! "$value" =~ ^[A-Za-z0-9._()\-]+$ ]]; then
                        echo "❌ Invalid file name characters. Please try again."
                        continue
                    fi

                    # Valid input → exit loop
                    break
                done

                sed_inplace "s|^EXAMPLE_FILE_NAMING=.*|EXAMPLE_FILE_NAMING='${value}'|" "$setup_file"

                echo
                echo "✅ Updated file naming convention example to:"
                echo "$value"
                echo
                source "$setup_file"
                continue
                ;;

            7)
                echo
                echo "Returning to main menu..."
                return 0
                ;;

            *)
                echo
                echo "No valid selection made. Reloading setup menu..."
                continue
                ;;
        esac
    done
    echo
}

validate_cfg_paths() {
    # Validate paths in cfg for existence and validity, logging warnings if issues.

    # PRINTER_PROFILES_PATH: should be a directory
    if [ -n "${PRINTER_PROFILES_PATH:-}" ]; then
        if [ ! -d "$PRINTER_PROFILES_PATH" ]; then
            echo "⚠️ Warning: PRINTER_PROFILES_PATH directory does not exist: '$PRINTER_PROFILES_PATH'"
        fi
    else
        echo "⚠️ Warning: PRINTER_PROFILES_PATH is not specified in setup file."
    fi

    # PRECONDITIONING_PROFILE_PATH: should be a file
    if [ -n "${PRECONDITIONING_PROFILE_PATH:-}" ]; then
        if [ ! -f "$PRECONDITIONING_PROFILE_PATH" ]; then
            echo "⚠️ Warning: PRECONDITIONING_PROFILE_PATH file does not exist: '$PRECONDITIONING_PROFILE_PATH'"
        fi
    # else
        # Do nothing: accepted that path is empty
    fi

    # PRINTER_ICC_PATH: should be a file
    if [ -n "${PRINTER_ICC_PATH:-}" ]; then
        if [ ! -f "$PRINTER_ICC_PATH" ]; then
            echo "⚠️ Warning: PRINTER_ICC_PATH file does not exist: '$PRINTER_ICC_PATH'"
        fi
    else
        echo "⚠️ Warning: PRINTER_ICC_PATH is not specified in setup file."
    fi

    # Check required non-path variables
    required_vars=("STRIP_PATCH_CONSISTENSY_TOLERANCE" "COLOR_SYNC_UTILITY_PATH" "PROFILE_SMOOTING" "TARGET_RESOLUTION")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var:-}" ]; then
            echo "⚠️ Warning: Variable $var not set. Check setup file."
        fi
    done
}


# --- Main --------------------------------------------------
main_menu() {
    while true; do
        # --- Load setup file -------------------------------------------------
        setup_file="${script_dir}/Argyll_Printer_Profiler_setup.ini"
        # Load variables
        source "$setup_file"
        validate_cfg_paths
        # Clear global variables
        source_folder=""
        dialog_title=""
        name=""
        desc=""
        action=""
        profile_folder=""
        new_name=""
        ti3_mtime_before=""
        ti3_mtime_after=""

        echo
        echo
        echo
        echo "─────────────────────────────────────────────────────────────────────────"
        echo "Printer Profiling — Main Menu"
        echo "─────────────────────────────────────────────────────────────────────────"
        echo 'General Notes: '
        echo '   1. Existing ti1/ti2/ti3/icc and target image (.tif) filenames must match.'
        echo '   2. If more than one target image, filenames must end with _01, _02, etc.'
        echo
        echo
        echo 'What action do you want to perform?'
        echo
        echo '1: Create target chart and printer profile from scratch'
        echo '    └─ Specify name → Generate targets → Measure target patches'
        echo '       → Create profile → Sanity check → Copy to profile folder'
        echo '       (Cancel after generating targets if only target chart is needed)'
        echo
        echo '2: Resume or re-read an existing target chart measurement and create profile'
        echo '    └─ Specify .ti3 file → Measure target patches'
        echo '       → Create profile → Sanity check → Copy to profile folder'
        echo
        echo '3: Read an existing target chart from scratch and create profile'
        echo '    └─ Specify .ti2 file → Measure target patches'
        echo '       → Create profile → Sanity check → Copy to profile folder'
        echo
        echo '4: Create printer profile from an existing measurement file'
        echo '    └─ Specify .ti3 file → Create profile → Sanity check'
        echo '       → Copy to profile folder'
        echo
        echo '5: Perform sanity check on existing profile'
        echo '    └─ Specify .ti3 file → Check profile against test chart data'
        echo '       → Create report'
        echo
        echo '6: Change setup parameters'
        echo
        echo '7: Show tips on how to improve accuracy of a profile'
        echo
        echo '8: Show ΔE2000 Color Accuracy — Quick Reference'
        echo
        echo '9: Exit script'
        echo "─────────────────────────────────────────────────────────────────────────"
        echo
        read -r -n 1 -p 'Enter your choice [1–9]: ' answer
        echo

        case $answer in
          1)
            action='1'
            # Call functions
            echo
            echo
            specify_profile_name || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
                continue   # <-- go back to menu
            }
            select_instrument || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
                continue   # <-- go back to menu
            }
            specify_and_generate_target || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
                continue   # <-- go back to menu
            }
            perform_measurement_and_profile_creation || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
                continue   # <-- go back to menu
            }
            install_profile_and_save_data || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
                continue   # <-- go back to menu
            }
            continue   # <-- go back to menu
            ;;
          2)
            action='2'
            # Call functions
            dialog_title="Select an existing .ti3 file to re-read/resume measuring target patches."
            echo
            echo
            echo "$dialog_title"
            echo
            select_file "ti3" "$dialog_title" "ti3" || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
                continue   # <-- go back to menu
            }
            perform_measurement_and_profile_creation || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
                continue   # <-- go back to menu
            }
            install_profile_and_save_data || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
                continue   # <-- go back to menu
            }
            continue   # <-- go back to menu
            ;;
          3)
            action='3'
            # Call functions
            dialog_title="Select an existing .ti2 file to measure target patches."
            echo
            echo
            echo "$dialog_title"
            echo
            select_file "ti2" "$dialog_title" "ti2" || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
                continue   # <-- go back to menu
            }
            perform_measurement_and_profile_creation || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
                continue   # <-- go back to menu
            }
            install_profile_and_save_data || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
                continue   # <-- go back to menu
            }
            continue   # <-- go back to menu
            ;;
          4)
            action='4'
            # Call functions
            dialog_title="Select an existing completed .ti3 file to create .icc profile with."
            echo
            echo
            echo "$dialog_title"
            echo
            select_file "ti3" "$dialog_title" "ti3_only" || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
                continue   # <-- go back to menu
            }
            create_profile_from_existing || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
                continue   # <-- go back to menu
            }
            install_profile_and_save_data || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
                continue   # <-- go back to menu
            }
            continue   # <-- go back to menu
            ;;
          5)
            action='5'
            # Call functions

            dialog_title="Select an existing .ti3 file that has a matching .icc profile."
            echo
            echo
            echo "$dialog_title"
            echo
            select_file "ti3" "$dialog_title" "ti3_only" || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
                continue   # <-- go back to menu
            }
            sanity_check || {
                echo 'Operation aborted.'
                echo
                read -p 'Press enter to return to main menu...'
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
            improving_accuracy
            read -p 'Press enter to return to main menu...'
            continue   # <-- go back to menu
            ;;
          8)
            action='8'
            show_de_reference
            read -p 'Press enter to return to main menu...'
            continue   # <-- go back to menu
            ;;
          9)
            action='9'
            echo
            echo 'Exiting script...'
            
            # Restore stdout/stderr before exit (with error handling)
            if ! exec >/dev/tty 2>&1 2>/dev/null; then
                echo '⚠️ Could not restore terminal output'
            fi
            
            # Exit cleanly
            exit 0
            ;;
          *)
            action='0'
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

