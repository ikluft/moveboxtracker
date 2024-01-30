"""
command-line interface for moveboxtracker

usage: moveboxtracker <cmd> args

operations
    init [--key=value ...]  initialize new database
    label box_id ...        print label(s) for specified box ids, start-end ranges accepted
    merge|ingest db_file    merge in an external SQLite database file, from another device
    destsign room_name      print a sign for what boxes to unload in a room
    db                      perform database operations

database operations (subcommands of db subcommand)
    batch | batch_move      batch/group of moving boxes
    box | moving_box        moving box including label info
    image                   images for boxes or items
    item                    item inside a box
    location                location where boxes may be
    project | move_project  overall move project info
    room                    room at origin & destination
    scan | box_scan         box scan event on move to new location
    user | uri_user         user who owns database or performs a box scan

The "db" subcommand takes one of the following "CRUD" operation arguments:
    create                  id --key=value [--key=value ...]
    read                    id
    update                  id --key=value [--key=value ...]
    delete                  id
"""

import os
import re
import sys
import warnings
import argparse
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
import lib_programname
from prettytable import PrettyTable, SINGLE_BORDER
from . import __version__
from .ui_callback import UICallback, UIDataTable
from .db import (
    MoveDbRecord,
    MoveBoxTrackerDB,
    MoveDbBatchMove,
    MoveDbMovingBox,
    MoveDbImage,
    MoveDbItem,
    MoveDbLocation,
    MoveDbMoveProject,
    MoveDbRoom,
    MoveDbBoxScan,
    MoveDbURIUser,
)
from .printable import MoveBoxLabel, MoveBoxDestSign

# manage table names used by CLI and by database classes
# Shorter names are preferred for a CLI. Descriptive names are preferred for an SQL schema.
# And some names, such as "box", are prohibited in an SQL schema due to conflicts.
# The CLI layer knows the CLI names. The CLI knows the class names for the database layer.
# The database classes know their schema names.
CLI_TO_DB_CLASS = {
    "batch": MoveDbBatchMove,
    "box": MoveDbMovingBox,
    "image": MoveDbImage,
    "item": MoveDbItem,
    "location": MoveDbLocation,
    "project": MoveDbMoveProject,
    "room": MoveDbRoom,
    "scan": MoveDbBoxScan,
    "user": MoveDbURIUser,
}

# type alias for error strings
ErrStr = str

# package and program name
PKG_NAME = "moveboxtracker"
PROG_NAME = (
    Path(sys.modules["__main__"].__file__).name
    if hasattr(sys.modules["__main__"], "__file__")
    else lib_programname.get_path_executed_script().name
)

# database record CLI action handler functions
CLI_ACTION = {
    "batch": {
        "commit": "_do_batch_commit",
        "list": "_do_list",
    },
    "box": {
        "list": "_do_list",
    },
    "image": {
        "list": "_do_list",
    },
    "item": {
        "list": "_do_list",
    },
    "location": {
        "list": "_do_list",
    },
    "project": {
        "list": "_do_list",
    },
    "room": {
        "list": "_do_list",
    },
    "scan": {
        "list": "_do_list",
        "boxes": "_do_scan_boxes",
    },
    "user": {
        "list": "_do_list",
    },
}


def _get_version():
    """display version"""
    if __version__ is not None:
        ver = __version__
    else:
        try:
            ver = f"{PKG_NAME} " + str(version(PKG_NAME))
        except PackageNotFoundError:
            ver = f"{PKG_NAME} version not available in development environment"
    return ver


def _args_to_data(args: dict, fields: list) -> dict:
    """create a query data map structure from fields in args"""
    result = {}
    omit_id = args.get("omit_id") or args.get("op") == "create"  # omit 'id'
    for key in fields:
        if key == "id" and omit_id:
            continue
        if key in args:
            if args[key] is None:
                continue
            result[key] = args[key]
    return result


