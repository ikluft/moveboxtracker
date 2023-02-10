"""
command-line interface for moveboxtracker

usage: moveboxtracker <cmd> args

operations
    init [--key=value ...]  initialize new database
    label box_id ...        print label(s) for specified box ids (TODO: accept a range m-n)
    merge|ingest db_file    merge in an external SQLite database file, from another device
    log                     view log
    db                      perform database operations

database operations (subcommands of db subcommand)
    batch | batch_move      batch/group of moving boxes
    box | moving_box        moving box including label info
    item                    item inside a box
    location                location where boxes may be
    log                     log of data update events
    project | move_project  overall move project info
    room                    room at origin & destination
    scan | box_scan         box scan event on move to new location
    user | uri_user         user who owns database or performs a box scan

All of the databasea access operations take the following ("CRUD") arguments:
    --create | --new | -c   id --key=value [--key=value ...]
    --read   | --get | -r   id
    --update | --set | -u   id --key=value [--key=value ...]
    --delete | --del | -d   id
"""

import argparse
from importlib.metadata import version, PackageNotFoundError
from . import __version__
from .db import (
    MoveBoxTrackerDB,
    MBT_DB_BatchMove,
    MBT_DB_MovingBox,
    MBT_DB_Item,
    MBT_DB_Location,
    MBT_DB_Log,
    MBT_DB_MoveProject,
    MBT_DB_Room,
    MBT_DB_BoxScan,
    MBT_DB_URIUser,
)

# manage table names used by CLI and by database classes
# Shorter names are preferred for a CLI. Descriptive names are preferred for an SQL schema.
# And some names, such as "box", are prohibited in an SQL schema due to conflicts.
# The CLI layer knows the CLI names. The CLI knows the class names for the database layer.
# The database classes know their schema names.
CLI_TO_DB_CLASS = {
    "batch": MBT_DB_BatchMove,
    "box": MBT_DB_MovingBox,
    "item": MBT_DB_Item,
    "location": MBT_DB_Location,
    "log": MBT_DB_Log,
    "project": MBT_DB_MoveProject,
    "room": MBT_DB_Room,
    "scan": MBT_DB_BoxScan,
    "user": MBT_DB_URIUser,
}

# type alias for error strings
ErrStr = str


def _get_version():
    """display version"""
    if __version__ is not None:
        ver = __version__
    else:
        try:
            ver = "moveboxtracker " + str(version("moveboxtracker"))
        except PackageNotFoundError:
            ver = "moveboxtracker version not available in development environment"
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


def _do_init(args: dict) -> ErrStr | None:
    """initialize new moving box database"""
    if "db_file" not in args:
        return "database file not specified"
    filepath = args["db_file"]
    data = _args_to_data(args, MBT_DB_MoveProject.fields())
    db_obj = MoveBoxTrackerDB(filepath, data)
    if not isinstance(db_obj, MoveBoxTrackerDB):
        return "database initialization failed"
    return None


def _do_label(args: dict) -> ErrStr | None:
    """print label(s) for specified box ids"""
    raise Exception("not implemented")  # TODO


def _do_merge(args: dict) -> ErrStr | None:
    """merge in an external SQLite database file, from another device"""
    raise Exception("not implemented")  # TODO


def _do_log(args: dict) -> ErrStr | None:
    """view log"""
    raise Exception("not implemented")  # TODO


def _do_db(args: dict) -> ErrStr | None:
    """lower-level database access commands"""

    # collect arguments
    if "table_name" not in args:
        return "_do_db: db table not specified"
    table_name = args["table_name"]
    if table_name not in CLI_TO_DB_CLASS:
        return f"_do_db: no db class found for {table_name}"
    table_class = CLI_TO_DB_CLASS[table_name]
    db_file = args["db_file"]
    data = _args_to_data(args, table_class.fields())
    db_obj = MoveBoxTrackerDB(db_file)
    if not isinstance(db_obj, MoveBoxTrackerDB):
        return "database initialization failed"

    # call CRUD (create, read, update, or delete) handler function
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


def _do_db_create(
    data: dict, table_class: str, db_obj: MoveBoxTrackerDB
) -> ErrStr | None:
    """lower-level database access: create a record"""
    rec_obj = table_class(db_obj)
    res_id = rec_obj.db_create(data)
    if res_id is None:
        return "failed to create record"
    print(f"success: created record {res_id}")
    return None


def _do_db_read(
    data: dict, table_class: str, db_obj: MoveBoxTrackerDB
) -> ErrStr | None:
    """lower-level database access: read a record"""
    rec_obj = table_class(db_obj)
    res = rec_obj.db_read(data)
    if res is None:
        return "failed to read record"
    print(f"read {res} records")
    return None


def _do_db_update(
    data: dict, table_class: str, db_obj: MoveBoxTrackerDB
) -> ErrStr | None:
    """lower-level database access: update a record"""
    rec_obj = table_class(db_obj)
    res = rec_obj.db_update(data)
    if res is None:
        return "failed to update record"
    print(f"success: updated record {res}")
    return None


