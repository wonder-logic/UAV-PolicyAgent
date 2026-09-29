"""
knowledge_agent.py

UAVGuard Knowledge Agent

Responsibilities
----------------
1. Receive mission request from AI Assistant (ai_request.json)
2. Retrieve drone specifications from OpenDroneList
3. Retrieve current weather
4. Retrieve current system time
5. Create mission_context.json

Later...

6. Receive simulator_response.json
7. Estimate battery feasibility
8. Use the LLM to explain the results
9. Create feasibility_response.json
"""

import json
import os
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from datetime import datetime
import requests
from manufacturer_lookup import (
    search_official_page,
    scrape_specs
)

from drone_repository import find_drone
from weather_lookup import get_weather
from flight_feasibility import estimate_feasibility
from knowledge_chatbot import KnowledgeChatbot
from location_lookup import get_coordinates
from timezonefinder import TimezoneFinder
from config import GEOAPIFY_KEY

tf = TimezoneFinder()

geolocator = Nominatim(user_agent="uavguard")

############################################################
# Helper
############################################################

def load_json(filename):

    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)

def get_human_activity_zones(
        start_coordinates,
        destination_coordinates):


    min_lat = min(
        start_coordinates["latitude"],
        destination_coordinates["latitude"]
    )

    max_lat = max(
        start_coordinates["latitude"],
        destination_coordinates["latitude"]
    )

    min_lon = min(
        start_coordinates["longitude"],
        destination_coordinates["longitude"]
    )

    max_lon = max(
        start_coordinates["longitude"],
        destination_coordinates["longitude"]
    )


    padding = 0.02

    min_lat -= padding
    max_lat += padding

    min_lon -= padding
    max_lon += padding


    url = (
        "https://api.geoapify.com/v2/places"
        "?categories="
        "education,"
        "healthcare,"
        "commercial,"
        "entertainment"
        f"&filter=rect:{min_lon},{min_lat},{max_lon},{max_lat}"
        "&limit=10"
        f"&apiKey={GEOAPIFY_KEY}"
    )


    response = requests.get(url)

    data = response.json()


    human_zones = []


    for place in data.get("features", []):

        props = place["properties"]


        human_zones.append({

            "name":
            props.get("name","Unknown"),

            "type":
            props.get("categories",[]),

            "latitude":
            props["lat"],

            "longitude":
            props["lon"]

        })


    return human_zones

def get_restricted_zones(start_coordinates,
                         destination_coordinates):

    ####################################################
    # Create bounding rectangle
    ####################################################

    min_lat = min(
        start_coordinates["latitude"],
        destination_coordinates["latitude"]
    )

    max_lat = max(
        start_coordinates["latitude"],
        destination_coordinates["latitude"]
    )

    min_lon = min(
        start_coordinates["longitude"],
        destination_coordinates["longitude"]
    )

    max_lon = max(
        start_coordinates["longitude"],
        destination_coordinates["longitude"]
    )

    ####################################################
    # Add padding
    ####################################################

    padding = 0.15

    min_lat -= padding
    max_lat += padding

    min_lon -= padding
    max_lon += padding

    ####################################################
    # Geoapify request
    ####################################################

    url = (

        "https://api.geoapify.com/v2/places"

        "?categories="

        "airport,"

        "airport.military,"

        "airport.airfield,"

        "building.military"

        f"&filter=rect:{min_lon},{min_lat},{max_lon},{max_lat}"

        "&limit=50"

        f"&apiKey={GEOAPIFY_KEY}"

    )

    response = requests.get(url)

    response.raise_for_status()

    data = response.json()
    #print(data)

    ####################################################
    # Build list
    ####################################################

    restricted = []

    for place in data["features"]:

        props = place["properties"]

        restricted.append({

            "name":

            props.get("name","Unknown"),

            "type":

            props.get("categories",[]),

            "latitude":

            props["lat"],

            "longitude":

            props["lon"]

        })

    return restricted

def get_elevation(latitude, longitude):

    try:

        url = (
            "https://api.opentopodata.org/v1/aster30m"
            f"?locations={latitude},{longitude}"
        )

        response = requests.get(
            url,
            timeout=10
        )

        data = response.json()

        meters = data["results"][0]["elevation"]

        feet = round(meters * 3.28084)

        return feet

    except:

        return None

