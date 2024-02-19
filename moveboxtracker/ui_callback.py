"""
user interface callback structure for moveboxtracker
"""
#    ui_callback.py - user interface callbacks for MoveBoxTracker
#    Copyright (C) 2023-2024 Ian Kluft
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.


class UIDataTable:
    """object to pass tabular data for display via UI callbacks"""

    def __init__(self, fields: list, rows: list):
        # get field names from list formatted from sqlite/DB-API Cursor.description()
        if not isinstance(fields, tuple) and not isinstance(fields, list):
            raise RuntimeError("UIDataTable: 'fields' must be list/tuple, got " + str(type(fields)))
        self.fields = []
        for entry in fields:
            if isinstance(entry, tuple):
                self.fields.append(entry[0])
            elif isinstance(entry, str):
                self.fields.append(entry)
            else:
                raise RuntimeError("unexpected parameter type for field entry: ", type(entry))

        # accept rows as list from sqlite/DB-API cur.fetchall()
        if not isinstance(rows, list):
            raise RuntimeError("UIDataTable: 'rows' must be a list, got " + str(type(rows)))
        self.rows = rows

    def get_fields(self) -> list:
        """read accessor for list of field names"""
        return self.fields

    def get_rows(self) -> list:
        """read accessor for list of row data"""
        return self.rows


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

    def display(self, **kwargs) -> None:
        """callback function which the database layer can use to display text or data tables"""
        try:
            result = self.display_cb(**kwargs)
        except Exception as e_info:  # pylint: disable="broad-except"
            self.error(f"display{kwargs} failed", exception=e_info)
            result = None
        return result

    def error(self, text: str, **kwargs) -> None:
        """callback function which the database layer can use to display errors"""
        return self.error_cb(text, **kwargs)
