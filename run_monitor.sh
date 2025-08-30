#!/bin/bash

# --- The Bulletproof Monitor Execution Script ---

# Immediately exit if any command fails
set -e

# Define a minimal, reliable PATH for the cron environment
# This tells the script exactly where to find basic system commands
export PATH="/usr/bin:/bin:/usr/sbin:/sbin"

# Get the absolute directory where this script is located
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# Navigate to the script's directory (your project root)
cd "$SCRIPT_DIR"

# Define absolute paths for all executables and files
PYTHON_EXEC="$SCRIPT_DIR/venv/bin/python"
MONITOR_SCRIPT="$SCRIPT_DIR/src/monitor.py"
LOG_FILE="$SCRIPT_DIR/cron.log"
DATE_EXEC="/bin/date" # Absolute path to the date command

# --- Execution ---
# We now manually append to the log file using robust commands
echo "--- Cron job started: $($DATE_EXEC) ---" >> "$LOG_FILE"

# Run the Python script and append its output (stdout and stderr) to the log file
"$PYTHON_EXEC" "$MONITOR_SCRIPT" >> "$LOG_FILE" 2>&1

echo "--- Cron job finished: $($DATE_EXEC) ---" >> "$LOG_FILE"