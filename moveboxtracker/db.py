"""
database (model layer) routines for moveboxtracker
"""

import re
from pathlib import Path
from datetime import timezone, datetime
import hashlib
import mimetypes
import sqlite3
import dateutil.parser
from tzlocal import get_localzone
from xdg import BaseDirectory
from colorlookup import Color
from .ui_callback import UICallback, UIDataTable

# type alias for error strings
ErrStr = str

# globals
DATA_HOME = BaseDirectory.xdg_data_home  # XDG default data directory
LOCAL_TZ = get_localzone()
MBT_PKGNAME = "moveboxtracker"
MBT_SCHEMA_PRAGMAS = ["PRAGMA foreign_keys=ON;"]
MBT_SCHEMA = {  # moveboxtracker SQL schema, used by _init_db() method
    "batch_move": [
        "CREATE TABLE IF NOT EXISTS batch_move ("
        "id INTEGER PRIMARY KEY,"
        "timestamp datetime NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%SZ', 'now')),"
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
        "timestamp datetime NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%SZ', 'now'))"
        ")",
        "CREATE INDEX IF NOT EXISTS box_scan_id_index ON box_scan(id)",
    ],
    "image": [
        "CREATE TABLE IF NOT EXISTS image ("
        "id INTEGER PRIMARY KEY NOT NULL,"
        "image_file text UNIQUE NOT NULL,"
        "hash text UNIQUE NOT NULL,"
        "mimetype text,"
        "encoding text,"
        "description text,"
        "timestamp datetime NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%SZ', 'now'))"
        ");",
        "CREATE INDEX IF NOT EXISTS image_id_index ON image(id);",
    ],
    "item": [
        "CREATE TABLE IF NOT EXISTS item ("
        "id INTEGER PRIMARY KEY,"
        "box integer NOT NULL REFERENCES moving_box (id),"
        "description text NOT NULL,"
        "image integer REFERENCES image (id)"
        ")",
        "CREATE INDEX IF NOT EXISTS item_id_index ON item(id);",
    ],
    "location": [
        "CREATE TABLE IF NOT EXISTS location ("
        "id INTEGER PRIMARY KEY,"
        "name text UNIQUE NOT NULL"
        ")",
        "CREATE INDEX IF NOT EXISTS location_id_index ON location(id)",
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
        "image integer REFERENCES image (id)"
        ")",
        "CREATE INDEX IF NOT EXISTS moving_box_id_index ON moving_box(id)",
    ],
    "room": [
        "CREATE TABLE IF NOT EXISTS room ("
        "id INTEGER PRIMARY KEY,"
        "name text UNIQUE NOT NULL,"
        "color text NOT NULL"
        ")",
        "CREATE INDEX IF NOT EXISTS room_id_index ON room(id)",
    ],
    "uri_user": [
        "CREATE TABLE IF NOT EXISTS uri_user ("
        "id INTEGER PRIMARY KEY,"
        "name text UNIQUE NOT NULL"
        ")",
        "CREATE INDEX IF NOT EXISTS uri_user_id_index ON uri_user(id)",
    ],
}
DB_CLASS_TO_TABLE = {
    "MoveDbBatchMove": "batch_move",
    "MoveDbMovingBox": "moving_box",
    "MoveDbImage": "image",
    "MoveDbItem": "item",
    "MoveDbLocation": "location",
    "MoveDbMoveProject": "move_project",
    "MoveDbRoom": "room",
    "MoveDbBoxScan": "box_scan",
    "MoveDbURIUser": "uri_user",
}


