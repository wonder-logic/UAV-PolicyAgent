import requests
import re
from bs4 import BeautifulSoup
from ddgs import DDGS


HEADERS = {
    "User-Agent":
    "Mozilla/5.0"
}


OFFICIAL_SITES = [

    "dji.com",

    "autelrobotics.com",

    "parrot.com",

    "skydio.com",

    "holystone.com",

    "ryzerobotics.com",

    "yuneec.com"

]


def search_official_page(drone_model):

    query = f"{drone_model} specifications"

    with DDGS() as ddgs:

        results = ddgs.text(
            query,
            max_results=10
        )

        for result in results:

            page_url = result["href"]

            for site in OFFICIAL_SITES:

                if site in page_url.lower():

                    # Determine manufacturer
                    if "dji.com" in page_url:
                        manufacturer = "DJI"

                    elif "autelrobotics.com" in page_url:
                        manufacturer = "Autel Robotics"

                    elif "skydio.com" in page_url:
                        manufacturer = "Skydio"

                    elif "parrot.com" in page_url:
                        manufacturer = "Parrot"

                    elif "holystone.com" in page_url:
                        manufacturer = "Holy Stone"

                    elif "yuneec.com" in page_url:
                        manufacturer = "Yuneec"

                    else:
                        manufacturer = None


                    return {
                        "url": page_url,
                        "manufacturer": manufacturer
                    }

    return None

def scrape_specs(url):

    page = requests.get(

        url,

        headers=HEADERS,

        timeout=15

    )

    soup = BeautifulSoup(

        page.text,

        "html.parser"

    )

    text = soup.get_text(" ")

    specs = {}

    specs["raw_text"] = text

    weight = re.search(
        r"([0-9]{2,5})\s*g",
        text,
        re.I
    )

    flight = re.search(
        r"([0-9]{1,3})\s*min",
        text,
        re.I
    )

    specs = {
        "weight_in_grams":
        weight.group(1) if weight else None,
        "endurance_in_mins":
        flight.group(1) if flight else None,
        "manufacturer": None,
    }

    return specs