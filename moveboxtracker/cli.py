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
import lib_programname
import argparse
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
import tempfile
from shutil import move
from qrcodegen import QrCode
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

# package and program name
PKG_NAME = "moveboxtracker"
PROG_NAME = lib_programname.get_path_executed_script()

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

# database record CLI action handler functions
CLI_ACTION = {
    "batch": {
        "commit": "_do_batch_commit",
    }
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


def _get_db_file(args: dict) -> Path | None:
    """get default database file path from environment"""
    if "db_file" in args and args["db_file"] is not None:
        return Path(args["db_file"])
    if "MBT_DB_FILE" in os.environ:
        return Path(os.environ["MBT_DB_FILE"])
    return None


def _do_init(args: dict) -> ErrStr | None:
    """initialize new moving box database"""
    db_file = _get_db_file(args)
    if db_file is None:
        return "database file not specified"
    data = _args_to_data(args, MoveDbMoveProject.fields())
    db_obj = MoveBoxTrackerDB(db_file, data, prompt=cli_prompt)
    if not isinstance(db_obj, MoveBoxTrackerDB):
        return "database initialization failed"
    return None


def _gen_label_uri(user: str, box: str, room: str, color: str):
    """generate URI for moving box label QR code"""

    # determine box URI text for QR code
    uri = f"movingbox://{user}/{box}?room={room},color={color}"
    return uri


# to_svg_str() borrowed from qrcodegen demo
def to_svg_str(qrcode: QrCode, border: int) -> str:
    """Returns a string of SVG code for an image depicting the given QR Code, with the given number
        of border modules. The string always uses Unix newlines (\n), regardless of the platform."""
    if border < 0:
        raise ValueError("Border must be non-negative")
    parts = []
    for y_pos in range(qrcode.get_size()):
        for x_pos in range(qrcode.get_size()):
            if qrcode.get_module(x_pos, y_pos):
                parts.append(f"M{x_pos+border},{y_pos+border}h1v1h-1z")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN"
            "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
        <svg xmlns="http://www.w3.org/2000/svg" version="1.1"
            viewBox="0 0 {qrcode.get_size()+border*2}
            {qrcode.get_size()+border*2}" stroke="none">
            <rect width="100%" height="100%" fill="#FFFFFF"/>
            <path d="{" ".join(parts)}" fill="#000000"/>
        </svg>
        """


def _do_batch_commit(data: dict, db_obj: MoveBoxTrackerDB) -> ErrStr | None:
    """change location of boxes in a batch to indicate the batch was moved as a group"""
    if "id" not in data:
        return "id not specified for batch commit"
    return MoveDbBatchMove.commit(db_obj, data)


def _do_record_cli(args: dict) -> ErrStr | None:
    """high-level CLI flow to create or modify a record"""
    table = args["table"]
    table_class = CLI_TO_DB_CLASS[table]
    if "id" not in args:
        args["omit_id"] = True
    db_file = _get_db_file(args)
    if db_file is None:
        return "database file not specified"
    db_obj = MoveBoxTrackerDB(db_file, prompt=cli_prompt)
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
                return handler_call(data, db_obj)

    # if an id was provided then update existing record
    if "id" in data:
        err = _do_db_update(data, table_class, db_obj)
    else:
        err = _do_db_create(data, table_class, db_obj)
    return err


def _gen_label_qrcode(
    tmpdirpath: Path, user: str, box: str, room: str, color: str
) -> str:
    """generate QR code in a file in the temporary directory for use in PDF generation"""

    # generate QR code in SVG for use in PDF
    errcorlvl = QrCode.Ecc.LOW  # Error correction level
    qr_svg_file = f"label_{box}.svg"
    qr_svg_path = Path(tmpdirpath) / qr_svg_file
    # qr_img = qrcode.make(
    #    _gen_label_uri(user, box, room, color),
    #    box_size=13,
    #    border=5,
    #    image_factory=qrcode.image.svg.SvgImage,
    #    error_correction=qrcode.constants.ERROR_CORRECT_Q,
    # )
    qrcode = QrCode.encode_text(
             _gen_label_uri(user, box, room, color),
             errcorlvl)

    # qrcode.save(f"{tmpdirpath}/{qr_svg_file}")
    with open(qr_svg_path, "wt", encoding="utf-8") as qr_file:
        qr_file.write(to_svg_str(qrcode, border=5))
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
    db_file = _get_db_file(args)
    if db_file is None:
        return "database file not specified"
    db_obj = MoveBoxTrackerDB(db_file, prompt=cli_prompt)
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
    db_file = _get_db_file(args)
    if db_file is None:
        return "database file not specified"
    db_obj = MoveBoxTrackerDB(db_file, prompt=cli_prompt)
    db_obj.db_dump()
    return None


def _do_db(args: dict) -> ErrStr | None:
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
    db_obj = MoveBoxTrackerDB(db_file, prompt=cli_prompt)
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


def _common_db_file_arg(arg_parser: argparse.ArgumentParser) -> None:
    arg_parser.add_argument(
        "--db", "--db_file", dest="db_file", action="store", metavar="DB", help="database file"
    )


def _gen_arg_subparsers_init(subparsers) -> None:
    # init subparser
    parser_init = subparsers.add_parser(
        "init", help="initialize new moving box database"
    )
    _common_db_file_arg(parser_init)
    parser_init.add_argument("--primary_user", "--user")  # db field
    parser_init.add_argument("--title")  # db field
    parser_init.add_argument("--found_contact", "--found", "--contact")  # db field
    parser_init.set_defaults(func=_do_init, omit_id=True)


def _gen_arg_subparsers_batch(subparsers) -> None:
    # batch subparser
    parser_batch = subparsers.add_parser(
        "batch", help="create or update a batch record"
    )
    _common_db_file_arg(parser_batch)
    parser_batch.add_argument("--id")  # db field
    parser_batch.add_argument("--timestamp")  # db field
    parser_batch.add_argument("--location")  # db field
    parser_batch.add_argument("--commit", action='store_true')  # action handler
    parser_batch.set_defaults(table="batch", func=_do_record_cli)


def _gen_arg_subparsers_box(subparsers) -> None:
    # box subparser
    parser_box = subparsers.add_parser(
        "box", help="create or update a moving box record"
    )
    _common_db_file_arg(parser_box)
    parser_box.add_argument("--id")  # db field
    parser_box.add_argument("--location")  # db field
    parser_box.add_argument("--info", "--desc", "--description")  # db field
    parser_box.add_argument("--room")  # db field
    parser_box.add_argument("--user")  # db field
    parser_box.add_argument("--image")  # db field
    parser_box.set_defaults(table="box", func=_do_record_cli)


def _gen_arg_subparsers_image(subparsers) -> None:
    # image subparser
    parser_image = subparsers.add_parser(
        "image", help="create or update an image record"
    )
    _common_db_file_arg(parser_image)
    parser_image.add_argument("--id")  # db field
    parser_image.add_argument("--image_file", "--file")  # db field
    parser_image.add_argument("--description", "--info", "--desc")  # db field
    parser_image.add_argument("--timestamp")  # db field
    parser_image.set_defaults(table="image", func=_do_record_cli)


def _gen_arg_subparsers_item(subparsers) -> None:
    # item subparser
    parser_item = subparsers.add_parser(
        "item", help="create or update an item record"
    )
    _common_db_file_arg(parser_item)
    parser_item.add_argument("--id")  # db field
    parser_item.add_argument("--box")  # db field
    parser_item.add_argument("--description", "--info", "--desc")  # db field
    parser_item.add_argument("--image")  # db field
    parser_item.set_defaults(table="item", func=_do_record_cli)


def _gen_arg_subparsers_location(subparsers) -> None:
    # location subparser
    parser_location = subparsers.add_parser(
        "location", help="create or update a location record"
    )
    _common_db_file_arg(parser_location)
    parser_location.add_argument("--id")  # db field
    parser_location.add_argument("--name")  # db field
    parser_location.set_defaults(table="location", func=_do_record_cli)


def _gen_arg_subparsers_room(subparsers) -> None:
    # room subparser
    parser_room = subparsers.add_parser(
        "room", help="create or update a room record"
    )
    _common_db_file_arg(parser_room)
    parser_room.add_argument("--id")  # db field
    parser_room.add_argument("--name")  # db field
    parser_room.add_argument("--color")  # db field
    parser_room.set_defaults(table="room", func=_do_record_cli)


def _gen_arg_subparsers_scan(subparsers) -> None:
    # scan subparser
    parser_scan = subparsers.add_parser(
        "scan", help="create or update a scan record"
    )
    _common_db_file_arg(parser_scan)
    parser_scan.add_argument("--id")  # db field
    parser_scan.add_argument("--box")  # db field
    parser_scan.add_argument("--batch")  # db field
    parser_scan.add_argument("--user")  # db field
    parser_scan.add_argument("--timestamp")  # db field
    parser_scan.set_defaults(table="scan", func=_do_record_cli)


def _gen_arg_subparsers_user(subparsers) -> None:
    # user subparser
    parser_user = subparsers.add_parser(
        "user", help="create or update a user record"
    )
    _common_db_file_arg(parser_user)
    parser_user.add_argument("--id")  # db field
    parser_user.add_argument("--name")  # db field
    parser_user.set_defaults(table="user", func=_do_record_cli)


def _gen_arg_subparsers_label(subparsers) -> None:
    # label subparser
    parser_label = subparsers.add_parser(
        "label", help="print label(s) for specified box ids"
    )
    _common_db_file_arg(parser_label)
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


def _gen_arg_subparsers_merge(subparsers) -> None:
    # merge subparser
    parser_merge = subparsers.add_parser(
        "merge", help="merge in an external SQLite database file, from another device"
    )
    _common_db_file_arg(parser_merge)
    parser_merge.add_argument(
        "db_merge", nargs=1, metavar="DB2", help="database file to merge in"
    )
    parser_merge.set_defaults(func=_do_merge)


def _gen_arg_subparsers_dump(subparsers) -> None:
    # dump subparser
    parser_dump = subparsers.add_parser(
        "dump", help="dump database contents to standard output"
    )
    _common_db_file_arg(parser_dump)
    parser_dump.set_defaults(func=_do_dump)


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
