"""
user interface callback structure for moveboxtracker
"""


class UICallback:
    """user interface callback structure for moveboxtracker"""

    def __init__(self, prompt_cb: callable, display_cb: callable, error_cb: callable):
        # check and store prompt callback function
        if not callable(prompt_cb):
            raise RuntimeError("prompt callback is not a callable type")
        self.prompt_cb = prompt_cb

        # check and store display callback function
        if not callable(display_cb):
            raise RuntimeError("display callback is not a callable type")
        self.display_cb = display_cb

        # check and store error callback function
        if not callable(error_cb):
            raise RuntimeError("error callback is not a callable type")
        self.error_cb = error_cb

    def prompt(self, table: str, field_prompts: dict) -> dict:
        """callback function which the database layer can use to prompt for data fields"""
        try:
            result = self.prompt_cb(table, field_prompts)
        except Exception as e_info:  # pylint: disable="broad-except"
            self.error("prompt(" + (",".join(field_prompts.keys)) + ") failed", exception=e_info)
            result = None
        return result

    def display(self, text: str) -> None:
        """callback function which the database layer can use to display text"""
        try:
            result = self.display_cb(text)
        except Exception as e_info:  # pylint: disable="broad-except"
            self.error(f"display{text} failed", exception=e_info)
            result = None
        return result

    def error(self, text: str, **kwargs) -> None:
        """callback function which the database layer can use to display errors"""
        return self.error_cb(text, **kwargs)
