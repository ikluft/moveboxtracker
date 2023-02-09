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
MBT_SCHEMA_PRAGMAS = ["PRAGMA foreign_keys=ON;"]
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
        "id INTEGER PRIMARY KEY,"
        "box integer NOT NULL REFERENCES moving_box (id),"
        "batch integer NOT NULL REFERENCES batch_move (id),"
        "user integer NOT NULL REFERENCES url_user (id),"
        "timestamp datetime NOT NULL"
        ")",
        "CREATE INDEX IF NOT EXISTS box_scan_id_index ON box_scan(id)",
    ],
    "item": [
        "CREATE TABLE IF NOT EXISTS item ("
        "id INTEGER PRIMARY KEY,"
        "box integer NOT NULL REFERENCES moving_box (id),"
        "description text NOT NULL,"
        "image blob"
        ")",
        "CREATE INDEX IF NOT EXISTS item_id_index  ON item(id);",
    ],
    "location": [
        "CREATE TABLE IF NOT EXISTS location ("
        "id INTEGER PRIMARY KEY,"
        "name text NOT NULL"
        ")",
        "CREATE INDEX IF NOT EXISTS location_id_index  ON location(id)",
    ],
    "log": [
        "CREATE TABLE IF NOT EXISTS log ("
        "id INTEGER PRIMARY KEY,"
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
        "id INTEGER PRIMARY KEY,"
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
        "id INTEGER PRIMARY KEY,"
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
DB_CLASS_TO_TABLE = {
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

    def __init__(self, filename, data: dict = ...):
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
            self._init_db(data)

    def __del__(self):
        self.conn.close()

    def _init_db(self, data: dict) -> None:
        """initialize database file from SQL schema statements"""
        # check required data fields
        if data is None:
            raise RuntimeError(
                "data for move_project is needed to initialize a new database"
            )
        missing = MBT_DB_MoveProject.check_missing_fields(data)
        if len(missing) > 0:
            raise RuntimeError(f"missing data for table initialization: {missing}")

        # run SQLite pragmas, if any were defined
        for sql_line in MBT_SCHEMA_PRAGMAS:
            self.conn.execute(sql_line)
        self.conn.commit()

        # set up database schema
        with self.conn:
            for schema_lines in MBT_SCHEMA.values():
                for sql_line in schema_lines:
                    self.conn.execute(sql_line)

        # populate initial records from provided data
        # create uri_user record first because move_project refers to it
        user = MBT_DB_URIUser(self)
        user_data = {"name": data["primary_user"]}
        user_id = user.db_create(user_data)

        # create move_project record
        data["primary_user"] = user_id
        project = MBT_DB_MoveProject(self)
        project.db_create(data)

    def db_filepath(self) -> Path:
        """get file path of SQLite database"""
        return self.filepath

    def db_conn(self) -> sqlite3.Connection:
        """get sqlite connection for performing queries"""
        return self.conn


class MBT_DB_Record:
    """base class for moveboxtracker database record classes"""

    def __init__(self, mbt_db: MoveBoxTrackerDB):
        if self.__class__.__name__ not in DB_CLASS_TO_TABLE:
            raise RuntimeError(
                f"MBT_DB_Record: class {self.__class__.__name__} is not recognized"
            )
        self.mbt_db = mbt_db

    @classmethod
    def fields(cls):
        """subclasses must override this to return a list of the table's fields"""
        raise NotImplementedError

    @classmethod
    def check_missing_fields(cls, data: dict) -> list:
        """check required fields and return list of missing fields"""
        missing = []
        for key in cls.fields():
            if key not in data:
                missing.append(key)
        return missing

    @classmethod
    def check_allowed_fields(cls, data: dict) -> list:
        """check allowed fields and return list of invalid fields"""
        fields = cls.fields()
        invalid = []
        for key in data:
            if key not in fields:
                invalid.append(key)
        return invalid

    @classmethod
    def table_name(cls) -> str:
        """find database table name for the current class"""
        if cls.__name__ not in DB_CLASS_TO_TABLE:
            raise RuntimeError(
                f"MBT_DB_Record.table_name(): class {cls.__name__} is not recognized"
            )
        return DB_CLASS_TO_TABLE[cls.__name__]

    def db_create(self, data: dict) -> int:
        """create a db record"""

        # verify field data is not empty
        table = self.__class__.table_name()
        if len(data) == 0:
            raise RuntimeError(f"no data fields provided for new {table} record")

        # check data field names are valid fields
        invalid = self.__class__.check_allowed_fields(data)
        if len(invalid) > 0:
            raise RuntimeError(f"invalid fields for table initialization: {invalid}")

        # insert record
        cur = self.mbt_db.conn.cursor()
        placeholder_list = []
        fields_list = data.keys()
        fields_str = (", ").join(fields_list)
        for key in fields_list:
            placeholder_list.append(f":{key}")
        placeholder_str = (", ").join(placeholder_list)
        sql_cmd = f"INSERT INTO {table} ({fields_str}) VALUES ({placeholder_str})"
        print(f"executing SQL [{sql_cmd} ] with {data}", file=sys.stderr)
        cur.execute(sql_cmd, data)
        if cur.rowcount == 0:
            raise RuntimeError("SQL insert failed")
        new_id = cur.lastrowid
        self.mbt_db.conn.commit()
        return new_id

    def db_read(self, data: dict) -> list:
        """read a db record"""
        raise NotImplementedError("db_read not implemented")

    def db_update(self, data: dict) -> int:
        """update a db record"""
        raise NotImplementedError("db_update not implemented")

    def db_delete(self, data: dict) -> int:
        """delete a db record"""
        raise NotImplementedError("db_delete not implemented")


class MBT_DB_BatchMove(MBT_DB_Record):
    """class to handle batch_move records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "timestamp", "location"]


class MBT_DB_MovingBox(MBT_DB_Record):
    """class to handle moving_box records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "location", "info", "room", "user", "image"]


class MBT_DB_Item(MBT_DB_Record):
    """class to handle item records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "box", "description", "image"]


class MBT_DB_Location(MBT_DB_Record):
    """class to handle location records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "name"]


class MBT_DB_Log(MBT_DB_Record):
    """class to handle log records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "table_name", "field_name", "old", "new", "timestamp"]


class MBT_DB_MoveProject(MBT_DB_Record):
    """class to handle mode_project records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["primary_user", "title", "found_contact"]


class MBT_DB_Room(MBT_DB_Record):
    """class to handle room records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "name", "color"]


class MBT_DB_BoxScan(MBT_DB_Record):
    """class to handle box_scan records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "box", "batch", "user", "timestamp"]


class MBT_DB_URIUser(MBT_DB_Record):
    """class to handle uri_user records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "name"]
