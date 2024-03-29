"""
printable: label & sign generator code for moveboxtracker
"""
#    printable.py - printable classes for MoveBoxTracker
#    Copyright (C) 2023-2024 Ian Kluft
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.`

import os
import sys
import tempfile
from shutil import move
from pathlib import Path
from abc import abstractmethod
import sh
from qrcodegen import QrCode
from colorlookup import Color

# for WeasyPrint HTML/CSS layout and PDF generation
from weasyprint import HTML, CSS

# for ReportLab layout and PDF generation
from reportlab.graphics.shapes import Drawing, Rect, String, Group
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.graphics.charts.textlabels import Label
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics import renderPDF

# database access
from .db import MoveBoxTrackerDB, MoveDbMovingBox, MoveDbRoom

# map label type names to subclasses
NAME_TO_LABEL_CLASS = {
    "page": "MoveBoxLabelPage",
    "bagtag": "MoveBoxLabelBagTag",
}
DEFAULT_LABEL_TYPE = "page"

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
DEST_SIGN_STYLESHEET = (
    """
    @page {
        size: """
    + PAGE_SIZE
    + """;
        margin: 1in;
    }
    table {
        width: 100%
        table-layout: fixed;
        font-family: sans-serif;
    }
    big {
        font-size: 48pt;
    }
    .box {
        height: 6in;
        width: 3in;
        margin: 15px;
        border: 1px solid black;
    }
    .centered
    {
        text-align: center;
    }
    """
)


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


class MoveBoxPrintable:
    """base class for printables"""

    def __init__(
        self,
        outdir: Path,
    ):
        # initialize common fields
        self.tempdirpath = None  # lazy initialization: allocated 1st call to tempdir() method
        self.field = {}

        # verify output directory exists
        self.outdir = outdir
        if not self.outdir.is_dir():
            self.outdir.mkdir(mode=0o770, parents=True, exist_ok=True)

    # abstract methods must be defined by subclasses
    @abstractmethod
    def pdf_basename(self) -> str:
        """get basename for label PDF file to be generated"""

    @abstractmethod
    def attrdump(self) -> str:
        """return string with attribute dump"""

    # common read accessor methods provided by parent class
    def tempdir(self) -> Path:
        """get temporary directory path"""
        if self.tempdirpath is None:
            # pylint: disable=consider-using-with
            self.tempdirpath = tempfile.mkdtemp(prefix="moving_label_")
        return Path(self.tempdirpath)

    def get_outdir(self) -> Path:
        """accessor for outdir attribute"""
        return self.outdir

    def room(self) -> str:
        """accessor for room field"""
        if "room" not in self.field:
            raise RuntimeError("accessed room without setting it")
        return self.field["room"]

    def color(self) -> str:
        """accessor for color field"""
        if "color" not in self.field:
            raise RuntimeError("accessed color without setting it")
        return self.field["color"].name.replace(" ", "")

    def color_rgb(self) -> tuple[float, float, float]:
        """accessor for color field as RGB tuple"""
        if "color" not in self.field:
            raise RuntimeError("accessed color without setting it")
        return self.field["color"].rgb

    def color_hex(self) -> str:
        """accessor for color field as RGB hexadecimal"""
        if "color" not in self.field:
            raise RuntimeError("accessed color without setting it")
        return self.field["color"].hex


class MoveBoxLabel(MoveBoxPrintable):
    """generate moving box labels"""

    def __init__(
        self,
        box_id: int,
        db_obj: MoveBoxTrackerDB,
        outdir: Path,
        label_type: str = DEFAULT_LABEL_TYPE,
    ):
        super().__init__(outdir)

        # retreive fields from database
        rec_obj = MoveDbMovingBox(db_obj)
        box_data = rec_obj.box_label_data(box_id)
        for key in ["box", "room", "color", "user", "found"]:
            if key not in box_data:
                raise RuntimeError(f"missing {key} in label parameters")

        # collect parameters
        self.type = label_type
        self.field["box"] = str(box_data["box"]).zfill(4)
        self.field["room"] = str(box_data["room"]).upper()
        self.field["color"] = Color(box_data["color"])
        self.field["user"] = str(box_data["user"])
        self.field["found"] = str(box_data["found"])

    @classmethod
    def typed_new(
        cls,
        box_id: int,
        db_obj: MoveBoxTrackerDB,
        outdir: Path,
        **kwargs,
    ):
        """create new MoveBoxLabel object of appropriate subclass based on type parameter"""
        if "type" in kwargs and kwargs["type"] is not None:
            label_type = kwargs["type"]
        else:
            label_type = DEFAULT_LABEL_TYPE
        if label_type in NAME_TO_LABEL_CLASS:
            label_class_name = NAME_TO_LABEL_CLASS[label_type]
            global_syms = globals()
            if label_class_name in global_syms:
                label_class = global_syms[label_class_name]
            else:
                raise RuntimeError(f"label class {label_class_name} not found")
        else:
            raise RuntimeError(f"no label class found to handle {label_type} type")
        label_obj = label_class(box_id, db_obj, outdir, label_type)
        return label_obj

    def gen_label(self) -> None:
        """generate one moving box label file from a dict of the box's data"""

        # skip this label if destination PDF exists
        label_pdf_basename = self.pdf_basename()
        if Path(self.outdir / label_pdf_basename).is_file():
            print(f"label {self.field['box']} PDF exists at {label_pdf_basename}: leaving it as-is")
            return

        # generate label using the subclass' gen_label2() method
        print("generating label with " + self.attrdump(), file=sys.stderr)
        try:
            gen_label2_func = getattr(self.__class__, "gen_label2")
        except AttributeError as exc:
            exc.add_note(f"class {self.__class__} doesn't implement gen_label2 method")
            raise
        gen_label2_func(self)

    def print_label(self) -> None:
        """send the PDF label to a printer"""

        print("printing label " + self.box())
        pdf_path = Path(self.outdir / self.pdf_basename())
        if pdf_path.is_file():
            lpr_cmd = sh.Command("lpr")
            lpr_cmd(pdf_path)
        else:
            raise RuntimeError(f"PDF file {pdf_path} not found")

    def box(self) -> str:
        """accessor for box field"""
        return self.field["box"]

    def user(self) -> str:
        """accessor for user field"""
        return self.field["user"]

    def found(self) -> str:
        """accessor for found field"""
        return self.field["found"]

    def get_type(self) -> str:
        """accessor for type attribute"""
        return self.type

    def attrdump(self) -> str:
        """return string with attribute dump"""
        return f"{self.field} type={self.type} outdir={self.outdir}"

    def pdf_basename(self) -> str:
        """get basename for label PDF file to be generated"""
        return f"label_{self.field['box']}.pdf"

    def _gen_label_uri(self):
        """generate URI for moving box label QR code"""

        # determine box URI text for QR code
        uri = (
            f"movingbox://{self.field['user']}/{self.field['box']}?room={self.field['room']},"
            + "color="
            + self.color()
        )
        return uri


class MoveBoxLabelPage(MoveBoxLabel):
    """generate moving box labels with HTML layout for full-page printing"""

    def _gen_label_qrcode(self, tmpdirpath: Path) -> str:
        """generate QR code in a file in the temporary directory for use in PDF generation"""

        # generate QR code in SVG for use in PDF
        errcorlvl = QrCode.Ecc.LOW  # Error correction level
        qr_svg_file = f"label_{self.field['box']}.svg"
        qr_svg_path = tmpdirpath / qr_svg_file
        qrcode = QrCode.encode_text(self._gen_label_uri(), errcorlvl)

        # qrcode.save(f"{tmpdirpath}/{qr_svg_file}")
        with open(qr_svg_path, "wt", encoding="utf-8") as qr_file:
            qr_file.write(to_svg_str(qrcode, border=5))
        return qr_svg_file

    def _gen_label_html(self, tmpdirpath: Path, qr_svg_file: Path) -> str:
        """generate HTML in a file in the temporary directory for use in PDF generation"""

        # generate label cell
        # 4 of these will be printed on each page
        label_cell = [
            '<table id="label_cell">',
            "<tr>",
            f"<td><big><b>{self.field['room']}</b></big></td>",
            f'<td style="text-align: right"><big>Box&nbsp;{self.field["box"]}</big></td>',
            "</tr>",
            "<tr>",
            '<td style="background: ' + self.color_hex() + '">&nbsp;</td>',
            f'<td><img src="{qr_svg_file}"></td>',
            "</tr>",
            "<tr>",
            '<td colspan=2 style="text-align: center">',
            "Lost &amp; found contact:",
            "<br/>",
            f"{self.field['found']}",
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
        html_file_path = Path(f"{tmpdirpath}/label_{self.field['box']}.html")
        with open(html_file_path, "wt", encoding="utf-8") as textfile:
            textfile.write("\n".join(label_html))
        return html_file_path

    def gen_label2(self) -> None:
        """generate a moving box label file for label object's data"""

        # allocate temporary directory
        tmpdirpath = self.tempdir()

        # generate QR code in SVG for use in PDF
        qr_svg_file = self._gen_label_qrcode(tmpdirpath)

        # Build moving box label as HTML and print.
        # Simple HTML is PDF'ed & printed, then discarded when the temporary directory is removed.
        # Just build HTML strings to minimize library dependencies.
        html_file_path = self._gen_label_html(tmpdirpath, qr_svg_file)
        css = CSS(string=BOX_LABEL_STYLESHEET)

        # generate PDF
        label_pdf_file = Path(tmpdirpath / self.pdf_basename())
        doc = HTML(filename=html_file_path)
        doc.write_pdf(
            target=label_pdf_file,
            stylesheets=[css],
            attachments=[f"{tmpdirpath}/{qr_svg_file}"],
            optimize_size=("fonts", "images"),
        )
        move(label_pdf_file, self.outdir)


class MoveBoxLabelBagTag(MoveBoxLabel):
    """generate moving box labels in bag tag format with SVG layout"""

    def gen_label2(self) -> None:
        """generate a moving box label file for label object's data"""

        # allocate temporary directory
        tmpdirpath = self.tempdir()

        # generate QR code
        qrcode_widget = QrCodeWidget(
            value=self._gen_label_uri(), barBorder=5, barWidth=1.5 * inch, barHeight=1.5 * inch
        )
        qrcode_drawing = Drawing(1.5 * inch, 1.5 * inch)
        qrcode_drawing.add(qrcode_widget)
        qrcode_drawing.translate(1.5 * inch, 0.5 * inch)

        # generate lost+found text
        found_label = Label()
        found_label.boxAnchor = "n"
        found_label.textAnchor = "middle"
        found_label.fontName = "Helvetica"
        found_label.fontSize = 10
        found_label.setOrigin(1.5 * inch, 0.5 * inch)
        found_label.setText(f"Lost & found contact:\n{self.field['found']}")

        # generate label graphic
        tag_group = Group(
            String(0, 1.8 * inch, "Box #" + self.box(), fontSize=18, fontName="Helvetica-Bold"),
            String(0, 1.55 * inch, self.room(), fontSize=18, fontName="Helvetica"),
            Rect(
                0,
                0.5 * inch,
                1.5 * inch,
                1.0 * inch,
                fillColor=HexColor(self.color_hex()),
                strokeWidth=0,
            ),
            qrcode_drawing,
            found_label,
        )
        two_tag_drawing = Drawing(3 * inch, 4.05 * inch)
        first_tag = Group(tag_group)
        first_tag.translate(0, 0)
        two_tag_drawing.add(first_tag)
        second_tag = Group(tag_group)
        second_tag.translate(0, 2.05 * inch)
        two_tag_drawing.add(second_tag)

        # write PDF file
        label_pdf_file = tmpdirpath / self.pdf_basename()
        renderPDF.drawToFile(two_tag_drawing, str(label_pdf_file))
        move(label_pdf_file, self.outdir)


class MoveBoxDestSign(MoveBoxPrintable):
    """generate room destination signs"""

    def __init__(
        self,
        room_id: int,
        db_obj: MoveBoxTrackerDB,
        outdir: Path,
    ):
        super().__init__(outdir)

        # retreive fields from database
        rec_obj = MoveDbRoom(db_obj)
        room_data = rec_obj.dest_sign_data(room_id)
        for key in ["room_id", "room", "color", "title"]:
            if key not in room_data:
                raise RuntimeError(f"missing {key} in label parameters")

        # collect parameters
        self.field["room_id"] = str(room_data["room_id"]).upper()
        self.field["room"] = str(room_data["room"]).upper()
        self.field["color"] = Color(room_data["color"])
        self.field["title"] = room_data["title"]

    def room_id(self) -> str:
        """accessor for room id"""
        if "room_id" not in self.field:
            raise RuntimeError("accessed room_id without setting it")
        return self.field["room_id"]

    def title(self) -> str:
        """accessor for room id"""
        if "title" not in self.field:
            raise RuntimeError("accessed title without setting it")
        return self.field["title"]

    def gen_destsign(self) -> None:
        """generate one room destination sign file from the room's data"""

        # skip this destination sign if destination PDF exists
        destsign_pdf_basename = self.pdf_basename()
        if Path(self.outdir / destsign_pdf_basename).is_file():
            print(f"destsign {self.field['room']} PDF exists at {destsign_pdf_basename}: "
                  + "leaving it as-is")
            return

        print("generating destsign with " + self.attrdump(), file=sys.stderr)

        # allocate temporary directory
        tmpdirpath = self.tempdir()

        # Build destination sign as HTML and print.
        # Simple HTML is PDF'ed & printed, then discarded when the temporary directory is removed.
        # Just build HTML strings to minimize library dependencies.
        html_file_path = self._gen_destsign_html(tmpdirpath)
        css = CSS(string=DEST_SIGN_STYLESHEET)

        # generate PDF
        destsign_pdf_file = Path(tmpdirpath / self.pdf_basename())
        doc = HTML(filename=html_file_path)
        doc.write_pdf(
            target=destsign_pdf_file,
            stylesheets=[css],
            optimize_size=("fonts", "images"),
        )
        move(destsign_pdf_file, self.outdir)

    def print_destsign(self) -> None:
        """send the PDF destination sign to a printer"""

        print("printing destsign " + self.room_id())
        pdf_path = Path(self.outdir / self.pdf_basename())
        if pdf_path.is_file():
            lpr_cmd = sh.Command("lpr")
            lpr_cmd(pdf_path)
        else:
            raise RuntimeError(f"PDF file {pdf_path} not found")

    def pdf_basename(self) -> str:
        """get basename for sign PDF file to be generated"""
        return "destsign_" + self.room_id() + ".pdf"

    def attrdump(self) -> str:
        """return string with attribute dump"""
        return f"{self.field} outdir={self.outdir}"

    def _gen_destsign_html(self, tmpdirpath: Path) -> str:
        """generate HTML in a file in the temporary directory for use in PDF generation"""

        # generate destination sign
        # this will be inserted in HTML page structure below
        destsign_cell = [
            '<table id="destsign_cell">',
            "<tr>",
            '<td><big><b>' + self.room() + '</b></big></td>',
            '<td rowspan=5>',
            '<div class="box" style="background: ' + self.color_hex() + '">',
            "</div>",
            "</td>",
            "</tr>",
            "<tr>",
            "<td>&nbsp;</td>",
            "</tr>",
            "<tr>",
            "<td>",
            "destination for boxes tagged",
            "</br>",
            "<b>" + self.room() + "</b>",
            "</td>",
            "</tr>",
            "<tr>",
            "<td>&nbsp;</td>",
            "</tr>",
            "<tr>",
            "<td>",
            "color coded",
            "</br>",
            "<b>" + self.color() + "</b>",
            "</td>",
            "</tr>",
            "<tr colspan=2>",
            "<td>&nbsp;</td>",
            "</tr>",
            "<tr>",
            '<td colspan=2 class="centered">',
            "Move project: " + self.title(),
            "</td>",
            "</tr>",
            "</table>",
        ]

        # generate HTML for destsign
        destsign_html = (
            [
                "<html>",
                "<head>",
                "</head>",
                "<body>",
            ]
            + destsign_cell
            + ["</body>", "</html>"]
        )
        html_file_path = Path(f"{tmpdirpath}/destsign_{self.field['room']}.html")
        with open(html_file_path, "wt", encoding="utf-8") as textfile:
            textfile.write("\n".join(destsign_html))
        return html_file_path
