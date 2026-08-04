'''processing_data.py'''
'''this file will be used by pathfinder.py, visualize_zones.py, fly.py'''
'''converts latitude and longitude coordinates to grid points'''

from grid_data import ZONE_SCALE, GRID_START, GRID_END, start_lat, start_long, end_lat, end_long
import math

start_zone = (0, 0) # doesn't change
end_zone = (0,0)

# calculating the x and y distances to get the ending point
def calculate_xy(lat1, lon1, lat2, lon2):
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    lon1_rad = math.radians(lon1)
    lon2_rad = math.radians(lon2)
    
    d_lat = lat2_rad - lat1_rad
    d_lon = lon2_rad - lon1_rad
    
    avg_lat = (lat1_rad + lat2_rad) / 2
    
    earth_radius = 6371000
    
    y_dist = d_lat * earth_radius
    x_dist = d_lon * math.cos(avg_lat) * earth_radius
    
    return x_dist, y_dist

def calculate_end_zone(x,y):
    #calculate the end zone based on x and y distances
    exact_x = x/ZONE_SCALE
    # if iusing math.floor, when x is 49 and ZONE_SCALE is 50, then it evaluates to 0.
    exact_y = y/ZONE_SCALE
    # same issue as above 

    grid_x = math.floor(exact_x + 0.5)
    grid_y = math.floor(exact_y + 0.5)

    #check if the x and y distances make the drone go out of bounds
    if not (GRID_START <= grid_x < GRID_END):
        raise ValueError("The x value of the ending point is out of bounds of the map")
    
    if not (GRID_START <= grid_y < GRID_END):
        raise ValueError("The y value of the ending point is out of bounds of the map")

    return (grid_x, grid_y), (exact_x, exact_y)
# haversine formula
# used previously, but ran into a problem because movement is not linear,
# so converting to x and y distances is more accurate for grid calculations
def haversine(lat1, lon1, lat2, lon2):
    # distance between latitudes
    # and longitudes
    dLat = (lat2 - lat1) * math.pi / 180.0
    dLon = (lon2 - lon1) * math.pi / 180.0

    # convert to radians
    lat1 = (lat1) * math.pi / 180.0
    lat2 = (lat2) * math.pi / 180.0

    # apply formulae
    a = (pow(math.sin(dLat / 2), 2) + 
         pow(math.sin(dLon / 2), 2) * 
             math.cos(lat1) * math.cos(lat2));
    rad = 6371000
    c = 2 * math.asin(math.sqrt(a))
    return rad * c
# credit: https://www.geeksforgeeks.org/dsa/haversine-formula-to-find-distance-between-two-points-on-a-sphere/
'''
dist = math.ceil(haversine(start_lat, start_long, end_lat, end_long))
#dist = 5923
TOTAL_ZONES = abs(GRID_START) + abs(GRID_END)
ZONE_SCALE = math.ceil(dist / math.ceil(TOTAL_ZONES / 2))
'''

x_dist, y_dist = calculate_xy(start_lat, start_long, end_lat, end_long)
end_zone, exact_end_target = calculate_end_zone(x_dist, y_dist)

if __name__ == "__main__":
    #print(the_grid)
    print("Zone scale is", ZONE_SCALE, "meters")
    #print(dist, "meters from starting to ending point")
    print(f"Distance: ({x_dist:.2f},{y_dist:.2f}) meters")
    print(f"End Zone is: {end_zone}")
