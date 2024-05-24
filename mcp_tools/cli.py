import inquirer

from mcp_tools.action import Action
from mcp_tools.export import ExportAction


def main() -> None:

    # Define all supported actions
    actions = [ExportAction(), Action("Anwendung beenden")]

    questions = [inquirer.List("task",
                               message="Welche Aktion soll ausgeführt werden?",
                               choices=[i.name for i in actions])]

    answers = inquirer.prompt(questions)

    # Get the selected action. It must be ensured, that all actions have unique names or this array will contain more
    # than one entry
    selected_action = [i for i in actions if i.name == answers["task"]]

    # Execute the selected action
    for i in selected_action:
        i.run()
