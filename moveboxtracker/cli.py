"""
command-line interface for moveboxtracker

usage: moveboxtracker <cmd> args

operations
    init [--key=value ...]  initialize new database
    label box_id ...        print label(s) for specified box ids, start-end ranges accepted
    merge|ingest db_file    merge in an external SQLite database file, from another device
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
import argparse
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
import tempfile
from shutil import move
import qrcode
import qrcode.image.svg
from colorlookup import Color
from weasyprint import HTML, CSS
from . import __version__
from .db import (
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

# CSS stylesheet for box label PDF generator
PAGE_SIZE = os.environ["MBT_PAGE_SIZE"] if "MBT_PAGE_SIZE" in os.environ else "Letter"
BOX_LABEL_STYLESHEET = (
    """
    @page {
        size: """
    + PAGE_SIZE
    + """;
        margin: 0.2cm;
    }
    table {
        width: 100%
        table-layout: fixed;
        font-family: sans-serif;
    }
    """
)


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


def _do_init(args: dict) -> ErrStr | None:
    """initialize new moving box database"""
    if "db_file" not in args:
        return "database file not specified"
    filepath = args["db_file"]
    data = _args_to_data(args, MoveDbMoveProject.fields())
    db_obj = MoveBoxTrackerDB(filepath, data, prompt=cli_prompt)
    if not isinstance(db_obj, MoveBoxTrackerDB):
        return "database initialization failed"
    return None


def _gen_label_uri(user: str, box: str, room: str, color: str):
    """generate URI for moving box label QR code"""

    # determine box URI text for QR code
    uri = f"movingbox://{user}/{box}?room={room},color={color}"
    return uri


def _gen_label_qrcode(
    tmpdirpath: Path, user: str, box: str, room: str, color: str
) -> str:
    """generate QR code in a file in the temporary directory for use in PDF generation"""

    # generate QR code in SVG for use in PDF
    qr_svg_file = f"label_{box}.svg"
    qr_img = qrcode.make(
        _gen_label_uri(user, box, room, color),
        box_size=13,
        border=5,
        image_factory=qrcode.image.svg.SvgImage,
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
    )
    qr_img.save(f"{tmpdirpath}/{qr_svg_file}")
    return qr_svg_file


def _gen_label_html(box_data: dict, tmpdirpath: Path, qr_svg_file: Path) -> str:
    """generate HTML in a file in the temporary directory for use in PDF generation"""

    # collect parameters
    box = str(box_data["box"]).zfill(4)
    color = Color(box_data["color"]).name.replace(" ", "")
    room = str(box_data["room"]).upper()

    # generate label cell
    # 4 of these will be printed on each page
    label_cell = [
        '<table id="label_cell">',
        "<tr>",
        f"<td><big><b>{room}</b></big></td>",
        f'<td style="text-align: right"><big>Box&nbsp;{box}</big></td>',
        "</tr>",
        "<tr>",
        f'<td style="background: {color}">&nbsp;</td>',
        f'<td><img src="{qr_svg_file}"></td>',
        "</tr>",
        "<tr>",
        '<td colspan=2 style="text-align: center">',
        "Lost &amp; found contact:",
        "<br/>",
        f'{box_data["found"]}',
        "</td>",
        "</tr>",
        "<tr>",
        "<td colspan=2>&nbsp;</td>",
        "</tr>",
        "</table>",
    ]

    # generate HTML for label
    label_html = (
        [
            "<html>",
            "<head>",
            "</head>",
            "<body>",
            "<table>",
            "<tr>",
            "<td>",
        ]
        + label_cell
        + ["</td>", "<td>&nbsp;</td>", "<td>"]
        + label_cell
        + ["</td>", "</tr>", "<tr>", "<td>"]
        + label_cell
        + ["</td>", "<td>&nbsp;</td>", "<td>"]
        + label_cell
        + ["</td>", "</tr>", "</table>", "</body>", "</html>"]
    )
    html_file_path = Path(f"{tmpdirpath}/label_{box}.html")
    with open(html_file_path, "wt", encoding="utf-8") as textfile:
        textfile.write("\n".join(label_html))
    return html_file_path


def _gen_label(box_data: dict, outdir: str) -> None:
    """generate one moving box label from a dict of the box's data"""

    # collect parameters
    user = str(box_data["user"])
    box = str(box_data["box"]).zfill(4)
    color = Color(box_data["color"]).name.replace(" ", "")
    room = str(box_data["room"]).upper()

    # verify output directory exists
    outdir.mkdir(mode=0o770, parents=True, exist_ok=True)

    # allocate temporary directory
    tmpdirpath = tempfile.mkdtemp(prefix="moving_label_")

    # generate QR code in SVG for use in PDF
    qr_svg_file = _gen_label_qrcode(tmpdirpath, user, box, room, color)

    # Build moving box label as HTML and print.
    # Simple HTML is PDF'ed & printed, then discarded when the temporary directory is removed.
    # Just build HTML strings to minimize library dependencies.
    html_file_path = _gen_label_html(box_data, tmpdirpath, qr_svg_file)
    css = CSS(string=BOX_LABEL_STYLESHEET)

    # generate PDF
    label_pdf_file = Path(f"{tmpdirpath}/label_{box}.pdf")
    doc = HTML(filename=html_file_path)
    doc.write_pdf(
        target=label_pdf_file,
        stylesheets=[css],
        attachments=[f"{tmpdirpath}/{qr_svg_file}"],
        optimize_size=("fonts", "images"),
    )
    move(label_pdf_file, outdir)


