"""
database (model layer) routines for moveboxtracker
"""

import sys
from pathlib import Path
import sqlite3
from prettytable import from_db_cursor, SINGLE_BORDER
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
        "user integer NOT NULL REFERENCES uri_user (id),"
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
        "user integer NOT NULL REFERENCES uri_user (id),"
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
    "MoveDbBatchMove": "batch_move",
    "MoveDbMovingBox": "moving_box",
    "MoveDbItem": "item",
    "MoveDbLocation": "location",
    "MoveDbLog": "log",
    "MoveDbMoveProject": "move_project",
    "MoveDbRoom": "room",
    "MoveDbBoxScan": "box_scan",
    "MoveDbURIUser": "uri_user",
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
        missing = MoveDbMoveProject.check_missing_fields(data)
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
        user = MoveDbURIUser(self)
        user_data = {"name": data["primary_user"]}
        user_id = user.db_create(user_data)

        # create move_project record
        data["primary_user"] = user_id
        project = MoveDbMoveProject(self)
        project.db_create(data)

    def db_filepath(self) -> Path:
        """get file path of SQLite database"""
        return self.filepath

    def db_conn(self) -> sqlite3.Connection:
        """get sqlite connection for performing queries"""
        return self.conn

    def db_dump(self) -> None:
        """dump database contents to standard output"""
        for line in self.conn.iterdump():
            print(line)


class MoveDbRecord:
    """base class for moveboxtracker database record classes"""

    def __init__(self, mbt_db: MoveBoxTrackerDB):
        if self.__class__.__name__ not in DB_CLASS_TO_TABLE:
            raise RuntimeError(
                f"MoveDbRecord: class {self.__class__.__name__} is not recognized"
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
                f"MoveDbRecord.table_name(): class {cls.__name__} is not recognized"
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
        print(f"executing SQL [{sql_cmd}] with {data}", file=sys.stderr)
        cur.execute(sql_cmd, data)
        if cur.rowcount == 0:
            raise RuntimeError("SQL insert failed")
        row_id = cur.lastrowid
        self.mbt_db.conn.commit()
        return row_id

    def db_read(self, data: dict) -> int:
        """read a db record by id"""

        # read record
        table = self.__class__.table_name()
        cur = self.mbt_db.conn.cursor()
        if "id" not in data:
            raise RuntimeError(f"read requested on {table} is missing 'id' parameter")
        sql_cmd = f"SELECT * FROM {table} WHERE id = :id"
        print(f"executing SQL [{sql_cmd}] with {data}", file=sys.stderr)
        cur.execute(sql_cmd, data)
        if cur.rowcount == 0:
            raise RuntimeError("SQL read failed")
        text_table = from_db_cursor(cur)
        text_table.set_style(SINGLE_BORDER)
        print(text_table)
        self.mbt_db.conn.commit()
        return 1  # if no exceptions raised by now, assume 1 record

    def db_update(self, data: dict) -> int:
        """update a db record by id"""

        # verify field data is not empty
        table = self.__class__.table_name()
        if len(data) == 0:
            raise RuntimeError(f"no data fields provided for {table} record update")

        # check data field names are valid fields
        invalid = self.__class__.check_allowed_fields(data)
        if len(invalid) > 0:
            raise RuntimeError(f"invalid fields for table initialization: {invalid}")

        # update record
        cur = self.mbt_db.conn.cursor()
        placeholder_list = []
        fields_list = data.keys()
        for key in fields_list:
            if key != "id":
                placeholder_list.append(f"{key} = :{key}")
        placeholder_str = (", ").join(placeholder_list)
        sql_cmd = f"UPDATE {table} SET {placeholder_str} WHERE id = :id"
        print(f"executing SQL [{sql_cmd}] with {data}", file=sys.stderr)
        cur.execute(sql_cmd, data)
        row_count = cur.rowcount
        if row_count == 0:
            raise RuntimeError("SQL update failed")
        self.mbt_db.conn.commit()
        return row_count

    def db_delete(self, data: dict) -> int:
        """delete a db record by id"""

        # delete record
        table = self.__class__.table_name()
        cur = self.mbt_db.conn.cursor()
        if "id" not in data:
            raise RuntimeError(f"delete requested on {table} is missing 'id' parameter")
        sql_cmd = f"DELETE FROM {table} WHERE id = :id"
        print(f"executing SQL [{sql_cmd}] with {data}", file=sys.stderr)
        cur.execute(sql_cmd, data)
        row_count = cur.rowcount
        if row_count == 0:
            raise RuntimeError("SQL delete failed")
        self.mbt_db.conn.commit()
        return row_count


class MoveDbBatchMove(MoveDbRecord):
    """class to handle batch_move records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "timestamp", "location"]


class MoveDbMovingBox(MoveDbRecord):
    """class to handle moving_box records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "location", "info", "room", "user", "image"]

    def box_label_data(self, box_id: int) -> dict:
        """return a dict of box data for generating its label"""

        # make sure we have a box id
        table = self.__class__.table_name()
        if box_id is None:
            raise RuntimeError(
                f"box label data request on {table} is missing 'id' parameter"
            )

        # set up database connection
        cur = self.mbt_db.conn.cursor()
        cur.row_factory = sqlite3.Row

        # use box id to query for room, location & user data via their foreign keys
        data = {"id": box_id}
        sql_cmd = (
            "SELECT box.id AS box, room.name AS room, room.color AS color, "
            "location.name AS location, user.name AS user, project.found_contact AS found "
            "FROM moving_box AS box, room, location, uri_user AS user, move_project AS project "
            "WHERE box.id = :id AND room.id = box.room AND location.id = box.location "
            "AND user.id = box.user AND project.rowid = 1"
        )
        print(f"executing SQL [{sql_cmd}] with {data}", file=sys.stderr)
        cur.execute(sql_cmd, data)
        if cur.rowcount == 0:
            raise RuntimeError("SQL read failed")
        row = cur.fetchone()

        # copy results to a dict and return it
        box_data = {}
        for key in row.keys():
            box_data[key] = row[key]
        return box_data


class MoveDbItem(MoveDbRecord):
    """class to handle item records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "box", "description", "image"]


class MoveDbLocation(MoveDbRecord):
    """class to handle location records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "name"]


class MoveDbLog(MoveDbRecord):
    """class to handle log records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "table_name", "field_name", "old", "new", "timestamp"]


class MoveDbMoveProject(MoveDbRecord):
    """class to handle mode_project records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["primary_user", "title", "found_contact"]


class MoveDbRoom(MoveDbRecord):
    """class to handle room records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "name", "color"]


class MoveDbBoxScan(MoveDbRecord):
    """class to handle box_scan records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "box", "batch", "user", "timestamp"]


class MoveDbURIUser(MoveDbRecord):
    """class to handle uri_user records"""

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        return ["id", "name"]