class MoveBoxTrackerDB:
    """access to moving box database file"""

    @staticmethod
    def _data_home() -> Path:
        """return XDG_DATA_HOME-based app data path"""
        datahome_path = Path(DATA_HOME) / MBT_PKGNAME
        if not datahome_path.exists():
            datahome_path.mkdir(mode=0o770, parents=True, exist_ok=True)
        if not datahome_path.is_dir():
            raise RuntimeError(
                f"cannot create data storage: {datahome_path} exists but is not a directory"
            )
        return datahome_path

    def __init__(self, filename: str, data: dict = None, ui_cb: UICallback = None):
        # construct database path from relative or absolute path
        if Path(filename).exists() or Path(filename).is_absolute():
            self.filepath = Path(filename)
        else:
            self.filepath = MoveBoxTrackerDB._data_home() / filename
        # print(f"database file: {self.filepath}", file=sys.stderr)

        # save object with user interface callback functions
        # default should be saved too: None indicates UI not available
        self.ui_cb = ui_cb

        # create the directory for the database file if it doesn't exist
        db_dir = self.filepath.parent
        if not db_dir.is_dir():
            db_dir.mkdir(mode=0o770, parents=True, exist_ok=True)

        # create the directory for image files if it doesn't exist
        self.imgdir = self.filepath.parent / (str(self.filepath.stem) + "-images")
        if not self.imgdir.is_dir():
            self.imgdir.mkdir(mode=0o770, exist_ok=True)

        # initalize the database if it doesn't exist
        need_init = not self.filepath.exists()
        self.conn = sqlite3.connect(self.filepath)
        if need_init:
            self._init_db(data)

    def __del__(self):
        self.conn.close()

    def display(self, **kwargs) -> None:
        """proxy method which calls UI display callback function"""
        if self.ui_cb is None:
            raise RuntimeError("attempt to display with uninitialized UI")
        if "text" not in kwargs and "data" not in kwargs:
            raise RuntimeError("missing text or data parameters for display")
        if "text" in kwargs and "data" in kwargs:
            raise RuntimeError("display requires just one of text or data parameters, not both")
        return self.ui_cb.display(**kwargs)

    def error(self, text: str) -> None:
        """proxy method which calls UI display callback function"""
        if self.ui_cb is None:
            raise RuntimeError("attempt to display with uninitialized UI")
        return self.ui_cb.error(text)

    def _init_db(self, data: dict) -> None:
        """initialize database file from SQL schema statements"""
        # check required data fields if UI didn't privide a prompt-callback
        if self.ui_cb is None:
            if data is None:
                raise RuntimeError("data for move_project is needed to initialize a new database")
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
        self.conn.commit()

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

    def db_imgdir(self) -> Path:
        """get file path of SQLite database"""
        return self.imgdir

    def db_conn(self) -> sqlite3.Connection:
        """get sqlite connection for performing queries"""
        return self.conn

    def db_dump(self) -> None:
        """dump database contents to standard output"""
        for line in self.conn.iterdump():
            self.display(text=line)