def get_timezone(latitude, longitude):

    try:

        timezone = tf.timezone_at(

            lat=latitude,

            lng=longitude

        )

        return timezone

    except:

        return None
####################################
# Remove previous mission
####################################

if os.path.exists("mission_context.json"):

    os.remove("mission_context.json")


def build_mission_context():

    if not os.path.exists("ai_request.json"):

        print("ai_request.json not found.")
        return None

    print("\n==============================")
    print("Knowledge Agent")
    print("Building Mission Context")
    print("==============================")

    request = load_json("ai_request.json")

    ########################################################

    drone = find_drone(request["drone_model"])

    if drone:
        print("Drone found in database.")
    else:
        print(
            "Drone not found locally. Searching manufacturer website..."
        )

        page = search_official_page(request["drone_model"])

        if page:
            drone = scrape_specs(page["url"])
            drone["name"] = request["drone_model"]
            drone["manufacturer"] = page["manufacturer"]
        else:
            print("Drone not found.")
            drone = {
                "name": request["drone_model"]
            }

    drone_status = "SUCCESS"

    ########################################################
    # Convert locations into GPS coordinates
    ########################################################

    start_coordinates = get_coordinates(
        request["start_location"]
    )

    destination_coordinates = get_coordinates(
        request.get("destination")
    )

    restricted_zones = []
    human_zones = []

    if (
        start_coordinates is not None
        and destination_coordinates is not None
    ):
        restricted_zones = get_restricted_zones(
            start_coordinates,
            destination_coordinates
        )
        human_zones = get_human_activity_zones(
            start_coordinates,
            destination_coordinates
        )
    else:
        print("Skipping restricted and human zone lookup.")

    # Resolve timezones only if coordinates were found

    start_timezone = None
    destination_timezone = None

    if start_coordinates is not None and start_coordinates.get("latitude") is not None:
        start_timezone = get_timezone(
            start_coordinates["latitude"],
            start_coordinates["longitude"]
        )
        start_coordinates["timezone"] = start_timezone

    if destination_coordinates is not None and destination_coordinates.get("latitude") is not None:
        destination_timezone = get_timezone(
            destination_coordinates["latitude"],
            destination_coordinates["longitude"]
        )
        destination_coordinates["timezone"] = destination_timezone

    start_status = "SUCCESS"

    if start_coordinates is None:

        print("Unable to locate start location.")

        start_status = "NOT FOUND"

        start_coordinates = {
            "latitude": None,
            "longitude": None
        }

        destination_status = "SUCCESS"

    # Assume destination lookup will succeed unless proven otherwise
    destination_status = "SUCCESS"

    if destination_coordinates is None:

        print("Unable to locate destination.")

        destination_status = "NOT FOUND"

        destination_coordinates = {
            "latitude": None,
            "longitude": None
        }

    start_elevation = get_elevation(

        start_coordinates["latitude"],
        start_coordinates["longitude"]

    )

    destination_elevation = get_elevation(

        destination_coordinates["latitude"],
        destination_coordinates["longitude"]

    )

    ########################################################
    # TERRAIN
    ########################################################

    terrain = {

    "start_elevation_ft_msl":
    start_elevation,

    "destination_elevation_ft_msl":
    destination_elevation

}
    

    ########################################################
    # Retrieve weather at mission start and destination
    ########################################################

    if start_coordinates["latitude"] is not None:
        start_weather = get_weather(
            start_coordinates["latitude"],
            start_coordinates["longitude"]
        )
    else:
        start_weather = {
            "status": "FAILED",
            "message": "Location unavailable"
        }

    if destination_coordinates["latitude"] is not None:
        destination_weather = get_weather(
            destination_coordinates["latitude"],
            destination_coordinates["longitude"]
        )
    else:
        destination_weather = {
            "status": "FAILED",
            "message": "Location unavailable"
        }

    ########################################################
    # Analyze weather
    ########################################################

    weather_warning = []

    ####################################
    # Wind
    ####################################

    if start_weather["status"] == "SUCCESS":

        if start_weather["wind_speed"] > 20:

            weather_warning.append(

                "High wind at launch."

            )

        elif start_weather["wind_speed"] > 10:

            weather_warning.append(

                "Moderate wind."

            )

    ####################################
    # Rain
    ####################################

    if start_weather["status"] == "SUCCESS":

        if start_weather["precipitation"] > 0:

                weather_warning.append(

                    "Rain detected."

                )

    ####################################
    # Visibility
    ####################################

        if start_weather["visibility"] < 5000:

            weather_warning.append(

                "Low visibility."

            )

    ####################################
    # Destination
    ####################################

    if destination_weather["status"] == "SUCCESS":

        if destination_weather["wind_speed"] > 20:

            weather_warning.append(

                "High wind at destination."

            )

    ####################################

    if len(weather_warning) == 0:

        weather_warning.append(

            "Weather acceptable."

        )

    ####################################################

    context = {

        "agent": "Knowledge Agent",

        "current_time": datetime.now().strftime("%I:%M:%S %p"),

        "drone": drone,

        "battery_percent":
        request["battery_percent"],

        "start_location":
        request["start_location"],

        "destination":
        request["destination"],

        "start_coordinates":
        start_coordinates,

        "destination_coordinates":
        destination_coordinates,

        "restricted_zones":
        restricted_zones,

        "human_zones":
        human_zones,

        "start_weather":
        start_weather,

        "destination_weather":
        destination_weather,

        "weather_warning":
        weather_warning,

        "start_lookup_status": 
        start_status,

        "destination_lookup_status": 
        destination_status,

        "terrain":
        terrain,

    }

    chatbot = KnowledgeChatbot()

    reasoning = chatbot.reason_mission_context(context)

    context["knowledge_reasoning"] = reasoning

    ########################################################

    with open(

        "mission_context.json",

        "w",

        encoding="utf-8"

    ) as file:

        json.dump(

            context,

            file,

            indent=4

        )