def cli_prompt(table: str, field_prompts: dict) -> dict:
    """callback function which the database layer can use to prompt for data fields"""
    result = {}
    total_prompts = len(field_prompts)
    count = 1
    for field, prompt in field_prompts.items():
        input_value = input(f"({table} {count}/{total_prompts}) Enter {prompt}:")
        if len(input_value) > 0:
            result[field] = input_value
        count += 1
    return result


def cli_display(**kwargs) -> None:
    """callback function which the database layer can use to display on the UI"""
    if "text" in kwargs:
        print(kwargs["text"], file=sys.stdout)
    elif "data" in kwargs:
        # display tabular data with PrettyTable
        if not isinstance(kwargs["data"], UIDataTable):
            raise RuntimeError("internal error: display data parameter is not a UIDataTable")
        text_table = PrettyTable()
        text_table.field_names = kwargs["data"].get_fields()
        text_table.add_rows(kwargs["data"].get_rows())
        text_table.set_style(SINGLE_BORDER)
        text_table.left_padding_width = 0
        text_table.right_padding_width = 0
        print(text_table)


def cli_error(text: str, **kwargs) -> None:
    """callback function which the database layer can use to display an error on the UI"""
    if "exception" in kwargs:
        print(f"exception {kwargs['exception']}: {text}", file=sys.stderr)
    else:
        print(text, file=sys.stderr)


def _get_db_file(args: dict) -> Path | None:
    """get default database file path from environment"""
    if "db_file" in args and args["db_file"] is not None:
        return Path(args["db_file"])
    if "MBT_DB_FILE" in os.environ:
        return Path(os.environ["MBT_DB_FILE"])
    return None


def _expand_id_list(id_list: list) -> list:
    """expand list of strings with record ids and ranges of ids into a list of integer ids"""
    ids = []
    for id_num in id_list:
        # regular expression check for start-end range of box ids
        match = re.fullmatch(r"^(\d+)-(\d+)$", str(id_num))
        if match:
            # process start-end range of box ids
            start, end = match.groups()
            for box_num in range(int(start), int(end) + 1):  # +1 so last item in range is included
                ids.append(box_num)
            continue

        # regular expression check for simple integer
        match = re.fullmatch(r"^(\d+)$", str(id_num))
        if match:
            # process a single box id
            id_match = match.group(1)
            ids.append(int(id_match))
            continue

        # unrecognized string
        warnings.warn(f"skipped unrecognized integer/range {id_num}")
    return ids


def _expand_room_list(room_list: list) -> list:
    """expand list of strings with room names, record ids or id ranges into list of integer ids"""
    ids = []
    for room_param in room_list:
        # regular expression check for start-end range of room ids
        match = re.fullmatch(r"^(\d+)-(\d+)$", str(room_param))
        if match:
            # process start-end range of room ids
            start, end = match.groups()
            for room_num in range(int(start), int(end) + 1):  # +1 so last item in range is included
                ids.append(room_num)
            continue

        # regular expression check for simple integer
        match = re.fullmatch(r"^(\d+)$", str(room_param))
        if match:
            # process a single room id
            id_match = match.group(1)
            ids.append(int(id_match))
            continue

        # search for room by name
        # TODO

        # unrecognized string
        warnings.warn(f"skipped unrecognized room name/id/range {room_param}")
    return ids


def _do_init(args: dict, ui_cb: UICallback) -> ErrStr | None:
    """initialize new moving box database"""
    db_file = _get_db_file(args)
    if db_file is None:
        return "database file not specified"
    data = _args_to_data(args, MoveDbMoveProject.fields())
    db_obj = MoveBoxTrackerDB(db_file, data, ui_cb=ui_cb)
    if not isinstance(db_obj, MoveBoxTrackerDB):
        return "database initialization failed"
    return None


def _do_batch_commit(table_class, db_obj: MoveBoxTrackerDB, **kwargs) -> ErrStr | None:
    """change location of boxes in a batch to indicate the batch was moved as a group"""
    if table_class is not MoveDbBatchMove:
        return f"commit operation only valid on batch record (got f{table_class}"
    if "data" not in kwargs:
        return "missing data parameter"
    data = kwargs["data"]
    if "id" not in data:
        return "id not specified for batch commit"
    return MoveDbBatchMove.commit(db_obj, data)