class MoveDbRecord:
    """base class for moveboxtracker database record classes"""

    def __init__(self, mbt_db: MoveBoxTrackerDB):
        if self.__class__.__name__ not in DB_CLASS_TO_TABLE:
            raise RuntimeError(f"MoveDbRecord: class {self.__class__.__name__} is not recognized")
        self.mbt_db = mbt_db

    @classmethod
    def fields(cls):
        """return list of the table's fields"""
        if "field_data" not in vars(cls):
            class_name = cls.__name__
            raise NotImplementedError(f"{class_name} does not provide required field_data")
        field_data = vars(cls)["field_data"]
        return list(field_data.keys())

    @classmethod
    def required_fields(cls):
        """return list of the table's required fields"""
        if "field_data" not in vars(cls):
            class_name = cls.__name__
            raise NotImplementedError(f"{class_name} does not provide required field_data")
        req_fields = []
        field_data = vars(cls)["field_data"]
        for key in field_data.keys():
            if getattr(field_data[key], "required", False):
                req_fields.append(key)
        return req_fields

    @classmethod
    def check_missing_fields(cls, data: dict) -> list:
        """check required fields and return list of missing fields"""
        missing = []
        field_list = cls.required_fields()
        for key in field_list:
            if key not in data:
                missing.append(key)
        return missing

    @classmethod
    def check_allowed_fields(cls, data: dict) -> list:
        """check allowed fields and return list of invalid fields"""
        field_list = cls.fields()
        invalid = []
        for key in data:
            if key not in field_list:
                invalid.append(key)
        return invalid

    @classmethod
    def table_name(cls) -> str:
        """find database table name for the current class"""
        if cls.__name__ not in DB_CLASS_TO_TABLE:
            raise RuntimeError(f"MoveDbRecord.table_name(): class {cls.__name__} is not recognized")
        return DB_CLASS_TO_TABLE[cls.__name__]

    def prompt(self, table: str, field_prompts: dict) -> dict:
        """proxy method which calls UI prompt callback function"""
        if self.mbt_db.ui_cb is None:
            raise RuntimeError("attempt to prompt with uninitialized UI")
        return self.mbt_db.ui_cb.prompt(table, field_prompts)

    def display(self, **kwargs) -> None:
        """proxy method which calls UI display callback function"""
        if self.mbt_db.ui_cb is None:
            raise RuntimeError("attempt to display text with uninitialized UI")
        if "text" not in kwargs and "data" not in kwargs:
            raise RuntimeError("missing text or data parameters for display")
        if "text" in kwargs and "data" in kwargs:
            raise RuntimeError("display requires just one of text or data parameters, not both")
        return self.mbt_db.ui_cb.display(**kwargs)

    def error(self, text: str) -> None:
        """proxy method which calls UI error callback function"""
        if self.mbt_db.ui_cb is None:
            raise RuntimeError("attempt to display error with uninitialized UI")
        return self.mbt_db.ui_cb.error(text)

    def _prompt_missing_fields(self, data: dict) -> None:
        """prompt user for missing fields"""
        if self.mbt_db.ui_cb is None:
            return
        field_prompts = {}
        field_data = vars(self.__class__)["field_data"]
        table = self.__class__.table_name()
        for key in field_data.keys():
            if key not in data:
                if "prompt" in field_data[key]:
                    # use UI-provided callback to prompt the user for the missing data
                    field_prompts[key] = field_data[key]["prompt"]
        response = self.prompt(table, field_prompts)
        for key in response.keys():
            data[key] = response[key]

    def _interpolate_image(self, image_path: str, data: dict) -> None:
        """interpolate image file path into image record number"""
        if "image_file" in data and "hash" in data:
            return  # do not interpolate image twice
        image_db = MoveDbImage(self.mbt_db)
        (
            image_internal,
            image_mimetype,
            image_encoding,
            image_hash,
        ) = image_db.get_image_file(image_path)
        data["image_file"] = str(image_internal)
        data["mimetype"] = image_mimetype
        data["encoding"] = image_encoding
        data["hash"] = image_hash

    def _interpolate_color(self, color_name: str) -> str:
        """validate a color name or RGB value"""
        return Color(color_name).name.lower()

    def _interpolate_timestamp(self, timestamp: str) -> str:
        """validate timestamp format and convert from CLI's local time to db's GMT"""
        if timestamp == "now":
            ts_dt = datetime.now(tz=timezone.utc).replace(microsecond=0)
        else:
            ts_dt = dateutil.parser.isoparse(timestamp)
        if ts_dt.tzinfo is None or ts_dt.tzinfo.utcoffset(ts_dt) is None:
            ts_dt.replace(tzinfo=LOCAL_TZ)
        ts_dt_utc = ts_dt.astimezone(timezone.utc)
        return ts_dt_utc.strftime("%Y-%m-%d %H:%M:%SZ")

    def _interpolate_fields(self, data: dict) -> None:
        """interpolate foreign keys & image file paths into record numbers, validate color names"""
        field_data = vars(self.__class__)["field_data"]
        data_keys = list(data.keys())  # separate list because dict gets modified
        for key in data_keys:
            if (
                "references" in field_data[key]
                and not isinstance(data[key], int)
                and not re.fullmatch(r"^\d+$", data[key])
            ):
                # reference field value is not an integer - interpolate it via reference key
                field_id = field_data[key]["references"].get_or_create(self.mbt_db, data[key], data)
                data[key] = field_id
            if "interpolate" in field_data[key]:
                match field_data[key]["interpolate"]:
                    case "image":
                        # raises exception if image file doesn't exist or can't be read
                        self._interpolate_image(data[key], data)
                    case "color":
                        data[key] = self._interpolate_color(data[key])
                    case "timestamp":
                        data[key] = self._interpolate_timestamp(data[key])

    def _generate_fields(self, data: dict) -> None:
        """prompt user for missing fields"""
        field_data = vars(self.__class__)["field_data"]
        for key in field_data.keys():
            if key not in data:
                if "generate" in field_data[key]:
                    # use a specified function to generate the field
                    generate_func = field_data[key]["generate"]
                    if not callable(generate_func) and str(generate_func) in vars(self.__class__):
                        generate_func = vars(self.__class__)[generate_func]
                    data[key] = generate_func(self, data)

    def db_create(self, data: dict) -> int:
        """create a db record"""
        # check data field names are valid fields
        invalid = self.__class__.check_allowed_fields(data)
        if len(invalid) > 0:
            raise RuntimeError(f"invalid fields for table initialization: {invalid}")

        # prompt for missing fields if user interface provided a prompt callback
        self._prompt_missing_fields(data)

        # interpolate foreign keys, images & colors
        self._interpolate_fields(data)

        # auto-generate fields last because they could depend on other provided data
        self._generate_fields(data)

        # safety net against empty records (SQLite would flag a syntax error for "()" )
        if len(data) == 0:
            raise RuntimeError("cannot insert record with empty data")

        # insert record
        table = self.__class__.table_name()
        cur = self.mbt_db.conn.cursor()
        placeholder_list = []
        fields_list = data.keys()
        fields_str = (", ").join(fields_list)
        for key in fields_list:
            placeholder_list.append(f":{key}")
        placeholder_str = (", ").join(placeholder_list)
        sql_cmd = f"INSERT INTO {table} ({fields_str}) VALUES ({placeholder_str})"
        self.display(text=f"executing SQL [{sql_cmd}] with {data}")
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
        sql_cmd = f"SELECT * FROM {table} WHERE id == :id"
        self.display(text=f"executing SQL [{sql_cmd}] with {data}")
        cur.execute(sql_cmd, data)
        if cur.rowcount == 0:
            raise RuntimeError("SQL read failed")
        data_table = UIDataTable(fields=cur.description, rows=cur.fetchall())
        self.display(data=data_table)
        self.mbt_db.conn.commit()
        return 1  # if no exceptions raised by now, assume 1 record

    def db_update(self, data: dict) -> int:
        """update a db record by id"""

        # interpolate foreign keys, images & colors
        self._interpolate_fields(data)

        # auto-generate fields last because they could depend on other provided data
        self._generate_fields(data)

        # update record
        table = self.__class__.table_name()
        cur = self.mbt_db.conn.cursor()
        placeholder_list = []
        fields_list = data.keys()
        for key in fields_list:
            if key != "id":
                placeholder_list.append(f"{key} = :{key}")
        placeholder_str = (", ").join(placeholder_list)
        sql_cmd = f"UPDATE {table} SET {placeholder_str} WHERE id == :id"
        self.display(text=f"executing SQL [{sql_cmd}] with {data}")
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
        sql_cmd = f"DELETE FROM {table} WHERE id == :id"
        self.display(text=f"executing SQL [{sql_cmd}] with {data}")
        cur.execute(sql_cmd, data)
        row_count = cur.rowcount
        if row_count == 0:
            raise RuntimeError("SQL delete failed")
        self.mbt_db.conn.commit()
        return row_count

    def kv_search(self, key: str, value: str) -> str | None:
        """search for a key/value pair in this table, return record id"""
        table = self.__class__.table_name()
        cur = self.mbt_db.conn.cursor()
        sql_data = {key: value}
        sql_cmd = f"SELECT id FROM {table} WHERE {key} LIKE :{key}"
        self.display(text=f"executing SQL [{sql_cmd}] with {sql_data}")
        cur.execute(sql_cmd, sql_data)
        row = cur.fetchone()
        cur.close()
        if row is None:
            return None
        return row[0]

    def gen_primary_user(self, data: dict) -> str:
        """get primary user string from move project"""
        del data  # unused, provided to all "generate" handlers
        table = MoveDbMoveProject.table_name()
        cur = self.mbt_db.conn.cursor()
        sql_cmd = f"SELECT primary_user FROM {table} WHERE rowid == 1"
        self.display(text=f"executing SQL [{sql_cmd}]")
        cur.execute(sql_cmd)
        row = cur.fetchone()
        cur.close()
        return row[0]

    @classmethod
    def do_list(cls, mbt_db: MoveBoxTrackerDB, data: dict) -> ErrStr | None:
        """list batch records"""
        table = cls.table_name()
        cur = mbt_db.conn.cursor()
        sql_cmd = f"SELECT * FROM {table}"
        mbt_db.display(text=f"executing SQL [{sql_cmd}] with {data}")
        cur.execute(sql_cmd, data)
        if cur.rowcount == 0:
            return "SQL read failed"
        data_table = UIDataTable(fields=cur.description, rows=cur.fetchall())
        mbt_db.display(data=data_table)
        mbt_db.conn.commit()
        return None