############################################################
# Stage 2
# Simulator -> Knowledge Agent
############################################################

def evaluate_route():

    if not os.path.exists("mission_context.json"):

        print("mission_context.json not found.")

        return None

    if not os.path.exists("simulator_response.json"):

        print("Waiting for simulator_response.json")

        return None

    print("\n==============================")
    print("Knowledge Agent")
    print("Evaluating Route")
    print("==============================")

    mission = load_json(

        "mission_context.json"

    )

    simulator = load_json(

        "simulator_response.json"

    )

    ########################################################

    distance = simulator["distance_miles"]

    battery = mission["battery_percent"]

    drone = mission["drone"]

    ########################################################

    feasibility = estimate_feasibility(

        distance,

        battery,

        int(

            drone.get(

                "endurance",

                30

            )

        ),
        mission["start_weather"],

        30

    )


    ########################################################

    output = {

        "agent": "Knowledge Agent",

        "distance": distance,

        "flight_feasibility":

        feasibility,

    }

    ########################################################

    with open(

        "flight_feasibility.json",

        "w",

        encoding="utf-8"

    ) as file:

        json.dump(

            output,

            file,

            indent=4

        )

    ########################################################
    # Create can_fly.json
    ########################################################

    can_fly = {

        "allowed_to_fly": 1 if feasibility["allowed_to_fly"] else 0

    }

    with open(

        "can_fly.json",

        "w",

        encoding="utf-8"

    ) as file:

        json.dump(

            can_fly,

            file,

            indent=4

        )

    ########################################################

    print("\nFlight Feasibility Complete")

    print("---------------------------")

    print("Distance:", distance, "miles")

    print("Battery:", battery, "%")

    print(

        "Can Complete:",

        feasibility["allowed_to_fly"]

    )

    print("\nflight_feasibility.json written successfully.\n")

    return output


############################################################
# Main
############################################################

if __name__ == "__main__":

    print("\nUAVGuard Knowledge Agent\n")

    if os.path.exists("ai_request.json"):

        build_mission_context()

    if os.path.exists("simulator_response.json"):

        evaluate_route()

    else:

        print("Nothing to process.")

        print("Expected : simulator_response.json")