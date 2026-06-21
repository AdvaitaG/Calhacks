#!/bin/bash
# Native (no-Docker) setup for the Booster T1 Webots sim with REAL presets.
# Downloads the public socrob release assets and unpacks them into ~/booster_sim
# on the Ubuntu 22.04 distro, installs the GL/X libs Webots needs, and grabs the
# FastDDS profile. Reuses the Booster SDK you already installed (SDK ok).
#
# Run once:
#     bash /mnt/c/Users/mradi/OneDrive/Desktop/Calhacks/scripts/setup_t1_sim.sh
#
# Big downloads (~1.3 GB); -C - resumes if interrupted, and existing files are
# skipped, so it's safe to re-run.
set -e

BASE=https://github.com/socrob/booster_webots_sim/releases/download/v1.0
DIR="$HOME/booster_sim"
mkdir -p "$DIR" && cd "$DIR"

echo "[t1] installing Webots GL/X runtime libs ..."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
  unzip libxext6 libxrender1 libxtst6 libxi6 libxrandr2 libxinerama1 \
  libxcursor1 libglvnd0 libgl1 libglx0 libegl1 libgles2 mesa-utils \
  libglu1-mesa libxkbcommon-x11-0 libxcb-xinerama0 libxcb-icccm4 \
  libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
  libxcb-shape0 libxcb-cursor0 libnss3 libasound2 \
  libfmt8 libspdlog1 libgoogle-glog0v5 liblua5.3-0 \
  libsdl2-2.0-0 >/dev/null  # control-runner deps

for f in worlds.zip sim_control.zip webots.zip; do
  if [ -f "$f.done" ]; then echo "[t1] $f already unpacked, skipping"; continue; fi
  echo "[t1] downloading $f ..."
  curl -L -C - -o "$f" "$BASE/$f"
  echo "[t1] unzipping $f ..."
  unzip -o -q "$f" && touch "$f.done" && rm -f "$f"
done

# The control runners come out of the zip without the execute bit.
chmod +x "$DIR"/sim_control/*.run 2>/dev/null || true

# Webots lives under ~/booster_sim/webots after unzip; expose it.
WEBOTS="$DIR/webots"
echo "[t1] fetching FastDDS profile ..."
curl -L -o "$DIR/fastdds_profile.xml" \
  https://raw.githubusercontent.com/socrob/booster_webots_sim/main/fastdds_profile.xml

# Write an env file you 'source' before running anything.
cat > "$DIR/env.sh" <<EOF
export WEBOTS_HOME=$WEBOTS
export LD_LIBRARY_PATH=\$LD_LIBRARY_PATH:\$WEBOTS_HOME/lib/controller
export PATH=\$WEBOTS_HOME:\$WEBOTS_HOME/bin:\$PATH
export FASTRTPS_DEFAULT_PROFILES_FILE=$DIR/fastdds_profile.xml
EOF

echo ""
echo "[t1] DONE. Contents:"
ls -1 "$DIR"
echo ""
echo "Next (each in its own terminal, after: source ~/booster_sim/env.sh):"
echo "  1) glxinfo | grep -i renderer      # confirm WSLg OpenGL works"
echo "  2) webots ~/booster_sim/worlds/T1_release.wbt"
echo "  3) ~/booster_sim/sim_control/booster-runner-webots-full-0.0.10.run"
echo "  4) ~/booster_robotics_sdk/build/b1_loco_example_client 127.0.0.1"