class MoveDbImage(MoveDbRecord):
    """class to handle image records"""

    field_data = {
        "id": {},
        "image_file": {
            "required": True,
            "prompt": "image file path",
            "interpolate": "image",
        },
        "hash": {
            "required": True,
            "generate": "gen_hash",
        },  # forward reference as str
        "mimetype": {
            "generate": "gen_mimetype",
        },
        "encoding": {},
        "description": {"prompt": "image description"},
        "timestamp": {"interpolate": "timestamp"},
    }

    def _image_hash(self, image_path: Path) -> (str, bytes):
        """calculate SHA256 hash of file and return binary value"""
        hasher = hashlib.sha256()
        blocksize = 65536
        with image_path.open("rb") as img_file:
            while buf := img_file.read(blocksize):
                hasher.update(buf)
        return (hasher.hexdigest(), hasher.digest())

    def get_image_file(self, image_path: Path) -> (bytes, str):
        """get image file info, and app-controlled path to existing or new image file"""
        (image_hashstr, image_hash) = self._image_hash(image_path)
        image_internal = (
            self.mbt_db.db_imgdir() / (image_hashstr + "_" + image_path.name)
        ).resolve(strict=False)
        try:
            image_internal.symlink_to(image_path)
        except Exception as exc:
            raise RuntimeError(f"failed to symlink {image_internal} -> {image_path}") from exc
        (image_mimetype, image_encoding) = mimetypes.guess_type(image_path, strict=False)
        return (image_internal, image_mimetype, image_encoding, image_hash)

    @classmethod
    def get_or_create(cls, mbt_db: MoveBoxTrackerDB, value: str, data: dict) -> int:
        """return record number of image record matching path, or of newly-created record"""

        # read image and compute hash
        image_db = MoveDbImage(mbt_db)
        image_path = Path(value)
        if not image_path.exists():
            raise RuntimeError(f"image file {image_path} does not exist")

        (
            image_internal,
            image_mimetype,
            image_encoding,
            image_hash,
        ) = image_db.get_image_file(image_path)
        # if image is already in database, get record number based on hash
        image_id = image_db.kv_search(key="hash", value=image_hash)

        # if image wasn't found, create a new record for it
        if image_id is None:
            newrec_data = {}
            for key in cls.fields():
                if key in data and key != "id":
                    newrec_data[key] = data[key]
            newrec_data["image_file"] = str(image_internal)
            newrec_data["mimetype"] = image_mimetype
            newrec_data["encoding"] = image_encoding
            newrec_data["hash"] = image_hash
            image_id = image_db.db_create(newrec_data)
        return image_id

    def gen_hash(self, data: dict) -> str:
        """get hash from image file"""
        if "image_file" not in data:
            raise RuntimeError("image_file not found in query data - can't generate hash value")
        (_, image_hash) = self._image_hash(data["image_file"])
        data["hash"] = image_hash

    def gen_mimetype(self, data: dict) -> str:
        """get mimetype from image data"""
        if "mimetype" not in data:
            raise RuntimeError("mimetype not found in query data - can't generate value")
        data["mimetype"] = data["mimetype"]


