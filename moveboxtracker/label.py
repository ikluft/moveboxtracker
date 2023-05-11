"""
label generator code for moveboxtracker
"""

import os
import sys
import tempfile
from shutil import move
from pathlib import Path
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


class MoveBoxLabel:
    """generate moving box labels"""

    def __init__(self, box_data: dict, outdir: Path):
        self.outdir = outdir
        for key in ["box", "room", "color", "user", "found"]:
            if key not in box_data:
                raise RuntimeError(f"missing {key} in label parameters")

        # collect parameters
        self.field = {}
        self.field["box"] = str(box_data["box"]).zfill(4)
        self.field["room"] = str(box_data["room"]).upper()
        self.field["color"] = Color(box_data["color"])
        self.field["user"] = str(box_data["user"])
        self.field["found"] = str(box_data["found"])
        if "type" in box_data:
            self.type = str(box_data["type"])
        else:
            self.type = DEFAULT_LABEL_TYPE
        self.tempdirpath = None  # lazy initialization: allocated 1st call to tempdir() method
        # setattr(self, key, box_data[key])

    @classmethod
    def gen_label(cls, box_data: dict, outdir: Path) -> None:
        """generate one moving box label file from a dict of the box's data"""

        # look up subclass to generate requested label type, default to HTML-layout full-page
        if "type" not in box_data:
            label_type = box_data["type"]
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

        # verify output directory exists
        if not outdir.exists():
            outdir.mkdir(mode=0o770, parents=True, exist_ok=True)

        # generate label using the subclass' gen_label2() method
        label_obj = label_class(box_data, outdir)
        print("generating label with " + label_obj.attrdump(), file=sys.stderr)
        label_obj.gen_label2()

    def box(self) -> str:
        """accessor for box field"""
        return self.field["box"]

    def room(self) -> str:
        """accessor for room field"""
        return self.field["room"]

    def color(self) -> str:
        """accessor for color field"""
        return self.field["color"].name.replace(" ", "")

    def color_rgb(self) -> tuple[float, float, float]:
        """accessor for color field as RGB tuple"""
        return self.field["color"].rgb

    def color_hex(self) -> str:
        """accessor for color field as RGB hexadecimal"""
        return self.field["color"].hex

    def user(self) -> str:
        """accessor for user field"""
        return self.field["user"]

    def found(self) -> str:
        """accessor for found field"""
        return self.field["found"]

    def get_type(self) -> str:
        """accessor for type attribute"""
        return self.type

    def get_outdir(self) -> Path:
        """accessor for outdir attribute"""
        return self.outdir

    def attrdump(self) -> str:
        """return string with attribute dump"""
        return f"{self.field} type={self.type} outdir={self.outdir}"

    def pdf_basename(self) -> str:
        """get basename for label PDF file to be generated"""
        return f"label_{self.field['box']}.pdf"

    def tempdir(self) -> Path:
        """get temporary directory path"""
        if self.tempdirpath is None:
            # pylint: disable=consider-using-with
            self.tempdirpath = tempfile.mkdtemp(prefix="moving_label_")
        return Path(self.tempdirpath)

    def _gen_label_uri(self):
        """generate URI for moving box label QR code"""

        # determine box URI text for QR code
        uri = (
            f"movingbox://{self.field['user']}/{self.field['box']}?room={self.field['room']},"
            + "color=" + self.color()
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

        # skip this label if destination PDF exists
        label_pdf_basename = self.pdf_basename()
        if Path(self.outdir / label_pdf_basename).is_file():
            print(
                f"skipping {self.field['box']}: label PDF exists at {label_pdf_basename}"
            )
            return

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
        return


class MoveBoxLabelBagTag(MoveBoxLabel):
    """generate moving box labels in bag tag format with SVG layout"""

    def gen_label2(self) -> None:
        """generate a moving box label file for label object's data"""

        # skip this label if destination PDF exists
        label_pdf_basename = self.pdf_basename()
        if Path(self.outdir / label_pdf_basename).is_file():
            print(
                f"skipping {self.field['box']}: label PDF exists at {label_pdf_basename}"
            )
            return

        # allocate temporary directory
        tmpdirpath = self.tempdir()

        # generate QR code
        qrcode_widget = QrCodeWidget(value=self._gen_label_uri(), barBorder=5,
                                     barWidth=1.5 * inch, barHeight=1.5 * inch)
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
            String(0, 1.8 * inch, "Box #" + self.box(), fontSize=18, fontName='Helvetica-Bold'),
            String(0, 1.55 * inch, self.room(), fontSize=18, fontName='Helvetica'),
            Rect(0, 0.5 * inch, 1.5 * inch, 1.0 * inch,
                 fillColor=HexColor(self.color_hex()),
                 strokeWidth=0),
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
        return