def _do_scan_boxes(table_class, db_obj: MoveBoxTrackerDB, **kwargs) -> ErrStr | None:
    """create scan record for a given batch with multiple boxes from command line"""
    if table_class is not MoveDbBoxScan:
        return f"scan operation only valid on box record (got f{table_class}"
    if "data" not in kwargs:
        return "missing data parameter"
    data = kwargs["data"]
    if "args" not in kwargs:
        return "missing args parameter"
    args = kwargs["args"]

    # create a scan for each box id
    errors = []
    for box_id in _expand_id_list(args["boxes"]):
        data["box"] = box_id
        err = _do_db_create(data, table_class, db_obj)
        if err is not None:
            errors.append(err)
    if len(errors) > 0:
        return "\n".join(errors)
    return None


def _do_list(table_class, db_obj: MoveBoxTrackerDB, **kwargs) -> ErrStr | None:
    """list batch records"""
    if not issubclass(table_class, MoveDbRecord):
        return "list operation on unsupported record class"
    if table_class is MoveDbRecord:
        return "list operation must be on a subclass of MoveDbRecord"
    if "data" not in kwargs:
        return "missing data parameter"
    data = kwargs["data"]
    return table_class.do_list(db_obj, data)


def _do_record_cli(args: dict, ui_cb: UICallback) -> ErrStr | None:
    """high-level CLI flow to create or modify a record"""
    table = args["table"]
    table_class = CLI_TO_DB_CLASS[table]
    if "id" not in args:
        args["omit_id"] = True
    db_file = _get_db_file(args)
    if db_file is None:
        return "database file not specified"
    db_obj = MoveBoxTrackerDB(db_file, ui_cb=ui_cb)
    data = _args_to_data(args, table_class.fields())
    if not isinstance(db_obj, MoveBoxTrackerDB):
        return "failed to open database"

    # check if an action handler function is needed
    if table in CLI_ACTION:
        for handler in CLI_ACTION[table].keys():
            if handler in args and args[handler]:
                handler_call = CLI_ACTION[table][handler]
                if not callable(handler_call) and str(handler_call) in globals():
                    handler_call = globals()[handler_call]
                return handler_call(table_class, db_obj, data=data, args=args)

    # if an id was provided then update existing record
    if "id" in data:
        err = _do_db_update(data, table_class, db_obj)
    else:
        err = _do_db_create(data, table_class, db_obj)
    return err


def _get_out_dir(args: dict) -> Path:
    """determine output directory location"""
    db_file = _get_db_file(args)
    if "out_dir" in args and args["out_dir"] is not None:
        # use --out_dir directory if provided via command line
        outdir = Path(args["out_dir"])
    else:
        # default labels directory is xxx-labels/ next to xxx.db from db_file
        outdir = db_file.parent / (str(db_file.stem) + "-labels")
        if not outdir.is_dir():
            outdir.mkdir(mode=0o770, exist_ok=True)
    return outdir


def _do_label(args: dict, ui_cb: UICallback) -> ErrStr | None:
    """generate label(s) for specified box ids"""
    db_file = _get_db_file(args)
    if db_file is None:
        return "database file not specified"
    db_obj = MoveBoxTrackerDB(db_file, ui_cb=ui_cb)
    if not isinstance(db_obj, MoveBoxTrackerDB):
        return "failed to open database"

    # determine output directory location
    outdir = _get_out_dir(args)

    # generate label data for each box
    label_args = {}
    if "type" in args:
        label_args["type"] = args["type"]
    for box_id in _expand_id_list(args["box_id"]):
        # process a single box id from range-expanded list
        label_obj = MoveBoxLabel.typed_new(box_id, db_obj, outdir, **label_args)
        label_obj.gen_label()
        if "print" in args and args["print"] is True:
            label_obj.print_label()
    return None


