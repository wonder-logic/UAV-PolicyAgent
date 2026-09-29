'''pathfinder.py'''
'''uses grid_data.py and processing_data.py'''
'''implements A* with Manhattan distance heuristic using Networkx'''

from grid_data import the_grid, ZONE_SCALE
from processing_data import start_zone, end_zone

import networkx as nx
import sys

import json
import math

def manhattan_heuristic(node, target):
    return abs(node[0] - target[0]) + abs(node[1] - target[1])

def find_shortest_path(grid, start, end):
    if grid.get(start) == 0:
        raise ValueError("Start coordinate is blocked")

    if grid.get(end) == 0:
        raise ValueError("End coordinate is blocked")
    
    G = nx.Graph()

    # add all unblocked tuples to graph
    for coordinate, val in grid.items():
        if val == 1:
            G.add_node(coordinate)
    
    # add edges between neighbors of each node
    for coordinate in G.nodes():
        r, c = coordinate
        moves = [(0,-1), (0,1), (-1,0), (1,0)]
        for row, col in moves:
            neighbor = (r+row, c+col)
            if neighbor in G:
                G.add_edge(coordinate, neighbor)
    try:
        return nx.astar_path(G, source=start, target=end, heuristic=manhattan_heuristic) 
    except Exception as error:
        raise RuntimeError(f"Error: {error}") from error
    
def calculate_distance(path, zone_scale):
    total_steps = max(0, len(path) - 1)
    return total_steps * zone_scale

def main():
    try:
        path = find_shortest_path(the_grid, start_zone, end_zone)
        expected_distance = calculate_distance(path, ZONE_SCALE)
    except Exception as error:
        print("UH OH! Something went wrong")
        print(f"Reason: {error}")
        sys.exit(1)
    
    print(f"PATH IS: {path}")
    print(f"Expected Total Waypoints: {len(path)-1}")
    print(f"Expected Flight Distance: {expected_distance:.2f} meters")

    miles = expected_distance * 0.000621371

    data = {
        "distance_miles": miles
    }

    with open("simulator_response.json", "w") as file:
        json.dump(data, file)

if __name__ == "__main__":
    main()