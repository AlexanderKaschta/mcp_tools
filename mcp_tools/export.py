import json

import inquirer
import requests

from mcp_tools.action import Action

OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"


class ExportAction(Action):

    def __init__(self):
        super().__init__("OpenStreetMaps-Export")

    def get_data(self, query_string: str):
        request = requests.get(OVERPASS_API_URL, params={"data": query_string})

        try:
            request.raise_for_status()
        except requests.exceptions.HTTPError:
            return None

        return request.json()

    def run(self) -> None:
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
                          f"(relation[\"type\"=\"boundary\"][\"admin_level\"~\"9|10\"](area););out;")

        response = self.get_data(overpass_query)

        if response is None:
            print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
            pass

        boundaries = response["elements"]

        if len(boundaries) == 0:
            # Do another check if the boundary is a root boundary
            overpass_backup_query = f"[out:json];area[name=\"{answers['city']}\"];out;"

            response = self.get_data(overpass_backup_query)

            if response is None:
                print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
                pass

            boundaries = []

            for element in response["elements"]:
                if element["type"] == "area":
                    if element["tags"]["type"] == "boundary" and element["tags"]["admin_level"] in ("8", "9", "10"):
                        boundaries.append(element)

            if len(boundaries) == 0:
                print("Fehler: Es konnten keine passenden Daten gefunden werden!")
                pass

        sections = []
        city_section = {"name": answers["city"], "addresses": [], "objects": []}

        counter = 1

        for item in boundaries:
            streets = set()

            print(f"Lade {item['tags']['name']}")

            area_id = item['id'] if 3700000000 > item['id'] > 3600000000 else 3600000000 + item['id']

            if export_street_options[0] in answers["options"]:
                # Get all streets in the area
                overpass_street_query = (f"[out:json];area({area_id});"
                                         f"way[highway~\"^(motorway|trunk|primary|secondary|tertiary|unclassified|"
                                         f"residential|living_street|pedestrian)$\"][name](area);out;")

                street_response = self.get_data(overpass_street_query)
                if street_response is None:
                    print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
                    pass

                for way in street_response["elements"]:
                    streets.add(way["tags"]["name"])

            if export_street_options[1] in answers["options"]:
                # Get all parks in the area
                overpass_park_query = (f"[out:json];area({area_id});"
                                       f"(way[\"leisure\"=\"park\"](area);relation[\"leisure\"=\"park\"](area););out;")

                park_response = self.get_data(overpass_park_query)
                if park_response is None:
                    print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
                    pass
                for park in park_response["elements"]:
                    if "name" in park["tags"]:
                        if "access" in park["tags"] and park["tags"]["access"] == "private":
                            continue
                        else:
                            streets.add(park["tags"]["name"])

            if export_street_options[2] in answers["options"]:
                # Get all squares in the area
                overpass_square_query = (f"[out:json];area({area_id});(way[\"place\"=\"square\"](area);"
                                         f"relation[\"place\"=\"square\"](area););out;")

                square_response = self.get_data(overpass_square_query)
                if square_response is None:
                    print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
                    pass

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
                overpass_building_query = (f"[out:json];area({area_id});"
                                           f"(way[\"building\"][\"name\"][\"addr:street\"](area);"
                                           f"relation[\"building\"][\"name\"][\"addr:street\"](area););out;")

                buildings_response = self.get_data(overpass_building_query)
                if buildings_response is None:
                    print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
                    pass

                for building in buildings_response["elements"]:
                    street = next((a for a in city_section["addresses"]
                                   if
                                   a["name"] == building["tags"]["addr:street"] and a["area"] == item["tags"]["name"]),
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