def _do_label(args: dict) -> ErrStr | None:
    """print label(s) for specified box ids"""
    if "db_file" not in args:
        return "database file not specified"
    filepath = args["db_file"]
    db_obj = MoveBoxTrackerDB(filepath, prompt=cli_prompt)
    if not isinstance(db_obj, MoveBoxTrackerDB):
        return "failed to open database"

    # print label data for each box
    rec_obj = MoveDbMovingBox(db_obj)
    outdir = Path(args["out_dir"])
    box_id_list = args["box_id"]
    for box_id in box_id_list:
        # regular expression check for start-end range of box ids
        match = re.fullmatch(r"^(\d+)-(\d+)$", str(box_id))
        if match:
            # process start-end range of box ids
            start, end = match.groups()
            for box_num in range(start, end):
                box_data = rec_obj.box_label_data(box_num)
                _gen_label(box_data, outdir)
        else:
            # process a single box id
            box_data = rec_obj.box_label_data(box_id)
            _gen_label(box_data, outdir)
    return None


def _do_merge(args: dict) -> ErrStr | None:
    """merge in an external SQLite database file, from another device"""
    raise NotImplementedError  # TODO


def _do_dump(args: dict) -> ErrStr | None:
    """dump database contents to standard output"""
    db_file = args["db_file"]
    db_obj = MoveBoxTrackerDB(db_file, prompt=cli_prompt)
    db_obj.db_dump()


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
    db_obj = MoveBoxTrackerDB(db_file, prompt=cli_prompt)
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


def _do_db_create(
    data: dict, table_class: str, db_obj: MoveBoxTrackerDB
) -> ErrStr | None:
    """lower-level database access: create a record"""
    rec_obj = table_class(db_obj)
    res_id = rec_obj.db_create(data)
    if res_id is None:
        return "failed to create record"
    print(f"success: created record #{res_id}")
    return None


def _do_db_read(
    data: dict, table_class: str, db_obj: MoveBoxTrackerDB
) -> ErrStr | None:
    """lower-level database access: read a record"""
    rec_obj = table_class(db_obj)
    res = rec_obj.db_read(data)
    if res is None:
        return "failed to read record"
    print(f"read {res} record(s)")
    return None


def _do_db_update(
    data: dict, table_class: str, db_obj: MoveBoxTrackerDB
) -> ErrStr | None:
    """lower-level database access: update a record"""
    rec_obj = table_class(db_obj)
    res = rec_obj.db_update(data)
    if res is None:
        return "failed to update record"
    print(f"success: updated {res} record(S)")
    return None


def _do_db_delete(
    data: dict, table_class: str, db_obj: MoveBoxTrackerDB
) -> ErrStr | None:
    """lower-level database access: delete a record"""
    rec_obj = table_class(db_obj)
    res = rec_obj.db_delete(data)
    if res is None:
        return "failed to delete record"
    print(f"success: deleted {res} record(s)")
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
        fields=_omit_id(MoveDbItem.fields()),
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
    parser_init = subparsers.add_parser(
        "init", help="initialize new moving box database"
    )
    parser_init.add_argument("--primary_user", "--user")
    parser_init.add_argument("--title")
    parser_init.add_argument("--found_contact", "--found", "--contact")
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
    parser_label.add_argument(
        "--outdir",
        dest="out_dir",
        action="store",
        metavar="PDFFILE",
        required=True,
        help="directory to place output PDF file(s)",
    )
    parser_label.add_argument("box_id", nargs="+", metavar="ID")
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

    parser_dump = subparsers.add_parser(
        "dump", help="dump database contents to standard output"
    )
    parser_dump.add_argument(
        "db_file", action="store", metavar="DB", help="database file"
    )
    parser_dump.set_defaults(func=_do_dump)

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