def _do_merge(args: dict) -> ErrStr | None:
    """merge in an external SQLite database file, from another device"""
    raise NotImplementedError  # TODO


def _do_destsign(args: dict, ui_cb: UICallback) -> ErrStr | None:
    """print destination room sign to direct helpers unloading truck"""
    db_file = _get_db_file(args)
    if db_file is None:
        return "database file not specified"
    db_obj = MoveBoxTrackerDB(db_file, ui_cb=ui_cb)
    if not isinstance(db_obj, MoveBoxTrackerDB):
        return "failed to open database"

    # determine output directory location
    outdir = _get_out_dir(args)

    # generate destination signs for each specified room (or * for all)
    for room in _expand_room_list(args["rooms"]):
        # process a single room name/id from expanded list
        destsign_obj = MoveBoxDestSign(room, db_obj, outdir)
        destsign_obj.gen_destsign()
        if "print" in args and args["print"] is True:
            destsign_obj.print_label()
    return None


def _do_dump(args: dict, ui_cb: UICallback) -> ErrStr | None:
    """dump database contents to standard output"""
    db_file = _get_db_file(args)
    if db_file is None:
        return "database file not specified"
    db_obj = MoveBoxTrackerDB(db_file, ui_cb=ui_cb)
    db_obj.db_dump()
    return None


def _do_db(args: dict, ui_cb: UICallback) -> ErrStr | None:
    """lower-level database access commands"""

    # collect arguments
    if "table_name" not in args:
        return "_do_db: db table not specified"
    table_name = args["table_name"]
    if table_name not in CLI_TO_DB_CLASS:
        return f"_do_db: no db class found for {table_name}"
    table_class = CLI_TO_DB_CLASS[table_name]
    db_file = _get_db_file(args)
    if db_file is None:
        return "database file not specified"
    db_obj = MoveBoxTrackerDB(db_file, ui_cb=ui_cb)
    data = _args_to_data(args, table_class.fields())
    if not isinstance(db_obj, MoveBoxTrackerDB):
        return "failed to open database"

    # call handler function:  CRUD (create, read, update, or delete)
    crud_op = args["op"]
    match crud_op:
        case "create":
            err = _do_db_create(data, table_class, db_obj)
        case "read":
            err = _do_db_read(data, table_class, db_obj)
        case "update":
            err = _do_db_update(data, table_class, db_obj)
        case "delete":
            err = _do_db_delete(data, table_class, db_obj)
        case _:
            err = f"operation '{crud_op}' not recognized"
    return err


def _do_db_create(data: dict, table_class: str, db_obj: MoveBoxTrackerDB) -> ErrStr | None:
    """lower-level database access: create a record"""
    rec_obj = table_class(db_obj)
    res_id = rec_obj.db_create(data)
    if res_id is None:
        return "failed to create record"
    print(f"success: created record #{res_id}")
    return None


def _do_db_read(data: dict, table_class: str, db_obj: MoveBoxTrackerDB) -> ErrStr | None:
    """lower-level database access: read a record"""
    rec_obj = table_class(db_obj)
    res = rec_obj.db_read(data)
    if res is None:
        return "failed to read record"
    print(f"read {res} record(s)")
    return None


def _do_db_update(data: dict, table_class: str, db_obj: MoveBoxTrackerDB) -> ErrStr | None:
    """lower-level database access: update a record"""
    rec_obj = table_class(db_obj)
    res = rec_obj.db_update(data)
    if res is None:
        return "failed to update record"
    print(f"success: updated {res} record(S)")
    return None


def _do_db_delete(data: dict, table_class: str, db_obj: MoveBoxTrackerDB) -> ErrStr | None:
    """lower-level database access: delete a record"""
    rec_obj = table_class(db_obj)
    res = rec_obj.db_delete(data)
    if res is None:
        return "failed to delete record"
    print(f"success: deleted {res} record(s)")
    return None