class MoveDbLocation(MoveDbRecord):
    """class to handle location records"""

    field_data = {"id": {}, "name": {"required": True, "prompt": "location name"}}

    @classmethod
    def get_or_create(cls, mbt_db: MoveBoxTrackerDB, value: str, data: dict) -> int:
        """return record number of location record matching name, or of newly-created record"""
        del data  # unused

        # if location is already in database, get record number
        loc_db = cls(mbt_db)
        loc_id = loc_db.kv_search(key="name", value=value)

        # if location wasn't found, create a new record for it
        if loc_id is None:
            newrec_data = {}
            newrec_data["name"] = value
            loc_id = loc_db.db_create(newrec_data)
        return loc_id


class MoveDbBatchMove(MoveDbRecord):
    """class to handle batch_move records"""

    field_data = {
        "id": {},
        "timestamp": {"interpolate": "timestamp"},
        "location": {
            "required": True,
            "references": MoveDbLocation,
            "prompt": "move destination location",
        },
    }

    @classmethod
    def commit(cls, mbt_db: MoveBoxTrackerDB, data: dict) -> ErrStr | None:
        """commit a batch: change location of boxes in a batch to the batch's location"""
        if "id" not in data:
            return "id not specified for batch commit"

        # for boxes in batch, update each box to batch location
        batch_id = data["id"]
        batch_table = cls.table_name()
        scan_table = MoveDbBoxScan.table_name()
        box_table = MoveDbMovingBox.table_name()
        cur = mbt_db.conn.cursor()
        sql_data = {"batch": batch_id}
        sql_cmd = (
            f"UPDATE {box_table} AS box "
            + "SET location = batch.location "
            + f"FROM {batch_table} AS batch, {scan_table} AS scan "
            + "WHERE batch.id == :batch AND scan.batch == batch.id AND scan.box == box.id"
        )
        mbt_db.display(text=f"executing SQL [{sql_cmd}] with {sql_data}")
        cur.execute(sql_cmd, sql_data)
        count = cur.rowcount
        if count == 0:
            return "no records modified"
        mbt_db.conn.commit()
        cur.close()

        return None


