'''fly.py'''
'''uses grid_data.py, data.py and pathfinder.py'''

from grid_data import ZONE_SCALE, the_grid
from grid_data import start_lat, start_long, end_lat, end_long
from processing_data import exact_end_target, start_zone, end_zone
from pathfinder import find_shortest_path

import asyncio
import sys
import math
import json

from mavsdk import System
from mavsdk.offboard import OffboardError, PositionNedYaw

FLIGHT_RECORDS_FILE = "flight_records.txt"
DRONE_COORDS_FILE = "drone_coords.txt"
TARGET_ALTITUDE = 20

LOCATION_LOOKUP = {
    # Starting locations
    (27.714913, -97.328388): "Grass near NRC",
    (27.714109, -97.327416): "Seahorse parking lot",
    (27.713359, -97.324324): "Grass outside Bell Library",
    (27.716402, -97.328298): "Circular area outside HRI",
    (27.713548, -97.329299): "Central Receiving Parking Lot",
    (27.712363, -97.325987): "Outside UC",
    (27.710660, -97.322446): "Outside Dolphin Building",
    (27.709806, -97.323921): "Near Chapman Field",

    # Ending locations
    #(27.702977, -97.336979): "Outside my window at Momentum Village",
    (27.714521, -97.325567): "Angelfish Parking Lot",
    (27.712431, -97.327000): "Jellyfish Parking Lot",
    (27.710927, -97.325776): "Turtle Cove Parking Lot",
    (27.712358, -97.323117): "Curlew Parking Lot",
    (27.713148, -97.322307): "Seabreeze Parking Lot",
    (27.712794, -97.321336): "Tarpon Parking Lot",
    (27.713890, -97.321072): "Sanddollar Parking lot",
    (27.713033, -97.319548): "Hammerhead Parking Lot",
}

def get_location_name(lat, lon):
    key = (round(float(lat), 6), round(float(lon), 6))
    return LOCATION_LOOKUP.get(key, "Unknown Location")

#change direction of drone
def heading_from_delta(dx, dy):
    if dx == 0 and dy == 0:
        return 0.0
    return math.degrees(math.atan2(dx, dy))

async def wait_for_waypoint(drone, north_target, east_target, threshold):
    async for nav_data in drone.telemetry.position_velocity_ned():
        current_n = nav_data.position.north_m
        current_e = nav_data.position.east_m
        if math.hypot(north_target - current_n, east_target - current_e) <= threshold:
            return

