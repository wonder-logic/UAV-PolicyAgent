#!/bin/bash
# Launches all 5 terminals
SESSION="drone_sim"
MAIN_DIR=$(pwd)
SCRIPTS_DIR="$MAIN_DIR/SCRIPTS"

tmux kill-session -t $SESSION 2>/dev/null

echo "Launching Simulation Stack from $SCRIPTS_DIR..."

tmux new-session -d -s $SESSION -n "Gazebo"
tmux send-keys -t $SESSION:"Gazebo" "cd $MAIN_DIR && $SCRIPTS_DIR/1_gazebo.sh" C-m
echo "Gazebo initializing..."
sleep 15

tmux new-window -t $SESSION -n "ArduPilot"
tmux send-keys -t $SESSION:"ArduPilot" "cd $MAIN_DIR && $SCRIPTS_DIR/2_ardupilot.sh" C-m
echo "SITL initializing..."
sleep 30

#tmux new-window -t $SESSION -n "QGC"
#tmux send-keys -t $SESSION:"QGC" "cd $MAIN_DIR && $SCRIPTS_DIR/3_qgc.sh" C-m
#sleep 2

tmux new-window -t $SESSION -n "Zones"
tmux send-keys -t $SESSION:"Zones" "cd $MAIN_DIR && $SCRIPTS_DIR/4_zones.sh" C-m
sleep 10

tmux new-window -t $SESSION -n "Fly"
tmux send-keys -t $SESSION:"Fly" "cd $MAIN_DIR && $SCRIPTS_DIR/5_fly.sh" C-m

#tmux attach-session -t $SESSION
