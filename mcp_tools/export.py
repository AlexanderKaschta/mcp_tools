import json

import inquirer
import requests

from mcp_tools.action import Action

OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"


def get_area_id(value):
    return value if 3700000000 > value > 3600000000 else 3600000000 + value


def get_data(query_string: str):
    request = requests.get(OVERPASS_API_URL, params={"data": query_string})

    try:
        request.raise_for_status()
    except requests.exceptions.HTTPError:
        return None

    return request.json()


class ExportAction(Action):

    def __init__(self):
        super().__init__("OpenStreetMaps-Export")

        # Define an output array
        self.output = []

    def run(self) -> None:
        export_street_options = ["Straßen", "Parks", "Plätze", "Stadien"]
        yes_no_options = ["Ja", "Nein"]

        location_question = [
            inquirer.Text("city", message="Welche Stadt soll exportiert werden?")
        ]

        location_answer = inquirer.prompt(location_question)

        if len(location_answer['city']) < 1:
            print("Fehler: Die Eingabe darf nicht leer sein!")
            return

        # Query all administrative boundaries with the provided name within the limit of Germany. The limit is required
        # to prevent confusion with simular named cites within e.g. the United States of America.
        location_query = (f"[out:json];"
                          f"area[name='Deutschland']->.de;area[name='{location_answer['city']}']->.loc;"
                          f"(relation['type'='boundary']['boundary'='administrative']"
                          f"['admin_level'~'6|7|8'](area.de)(area.loc););out;")

        print("Lade Daten ...\n")
        location_response = get_data(location_query)

        if location_response is None:
            print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
            return
        elif len(location_response["elements"]) == 0:
            print("Fehler: Kein Ort mit dem Namen gefunden!")
            return

        location_selection = []

        for item in location_response["elements"]:
            location_selection.append(f"{item["tags"]["name"]} (Admin-Level: {item["tags"]["admin_level"]})")

        location_question = [
            inquirer.List("city", message="Welche Stadt soll exportiert werden?", choices=location_selection)
        ]

        # Ask which of the found cities to export
        answer = inquirer.prompt(location_question)

        export_questions = [
            inquirer.Checkbox("options",
                              message="Was soll alles als Straße exportiert werden?",
                              choices=export_street_options),
            inquirer.List("buildings", message="Sollen auch Gebäude exportiert werden?", choices=yes_no_options)
        ]

        export_answers = inquirer.prompt(export_questions)

        location_index = location_selection.index(answer["city"])

        # Create a list of boundaries that should be exported
        boundaries = []

        # Get all level 8 admin boundaries from the selection.
        # If the current admin boundary is already of level 8, were are already done.
        # If the current admin boundary is of level < 8 and has entries of level 8, use all the level 8 entries.
        # If the current admin boundary if of level < 8 and has no entries of level 8, keep using the original boundary.
        boundary_selection_query = (
            f"[out:json];area({get_area_id(location_response["elements"][location_index]["id"])});"
            f"(relation['type'='boundary']['admin_level'~'8'](area););out;")

        boundary_selection_response = get_data(boundary_selection_query)
        if boundary_selection_response is None:
            print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
            return

        if len(boundary_selection_response["elements"]) == 0:
            # Add the current boundary to the selection
            boundaries.append(get_area_id(location_response["elements"][location_index]["id"]))
        else:
            # Iterate over all elements and add them
            for item in boundary_selection_response["elements"]:
                boundaries.append(get_area_id(item["id"]))

        # Iterate over all boundaries
        for boundary in boundaries:
            self.generate_city(boundary, export_street_options[0] in export_answers["options"],
                               export_street_options[1] in export_answers["options"],
                               export_street_options[2] in export_answers["options"],
                               export_street_options[3] in export_answers["options"],
                               export_answers["buildings"] == yes_no_options[0])

        # Write the data to a file
        self.export_to_file()

    def generate_city(self, area_id: int, export_streets: bool = False, export_parks: bool = False,
                      export_squares: bool = False, export_stadiums: bool = False,
                      export_buildings: bool = False) -> None:
        """
        Method to load the
        :param area_id: Area id of the OSM area to export, which must be of level 6, 7, or 8 without child nodes of
        level 7 or 8.
        :param export_streets:
        :param export_parks:
        :param export_squares:
        :param export_stadiums:
        :param export_buildings:
        :return:
        """

        # Check if the area id is with in the expected limits
        if not (3700000000 > area_id > 3600000000):
            raise ValueError("Invalid data provided!")

        # Create a counter
        counter = 1

        # Query the city
        city_query = f"[out:json];area({area_id});out;"
        city_response = get_data(city_query)

        if city_response is None:
            print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
            return

        print(f"Lade Daten für {city_response['elements'][0]['tags']['name']}")

        # Check if there are any city districts
        city_districts_query = (f"[out:json];area({area_id});"
                                f"(relation['type'='boundary']['admin_level'~'9|10'](area););out;")

        city_district_response = get_data(city_districts_query)
        if city_district_response is None:
            print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
            return

        if len(city_district_response["elements"]) == 0:
            # Export only the city without any city districts

            # Create set for the streets
            streets = set()

            city_section = {"name": city_response['elements'][0]['tags']['name'], "addresses": [], "objects": []}

            if export_streets:
                for element in self.get_streets(area_id):
                    streets.add(element)
            if export_squares:
                for element in self.get_squares(area_id):
                    streets.add(element)
            if export_parks:
                for element in self.get_parks(area_id):
                    streets.add(element)
            if export_stadiums:
                for element in self.get_stadiums(area_id):
                    streets.add(element)

            # Add the result into a dict
            for unique_way in streets:
                address = {"name": unique_way, "area": city_response['elements'][0]['tags']['name'], "id": counter}
                counter += 1
                city_section["addresses"].append(address)

            if export_buildings:
                # Export buildings
                overpass_building_query = (f"[out:json];area({area_id});"
                                           f"(way['building']['name']['addr:street'](area);"
                                           f"relation['building']['name']['addr:street'](area););out;")

                buildings_response = get_data(overpass_building_query)
                if buildings_response is None:
                    print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
                    pass

                for building in buildings_response["elements"]:
                    street = next((a for a in city_section["addresses"]
                                   if a["name"] == building["tags"]["addr:street"] and
                                   a["area"] == city_response['elements'][0]['tags']['name']),
                                  None)

                    if street is not None:
                        if "addr:housenumber" in building["tags"]:
                            mcp_object = {"name": building["tags"]["name"], "address": street["id"],
                                          "houseNumber": building["tags"]["addr:housenumber"], "description": ""}
                        else:
                            mcp_object = {"name": building["tags"]["name"], "address": street["id"], "houseNumber": "",
                                          "description": ""}

                        city_section["objects"].append(mcp_object)

            # Append the exported city to the output array
            self.output.append(city_section)
        else:
            # Export each city district separately
            for item in city_district_response["elements"]:

                print(f"Lade Daten für {item['tags']['name']}")

                # Create set for the streets
                streets = set()

                city_section = {"name": city_response['elements'][0]['tags']['name'], "addresses": [], "objects": []}

                if export_streets:
                    for element in self.get_streets(area_id):
                        streets.add(element)
                if export_squares:
                    for element in self.get_squares(area_id):
                        streets.add(element)
                if export_parks:
                    for element in self.get_parks(area_id):
                        streets.add(element)
                if export_stadiums:
                    for element in self.get_stadiums(area_id):
                        streets.add(element)

                # Add the result into a dict
                for unique_way in streets:
                    address = {"name": unique_way, "area": item['tags']['name'], "id": counter}
                    counter += 1
                    city_section["addresses"].append(address)

                if export_buildings:
                    # Export buildings
                    overpass_building_query = (f"[out:json];area({area_id});"
                                               f"(way['building']['name']['addr:street'](area);"
                                               f"relation['building']['name']['addr:street'](area););out;")

                    buildings_response = get_data(overpass_building_query)
                    if buildings_response is None:
                        print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
                        pass

                    for building in buildings_response["elements"]:
                        street = next((a for a in city_section["addresses"]
                                       if a["name"] == building["tags"]["addr:street"] and
                                       a["area"] == item['tags']['name']),
                                      None)

                        if street is not None:
                            if "addr:housenumber" in building["tags"]:
                                mcp_object = {"name": building["tags"]["name"], "address": street["id"],
                                              "houseNumber": building["tags"]["addr:housenumber"], "description": ""}
                            else:
                                mcp_object = {"name": building["tags"]["name"], "address": street["id"],
                                              "houseNumber": "",
                                              "description": ""}

                            city_section["objects"].append(mcp_object)

                # Append the exported city to the output array
                self.output.append(city_section)

    def get_streets(self, area_id: int) -> list[str]:
        # Define result array
        result = []

        # Get all streets in the area
        overpass_street_query = (f"[out:json];area({area_id});"
                                 f"way[highway~\"^(motorway|trunk|primary|secondary|tertiary|unclassified|"
                                 f"residential|living_street|pedestrian)$\"][name](area);out;")

        street_response = get_data(overpass_street_query)
        if street_response is None:
            print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
            pass

        for way in street_response["elements"]:
            result.append(way["tags"]["name"])
        # Return result
        return result

    def get_parks(self, area_id: int) -> list[str]:
        # Return parks
        result = []

        # Get all parks in the area
        overpass_park_query = (f"[out:json];area({area_id});"
                               f"(way[\"leisure\"=\"park\"](area);relation[\"leisure\"=\"park\"](area););out;")

        park_response = get_data(overpass_park_query)
        if park_response is None:
            print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
            pass
        for park in park_response["elements"]:
            if "name" in park["tags"]:
                if "access" in park["tags"] and park["tags"]["access"] == "private":
                    continue
                else:
                    result.append(park["tags"]["name"])
        return result

    def get_squares(self, area_id: int) -> list[str]:
        result = []

        # Get all squares in the area
        overpass_square_query = (f"[out:json];area({area_id});(way[\"place\"=\"square\"](area);"
                                 f"relation[\"place\"=\"square\"](area););out;")

        square_response = get_data(overpass_square_query)
        if square_response is None:
            print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
            pass

        for square in square_response["elements"]:
            if "name" in square["tags"]:
                result.append(square["tags"]["name"])
        return result

    def get_stadiums(self, area_id: int) -> list[str]:
        result = []

        # Get all stadiums in the area
        overpass_stadiums_query = f"[out:json];area({area_id});" \
                                  f"(way['leisure'='stadium'][!'building'](area);" \
                                  f"relation['leisure'='stadium'][!'building'](area););out;"

        stadium_response = get_data(overpass_stadiums_query)
        if stadium_response is None:
            print("Fehler: Fehlerhafter Status-Code der HTTP-Anfrage!")
            pass

        for stadium in stadium_response["elements"]:
            if "name" in stadium["tags"]:
                result.append(stadium["tags"]["name"])

        return result

    def export_to_file(self) -> None:
        # Check if there is an output
        if len(self.output) > 0:
            file = open("MCP-Orte-Adressen.json", "w", encoding="utf-8")
            file.write(json.dumps(self.output))
            file.close()

            print("Dateiexport fertig!")
        else:
            print("Nicht zu exportiere gefunden.")