async def run():
    with open('can_fly.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    #print(data)
    val = data["allowed_to_fly"]
    if val == 0:
        sys.exit("Not allowed to fly due to battery limitations!")

    # retrieve path first
    try:
        path = find_shortest_path(the_grid, start_zone, end_zone)
        if len(path) > 0:
            path.append(exact_end_target)
    except Exception as error:
        print("UH OH! Something went wrong")
        print(f"Reason: {error}")
        sys.exit(1)
    
    print(f"PATH IS: {path}\n")

    # connect to port
    drone = System()
    print("Connecting to drone on 127.0.0.1:14552")
    await drone.connect(system_address="udpin://127.0.0.1:14552")

    print("Waiting for global position estimate (GPS lock)...")
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("Global position estimates verified...")
            break
    
    # record health, battery and flight information to file
    with open(FLIGHT_RECORDS_FILE, "a") as f:
        f.write("----------------------------RUN START----------------------------\n")
        f.write(f"PATH IS: {path}\n")
        async for health in drone.telemetry.health():
            f.write(f"Health: GYRO ok={health.is_gyrometer_calibration_ok}, "
                    f"ACCEL ok={health.is_accelerometer_calibration_ok}, "
                    f"MAG ok={health.is_magnetometer_calibration_ok}\n")
            break
        async for battery in drone.telemetry.battery():
            f.write(f"Battery before run: {battery.remaining_percent}%, Voltage: {battery.voltage_v:.2f}V\n")
            break
        async for flight_mode in drone.telemetry.flight_mode():
            f.write(f"Initial Flight Mode: {flight_mode}\n")
            break
        
    print(f"Setting takeoff altitude to {TARGET_ALTITUDE} meters...")
    await drone.action.set_takeoff_altitude(TARGET_ALTITUDE)

    print("Arming...")
    await drone.action.arm()

    print("Taking off...")
    await drone.action.takeoff()

    #verify it reached the takeoff altitude
    print("Monitoring ascent...")
    async for position in drone.telemetry.position():
        current_alt = position.relative_altitude_m
        print(f"Current Altitude: {current_alt:.2f} m / Target: {TARGET_ALTITUDE} m")
        if (TARGET_ALTITUDE - 0.2) <= current_alt <= (TARGET_ALTITUDE + 0.5):
            print("Target takeoff altitude reached!")
            break
    
    #save live starting coords
    async for pos in drone.telemetry.position():
        start_lat_live = pos.latitude_deg
        start_lon_live = pos.longitude_deg
        break

    await asyncio.sleep(2) 

    await drone.offboard.set_position_ned(PositionNedYaw(0.0, 0.0, -TARGET_ALTITUDE, 0.0))

    # start offboard mode
    try:
        await drone.offboard.start()
        print("Offboard mode activated successfully.")
    except OffboardError as error:
        print(f"Offboard failed to start: {error}")
        return

    # travel to each point in path
    current_pos = start_zone 
    for index, coord in enumerate(path):
        x,y = coord
        east_target = float(x*ZONE_SCALE)
        north_target = float(y*ZONE_SCALE)

        delta_east = x - current_pos[0]
        delta_north = y - current_pos[1]

        yaw_deg = heading_from_delta(delta_east, delta_north)
        #yaw_deg = 0.0
        print(f"Flying to {coord} -> (North: {north_target}m, East: {east_target}m)")

        await drone.offboard.set_position_ned(PositionNedYaw(north_target, east_target, -TARGET_ALTITUDE, yaw_deg))
        if index == len(path) - 1:
            await wait_for_waypoint(drone, north_target, east_target, threshold=0.01*ZONE_SCALE)
        else:
            await wait_for_waypoint(drone, north_target, east_target, threshold=0.25*ZONE_SCALE)

        current_pos = coord

    # stop offboard mode
    print("Stopping offboard mode...")
    try:
        await drone.offboard.stop()
    except OffboardError as error:
        print(f"Failed to stop offboard mode cleanly: {error}")        

    print("Landing...")
    await drone.action.land()

    print("Waiting for touchdown...")
    async for position in drone.telemetry.position():
        if position.relative_altitude_m < 0.3:
            print("Drone has landed safely.")
            break   

    # record battery after flight
    with open(FLIGHT_RECORDS_FILE, "a") as f:
        async for battery in drone.telemetry.battery():
            f.write(f"Battery after run: {battery.remaining_percent}%, Voltage: {battery.voltage_v:.2f}V\n")
            break
        f.write("----------------------------RUN END----------------------------\n\n")

    print(f"!!!Stuff saved to {FLIGHT_RECORDS_FILE}!!!")
        
    # save live ending coords
    async for pos in drone.telemetry.position():
        end_lat_live = pos.latitude_deg
        end_lon_live = pos.longitude_deg
        break

    start_location_name = get_location_name(start_lat, start_long)
    end_location_name = get_location_name(end_lat, end_long)

    with open(DRONE_COORDS_FILE, "a") as f:
        f.write("----------------------------START----------------------------\n")
        f.write(f"Flight Route: [{start_location_name}] ---> [{end_location_name}]\n")
        f.write(f"Starting coords given: ({start_lat},{start_long})\n")
        f.write(f"Starting coords live: ({start_lat_live},{start_lon_live})\n")
        f.write(f"Ending coords given: ({end_lat},{end_long})\n")
        f.write(f"Ending coords live: ({end_lat_live},{end_lon_live})\n")
        f.write("----------------------------END----------------------------\n\n")

    print(f"!!!Coords saved to file '{DRONE_COORDS_FILE}'!!!")

if __name__ == "__main__":
    asyncio.run(run())