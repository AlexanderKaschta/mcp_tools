import json

import inquirer
import requests

OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"


def main() -> None:

    task_choices = ["OpenStreetMaps-Export", "Anwendung beenden"]

    questions = [inquirer.List("task",
                               message="Welche Aktion soll ausgeführt werden?",
                               choices=task_choices)]

    answers = inquirer.prompt(questions)

    if answers["task"] == task_choices[0]:
        osm_export()


def osm_export() -> None:

    export_street_options = ["Straßen", "Parks", "Plätze"]
    yes_no_options = ["Ja", "Nein"]

    export_questions = [
        inquirer.Text("city", message="Welche Stadt soll exportiert werden?"),
        inquirer.Checkbox("options",
                          message="Was soll alles als Straße exportiert werden?",
                          choices=export_street_options),
        inquirer.List("buildings", message="Sollen auch Gebäude exportiert werden?", choices=yes_no_options)
    ]

    answers = inquirer.prompt(export_questions)

    if len(answers['city']) < 1:
        print("Fehler: Die Eingabe darf nicht leer sein!")
        pass

    overpass_query = (f"[out:json];area[name=\"{answers['city']}\"];"
                      f"(relation[\"type\"=\"boundary\"][\"admin_level\"~\"8|9|10\"](area););out;")

    request = requests.get(OVERPASS_API_URL, params={"data": overpass_query})

    try:
        request.raise_for_status()
    except requests.exceptions.HTTPError:
        print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
        pass

    response = request.json()

    sections = []
    city_section = {"name": answers["city"], "addresses": [], "objects": []}

    counter = 1

    if len(response["elements"]) == 0:
        print("Fehler: Es konnten keine passenden Daten gefunden werden!")
        pass

    for item in response["elements"]:
        streets = set()

        print(f"Lade {item['tags']['name']}")

        if export_street_options[0] in answers["options"]:
            # Get all streets in the area
            overpass_street_query = (f"[out:json];area({3600000000 + item['id']});"
                                     f"way[highway~\"^(motorway|trunk|primary|secondary|tertiary|unclassified|"
                                     f"residential|living_street|pedestrian)$\"][name](area);out;")
            request = requests.get(OVERPASS_API_URL, params={"data": overpass_street_query})

            street_response = request.json()

            for way in street_response["elements"]:
                streets.add(way["tags"]["name"])

        if export_street_options[1] in answers["options"]:
            # Get all parks in the area
            overpass_park_query = (f"[out:json];area({3600000000 + item['id']});"
                                   f"(way[\"leisure\"=\"park\"](area);relation[\"leisure\"=\"park\"](area););out;")
            request = requests.get(OVERPASS_API_URL, params={"data": overpass_park_query})

            park_response = request.json()
            for park in park_response["elements"]:
                if "name" in park["tags"]:
                    if "access" in park["tags"] and park["tags"]["access"] == "private":
                        continue
                    else:
                        streets.add(park["tags"]["name"])

        if export_street_options[2] in answers["options"]:
            # Get all squares in the area
            overpass_square_query = (f"[out:json];area({3600000000 + item['id']});"
                                     f"(way[\"place\"=\"square\"](area);relation[\"place\"=\"square\"](area););out;")
            request = requests.get(OVERPASS_API_URL, params={"data": overpass_square_query})

            square_response = request.json()
            for square in square_response["elements"]:
                if "name" in square["tags"]:
                    streets.add(square["tags"]["name"])

        # Add the result into a dict
        for unique_way in streets:
            address = {"name": unique_way, "area": item["tags"]["name"], "id": counter}
            counter += 1
            city_section["addresses"].append(address)

        if answers["buildings"] == yes_no_options[0]:
            # Export buildings
            overpass_building_query = (f"[out:json];area({3600000000 + item['id']});"
                                       f"(way[\"building\"][\"name\"][\"addr:street\"](area);"
                                       f"relation[\"building\"][\"name\"][\"addr:street\"](area););out;")

            request = requests.get(OVERPASS_API_URL, params={"data": overpass_building_query})
            buildings_response = request.json()

            for building in buildings_response["elements"]:
                street = next((a for a in city_section["addresses"]
                               if a["name"] == building["tags"]["addr:street"] and a["area"] == item["tags"]["name"]),
                              None)

                if street is not None:
                    if "addr:housenumber" in building["tags"]:
                        mcp_object = {"name": building["tags"]["name"], "address": street["id"],
                                      "houseNumber": building["tags"]["addr:housenumber"], "description": ""}
                    else:
                        mcp_object = {"name": building["tags"]["name"], "address": street["id"], "houseNumber": "",
                                      "description": ""}

                    city_section["objects"].append(mcp_object)

    sections.append(city_section)

    file_content = json.dumps(sections)

    file = open("MCP-Orte-Adressen.json", "w", encoding="utf-8")
    file.write(file_content)
    file.close()

    print("Dateiexport fertig!")
