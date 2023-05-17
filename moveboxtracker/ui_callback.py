"""
user interface callback structure for moveboxtracker
"""


class UICallback:
    """user interface callback structure for moveboxtracker"""

    def __init__(self, prompt_cb: callable, display_cb: callable):
        # check and store prompt callback function
        if not callable(prompt_cb):
            raise RuntimeError("prompt callback is not a callable type")
        self.prompt_cb = prompt_cb

        # check and store display callback function
        if not callable(display_cb):
            raise RuntimeError("display callback is not a callable type")
        self.display_cb = display_cb

    def prompt(self, table: str, field_prompts: dict) -> dict:
        """callback function which the database layer can use to prompt for data fields"""
        return self.prompt_cb(table, field_prompts)

    def display(self, text: str) -> str | None:
        """callback function which the database layer can use to display text"""
        return self.display_cb(text)
