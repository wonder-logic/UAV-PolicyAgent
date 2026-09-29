#!/bin/bash
# Closes all teminals when running either master_launch or test_launch
echo "Shutting down drone simulation..."

tmux kill-session -t drone_sim 2>/dev/null

pkill -9 -f xterm
pkill -9 -f wish
pkill -9 -f sim_vehicle.py
pkill -9 -f mavproxy.py
pkill -9 -f arducopter

pkill -9 -f "gz sim"
pkill -9 -f ruby
pkill -9 -f gz-sim

#pkill -9 -f QGroundControl-x86_64.AppImage
#pkill -9 -f qgroundcontrol

pkill -9 -f fly.py
pkill -9 -f visualize_zones.py

pkill -9 -f 1_gazebo.sh
pkill -9 -f 2_ardupilot.sh
pkill -9 -f 3_qgc.sh
pkill -9 -f 4_zones.sh
pkill -9 -f 5_fly.sh

echo "Closed all simulation components"