def _common_db_file_arg(arg_parser: argparse.ArgumentParser) -> None:
    arg_parser.add_argument(
        "--db",
        "--db_file",
        dest="db_file",
        action="store",
        metavar="DB",
        help="database file",
    )


def _gen_arg_subparsers_init(subparsers) -> None:
    # init subparser
    parser_init = subparsers.add_parser("init", help="initialize new moving box database")
    _common_db_file_arg(parser_init)
    parser_init.add_argument("--primary_user", "--user")  # db field
    parser_init.add_argument("--title")  # db field
    parser_init.add_argument("--found_contact", "--found", "--contact")  # db field
    parser_init.set_defaults(func=_do_init, omit_id=True)


def _gen_arg_subparsers_batch(subparsers) -> None:
    # batch subparser
    parser_batch = subparsers.add_parser("batch", help="create or update a batch record")
    _common_db_file_arg(parser_batch)
    parser_batch.add_argument("--id")  # db field
    parser_batch.add_argument("--timestamp")  # db field
    parser_batch.add_argument("--location")  # db field
    parser_batch.add_argument("--commit", action="store_true")  # action handler
    parser_batch.add_argument("--list", action="store_true")  # action handler
    parser_batch.set_defaults(table="batch", func=_do_record_cli)


def _gen_arg_subparsers_box(subparsers) -> None:
    # box subparser
    parser_box = subparsers.add_parser("box", help="create or update a moving box record")
    _common_db_file_arg(parser_box)
    parser_box.add_argument("--id")  # db field
    parser_box.add_argument("--location")  # db field
    parser_box.add_argument("--info", "--desc", "--description")  # db field
    parser_box.add_argument("--room")  # db field
    parser_box.add_argument("--user")  # db field
    parser_box.add_argument("--image")  # db field
    parser_box.add_argument("--list", action="store_true")  # action handler
    parser_box.set_defaults(table="box", func=_do_record_cli)


def _gen_arg_subparsers_image(subparsers) -> None:
    # image subparser
    parser_image = subparsers.add_parser("image", help="create or update an image record")
    _common_db_file_arg(parser_image)
    parser_image.add_argument("--id")  # db field
    parser_image.add_argument("--image_file", "--file")  # db field
    parser_image.add_argument("--description", "--info", "--desc")  # db field
    parser_image.add_argument("--timestamp")  # db field
    parser_image.add_argument("--list", action="store_true")  # action handler
    parser_image.set_defaults(table="image", func=_do_record_cli)


def _gen_arg_subparsers_item(subparsers) -> None:
    # item subparser
    parser_item = subparsers.add_parser("item", help="create or update an item record")
    _common_db_file_arg(parser_item)
    parser_item.add_argument("--id")  # db field
    parser_item.add_argument("--box")  # db field
    parser_item.add_argument("--description", "--info", "--desc")  # db field
    parser_item.add_argument("--image")  # db field
    parser_item.add_argument("--list", action="store_true")  # action handler
    parser_item.set_defaults(table="item", func=_do_record_cli)


def _gen_arg_subparsers_location(subparsers) -> None:
    # location subparser
    parser_location = subparsers.add_parser("location", help="create or update a location record")
    _common_db_file_arg(parser_location)
    parser_location.add_argument("--id")  # db field
    parser_location.add_argument("--name")  # db field
    parser_location.add_argument("--list", action="store_true")  # action handler
    parser_location.set_defaults(table="location", func=_do_record_cli)


def _gen_arg_subparsers_room(subparsers) -> None:
    # room subparser
    parser_room = subparsers.add_parser("room", help="create or update a room record")
    _common_db_file_arg(parser_room)
    parser_room.add_argument("--id")  # db field
    parser_room.add_argument("--name")  # db field
    parser_room.add_argument("--color")  # db field
    parser_room.add_argument("--list", action="store_true")  # action handler
    parser_room.set_defaults(table="room", func=_do_record_cli)


