
#!/bin/bash
export GZ_IP=127.0.0.1 
export GZ_PARTITION=$(hostname)
GZ_SIM_SYSTEM_PLUGIN_PATH=$HOME/ardupilot_gazebo/build \
GZ_SIM_RESOURCE_PATH=$HOME/ardupilot_gazebo/models:$HOME/ardupilot_gazebo/worlds \
gz sim -v4 -s -r ~/ardupilot_gazebo/worlds/iris_runway.sdf # -s makes it headless
