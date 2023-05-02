"""
label generator code for moveboxtracker
"""

import os
import tempfile
from shutil import move
from pathlib import Path
from qrcodegen import QrCode
from colorlookup import Color
from weasyprint import HTML, CSS

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
        for key in ["box", "room", "color", "location", "user", "found"]:
            if key not in box_data:
                raise RuntimeError(f"missing {key} in label parameters")

        # collect parameters
        self.box = str(box_data["box"]).zfill(4)
        self.room = str(box_data["room"]).upper()
        self.color = Color(box_data["color"]).name.replace(" ", "")
        self.location = str(box_data["location"])
        self.user = str(box_data["user"])
        self.found = str(box_data["found"])
        # setattr(self, key, box_data[key])

    @classmethod
    def gen_label(cls, box_data: dict, outdir: Path) -> None:
        """generate one moving box label file from a dict of the box's data"""
        label_obj = MoveBoxLabel(box_data, outdir)
        label_obj._gen_label()

    def get_box(self):
        """accessor for box attribute"""
        return self.box

    def get_room(self):
        """accessor for room attribute"""
        return self.room

    def get_color(self):
        """accessor for color attribute"""
        return self.color

    def get_location(self):
        """accessor for location attribute"""
        return self.location

    def get_user(self):
        """accessor for user attribute"""
        return self.user

    def get_found(self):
        """accessor for found attribute"""
        return self.found

    def get_outdir(self):
        """accessor for outdir attribute"""
        return self.outdir

    def _gen_label_uri(self):
        """generate URI for moving box label QR code"""

        # determine box URI text for QR code
        uri = f"movingbox://{self.user}/{self.box}?room={self.room},color={self.color}"
        return uri

    def _gen_label_qrcode(self, tmpdirpath: Path) -> str:
        """generate QR code in a file in the temporary directory for use in PDF generation"""

        # generate QR code in SVG for use in PDF
        errcorlvl = QrCode.Ecc.LOW  # Error correction level
        qr_svg_file = f"label_{self.box}.svg"
        qr_svg_path = Path(tmpdirpath) / qr_svg_file
        qrcode = QrCode.encode_text(
                 self._gen_label_uri(),
                 errcorlvl)

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
            f"<td><big><b>{self.room}</b></big></td>",
            f'<td style="text-align: right"><big>Box&nbsp;{self.box}</big></td>',
            "</tr>",
            "<tr>",
            f'<td style="background: {self.color}">&nbsp;</td>',
            f'<td><img src="{qr_svg_file}"></td>',
            "</tr>",
            "<tr>",
            '<td colspan=2 style="text-align: center">',
            "Lost &amp; found contact:",
            "<br/>",
            f'{self.found}',
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
        html_file_path = Path(f"{tmpdirpath}/label_{self.box}.html")
        with open(html_file_path, "wt", encoding="utf-8") as textfile:
            textfile.write("\n".join(label_html))
        return html_file_path

    def _gen_label(self) -> None:
        """generate a moving box label file for label object's data"""

        # verify output directory exists
        if not self.outdir.exists():
            self.outdir.mkdir(mode=0o770, parents=True, exist_ok=True)

        # skip this label if destination PDF exists
        label_pdf_basename = f"label_{self.box}.pdf"
        if Path(self.outdir / label_pdf_basename).is_file():
            print(f"skipping {self.box}: label PDF exists at {label_pdf_basename}")
            return

        # allocate temporary directory
        tmpdirpath = tempfile.mkdtemp(prefix="moving_label_")

        # generate QR code in SVG for use in PDF
        qr_svg_file = self._gen_label_qrcode(tmpdirpath)

        # Build moving box label as HTML and print.
        # Simple HTML is PDF'ed & printed, then discarded when the temporary directory is removed.
        # Just build HTML strings to minimize library dependencies.
        html_file_path = self._gen_label_html(tmpdirpath, qr_svg_file)
        css = CSS(string=BOX_LABEL_STYLESHEET)

        # generate PDF
        label_pdf_file = Path(tmpdirpath + "/" + label_pdf_basename)
        doc = HTML(filename=html_file_path)
        doc.write_pdf(
            target=label_pdf_file,
            stylesheets=[css],
            attachments=[f"{tmpdirpath}/{qr_svg_file}"],
            optimize_size=("fonts", "images"),
        )
        move(label_pdf_file, self.outdir)
        return