def _gen_arg_subparsers_scan(subparsers) -> None:
    # scan subparser
    parser_scan = subparsers.add_parser("scan", help="create or update a scan record")
    _common_db_file_arg(parser_scan)
    parser_scan.add_argument("--id")  # db field
    parser_scan.add_argument("--box")  # db field
    parser_scan.add_argument("--batch")  # db field
    parser_scan.add_argument("--user")  # db field
    parser_scan.add_argument("--timestamp")  # db field
    handler_group = parser_scan.add_mutually_exclusive_group()
    handler_group.add_argument("--list", action="store_true")  # action handler
    handler_group.add_argument("--boxes", nargs="+", metavar="BOXID")  # action handler
    parser_scan.set_defaults(table="scan", func=_do_record_cli)


def _gen_arg_subparsers_user(subparsers) -> None:
    # user subparser
    parser_user = subparsers.add_parser("user", help="create or update a user record")
    _common_db_file_arg(parser_user)
    parser_user.add_argument("--id")  # db field
    parser_user.add_argument("--name")  # db field
    parser_user.add_argument("--list", action="store_true")  # action handler
    parser_user.set_defaults(table="user", func=_do_record_cli)


def _gen_arg_subparsers_label(subparsers) -> None:
    # label subparser
    parser_label = subparsers.add_parser("label", help="print label(s) for specified box ids")
    _common_db_file_arg(parser_label)
    parser_label.add_argument("--type", nargs="?")
    parser_label.add_argument("--print", action="store_true")
    parser_label.add_argument(
        "--outdir",
        dest="out_dir",
        action="store",
        metavar="LABELDIR",
        help="directory to place output PDF file(s), default: xxx-labels in same dir as xxx.db",
    )
    parser_label.add_argument("box_id", nargs="+", metavar="ID")
    parser_label.set_defaults(func=_do_label)


def _gen_arg_subparsers_merge(subparsers) -> None:
    # merge subparser
    parser_merge = subparsers.add_parser(
        "merge", help="merge in an external SQLite database file, from another device"
    )
    _common_db_file_arg(parser_merge)
    parser_merge.add_argument("db_merge", nargs=1, metavar="DB2", help="database file to merge in")
    parser_merge.set_defaults(func=_do_merge)


def _gen_arg_subparsers_destsign(subparsers) -> None:
    # print destination room sign for unloading truck
    parser_destsign = subparsers.add_parser(
        "destsign", help="print destination room sign to direct helpers unloading truck"
    )
    parser_destsign.add_argument("--print", action="store_true")
    parser_destsign.add_argument(
        "--outdir",
        dest="out_dir",
        action="store",
        metavar="LABELDIR",
        help="directory to place output PDF file(s), default: xxx-labels in same dir as xxx.db",
    )
    parser_destsign.add_argument("rooms", nargs="+", metavar="ROOM")
    parser_destsign.set_defaults(func=_do_destsign)


def _gen_arg_subparsers_dump(subparsers) -> None:
    # dump subparser
    parser_dump = subparsers.add_parser("dump", help="dump database contents to standard output")
    _common_db_file_arg(parser_dump)
    parser_dump.set_defaults(func=_do_dump)


def _gen_arg_subparser_table(subparsers_db, parser_db_parent, table_name, help_str, fields) -> None:
    subparser_table = subparsers_db.add_parser(
        table_name, help=help_str, parents=[parser_db_parent]
    )
    subparser_table.set_defaults(table_name=table_name)
    for field in fields:
        subparser_table.add_argument(f"--{field}", help=f"{field} field of {table_name} table")


def _omit_id(in_list: list) -> list:
    """omit the "id" field so that it is not included in fields for update"""
    if in_list[0] == "id":
        del in_list[0]
    return in_list


