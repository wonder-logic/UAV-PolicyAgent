'''grid_data.py'''
'''this file will be used by pathfinder.py, visualize_zones.py, fly.py, data.py'''
'''creates the grid'''

ZONE_SCALE = 100 # for now
GRID_START = -10
GRID_END = 11 # actually ends at this minus 1
TOTAL_ZONES = abs(GRID_START) + abs(GRID_END)
CLOSED_CELLS = {
    
}

# using dictionary with tuple keys to represent the grid,
# and values 1 for open cells and 0 for blocked cells
the_grid = {}
for num in range(GRID_START,GRID_END):
    for num2 in range(GRID_START, GRID_END):
        if (num, num2) in CLOSED_CELLS:
            the_grid[(num, num2)] = 0
        else:
            the_grid[(num, num2)] = 1


# starting point to be replaced by what is given
start_lat = 27.714109
start_long = -97.327416

# ending point to be replaced by what is given
end_lat = 27.713033
end_long = -97.319548