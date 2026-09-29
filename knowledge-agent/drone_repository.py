"""
Drone Repository

Loads drone specifications from OpenDroneList.

Acts as the primary source of drone metadata.
"""

import json
from difflib import get_close_matches
from drone_cache import *


def load_drone_data():

    with open("opendronelist.json", "r", encoding="utf-8") as file:
        return json.load(file)


def find_drone(model_name):
    cache = load_cache()
    if model_name in cache:
        print("Loaded from cache.")
        return cache[model_name]

    data = load_drone_data()

    all_drones = []
    for manufacturer in data:
        for drone in data[manufacturer]:
            drone["manufacturer"] = manufacturer
            all_drones.append(drone)

    drone_names = [d["name"] for d in all_drones]

    # Exact match
    for drone in all_drones:

        if drone["name"].lower().strip() == model_name.lower().strip():

            print("Exact match found.")

            cache[model_name] = drone
            save_cache(cache)

            return drone

    # Fuzzy match

    normalized_names = [
    d["name"].strip().lower()
    for d in all_drones
]
    match = get_close_matches(
        model_name.strip().lower(),
        normalized_names,
        n=1,
        cutoff=0.70
    )

    if match:
        matched_name = match[0]
        for drone in all_drones:
            if drone["name"].strip().lower() == matched_name:
                drone["note"] = f"Closest match used: {match[0]}"
                cache[model_name] = drone
                save_cache(cache)
                return drone

    return None