def _do_db_delete(
    data: dict, table_class: str, db_obj: MoveBoxTrackerDB
) -> ErrStr | None:
    """lower-level database access: delete a record"""
    rec_obj = table_class(db_obj)
    res = rec_obj.db_delete(data)
    if res is None:
        return "failed to delete record"
    print(f"success: deleted record {res}")
    return None


def _gen_arg_subparser_table(
    subparsers_db, parser_db_parent, table_name, help_str, fields
) -> None:
    subparser_table = subparsers_db.add_parser(
        table_name, help=help_str, parents=[parser_db_parent]
    )
    subparser_table.set_defaults(table_name=table_name)
    for field in fields:
        subparser_table.add_argument(
            f"--{field}", help=f"{field} field of {table_name} table"
        )


def _omit_id(in_list: list) -> list:
    """omit the "id" field so that it is not included in fields for update"""
    if in_list[0] == "id":
        del in_list[0]
    return in_list


def _gen_arg_subparsers_db(subparsers) -> None:
    # define subparsers for low-level database access
    parser_db = subparsers.add_parser(
        "db", help="low-level database access subcommands"
    )
    parser_db.set_defaults(func=_do_db)

    # parser_db_parent contains template for common parameters in all the db subparsers
    parser_db_parent = argparse.ArgumentParser(add_help=False)
    parser_db_parent.add_argument("op", choices=["create", "read", "update", "delete"])
    parser_db_parent.add_argument(
        "--file",
        dest="db_file",
        action="store",
        metavar="DB",
        help="database file",
        required=True,
    )
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
        fields=_omit_id(MBT_DB_BatchMove.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="box",
        help_str="moving box including label info",
        fields=_omit_id(MBT_DB_MovingBox.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="item",
        help_str="item inside a box",
        fields=_omit_id(MBT_DB_Item.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="location",
        help_str="location where boxes may be",
        fields=_omit_id(MBT_DB_Location.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="log",
        help_str="log of data update events",
        fields=_omit_id(MBT_DB_Log.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="project",
        help_str="overall move project info",
        fields=_omit_id(MBT_DB_MoveProject.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="room",
        help_str="room at origin & destination",
        fields=_omit_id(MBT_DB_Room.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="scan",
        help_str="box scan event on move to new location",
        fields=_omit_id(MBT_DB_BoxScan.fields()),
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        table_name="user",
        help_str="user who owns database or performs a box scan",
        fields=_omit_id(MBT_DB_URIUser.fields()),
    )


def _gen_arg_subparsers(top_parser) -> None:
    """generate argparse first-level sub-parsers"""
    # define subparsers for high-level operations
    subparsers = top_parser.add_subparsers(help="sub-command help")
    parser_init = subparsers.add_parser(
        "init", help="initialize new moving box database"
    )
    parser_init.add_argument("--primary_user", "--user", required=True)
    parser_init.add_argument("--title", required=True)
    parser_init.add_argument("--found_contact", "--found", "--contact", required=True)
    parser_init.add_argument(
        "db_file", action="store", metavar="DB", help="database file"
    )
    parser_init.set_defaults(func=_do_init, omit_id=True)

    parser_label = subparsers.add_parser(
        "label", help="print label(s) for specified box ids"
    )
    parser_label.add_argument(
        "db_file", action="store", metavar="DB", help="database file"
    )
    parser_label.add_argument("box_id", nargs="+", metavar="ID", type=int)
    parser_label.set_defaults(func=_do_label)

    parser_merge = subparsers.add_parser(
        "merge", help="merge in an external SQLite database file, from another device"
    )
    parser_merge.add_argument(
        "db_file", action="store", metavar="DB1", help="database file"
    )
    parser_merge.add_argument(
        "db_merge", nargs=1, metavar="DB2", help="database file to merge in"
    )
    parser_merge.set_defaults(func=_do_merge)

    parser_log = subparsers.add_parser("log", help="view log")
    parser_log.add_argument(
        "db_file", action="store", metavar="DB", help="database file"
    )
    parser_log.set_defaults(func=_do_log)

    # define subparsers for low-level database access
    _gen_arg_subparsers_db(subparsers)


def _gen_arg_parser() -> argparse.ArgumentParser:
    """generate argparse parser hierarchy"""

    # define global parser
    top_parser = argparse.ArgumentParser(
        prog="moveboxtracker",
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

    # parse arguments and run subcommand functions
    args = vars(top_parser.parse_args())
    err = None
    if "func" not in args:
        top_parser.error("no command was specified")
    try:
        err = args["func"](args)
    except Exception as exc:
        exc_class = exc.__class__
        if "verbose" in args and args["verbose"]:
            print(f"exception {exc_class} occurred with args: ", args)
        raise exc

    # return success/failure results
    if err is not None:
        top_parser.exit(status=1, message=err + "\n")
    top_parser.exit()