class MoveDbRoom(MoveDbRecord):
    """class to handle room records"""

    field_data = {
        "id": {},
        "name": {"required": True, "prompt": "room name"},
        "color": {
            "required": True,
            "prompt": "room label color",
            "interpolate": "color",
        },
    }

    @classmethod
    def get_or_create(cls, mbt_db: MoveBoxTrackerDB, value: str, data: dict) -> int:
        """return record number of room record matching name, or of newly-created record"""

        # if room is already in database, get record number
        room_db = cls(mbt_db)
        room_id = room_db.kv_search(key="name", value=value)

        # if room wasn't found, create a new record for it
        if room_id is None:
            newrec_data = {}
            for key in cls.fields():
                if key in data:
                    newrec_data[key] = data[key]
            newrec_data["name"] = value
            room_id = room_db.db_create(newrec_data)
        return room_id


class MoveDbURIUser(MoveDbRecord):
    """class to handle uri_user records"""

    field_data = {
        "id": {},
        "name": {"required": True, "prompt": "URI user name/address"},
    }

    @classmethod
    def get_or_create(cls, mbt_db: MoveBoxTrackerDB, value: str, data: dict) -> int:
        """return record number of uri_user record matching name, or of newly-created record"""
        del data  # unused

        # if uri_user is already in database, get record number
        user_db = cls(mbt_db)
        user_id = user_db.kv_search(key="name", value=value)

        # if uri_user wasn't found, create a new record for it
        if user_id is None:
            newrec_data = {}
            newrec_data["name"] = value
            user_id = user_db.db_create(newrec_data)
        return user_id


class MoveDbMoveProject(MoveDbRecord):
    """class to handle mode_project records"""

    field_data = {
        "primary_user": {
            "required": True,
            "references": MoveDbURIUser,
            "prompt": "URI user name/address",
        },
        "title": {"required": True, "prompt": "project title"},
        "found_contact": {"required": True, "prompt": "label found/contact info"},
    }


class MoveDbMovingBox(MoveDbRecord):
    """class to handle moving_box records"""

    field_data = {
        "id": {},
        "location": {
            "required": True,
            "references": MoveDbLocation,
            "prompt": "box location",
        },
        "info": {"required": True, "prompt": "box description/info"},
        "room": {
            "required": True,
            "references": MoveDbRoom,
            "prompt": "box origin/destination room",
        },
        "user": {
            "required": True,
            "references": MoveDbURIUser,
            "generate": MoveDbRecord.gen_primary_user,
        },
        "image": {"references": MoveDbImage},
    }

    def box_label_data(self, box_id: int) -> dict:
        """return a dict of box data for generating its label"""

        # make sure we have a box id
        table = self.__class__.table_name()
        if box_id is None:
            raise RuntimeError(f"box label data request on {table} is missing 'id' parameter")

        # set up database connection
        cur = self.mbt_db.conn.cursor()
        cur.row_factory = sqlite3.Row

        # use box id to query for room & user data via their foreign keys
        data = {"id": box_id}
        sql_cmd = (
            "SELECT box.id AS box, room.name AS room, room.color AS color, "
            "user.name AS user, project.found_contact AS found "
            "FROM moving_box AS box, room, uri_user AS user, move_project AS project "
            "WHERE box.id == :id AND room.id == box.room "
            "AND user.id == box.user AND project.rowid == 1"
        )
        self.display(text=f"executing SQL [{sql_cmd}] with {data}")
        cur.execute(sql_cmd, data)
        if cur.rowcount == 0:
            raise RuntimeError("SQL read failed")
        row = cur.fetchone()

        # copy results to a dict and return it
        box_data = {}
        for key in row.keys():
            box_data[key] = row[key]
        cur.close()
        return box_data


class MoveDbBoxScan(MoveDbRecord):
    """class to handle box_scan records"""

    field_data = {
        "id": {},
        "box": {"required": True, "references": MoveDbMovingBox},
        "batch": {"required": True, "references": MoveDbBatchMove},
        "user": {
            "required": True,
            "references": MoveDbURIUser,
            "generate": MoveDbRecord.gen_primary_user,
        },
        "timestamp": {"interpolate": "timestamp"},
    }


class MoveDbItem(MoveDbRecord):
    """class to handle item records"""

    field_data = {
        "id": {},
        "box": {"required": True, "references": MoveDbMovingBox},
        "description": {"required": True, "prompt": "item description/info"},
        "image": {"references": MoveDbImage},
    }
