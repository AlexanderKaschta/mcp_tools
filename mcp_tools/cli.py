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
    export_questions = [
        inquirer.Text("city", message="Welche Stadt soll exportiert werden?"),
    ]

    answers = inquirer.prompt(export_questions)

    overpass_query = f"[out:json];area[name=\"{answers['city']}\"];(relation[\"type\"=\"boundary\"][\"admin_level\"~\"8|9|10\"](area););out;"

    request = requests.get(OVERPASS_API_URL, params={"data": overpass_query})

    response = request.json()

    sections = []
    city_section = {"name": answers["city"], "addresses": [], "objects": []}

    counter = 1

    for item in response["elements"]:

        streets = set()

        print(f"Lade {item['tags']['name']}")
        overpass_street_query = f"[out:json];area({3600000000 + item['id']});way[highway~\"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|pedestrian)$\"][name](area);out;"
        request = requests.get(OVERPASS_API_URL, params={"data": overpass_street_query})

        street_response = request.json()

        for way in street_response["elements"]:
            streets.add(way["tags"]["name"])

        for unique_way in streets:
            address = {"name": unique_way, "area": item["tags"]["name"], "id": counter}
            counter += 1
            city_section["addresses"].append(address)

    sections.append(city_section)

    file_content = json.dumps(sections)

    file = open("MCP-Orte-Adressen.json", "w", encoding="utf-8")
    file.write(file_content)
    file.close()
