"""
knowledge_chatbot.py

LLM interface for the UAVGuard Knowledge Agent.

Responsibilities
----------------
1. Extract mission information from natural language.
2. Generate mission explanations.
"""

import json
import ollama


class KnowledgeChatbot:

    def __init__(self):
        """
        Local Ollama model.
        """
        self.model = "llama3.2"

###############################################################
# Normalize a location name
###############################################################

    def normalize_location(self, location_name):
        prompt = f"""
You are an expert in geographic locations.

A user entered this location:

{location_name}

If it is abbreviated, misspelled, or incomplete,
rewrite it as the most likely official place name.

You are preparing a location for GPS geocoding.

Rules:

1. Correct spelling mistakes.
2. Expand common abbreviations.
3. Preserve building names, landmarks, airports, parks, and street names.
4. NEVER replace a specific location with a broader location..
5. Never replace a building with the campus or city.
6. Never generalize a specific location.
7. Never invent locations.
8. If the user specifies a building, return the building name.
9. If uncertain, return the original input unchanged.

Return ONLY the normalized location.
Do not explain.
Do not include arrows.
Do not include extra text.


Examples:

If the input is TIMUCC, the output should only be Texas A&M University-Corpus Christi

If the input is XULA the output should only be Xavier University of Louisiana

If the input is Carlos Truan NRC the output should only be Carlos F. Truan Natural Resources Center, Texas A&M University-Corpus Christi

If the iput is DJI HQ the output should only be DJI Headquarters

If the input is St Katherine Drexel Residence Hall the ouput should be St Katherine Drexel Residence Hall



Return ONLY the corrected location.
"""

        response = ollama.chat(

            model=self.model,

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response["message"]["content"].strip()

    ###############################################################
    # Extract mission information from natural language
    ###############################################################

    def reason_mission_context(self, context):
        prompt = f"""

{json.dumps(context, indent=2)}

1. Identify missing information that is still required and essential for flight planning.
2. Check the time of day and consider whether night lighting or anti-collision lighting is required for the flight.
3. During daytime hours, night light and anti-collision strobe are NOT required so no need for it during the day time.
4. If and only if time is night time and night lighting or anti-collision lighting are missing, explain that flight is not feasible in low visibility conditions and why.

Return ONLY valid JSON.

Example:

{{

    "missing_information":[
    ],

}}
"""

        response = ollama.chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            format={
                "type": "object",
                "properties": {
                    "missing_information": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
        )

        return json.loads(response["message"]["content"])

   