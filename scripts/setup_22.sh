#!/bin/bash
# One-shot environment setup for the Ubuntu 22.04 WSL distro.
# Run it with a single short command (no copy-paste of long lines):
#     bash /mnt/c/Users/mradi/OneDrive/Desktop/Calhacks/scripts/setup_22.sh
#
# Creates the Python venv in the LINUX filesystem (~/baymax-venv), NOT on the
# Windows mount — venvs on /mnt/c hit DrvFs symlink/copy bugs. Your code stays
# on /mnt/c; only the venv lives in ~. Idempotent: safe to re-run.
set -e

REPO=/mnt/c/Users/mradi/OneDrive/Desktop/Calhacks
VENV="$HOME/baymax-venv"

echo "[setup] removing any broken venvs ..."
rm -rf "$REPO/.venv-22" "$VENV"

echo "[setup] creating venv at $VENV (Linux filesystem) ..."
python3 -m venv "$VENV"

echo "[setup] installing requirements from $REPO/requirements.txt ..."
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install -r "$REPO/requirements.txt"

echo ""
echo "[setup] DONE. Activate the venv in your shell with:"
echo "    source ~/baymax-venv/bin/activate"
