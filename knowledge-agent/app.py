import streamlit as st
import json
import os
import time

from knowledge_agent import (
    build_mission_context,
    evaluate_route
)

page = st.sidebar.radio(
    "Navigation",
    [
        "Mission Request",
        "Knowledge Agent",
        "Simulation",
        "Flight Results"
    ]
)

knowledge_page = None

if page == "Knowledge Agent":
    knowledge_page = st.sidebar.radio(
        "Knowledge Sections",
        [
            "Drone Specifications",
            "Location Resolution",
            "Weather",
            "Terrain",
            "Restricted Areas",
            "Population",
            "Reasoning"
        ]
    )

mission = {}

st.set_page_config(
    page_title="UAVGuard",
    page_icon="✈️",
    layout="wide"
)

col1, col2 = st.columns([1,5])

with col1:
    st.image("tamucc_logo.png", width=80)

with col2:
    st.markdown(
        "<h1 style='color:#003B71;'>✈️UAVGuard</h1>",
        unsafe_allow_html=True
    )

    st.write("A Multi-Agent Architecture for Drone Flight Compliance")

st.markdown("""
<style>

/* Main title */
h1{
    color:#003B71 !important;
    font-weight:800;
}

/* Section headers */
h2,h3{
    color:#003B71 !important;
}

/* Metric cards */
div[data-testid="metric-container"]{
    background:white;
    border-radius:12px;
    border-left:6px solid #FDB913;
    padding:15px;
    box-shadow:0px 2px 8px rgba(0,0,0,.15);
}

/* Buttons */
.stButton>button{
    background-color:#003B71;
    color:white;
    border-radius:10px;
    border:none;
    font-weight:bold;
}

.stButton>button:hover{
    background-color:#00508C;
    color:white;
}

/* Text inputs */
.stTextInput input{
    border:2px solid #003B71;
    border-radius:8px;
}

/* Slider */
.stSlider{
    color:#FDB913;
}

/* Success boxes */
div[data-baseweb="notification"]{
    border-left:6px solid #FDB913;
}

</style>
""", unsafe_allow_html=True)

##############################################################
# Mission Input
##############################################################
if page == "Mission Request":

    st.header("📝 Mission Request")

    with st.form("mission_form"):

        drone = st.text_input(
            "Drone",
            "Mini 4 Pro"
        )

        battery = st.slider(
            "Battery (%)",
            0,
            100,
            80
        )

        start = st.text_input(
            "Start Location",
            "Texas A&M University-Corpus Christi"
        )

        destination = st.text_input(
            "Destination",
            "Padre Island"
        )

        submitted = st.form_submit_button(
            "Analyze Mission"
        )

    if submitted:

        request = {

            "drone_model": drone,

            "battery_percent": battery,

            "start_location": start,

            "destination": destination

        }

        with open(

            "ai_request.json",

            "w",

            encoding="utf-8"

        ) as f:

            json.dump(

                request,

                f,

                indent=4

            )

            simulator_response = {

            "distance_miles": 2

        }

        with open(
            "simulator_response.json",
            "w"
        ) as f:

            json.dump(
                simulator_response,
                f,
                indent=4
            )

        ##################################################
        # Always rebuild using newest request
        ##################################################

        if os.path.exists("ai_request.json"):

            with open("ai_request.json") as f:

                request = json.load(f)

        st.divider()

        st.subheader("Current Mission")

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Drone",
            request["drone_model"]
        )

        c2.metric(
            "Battery",
            f'{request["battery_percent"]}%'
        )

        c1.metric(
            "Start",
            request["start_location"]
        )

        c2.metric(
            "Destination",
            request["destination"]
        )

        start_time = time.perf_counter()

        build_mission_context()

        end_time = time.perf_counter()

        response_time = end_time - start_time

        if os.path.exists("simulator_response.json"):

            evaluate_route()

        st.success("Mission processed successfully.")

        st.metric(
            "Knowledge Agent Response Time",
            f"{response_time:.3f} sec"
        )

