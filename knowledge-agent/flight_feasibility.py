"""
Flight Feasibility Module

Uses route distance and battery
information to estimate whether
the flight can be completed.
"""

def estimate_feasibility(distance_miles,battery_percent, endurance_in_minutes,weather,cruise_speed=30):
    """
    Estimates flight feasibility using
    battery, speed and weather.
    """

    ####################################
    # Available battery time
    ####################################

    available_minutes = (
        endurance_in_minutes *
        (battery_percent / 100)
    )

    ####################################
    # Flight time
    ####################################

    required_minutes = (
        distance_miles /
        cruise_speed
    ) * 60

    ####################################
    # Wind penalty
    ####################################

    if weather.get("status") != "SUCCESS":
        wind_speed = 0
    else:
        wind_speed = weather.get("wind_speed", 0)

    wind_penalty = 1.0

    wind_speed = weather.get("wind_speed", 0)

    if wind_speed > 20:
        wind_penalty = 0.70

    elif wind_speed > 15:
        wind_penalty = 0.85

    elif wind_speed > 10:
        wind_penalty = 0.95
        
    else:
        wind_penalty = 1.0

    required_minutes *= wind_penalty

    ####################################
    # Safety reserve
    ####################################

    reserve = 5

    required_minutes += reserve

    ####################################

    battery_margin = (
        available_minutes -
        required_minutes
    )

    ####################################

    return {

        "available_minutes":
        round(available_minutes,2),

        "required_minutes":
        round(required_minutes,2),

        "battery_margin":
        round(battery_margin,2),

        "wind_penalty":
        wind_penalty,

        "reserve_minutes":
        reserve,

        "allowed_to_fly":
        battery_margin >= 0

    }

