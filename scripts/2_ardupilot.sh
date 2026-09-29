#!/bin/bash
MAIN_DIR=$(pwd)

# Take coordinates out of data.py
COORDS=$(python3 -c "import sys; sys.path.append('$MAIN_DIR'); import data; print(f'{data.start_lat},{data.start_long},0,0')" 2>/dev/null)

if [ -z "$COORDS" ]; then
    echo "Default coordinates (TAMUCC NRC grass area) used"
    COORDS="27.714913,-97.328388,0,0"
fi

cd ~/ardupilot/ArduCopter
#-f gazebo-iris --map --console
sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --custom-location=$COORDS --out=udp:127.0.0.1:14550 --out=udp:127.0.0.1:14551 --out=udp:127.0.0.1:14552