##############################################################
# Knowledge Agent
##############################################################

if os.path.exists("mission_context.json"):

    if os.path.exists("ai_request.json"):
        with open("ai_request.json", "r") as f:
            request = json.load(f)

    st.divider()

if page == "Knowledge Agent":
    st.header("🧠 Knowledge Agent")

    with open("mission_context.json","r") as file:

        mission = json.load(file)

        drone = mission["drone"]

        start_weather = mission["start_weather"]

        destination_weather = mission["destination_weather"]

        terrain = mission.get(
            "terrain",
            {
                "start_elevation_ft_msl": "N/A",
                "destination_elevation_ft_msl": "N/A"
            }
        )

        resolved_start = mission["start_coordinates"]
        resolved_destination = mission["destination_coordinates"]

####################################################
# Prevent crashes if weather lookup failed
####################################################

    if start_weather.get("status") != "SUCCESS":
        start_weather = {
            "temperature": "N/A",
            "wind_speed": "N/A",
            "weather": "Unavailable",
            "wind_direction": "N/A"
        }

    if destination_weather.get("status") != "SUCCESS":
        destination_weather = {
            "temperature": "N/A",
            "wind_speed": "N/A",
            "weather": "Unavailable",
            "wind_direction": "N/A"
        }

    if st.button("View Drone Specifications"):
        @st.dialog("📦Drone Specifications")
        def drone_dialog():
            left, right = st.columns(2)

            with left:
                st.subheader("Drone Specifications")
                st.metric("Manufacturer", drone["manufacturer"])
                st.metric("Model", drone["name"])
                st.metric("UAV Class", drone["uas_class"])
            with right:
                st.metric("Max Altitude In Ft", drone["maximum_operating_altitude_ft"])
                st.metric("Endurance In Mins", drone["endurance_in_mins"])
                st.metric("Weight In Grams", drone["weight_in_grams"])
            st.metric("Anti Collision", drone["anti_collision"])

        drone_dialog()
    
    if st.button("View Location Resolution"):
        @st.dialog("🗺️Location Resolution")
        def location_dialog():
            left, right = st.columns(2)

            with left:
                st.subheader("Start Location")

                st.write("Original Input")
                st.write(request["start_location"])

                st.write("Normalized Location")
                st.write(resolved_start["normalized_location"])

                st.write("Resolved Address")
                st.write(resolved_start["resolved_location"])

                st.metric("Latitude", resolved_start["latitude"])
                st.metric("Longitude", resolved_start["longitude"])

            with right:
                st.subheader("Destination")

                st.write("Original Input")
                st.write(request["destination"])

                st.write("Normalized Location")
                st.write(resolved_destination["normalized_location"])

                st.write("Resolved Address")
                st.write(resolved_destination["resolved_location"])

                st.metric("Latitude", resolved_destination["latitude"])
                st.metric("Longitude", resolved_destination["longitude"])

        location_dialog()

    if st.button("View Weather"):

        @st.dialog("🌤Weather")
        def weather_dialog():

            left, right = st.columns(2)

            with left:

                st.subheader("📍Start Weather")

                st.metric("Temperature", f'{start_weather["temperature"]} °F')
                st.metric("Wind Speed", f'{start_weather["wind_speed"]} mph')
                st.metric("Wind Gusts", f'{start_weather["wind_gusts"]} mph')
                st.metric("Visibility", start_weather["visibility"])
                st.metric("Conditions", start_weather["weather"])

            with right:

                st.subheader("🏁Destination Weather")

                st.metric("Temperature", f'{destination_weather["temperature"]} °F')
                st.metric("Wind Speed", f'{destination_weather["wind_speed"]} mph')
                st.metric("Wind Gusts", f'{destination_weather["wind_gusts"]} mph')
                st.metric("Visibility", destination_weather["visibility"])
                st.metric("Conditions", destination_weather["weather"])

        weather_dialog()

    if st.button("View Terrain"):
        @st.dialog("⛰️Terrain")
        def terrain_dialog():

            st.metric(
                "Start Elevation",
                f'{terrain["start_elevation_ft_msl"]} ft'
            )

            st.metric(
                "Destination Elevation",
                f'{terrain["destination_elevation_ft_msl"]} ft'
            )

        terrain_dialog()


    if st.button("View Restricted Areas"):

        @st.dialog("🚫Restricted Areas")
        def restricted_dialog():

            restricted_zones = mission.get("restricted_zones", [])

            if restricted_zones:
                for zone in restricted_zones:
                    st.info(
                        f'**{zone["name"]}**\n\n'
                        f'Latitude: {zone["latitude"]}\n\n'
                        f'Longitude: {zone["longitude"]}'
                    )
            else:
                st.success("No Restricted Areas Detected")

        restricted_dialog()


    st.divider()


    if page == "Simulation":
        st.header("🌎 Simulation Agent")

        if not os.path.exists("simulator_response.json"):
            st.warning(
                "Waiting for simulator_response.json from Simulator..."
            )
        else:
            with open("simulator_response.json", "r") as file:
                simulator = json.load(file)

            st.metric(
                "Distance",
                f'{simulator["distance_miles"]:.2f} miles'
            )

            evaluate_route()

            reasoning = mission["knowledge_reasoning"]

    st.markdown("### 🧠 Knowledge Agent Summary")

    if knowledge_page == "Reasoning":
        st.markdown("### 🤖 Reasoning")

        reason_text = reasoning.get(
            "reasoning",
            "Knowledge Agent successfully collected drone, weather, terrain, and restricted zone information."
        )

        st.write(reason_text)

        missing = reasoning.get("missing_information", [])

        if missing:
            st.warning("Missing Information")
            for item in missing:
                st.write(f"• {item}")

