"""
database (model layer) routines for moveboxtracker
"""

import sys
from pathlib import Path
import sqlite3
from xdg import BaseDirectory

# globals
DATA_HOME = BaseDirectory.xdg_data_home  # XDG default data directory
MBT_PKGNAME = "moveboxtracker"
MBT_SCHEMA = {  # moveboxtracker SQL schema, used by _init_db() method
    "batch_move": [
        "CREATE TABLE IF NOT EXISTS batch_move ("
        "id INTEGER PRIMARY KEY,"
        "timestamp datetime NOT NULL,"
        "location integer NOT NULL REFERENCES location (id)"
        ")",
        "CREATE INDEX IF NOT EXISTS batch_move_id_index ON batch_move(id)",
    ],
    "box_scan": [
        "CREATE TABLE IF NOT EXISTS box_scan ("
        "id integer INTEGER PRIMARY KEY,"
        "box integer NOT NULL REFERENCES moving_box (id),"
        "batch integer NOT NULL REFERENCES batch_move (id),"
        "user integer NOT NULL REFERENCES url_user (id),"
        "timestamp datetime NOT NULL"
        ")",
        "CREATE INDEX IF NOT EXISTS box_scan_id_index ON box_scan(id)",
    ],
    "item": [
        "CREATE TABLE IF NOT EXISTS item ("
        "id integer INTEGER PRIMARY KEY,"
        "box integer NOT NULL REFERENCES moving_box (id),"
        "description text NOT NULL,"
        "image blob"
        ")",
        "CREATE INDEX IF NOT EXISTS item_id_index  ON item(id);",
    ],
    "location": [
        "CREATE TABLE IF NOT EXISTS location ("
        "id integer INTEGER PRIMARY KEY,"
        "name text NOT NULL"
        ")",
        "CREATE INDEX IF NOT EXISTS location_id_index  ON location(id)",
    ],
    "log": [
        "CREATE TABLE IF NOT EXISTS log ("
        "id integer INTEGER PRIMARY KEY,"
        "table_name text NOT NULL ,"
        "field_name text NOT NULL ,"
        "old text,"
        "new text,"
        "timestamp datetime NOT NULL"
        ")",
        "CREATE INDEX IF NOT EXISTS log_id_index  ON log(id)",
    ],
    "move_project": [
        "CREATE TABLE IF NOT EXISTS move_project ("
        "primary_user integer NOT NULL REFERENCES uri_user (id),"
        "title text NOT NULL,"
        "found_contact text NOT NULL"
        ")"
    ],
    "moving_box": [
        "CREATE TABLE IF NOT EXISTS moving_box ("
        "id integer INTEGER PRIMARY KEY,"
        "location integer NOT NULL REFERENCES location (id),"
        "info text NOT NULL ,"
        "room integer NOT NULL REFERENCES room (id),"
        "user integer NOT NULL REFERENCES url_user (id),"
        "image blob"
        ")",
        "CREATE INDEX IF NOT EXISTS moving_box_id_index  ON moving_box(id)",
    ],
    "room": [
        "CREATE TABLE IF NOT EXISTS room ("
        "id integer INTEGER PRIMARY KEY,"
        "name text NOT NULL,"
        "color text NOT NULL"
        ")",
        "CREATE INDEX IF NOT EXISTS room_id_index  ON room(id)",
    ],
    "uri_user": [
        "CREATE TABLE IF NOT EXISTS uri_user ("
        "id INTEGER PRIMARY KEY,"
        "name text NOT NULL"
        ")",
        "CREATE INDEX IF NOT EXISTS uri_user_id_index ON uri_user(id)",
    ],
}
class_to_table = {
    "MBT_DB_BatchMove": "batch_move",
    "MBT_DB_MovingBox": "moving_box",
    "MBT_DB_Item": "item",
    "MBT_DB_Location": "location",
    "MBT_DB_Log": "log",
    "MBT_DB_MoveProject": "move_project",
    "MBT_DB_Room": "room",
    "MBT_DB_BoxScan": "box_scan",
    "MBT_DB_URIUser": "uri_user",
}


class MoveBoxTrackerDB:
    """access to moving box database file"""

    def __init__(self, filename):
        # construct database path from relative or absolute path
        if Path(filename).is_absolute():
            self.filepath = Path(filename)
        else:
            self.filepath = Path(f"{DATA_HOME}/{MBT_PKGNAME}/{filename}")
        # print(f"database file: {self.filepath}", file=sys.stderr)

        # create the directory for the database file if it doesn't exist
        db_dir = self.filepath.parent
        if not db_dir.is_dir():
            db_dir.mkdir(
                mode=0o770, parents=True, exist_ok=True
            )  # create parent directory

        # initalize the database if it doesn't exist
        need_init = not self.filepath.exists()
        self.conn = sqlite3.connect(self.filepath)
        if need_init:
            self._init_db()

    def _init_db(self) -> None:
        """initialize database file from SQL schema statements"""
        with self.conn:
            for schema_lines in MBT_SCHEMA.values():
                for sql_line in schema_lines:
                    self.conn.execute(sql_line)
        self.conn.close()

    def db_filepath(self) -> Path:
        """get file path of SQLite database"""
        return self.filepath

    def db_conn(self) -> sqlite3.Connection:
        """get sqlite connection for performing queries"""
        return self.conn


class MBT_DB_Table:
    """base class for moveboxtracker database table classes"""

    def __init__(self, mbt_db: MoveBoxTrackerDB):
        self.mbt_db = mbt_db
        if self.__class__.__name__ not in class_to_table:
            raise Exception(
                f"MBT_DB_Table: class {self.__class__.__name__} is not recognized"
            )
        self.table = class_to_table[self.__class__.__name__]


class MBT_DB_BatchMove(MBT_DB_Table):
    """class to handle batch_move records"""


class MBT_DB_MovingBox(MBT_DB_Table):
    """class to handle moving_box records"""


class MBT_DB_Item(MBT_DB_Table):
    """class to handle item records"""


class MBT_DB_Location(MBT_DB_Table):
    """class to handle location records"""


class MBT_DB_Log(MBT_DB_Table):
    """class to handle log records"""


class MBT_DB_MoveProject(MBT_DB_Table):
    """class to handle mode_project records"""


class MBT_DB_Room(MBT_DB_Table):
    """class to handle room records"""


class MBT_DB_BoxScan(MBT_DB_Table):
    """class to handle box_scan records"""


class MBT_DB_URIUser(MBT_DB_Table):
    """class to handle uri_user records"""
