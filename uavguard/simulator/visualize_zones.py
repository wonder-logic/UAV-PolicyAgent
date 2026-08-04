'''visualize_zones.py'''
'''uses grid_data.py, data.py'''
'''visualizes the grid'''

from grid_data import ZONE_SCALE, the_grid, GRID_START, GRID_END
from processing_data import start_zone

import matplotlib
#matplotlib.use('Agg') # makes headless
import matplotlib.patches as patches
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

import numpy as np
import math

import sys
import time

from pymavlink import mavutil

'''COMMENT LINES 19 - 34 OUT WHEN TESTING GRID ALONE''' '''
# connect to drone before drawing grid
print("Trying to connect on port 14551...")
try:
    mav_link = mavutil.mavlink_connection("udp:127.0.0.1:14551")
    print("Waiting for drone connection...")
    msg = mav_link.recv_match(type="HEARTBEAT", blocking=True, timeout=20)
    if msg is None:
        print("Did you forget to run 'output add 127.0.0.1:14551' in MAVProxy??")
        sys.exit(1)
    print("Connected!!")
except Exception as error:
    print("\nUH OH! Something serious happened")
    print(f"Error: {error}")
    sys.exit(1)'''

# no modifying my grid!!
matplotlib.rcParams['toolbar'] = 'None'

# basic stuff
fig, ax = plt.subplots(figsize=(7, 7))
ax.set_title("Drone Grid View", fontsize=14, fontweight="bold", pad=10)
fig.canvas.manager.set_window_title("Drone Grid View Window")
ax.set_xlabel("X Position (meters)", fontsize=11)
ax.set_ylabel("Y Position (meters)", fontsize=11)

# no modifying my grid!!
fig.canvas.widgetlock(ax)

left_lim = (GRID_START - 0.5) * ZONE_SCALE
right_lim = (GRID_END - 0.5) * ZONE_SCALE
#limits of graph
ax.set_xlim(left_lim, right_lim)
ax.set_ylim(left_lim, right_lim)
ax.set_aspect("equal", adjustable="box")

# draw gridlines
gridlines = np.arange(left_lim, right_lim+1, 1*ZONE_SCALE)
ax.set_xticks(gridlines, minor=True)
ax.set_yticks(gridlines, minor=True)

# draw ticks
ticks = np.arange(GRID_START*ZONE_SCALE, GRID_END*ZONE_SCALE, 1*ZONE_SCALE)
ax.set_xticks(ticks)
ax.set_yticks(ticks)

ax.tick_params(axis='x', rotation=45)

# make green and red zones
for (x,y), val in the_grid.items():
    if val == 1:
        zone_color = "green"
    else:
        zone_color = "red"

    corner_x = (x - 0.5) * ZONE_SCALE
    corner_y = (y - 0.5) * ZONE_SCALE

    rect = patches.Rectangle((corner_x, corner_y), ZONE_SCALE, ZONE_SCALE, 
                             facecolor=zone_color, 
                             alpha=0.4, #opacity
    )
    ax.add_patch(rect)

#drone stuff
drone_home_x = start_zone[0] * ZONE_SCALE
drone_home_y = start_zone[1] * ZONE_SCALE
(drone_dot,) = ax.plot(drone_home_x, drone_home_y, marker="o", color="blue")

#legend stuff
green_legend = patches.Patch(color="green", alpha=0.5, label="Green Zone")
red_legend = patches.Patch(color="red", alpha=0.5, label="Red Zone")
drone_legend = plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="blue",
                          markersize=8, label="Drone Position", alpha=0.5
)
ax.legend(handles=[green_legend, red_legend, drone_legend], loc="upper left")

plt.grid(False, which="major")
plt.grid(True, which="minor", color="black")

'''COMMENT LINES 99 - 120 OUT WHEN TESTING GRID ALONE''' 
#drone tracking
state_tracker = {"x": drone_home_x, "y": drone_home_y, "last_heartbeat_time": 0.0}

def update_drone_pos(_):
    current_time = time.time()
    message = mav_link.recv_match(blocking=False)

    while message is not None:
        if message.get_type() == "HEARTBEAT":
            state_tracker["last_heartbeat_time"] = current_time
        elif message.get_type() == "LOCAL_POSITION_NED":
            #MAVLink tracks using NED which is weird
            state_tracker["x"] = drone_home_x + message.y
            state_tracker["y"] = drone_home_y + message.x 

        message = mav_link.recv_match(blocking=False)

    drone_dot.set_data([state_tracker["x"]], [state_tracker["y"]])

ani = FuncAnimation(fig, update_drone_pos, blit=False, interval=100, cache_frame_data=False)

plt.tight_layout()
#plt.savefig("latest_grid_view.png") # makes headless
#plt.close(fig) # makes headless
plt.show() #uncomment to bring back visualization