##############################################################
# Final Results
##############################################################

if os.path.exists("flight_feasibility.json"):

    st.divider()

if page == "Flight Results":
    st.header("🛩 Flight Feasibility")

    with open(

        "flight_feasibility.json",

        "r"

    ) as file:

        result = json.load(file)

    feasibility = result["flight_feasibility"]

    if feasibility["allowed_to_fly"]:

        st.success("Mission appears feasible.")

    else:

        st.error("Mission is NOT feasible.")

    col1, col2 = st.columns(2)

    with col1:

        st.metric(

            "Available Flight Time",

            f'{feasibility["available_minutes"]:.1f} min'

        )

        st.metric(

            "Required Flight Time",

            f'{feasibility["required_minutes"]:.1f} min'

        )

    with col2:

        st.metric(

            "Battery Margin",

            f'{feasibility["battery_margin"]:.1f} min'

        )

        st.metric(

            "Wind Penalty",

            f'{feasibility["wind_penalty"]:.2f}'

        )

    st.metric(

        "Safety Reserve",

        f'{feasibility["reserve_minutes"]} min'

    )

##############################################################
# Optional Raw JSON
##############################################################

st.divider()

with st.expander("View AI Assistant JSON"):

    if os.path.exists("ai_request.json"):

        with open("ai_request.json") as f:

            st.json(json.load(f))

with st.expander("View Mission Context JSON"):

    if os.path.exists("mission_context.json"):

        with open("mission_context.json") as f:

            st.json(json.load(f))

with st.expander("View Simulator JSON"):

    if os.path.exists("simulator_response.json"):

        with open("simulator_response.json") as f:

            st.json(json.load(f))

with st.expander("View Can Fly JSON"):

    if os.path.exists("can_fly.json"):  

        with open("can_fly.json") as f:

            st.json(json.load(f))

with st.expander("View Flight Feasibility JSON"):

    if os.path.exists("flight_feasibility.json"):  

        with open("flight_feasibility.json") as f:

            st.json(json.load(f))