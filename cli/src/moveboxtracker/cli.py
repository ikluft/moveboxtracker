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

# manage table names used by CLI and by database classes
# Shorter names are preferred for a CLI. Descriptive names are preferred for an SQL schema.
# And some names, such as "box", are prohibited in an SQL schema due to conflicts.
# The CLI layer knows the CLI names. The CLI knowns the class names for the database layer.
# The database classes know their schema names.
cli_to_db_name = {
    "batch": "DB_BatchMove",
    "box": "DB_MovingBox",
    "item": "DB_Item",
    "location": "DB_Location",
    "log": "DB_Log",
    "project": "DB_MoveProject",
    "room": "DB_Room",
    "scan": "DB_BoxScan",
    "user": "DB_URIUser",
}


def _get_version():
    """display version"""
    try:
        ver = "moveboxtracker " + str(version("moveboxtracker"))
    except PackageNotFoundError:
        ver = "moveboxtracker version not available in development environment"
    return ver


def _do_init(args) -> str | None:
    """initialize new moving box database"""
    raise Exception("not implemented")  # TODO


def _do_label(args) -> str | None:
    """print label(s) for specified box ids"""
    raise Exception("not implemented")  # TODO


def _do_merge(args) -> str | None:
    """merge in an external SQLite database file, from another device"""
    raise Exception("not implemented")  # TODO


def _do_log(args) -> str | None:
    """view log"""
    raise Exception("not implemented")  # TODO


def _do_db(args) -> str | None:
    """lower-level database access commands"""
    raise Exception("not implemented")  # TODO


def _gen_arg_subparser_table(
    subparsers_db, parser_db_parent, name, help_str, fields
) -> None:
    subparser_table = subparsers_db.add_parser(
        name, help=help_str, parents=[parser_db_parent]
    )
    subparser_table.set_defaults(table=name)
    for field in fields:
        subparser_table.add_argument(
            f"--{field}", help=f"{field} field of {name} table"
        )


def _gen_arg_subparsers_db(subparsers) -> None:
    # define subparsers for low-level database access
    parser_db = subparsers.add_parser(
        "db", help="low-level database access subcommands"
    )
    parser_db.set_defaults(func=_do_db)
    subparsers_db = parser_db.add_subparsers(help="low-level db sub-command help")

    # parser_db_parent contains template for common parameters in all the db subparsers
    parser_db_parent = argparse.ArgumentParser(add_help=False)
    parser_db_parent.add_argument(
        "op", choices=["create", "read", "update", "delete"], nargs=1
    )
    parser_db_parent.add_argument("id", type=int, nargs="?", help="database record id")

    # generate subparsers for each table
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        name="batch",
        help_str="batch/group of moving boxes",
        fields=["timestamp", "location"],
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        name="box",
        help_str="moving box including label info",
        fields=["location", "info", "room", "user", "image"],
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        name="item",
        help_str="item inside a box",
        fields=["box", "description", "image"],
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        name="location",
        help_str="location where boxes may be",
        fields=["name"],
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        name="log",
        help_str="log of data update events",
        fields=["table_name", "field_name", "old", "new", "timestamp"],
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        name="project",
        help_str="overall move project info",
        fields=["primary_user", "title", "found_contact"],
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        name="room",
        help_str="room at origin & destination",
        fields=["name", "color"],
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        name="scan",
        help_str="box scan event on move to new location",
        fields=["box", "batch", "user", "timestamp"],
    )
    _gen_arg_subparser_table(
        subparsers_db,
        parser_db_parent,
        name="user",
        help_str="user who owns database or performs a box scan",
        fields=["name"],
    )


def _gen_arg_subparsers(top_parser) -> None:
    """generate argparse first-level sub-parsers"""
    # define subparsers for high-level operations
    subparsers = top_parser.add_subparsers(help="sub-command help")
    parser_init = subparsers.add_parser(
        "init", help="initialize new moving box database"
    )
    parser_init.add_argument("--primary_user", "--user")
    parser_init.add_argument("--title")
    parser_init.add_argument("--found_contact", "--found", "--contact")
    parser_init.set_defaults(func=_do_init)

    parser_label = subparsers.add_parser(
        "label", help="print label(s) for specified box ids"
    )
    parser_label.add_argument("box_id", nargs="*", metavar="ID", type=int)
    parser_label.set_defaults(func=_do_label)

    parser_merge = subparsers.add_parser(
        "merge", help="merge in an external SQLite database file, from another device"
    )
    parser_merge.add_argument("db_file", metavar="DB", help="database file")
    parser_merge.set_defaults(func=_do_merge)

    parser_log = subparsers.add_parser("log", help="view log")
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

    # define subparsers for high-level operations
    _gen_arg_subparsers(top_parser)

    return top_parser


def run():
    """process command line arguments and run program"""

    # define global parser
    top_parser = _gen_arg_parser()

    # parse arguments and run subcommand functions
    args = vars(top_parser.parse_args())
    if "func" not in args:
        top_parser.error("no command was specified")
    err = args["func"](args)

    # return success/failure results
    if err is not None:
        top_parser.exit(status=1, message=err)
    top_parser.exit()
