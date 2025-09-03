#!/bin/bash

# --- The Bulletproof Reporter Execution Script ---

# Immediately exit if any command fails
set -e

# Define a minimal, reliable PATH for the cron environment
export PATH="/usr/bin:/bin:/usr/sbin:/sbin"

# Get the absolute directory where this script is located
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# Navigate to the script's directory (your project root)
cd "$SCRIPT_DIR"

# Define absolute paths for all executables and files
PYTHON_EXEC="$SCRIPT_DIR/venv/bin/python"
REPORTER_SCRIPT="$SCRIPT_DIR/src/reporter.py"
LOG_FILE="$SCRIPT_DIR/reporter.log" # Using a separate log file
DATE_EXEC="/bin/date"

# --- Execution ---
echo "--- Reporter cron job started: $($DATE_EXEC) ---" >> "$LOG_FILE"

# Run the Python script and append its output to the log file
"$PYTHON_EXEC" "$REPORTER_SCRIPT" >> "$LOG_FILE" 2>&1

echo "--- Reporter cron job finished: $($DATE_EXEC) ---" >> "$LOG_FILE"