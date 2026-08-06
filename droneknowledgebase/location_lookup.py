"""
location_lookup.py

Uses the Knowledge Agent LLM to normalize a location
before retrieving GPS coordinates with Geopy.
"""

from geopy.geocoders import Nominatim
from knowledge_chatbot import KnowledgeChatbot
import requests
from urllib.parse import quote

GEOAPIFY_KEY = "fc5c4f83881a4d9cb682b58454fa68a7"



##########################################################
# Initialize
##########################################################

geolocator = Nominatim(user_agent="uavguard")

chatbot = KnowledgeChatbot()

##########################################################
# Lookup
##########################################################

def get_coordinates(location_name):

    try:

        print(f"\nOriginal Location: {location_name}")

        ##################################################
        # Step 1
        ##################################################

        normalized_location = chatbot.normalize_location(
            location_name
        )

        print(
            f"LLM Normalized Location: {normalized_location}"
        )

        ##################################################
        # Step 2
        # Nominatim (normalized)
        ##################################################

        location = geolocator.geocode(
            normalized_location,
            exactly_one=True,
            addressdetails=True
        )

        ##################################################
        # Step 3
        # Nominatim (original)
        ##################################################

        if location is None:

            print("Normalized lookup failed.")

            location = geolocator.geocode(

                location_name,

                exactly_one=True,

                addressdetails=True

            )

        ##################################################
        # Step 4
        # Geoapify Geocoder (normalized)
        ##################################################

        if location is None:

            print("Trying Geoapify geocoder...")

            url = (

                "https://api.geoapify.com/v1/geocode/search"

                f"?text={quote(normalized_location)}"

                f"&limit=1"

                f"&apiKey={GEOAPIFY_KEY}"

            )

            response = requests.get(url)

            data = response.json()

            if data.get("features"):

                props = data["features"][0]["properties"]

                return {

                    "original_input": location_name,

                    "normalized_location": normalized_location,

                    "resolved_location": props["formatted"],

                    "latitude": round(props["lat"],6),

                    "longitude": round(props["lon"],6)

                }

        ##################################################
        # Step 5
        # Geoapify Geocoder (original)
        ##################################################

        if location is None:

            print("Trying original input with Geoapify...")

            url = (

                "https://api.geoapify.com/v1/geocode/search"

                f"?text={quote(location_name)}"

                f"&limit=1"

                f"&apiKey={GEOAPIFY_KEY}"

            )

            response = requests.get(url)

            data = response.json()

            if data.get("features"):

                props = data["features"][0]["properties"]

                return {

                    "original_input": location_name,

                    "normalized_location": normalized_location,

                    "resolved_location": props["formatted"],

                    "latitude": round(props["lat"],6),

                    "longitude": round(props["lon"],6)

                }

        ##################################################
        # Step 6
        # Geoapify Places Search
        # Better for buildings
        ##################################################

        if location is None:

            print("Trying Geoapify Places Search...")

            url = (

                "https://api.geoapify.com/v2/places"

                "?categories=building"

                f"&filter=text:{quote(location_name)}"

                "&limit=1"

                f"&apiKey={GEOAPIFY_KEY}"

            )

            response = requests.get(url)

            data = response.json()

            if data.get("features"):

                props = data["features"][0]["properties"]

                return {

                    "original_input": location_name,

                    "normalized_location": normalized_location,

                    "resolved_location": props.get("formatted","Unknown"),

                    "latitude": round(props["lat"],6),

                    "longitude": round(props["lon"],6)

                }

        ##################################################
        # Step 7
        ##################################################

        if location is None:

            print("Unable to locate location.")

            return None

        ##################################################
        # Success from Nominatim
        ##################################################

        return {

            "original_input": location_name,

            "normalized_location": normalized_location,

            "resolved_location": location.address,

            "latitude": round(location.latitude,6),

            "longitude": round(location.longitude,6)

        }

    except Exception as e:

        print(e)

        return None