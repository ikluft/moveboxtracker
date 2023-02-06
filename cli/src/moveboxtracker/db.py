"""
database (model layer) routines for moveboxtracker
"""

from pathlib import Path
from sqlalchemy import create_engine, text
from xdg import BaseDirectory

# globals
data_home = BaseDirectory.xdg_data_home  # XDG default data directory
mbt_schema = {  # moveboxtracker SQL schema, used by _init_db() method
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


class DBMovingBox:
    """moving box database access"""

    def __init__(self, filename):
        self.filepath = Path(f"{data_home}/{filename}")
        need_init = not self.filepath.exists()
        self.engine = create_engine("sqlite+pysqlite://" + str(self.filepath))
        if need_init:
            self._init_db()
        # TODO

    def _init_db(self) -> None:
        """initialize database file from SQL schema statements"""
        with self.engine.connect() as conn:
            for table_name in mbt_schema.items():
                for sql_line in mbt_schema[table_name]:
                    conn.execute(text(sql_line))
