import json
import os

CACHE = "drone_cache.json"

def load_cache():

    if not os.path.exists(CACHE):

        return {}

    with open(CACHE,"r") as f:

        return json.load(f)

def save_cache(cache):

    with open(CACHE,"w") as f:

        json.dump(cache,f,indent=4)