def _gen_arg_subparsers_db(subparsers) -> None:
    # define subparsers for low-level database access
    parser_db = subparsers.add_parser("db", help="low-level database access subcommands")
    parser_db.set_defaults(func=_do_db)

    # parser_db_parent contains template for common parameters in all the db subparsers
    parser_db_parent = argparse.ArgumentParser(add_help=False)
    parser_db_parent.add_argument("op", choices=["create", "read", "update", "delete"])
    _common_db_file_arg(parser_db_parent)
    subparsers_db = parser_db.add_subparsers(help="low-level db sub-command help")
    parser_db_parent.add_argument(
        "id", type=int, action="store", nargs="?", help="database record id"
    )

    # generate subparsers for each table
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="batch",
        help_str="batch/group of moving boxes",
        fields=_omit_id(MoveDbBatchMove.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="box",
        help_str="moving box including label info",
        fields=_omit_id(MoveDbMovingBox.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="image",
        help_str="images for boxes or items",
        fields=_omit_id(MoveDbImage.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="item",
        help_str="item inside a box",
        fields=_omit_id(MoveDbItem.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="location",
        help_str="location where boxes may be",
        fields=_omit_id(MoveDbLocation.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="project",
        help_str="overall move project info",
        fields=_omit_id(MoveDbMoveProject.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="room",
        help_str="room at origin & destination",
        fields=_omit_id(MoveDbRoom.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="scan",
        help_str="box scan event on move to new location",
        fields=_omit_id(MoveDbBoxScan.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="user",
        help_str="user who owns database or performs a box scan",
        fields=_omit_id(MoveDbURIUser.fields()),
    )


def _gen_arg_subparsers(top_parser) -> None:
    """generate argparse first-level sub-parsers"""
    # define subparsers for high-level operations
    subparsers = top_parser.add_subparsers(help="sub-command help")

    # init subparser
    _gen_arg_subparsers_init(subparsers)

    # batch subparser
    _gen_arg_subparsers_batch(subparsers)

    # box subparser
    _gen_arg_subparsers_box(subparsers)

    # image subparser
    _gen_arg_subparsers_image(subparsers)

    # item subparser
    _gen_arg_subparsers_item(subparsers)

    # location subparser
    _gen_arg_subparsers_location(subparsers)

    # room subparser
    _gen_arg_subparsers_room(subparsers)

    # scan subparser
    _gen_arg_subparsers_scan(subparsers)

    # user subparser
    _gen_arg_subparsers_user(subparsers)

    # label subparser
    _gen_arg_subparsers_label(subparsers)

    # merge subparser
    _gen_arg_subparsers_merge(subparsers)

    # print destination room signs
    _gen_arg_subparsers_destsign(subparsers)

    # dump subparser
    _gen_arg_subparsers_dump(subparsers)

    # define subparsers for low-level database access
    _gen_arg_subparsers_db(subparsers)


def _gen_arg_parser() -> argparse.ArgumentParser:
    """generate argparse parser hierarchy"""

    # define global parser
    top_parser = argparse.ArgumentParser(
        prog=PROG_NAME,
        description="moving box database manager and label generator",
    )
    top_parser.add_argument("--version", action="version", version=_get_version())
    top_parser.add_argument(
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="more verbose output",
    )
    top_parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="turn on debugging mode",
    )

    # define subparsers for high-level operations
    _gen_arg_subparsers(top_parser)

    return top_parser


def run():
    """process command line arguments and run program"""

    # define global parser
    top_parser = _gen_arg_parser()

    # callback functions for DB to access CLI
    cli_callback = UICallback(prompt_cb=cli_prompt, display_cb=cli_display, error_cb=cli_error)

    # parse arguments and run subcommand functions
    args = vars(top_parser.parse_args())
    err = None
    if "func" not in args:
        top_parser.error("no command was specified")
    try:
        err = args["func"](args, ui_cb=cli_callback)
    except Exception as exc:
        exc_class = exc.__class__
        if "verbose" in args and args["verbose"]:
            print(f"exception {exc_class} occurred with args: ", args)
        raise exc

    # return success/failure results
    if err is not None:
        top_parser.exit(status=1, message=err + "\n")
    top_parser.exit()
