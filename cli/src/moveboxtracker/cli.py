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
from importlib.metadata import (version, PackageNotFoundError)
from pathlib import Path
from xdg import BaseDirectory

# globals
data_home = BaseDirectory.xdg_data_home


def _get_version():
    """display version"""
    try:
        ver = str(version('moveboxtracker'))
    except PackageNotFoundError:
        ver = "development environment - version not available"
    return ver


def _do_init():
    """initialize new moving box database"""
    raise Exception("not implemented")  # TODO


def _do_label():
    """print label(s) for specified box ids"""
    raise Exception("not implemented")  # TODO


def _do_merge():
    """merge in an external SQLite database file, from another device"""
    raise Exception("not implemented")  # TODO


def _do_log():
    """view log"""
    raise Exception("not implemented")  # TODO


def _do_db_batch():
    """database access: batch/group of moving boxes"""
    raise Exception("not implemented")  # TODO


def _do_db_box():
    """database access: moving box including label info"""
    raise Exception("not implemented")  # TODO


def _do_db_item():
    """database access: item inside a box"""
    raise Exception("not implemented")  # TODO


def _do_db_location():
    """database access: location where boxes may be"""
    raise Exception("not implemented")  # TODO


def _do_db_log():
    """database access: log of data update events"""
    raise Exception("not implemented")  # TODO


def _do_db_project():
    """database access: overall move project info"""
    raise Exception("not implemented")  # TODO


def _do_db_room():
    """database access: room at origin & destination"""
    raise Exception("not implemented")  # TODO


def _do_db_scan():
    """database access: box scan event on move to new location"""
    raise Exception("not implemented")  # TODO


def _do_db_user():
    """database access: user who owns database or performs a box scan"""
    raise Exception("not implemented")  # TODO


def run():
    """process command line arguments and run program"""

    # define global parser
    top_parser = argparse.ArgumentParser(
        prog="moveboxtracker",
        description="moving box database manager and label generator",
    )
    top_parser.add_argument("--version", action="version", version=_get_version())

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
    parser_db = subparsers.add_parser("db", help="low-level database access subcommands")
    subparsers_db = parser_db.add_subparsers(help="low-level db sub-command help")

    # parser_db_parent contains template for common parameters in all the db subparsers
    parser_db_parent = argparse.ArgumentParser(add_help=False)
    parser_db_parent.add_argument("--create", "--new", "-c", help="create/add record")
    parser_db_parent.add_argument("--read", "--get", "-r", help="read/get record")
    parser_db_parent.add_argument("--update", "--set", "-s", help="update/set record")
    parser_db_parent.add_argument("--delete", "--del", "-d", help="delete record")

    parser_db_batch = subparsers_db.add_parser(
        "batch", help="batch/group of moving boxes", parents=[parser_db_parent]
    )
    parser_db_batch.set_defaults(func=_do_db_batch)

    parser_db_box = subparsers_db.add_parser(
        "box", help="moving box including label info", parents=[parser_db_parent]
    )
    parser_db_box.set_defaults(func=_do_db_box)

    parser_db_item = subparsers_db.add_parser(
        "item", help="item inside a box", parents=[parser_db_parent]
    )
    parser_db_item.set_defaults(func=_do_db_item)

    parser_db_location = subparsers_db.add_parser(
        "location", help="location where boxes may be", parents=[parser_db_parent]
    )
    parser_db_location.set_defaults(func=_do_db_location)

    parser_db_log = subparsers_db.add_parser(
        "log", help="log of data update events", parents=[parser_db_parent]
    )
    parser_db_log.set_defaults(func=_do_db_log)

    parser_db_project = subparsers_db.add_parser(
        "project", help="overall move project info", parents=[parser_db_parent]
    )
    parser_db_project.set_defaults(func=_do_db_project)

    parser_db_room = subparsers_db.add_parser(
        "room", help="room at origin & destination", parents=[parser_db_parent]
    )
    parser_db_room.set_defaults(func=_do_db_room)

    parser_db_scan = subparsers_db.add_parser(
        "scan", help="box scan event on move to new location", parents=[parser_db_parent]
    )
    parser_db_scan.set_defaults(func=_do_db_scan)

    parser_db_user = subparsers_db.add_parser(
        "user", help="user who owns database or performs a box scan", parents=[parser_db_parent]
    )
    parser_db_user.set_defaults(func=_do_db_user)

    # parse arguments and run subcommand functions
    args = vars(top_parser.parse_args())
    if "func" not in args:
        top_parser.error("no command was specified")
    args["func"](args)
