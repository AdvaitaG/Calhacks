#!/bin/bash
# Finish building the Booster SDK Python binding on the Ubuntu 22.04 distro.
# Run with one short command:
#     bash scripts/build_sdk_22.sh
#
# Installs into SYSTEM python3 (via `sudo make install`), so the smoke test runs
# with plain `python3` — no venv, no band-sdk, no requirements.txt needed.
# Prereq: `sudo ./install.sh` in the SDK repo already ran (C++ libs installed).
set -e

SDK="$HOME/booster_robotics_sdk"
export PATH="$HOME/.local/bin:$PATH"   # so pybind11-stubgen is found

if [ ! -d "$SDK" ]; then
    echo "ERROR: $SDK not found. Clone + run sudo ./install.sh first."
    exit 1
fi

# Use the SYSTEM pybind11 (apt, 2.9.x): headers land in /usr/include (on the
# compiler's default path) and its CMake config wires the legacy variables this
# SDK relies on. The pip pybind11 3.x puts headers off-path and dropped those
# vars -> "pybind11/pybind11.h: No such file or directory". Remove the pip one.
sudo apt-get install -y pybind11-dev
python3 -m pip uninstall -y pybind11 >/dev/null 2>&1 || true
python3 -m pip install --user pybind11-stubgen >/dev/null 2>&1 || true

echo "[build] clearing any stale (root-owned) build dir ..."
sudo rm -rf "$SDK/build"          # earlier `sudo make install` left root-owned files

echo "[build] configuring (pointing CMake at pybind11) ..."
mkdir -p "$SDK/build"
cd "$SDK/build"
cmake "$SDK" -DBUILD_PYTHON_BINDING=on

echo "[build] compiling ..."
make -j"$(nproc)"

echo "[build] installing (needs sudo) ..."
sudo make install

echo "[build] verifying import ..."
cd "$HOME"
python3 -c "import booster_robotics_sdk_python; print('SDK ok')"
