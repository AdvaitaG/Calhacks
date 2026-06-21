#!/bin/bash
# Set up the LISTENER side of the full pipeline on the Ubuntu 22.04 distro:
# a Python 3.11 venv (band-sdk needs >=3.11) that can both talk to Band AND
# drive the robot via the SDK. Run once:
#     bash /mnt/c/Users/mradi/OneDrive/Desktop/Calhacks/scripts/setup_bridge_311.sh
#
# Why 3.11: band-sdk requires Python >=3.11, but the distro default is 3.10.
# deadsnakes provides 3.11 alongside it. The Booster C++ libs are already
# installed system-wide (install.sh earlier), so the SDK just recompiles its
# Python binding for 3.11 the same way it did for 3.10.
set -e

echo "[bridge311] installing Python 3.11 (deadsnakes) ..."
sudo apt-get update -qq
sudo apt-get install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update -qq
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev

VENV="$HOME/baymax-bridge"
echo "[bridge311] creating venv at $VENV ..."
rm -rf "$VENV"
python3.11 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip

echo "[bridge311] installing Band + LiveKit + dotenv ..."
"$VENV/bin/pip" install band-sdk python-dotenv livekit livekit-api

echo "[bridge311] swapping in a Python-3.11-compatible pybind11 (apt's 2.9.1 is too old) ..."
# Python 3.11 made PyFrameObject opaque; pybind11 must be >=2.10. Ubuntu jammy
# only packages 2.9.1, and the SDK build picks up /usr/include/pybind11. Install
# a modern pybind11 and place its headers on /usr/local/include (searched before
# /usr/include), and drop the apt one so it can't shadow it.
sudo apt-get remove -y pybind11-dev 2>/dev/null || true
"$VENV/bin/pip" install pybind11
PBINC=$("$VENV/bin/python" -c "import pybind11; print(pybind11.get_include())")
sudo rm -rf /usr/local/include/pybind11
sudo cp -r "$PBINC/pybind11" /usr/local/include/
echo "[bridge311]   pybind11 headers -> /usr/local/include/pybind11 (from $PBINC)"

echo "[bridge311] building the Booster SDK for Python 3.11 (recompiles binding) ..."
"$VENV/bin/pip" install booster_robotics_sdk_python

echo "[bridge311] verifying ..."
"$VENV/bin/python" -c "from band.platform.link import BandLink; import booster_robotics_sdk_python; print('bridge env OK')"
echo ""
echo "[bridge311] DONE. Run the listener with:"
echo "    cd /mnt/c/Users/mradi/OneDrive/Desktop/Calhacks/robot"
echo "    ~/baymax-bridge/bin/python command_bridge.py band real"
