

class Action:

    def __init__(self, name: str):
        if name is None or len(name.strip()) == 0:
            raise ValueError("Name can't be none.")
        self.name = name

    def run(self) -> None:
        pass
