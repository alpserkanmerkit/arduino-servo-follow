"""Shared drawing kit for the breadboard wiring diagrams (Tinkercad/Fritzing style).

One drawing language for every project in this repo: an Arduino Uno R3 on the left (rotated so the digital
header faces the breadboard), an 830-point breadboard, realistic parts, coloured jumper wires with a white
numbered circle on each, and a "Build it in this order" panel whose numbers match the circles.

Adding a new experiment = a new `docs/draw_wiring.py` that
  1. creates `Sheet(title, subtitle, height)`,
  2. calls `uno(...)`, `breadboard()` and the part helpers it needs,
  3. draws wires with `wire(...)` / `uno_wire(...)` (the second one also records the Uno pin + code symbol),
  4. calls `panel(steps, notes)` and `save(svg_path, sketches=[...])`.
`save()` refuses to write when a numbered circle has no step (or a step has no circle), and writes a
`*.pins.json` next to the SVG that `tools/check_pins.py` compares against the sketches.

Arduino Uno R3 header order (official board layout; also visible in the owner's Tinkercad screenshots):
  digital  SCL SDA AREF GND 13 12 ~11 ~10 ~9 8 | 7 ~6 ~5 4 ~3 2 TX1 RX0
  power    NC IOREF RESET 3.3V 5V GND GND VIN  | A0 A1 A2 A3 A4 A5
"""
import json
from pathlib import Path

P = 20                       # breadboard pitch (0.1") in px
W = 1960                     # canvas width (height is per sheet)
UX, UY = 60, 200             # Uno origin (drawn rotated 90 deg clockwise)
BX, BY = 600, UY + 158       # breadboard origin: D11/D10/D9 sit between rows b/c, c/d, d/e

ROW = {"T+": BY + 30, "T-": BY + 50,
       **{r: BY + 100 + i * P for i, r in enumerate("abcde")},
       **{r: BY + 240 + i * P for i, r in enumerate("fghij")},
       "B+": BY + 370, "B-": BY + 390}
BB_BOTTOM = BY + 420

# wire colours: COL = jacket, DARK = outline / badge ring
COL = {"5v": "#e53935", "gnd": "#263238", "trig": "#43a047", "echo": "#1e88e5", "red": "#fb8c00",
       "blue": "#8e24aa", "green": "#00acc1", "pwm": "#fdd835", "bat": "#d81b60", "sig": "#fb8c00",
       "soil": "#7cb342"}
DARK = {"5v": "#8e1b18", "gnd": "#000000", "trig": "#1b5e20", "echo": "#0d47a1", "red": "#a35a00",
        "blue": "#4a148c", "green": "#006064", "pwm": "#a68f00", "bat": "#880e4f", "sig": "#a35a00",
        "soil": "#33691e"}

R220 = ["#e53935", "#e53935", "#6d4c41", "#c9a227"]     # red red brown gold
R1K = ["#6d4c41", "#212121", "#e53935", "#c9a227"]      # brown black red gold

# (key, printed label, offset along the header in the board's native frame)
DIGITAL = [("SCL", "SCL", 168), ("SDA", "SDA", 188), ("AREF", "AREF", 208), ("GND_D", "GND", 228),
           ("D13", "13", 248), ("D12", "12", 268), ("D11", "~11", 288), ("D10", "~10", 308), ("D9", "~9", 328),
           ("D8", "8", 348), ("D7", "7", 380), ("D6", "~6", 400), ("D5", "~5", 420), ("D4", "4", 440),
           ("D3", "~3", 460), ("D2", "2", 480), ("D1", "TX 1", 500), ("D0", "RX 0", 520)]
POWER = [("NC", "NC", 240), ("IOREF", "IOREF", 260), ("RESET", "RESET", 280), ("3V3", "3.3V", 300),
         ("5V", "5V", 320), ("GND", "GND", 340), ("GND2", "GND", 360), ("VIN", "VIN", 380),
         ("A0", "A0", 420), ("A1", "A1", 440), ("A2", "A2", 460), ("A3", "A3", 480), ("A4", "A4", 500),
         ("A5", "A5", 520)]
_D = {k: o for k, _, o in DIGITAL}
_P = {k: o for k, _, o in POWER}
PIN_LABEL = {"GND_D": "GND", "GND2": "GND", "3V3": "3.3V"}


def cx(col):
    return BX + 40 + (col - 1) * P


def hole(col, row):
    return (cx(col), ROW[row])


def pin_xy(key):
    """Global position of an Uno header pin. Digital header = right edge, power/analog = left edge."""
    if key in _D:
        return (UX + 400, UY + _D[key])
    return (UX + 20, UY + _P[key])


def rounded(points, r=8):
    d = f"M{points[0][0]},{points[0][1]}"
    for i in range(1, len(points) - 1):
        (x0, y0), (x1, y1), (x2, y2) = points[i - 1], points[i], points[i + 1]

        def towards(ax, ay, bx, by, dist):
            L = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5 or 1
            k = min(dist, L / 2) / L
            return ax + (bx - ax) * k, ay + (by - ay) * k
        a = towards(x1, y1, x0, y0, r)
        b = towards(x1, y1, x2, y2, r)
        d += f" L{a[0]:.1f},{a[1]:.1f} Q{x1},{y1} {b[0]:.1f},{b[1]:.1f}"
    d += f" L{points[-1][0]},{points[-1][1]}"
    return d


class Sheet:
    def __init__(self, title, subtitle, height, subtitle2=None):
        self.H = height
        self.out = []
        self.badges = []
        self.pins = []
        self.free = []
        self.steps_nums = set()
        self.add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" height="{height}" '
                 f'font-family="Segoe UI, Helvetica, Arial, sans-serif">')
        self.add(f'<rect width="{W}" height="{height}" fill="#ffffff"/>')
        self.text(40, 52, title, 28, "#263238", "start", 700)
        self.text(40, 80, subtitle, 15, "#607d8b")
        if subtitle2:
            self.text(40, 102, subtitle2, 15, "#b71c1c", "start", 700)

    # ------------------------------------------------------------ primitives
    def add(self, s):
        self.out.append(s)

    def text(self, x, y, s, size=12, fill="#263238", anchor="start", weight=400, rot=None, family=None):
        s = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        tr = f' transform="rotate({rot} {x} {y})"' if rot is not None else ""
        fam = f' font-family="{family}"' if family else ""
        self.add(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
                 f'font-weight="{weight}"{tr}{fam}>{s}</text>')

    def tag(self, x, y, s, size=10, fill="#263238", anchor="middle"):
        """Bold label on a light pill so it stays readable over breadboard holes."""
        w = len(s) * size * 0.62 + 8
        x0 = x - w / 2 if anchor == "middle" else (x - 4 if anchor == "start" else x - w + 4)
        self.add(f'<rect x="{x0:.1f}" y="{y - size}" width="{w:.1f}" height="{size + 5}" rx="4" fill="#ffffff" opacity="0.92"/>')
        self.text(x, y, s, size, fill, anchor, 700)

    def lead(self, x, y):
        self.add(f'<circle cx="{x}" cy="{y}" r="3.5" fill="#757575"/>')

    def pinhead(self, x, y):
        self.add(f'<rect x="{x - 3}" y="{y - 3}" width="6" height="6" fill="#d4af37"/>')

    # ------------------------------------------------------------ Arduino Uno R3
    def uno(self, used):
        """`used` = set of pin keys (D9, A0, 5V, GND ...) to highlight."""
        add = self.add
        add(f'<g transform="translate({UX + 420} {UY}) rotate(90)">')
        add('<rect x="0" y="0" width="540" height="420" rx="14" fill="#0f7fa6" stroke="#0a5a76" stroke-width="3"/>')
        for hx, hy in ((60, 30), (520, 120), (500, 400), (40, 380)):
            add(f'<circle cx="{hx}" cy="{hy}" r="10" fill="#f4f4f0" stroke="#d6d6cc" stroke-width="2"/>')
        add('<rect x="-26" y="70" width="96" height="90" rx="4" fill="#c9ccd1" stroke="#8f959c" stroke-width="2"/>')  # USB-B
        add('<rect x="-14" y="300" width="84" height="74" rx="6" fill="#222" stroke="#000"/>')                      # DC jack
        add('<rect x="250" y="292" width="232" height="54" rx="4" fill="#262626"/><circle cx="262" cy="319" r="6" fill="#444"/>')
        add('<ellipse cx="190" cy="252" rx="34" ry="12" fill="#d9d9d9" stroke="#9e9e9e"/>')                         # crystal
        add('<rect x="40" y="186" width="34" height="34" rx="4" fill="#cfcfcf"/><circle cx="57" cy="203" r="10" fill="#c62828"/>')
        for x0, n in ((158, 10), (370, 8)):
            add(f'<rect x="{x0}" y="8" width="{n * 20}" height="24" fill="#1a1a1a"/>')
        for x0, n in ((230, 8), (410, 6)):
            add(f'<rect x="{x0}" y="388" width="{n * 20}" height="24" fill="#1a1a1a"/>')
        for key, _, x in DIGITAL:
            add(f'<rect x="{x - 4}" y="16" width="8" height="8" fill="{"#ffd54f" if key in used else "#8a8a8a"}"/>')
        for key, _, x in POWER:
            add(f'<rect x="{x - 4}" y="396" width="8" height="8" fill="{"#ffd54f" if key in used else "#8a8a8a"}"/>')
        add('<text x="300" y="180" font-size="30" font-weight="800" fill="#ffffff" text-anchor="middle">ARDUINO</text>')
        add('<rect x="380" y="150" width="88" height="40" rx="20" fill="none" stroke="#ffffff" stroke-width="3"/>'
            '<text x="424" y="180" font-size="26" font-weight="700" fill="#ffffff" text-anchor="middle">UNO</text>')
        add('<text x="300" y="330" font-size="12" fill="#bdbdbd" text-anchor="middle">ATMEGA328P</text>')
        add('</g>')
        for key, lab, _ in DIGITAL:
            x, y = pin_xy(key)
            hi = key in used
            self.text(x - 14, y + 4, lab, 10, "#ffffff" if hi else "#b3e5fc", "end", 700 if hi else 400)
        for key, lab, _ in POWER:
            x, y = pin_xy(key)
            hi = key in used
            self.text(x + 14, y + 4, lab, 10, "#ffffff" if hi else "#b3e5fc", "start", 700 if hi else 400)
        self.text(UX + 210, UY - 40, "Arduino Uno R3", 14, "#263238", "middle", 700)

    # ------------------------------------------------------------ breadboard (830 points)
    def breadboard(self):
        add, text = self.add, self.text
        w = 40 + 62 * P + 40
        add(f'<rect x="{BX}" y="{BY}" width="{w}" height="420" rx="10" fill="#f1f1ec" stroke="#c9c9c0" stroke-width="2"/>')
        add(f'<rect x="{BX}" y="{BY + 195}" width="{w}" height="30" fill="#e2e2da"/>')
        for y, c in ((BY + 16, "#e53935"), (BY + 64, "#1e88e5"), (BY + 356, "#e53935"), (BY + 404, "#1e88e5")):
            add(f'<line x1="{BX + 30}" y1="{y}" x2="{BX + w - 30}" y2="{y}" stroke="{c}" stroke-width="2"/>')
        for (y, s, c) in ((ROW["T+"], "+", "#e53935"), (ROW["T-"], "−", "#1e88e5"),
                          (ROW["B+"], "+", "#e53935"), (ROW["B-"], "−", "#1e88e5")):
            text(BX + 14, y + 5, s, 16, c, "middle", 700)
            text(BX + w - 14, y + 5, s, 16, c, "middle", 700)
        for r, y in ROW.items():
            for col in range(1, 64):
                add(f'<rect x="{cx(col) - 3.5}" y="{y - 3.5}" width="7" height="7" rx="1.5" fill="#55554f"/>')
            if len(r) == 1:
                text(BX + 18, y + 4, r, 11, "#8a8a80", "middle")
                text(BX + w - 18, y + 4, r, 11, "#8a8a80", "middle")
        for col in [1] + list(range(5, 64, 5)):
            text(cx(col), BY + 84, col, 10, "#8a8a80", "middle")
            text(cx(col), BY + 344, col, 10, "#8a8a80", "middle")

    # ------------------------------------------------------------ parts
    def resistor(self, c0, c1, row, value, bands, label_dy=-14):
        (x0, y), (x1, _) = hole(c0, row), hole(c1, row)
        self.add(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="#9e9e9e" stroke-width="3"/>')
        mx = (x0 + x1) / 2
        self.add(f'<rect x="{mx - 20}" y="{y - 9}" width="40" height="18" rx="8" fill="#e6cfa3" stroke="#8d6e63"/>')
        for i, c in enumerate(bands):
            self.add(f'<rect x="{mx - 13 + i * 7}" y="{y - 9}" width="4" height="18" fill="{c}"/>')
        self.lead(x0, y)
        self.lead(x1, y)
        self.tag(mx, y + label_dy, value, 11, "#5d4037")

    def resistor_v(self, col, value, bands):
        """Resistor standing across the centre gap: row e <-> row f of the same column."""
        (x, y0), (_, y1) = hole(col, "e"), hole(col, "f")
        self.add(f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y1}" stroke="#9e9e9e" stroke-width="3"/>')
        my = (y0 + y1) / 2
        self.add(f'<rect x="{x - 9}" y="{my - 20}" width="18" height="40" rx="8" fill="#e6cfa3" stroke="#8d6e63"/>')
        for i, c in enumerate(bands):
            self.add(f'<rect x="{x - 9}" y="{my - 13 + i * 7}" width="18" height="4" fill="{c}"/>')
        self.lead(x, y0)
        self.lead(x, y1)
        self.tag(x + 14, my + 4, value, 11, "#5d4037", anchor="start")

    def led(self, col_a, row, color, glow):
        """5 mm LED lying in one row: long leg (+, anode) in col_a, short leg in col_a + 1."""
        (xa, y), (xk, _) = hole(col_a, row), hole(col_a + 1, row)
        self.lead(xa, y)
        self.lead(xk, y)
        mx = (xa + xk) / 2
        self.add(f'<circle cx="{mx}" cy="{y}" r="17" fill="{glow}" opacity="0.35"/>')
        self.add(f'<path d="M{mx + 9},{y - 12} A15,15 0 1,0 {mx + 9},{y + 12} Z" fill="{color}" stroke="#00000066" stroke-width="1.5"/>')
        self.add(f'<circle cx="{mx - 4}" cy="{y - 5}" r="4" fill="#ffffff" opacity="0.55"/>')
        self.text(xa - 2, y - 18, "+", 12, "#263238", "middle", 700)

    def hcsr04(self, cols):
        """HC-SR04 standing in row a of the top half; pins VCC TRIG ECHO GND in `cols`."""
        add, text = self.add, self.text
        xc = (cx(cols[0]) + cx(cols[-1])) / 2
        w, h = 354, 157
        x0, bot = xc - w / 2, ROW["a"] - 14
        top = bot - h
        add(f'<rect x="{x0}" y="{top}" width="{w}" height="{h}" rx="6" fill="#1d4f91" stroke="#0d2c57" stroke-width="2"/>')
        for hx, hy in ((x0 + 10, top + 10), (x0 + w - 10, top + 10), (x0 + 10, bot - 10), (x0 + w - 10, bot - 10)):
            add(f'<circle cx="{hx}" cy="{hy}" r="5" fill="#f1f1ec" stroke="#c9a227" stroke-width="1.5"/>')
        for tx in (x0 + 78, x0 + w - 78):
            add(f'<circle cx="{tx}" cy="{top + 68}" r="58" fill="#cfd3d6" stroke="#8f959c" stroke-width="3"/>')
            add(f'<circle cx="{tx}" cy="{top + 68}" r="46" fill="#2b2b2b"/>')
            for r in (38, 28, 18):
                add(f'<circle cx="{tx}" cy="{top + 68}" r="{r}" fill="none" stroke="#4a4a4a" stroke-width="2"/>')
        add(f'<rect x="{xc - 26}" y="{top + 12}" width="52" height="18" rx="9" fill="#d9d9d9" stroke="#9e9e9e"/>')
        text(xc, top + 52, "HC-SR04", 14, "#ffffff", "middle", 700)
        text(x0 + 78, top + 146, "T", 11, "#ffffff", "middle", 700)
        text(x0 + w - 78, top + 146, "R", 11, "#ffffff", "middle", 700)
        for col, lab in zip(cols, ["VCC", "TRIG", "ECHO", "GND"]):
            x, y = hole(col, "a")
            add(f'<rect x="{x - 5}" y="{y - 16}" width="10" height="10" fill="#111"/>')
            add(f'<rect x="{x - 3}" y="{y - 10}" width="6" height="13" fill="#d4af37"/>')
            text(x + 4, bot - 6, lab, 10, "#ffffff", "start", 700, rot=-90)
        text(xc, top - 12, "HC-SR04 ultrasonic sensor (5 V)", 13, "#263238", "middle", 700)

    def tip120(self, col_b, row, label="TIP120"):
        """TO-220 seen from above: printed face toward the viewer, metal tab at the back. Legs B-C-E."""
        (xb, y) = hole(col_b, row)
        xm = xb + P
        self.add(f'<rect x="{xm - 35}" y="{y - 17}" width="70" height="34" rx="3" fill="#212121" stroke="#000" stroke-width="1.5"/>')
        self.add(f'<rect x="{xm - 35}" y="{y - 17}" width="70" height="5" rx="2" fill="#bdbdbd"/>')
        self.text(xm, y - 5, label, 8, "#ffffff", "middle", 700)
        for i, lab in enumerate("BCE"):
            self.add(f'<rect x="{xb + i * P - 3}" y="{y - 1}" width="6" height="6" fill="#d4af37"/>')
            self.text(xb + i * P, y + 14, lab, 8, "#ffffff", "middle", 700)

    def diode(self, c0, c1, row):
        """1N4007, stripe (cathode) at c1."""
        (x0, y), (x1, _) = hole(c0, row), hole(c1, row)
        self.add(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="#9e9e9e" stroke-width="3"/>')
        mx = (x0 + x1) / 2
        self.add(f'<rect x="{mx - 22}" y="{y - 8}" width="44" height="16" rx="3" fill="#212121"/>')
        self.add(f'<rect x="{mx + 12}" y="{y - 8}" width="6" height="16" fill="#d9d9d9"/>')
        self.lead(x0, y)
        self.lead(x1, y)
        self.tag(mx + 10, y - 14, "1N4007")

    def motor(self, x0, x1, y, title, sub):
        """Small DC motor (side view) with a propeller on the left end of the shaft."""
        add = self.add
        add(f'<rect x="{x0}" y="{y}" width="{x1 - x0}" height="56" rx="10" fill="#cfd3d6" stroke="#8f959c" stroke-width="2"/>')
        add(f'<rect x="{x1 - 20}" y="{y}" width="20" height="56" rx="6" fill="#b0b5ba"/>')
        add(f'<rect x="{x0 - 14}" y="{y + 24}" width="14" height="8" fill="#9e9e9e"/>')
        px, py = x0 - 16, y + 28
        add(f'<ellipse cx="{px}" cy="{py}" rx="5" ry="40" fill="#42a5f5" opacity="0.18"/>')
        for dy in (-19, 19):
            add(f'<ellipse cx="{px}" cy="{py + dy}" rx="5" ry="19" fill="#42a5f5" stroke="#1565c0" stroke-width="1.5" '
                f'transform="rotate(12 {px} {py})"/>')
        add(f'<circle cx="{px}" cy="{py}" r="5" fill="#fafafa" stroke="#9e9e9e" stroke-width="1.5"/>')
        xc = (x0 + x1) / 2
        self.text(xc - 10, y + 36, "M", 20, "#37474f", "middle", 800)
        self.text(xc - 30, y + 82, title, 12, "#263238", "middle", 700)
        self.text(xc - 30, y + 98, sub, 10, "#607d8b", "middle")

    def battery(self, x, y, label):
        """4xAA holder (2x2 cells), 154 px wide. Returns (+ terminal, - terminal); + is on the left."""
        self.add(f'<rect x="{x}" y="{y}" width="154" height="108" rx="6" fill="#263238"/>')
        for r in range(2):
            for i in range(2):
                bx, by = x + 12 + i * 68, y + 14 + r * 46
                self.add(f'<rect x="{bx}" y="{by}" width="62" height="38" rx="17" fill="#9e9e9e"/>'
                         f'<rect x="{bx + 18}" y="{by}" width="44" height="38" rx="17" fill="#2e7d32"/>')
                self.text(bx + 40, by + 24, "AA", 11, "#ffffff", "middle", 700)
        self.text(x + 77, y + 128, label, 12, "#263238", "middle", 700)
        self.add(f'<circle cx="{x + 12}" cy="{y + 6}" r="6" fill="#c62828"/>')
        self.add(f'<circle cx="{x + 142}" cy="{y + 6}" r="6" fill="#111"/>')
        return (x + 12, y + 6), (x + 142, y + 6)

    def servo(self, col_sig, title, sub="micro servo", model="SG90"):
        """SG90 seen from above, sitting above the board; brown -> top − rail (col_sig-2),
        red -> top + rail (col_sig-1), orange signal -> row a of col_sig."""
        add, text = self.add, self.text
        xc = cx(col_sig - 1)
        top, h, w = BY - 190, 96, 190
        x0 = xc - w / 2
        add(f'<rect x="{x0 - 26}" y="{top + 34}" width="{w + 52}" height="28" rx="6" fill="#1565c0" stroke="#0d47a1" stroke-width="2"/>')
        for hx in (x0 - 13, x0 + w + 13):
            add(f'<circle cx="{hx}" cy="{top + 48}" r="6" fill="#ffffff" stroke="#0d47a1"/>')
        add(f'<rect x="{x0}" y="{top}" width="{w}" height="{h}" rx="8" fill="#1e88e5" stroke="#0d47a1" stroke-width="2"/>')
        hx, hy = x0 + 52, top + 48
        add(f'<circle cx="{hx}" cy="{hy}" r="30" fill="#1976d2" stroke="#0d47a1" stroke-width="2"/>')
        add(f'<path d="M{hx},{hy - 5} L{hx - 66},{hy - 9} A9,9 0 0,0 {hx - 66},{hy + 9} L{hx},{hy + 5} Z" '
            f'fill="#ffb547" stroke="#a35a00" stroke-width="1.5" transform="rotate(35 {hx} {hy})"/>')
        add(f'<circle cx="{hx}" cy="{hy}" r="9" fill="#fafafa" stroke="#9e9e9e" stroke-width="2"/>')
        text(x0 + 130, top + 44, model, 15, "#ffffff", "middle", 700)
        text(x0 + 130, top + 62, sub, 10, "#e3f2fd", "middle")
        text(xc, top - 14, title, 13, "#263238", "middle", 700)
        bot = top + h
        leads = [("#6d4c41", col_sig - 2, "T-"), ("#e53935", col_sig - 1, "T+"), ("#fb8c00", col_sig, "a")]
        for c, col, row in leads:
            x, y = hole(col, row)
            if row == "T+":
                pts = [(x, bot), (x, y)]
            elif row == "T-":
                pts = [(x + 10, bot), (x + 10, ROW["T+"] + 10), (x, ROW["T+"] + 10), (x, y)]
            else:
                pts = [(x + 10, bot), (x + 10, ROW["T-"] + 25), (x, ROW["T-"] + 25), (x, y)]
            add(f'<path d="{rounded(pts, 4)}" fill="none" stroke="{c}" stroke-width="4" stroke-linecap="round"/>')
            self.pinhead(x, y)
        return bot

    def soil_sensor(self, x_vcc, top, title):
        """Resistive soil-moisture probe (red board, two prongs) pushed into a pot.
        Pins on the top edge, left to right: VCC, GND, SIG at x_vcc, x_vcc + P, x_vcc + 2P.
        Returns the pin positions."""
        add, text = self.add, self.text
        xs = [x_vcc + i * P for i in range(3)]
        xc = xs[1]
        bw = 110
        x0 = xc - bw / 2
        pot_top = top + 124
        # board + prongs first, then the pot in front: the prongs disappear into the soil
        add(f'<rect x="{x0}" y="{top}" width="{bw}" height="70" rx="8" fill="#d32f2f" stroke="#7f0000" stroke-width="2"/>')
        for px in (x0 + 10, x0 + bw - 34):
            add(f'<rect x="{px}" y="{top + 62}" width="24" height="130" rx="4" fill="#cfd3d6" stroke="#8f959c" stroke-width="1.5"/>')
        add(f'<path d="M{xc - 120},{pot_top + 10} L{xc + 120},{pot_top + 10} L{xc + 96},{pot_top + 130} L{xc - 96},{pot_top + 130} Z" '
            f'fill="#c1693c" stroke="#8d4524" stroke-width="2"/>')
        add(f'<rect x="{xc - 128}" y="{pot_top - 8}" width="256" height="20" rx="4" fill="#d27a49" stroke="#8d4524" stroke-width="2"/>')
        add(f'<ellipse cx="{xc}" cy="{pot_top - 8}" rx="120" ry="7" fill="#5d4037"/>')
        for px in (x0 + 10, x0 + bw - 34):
            add(f'<rect x="{px}" y="{pot_top - 20}" width="24" height="14" fill="#cfd3d6"/>')
        for hx in (x0 + 12, x0 + bw - 12):
            add(f'<circle cx="{hx}" cy="{top + 14}" r="6" fill="#ffffff" stroke="#7f0000"/>')
        for x, lab in zip(xs, ["VCC", "GND", "SIG"]):
            add(f'<rect x="{x - 5}" y="{top + 4}" width="10" height="10" fill="#111"/>')
            self.pinhead(x, top + 2)
            text(x + 4, top + 48, lab, 10, "#ffffff", "start", 700, rot=-90)
        text(xc - 140, top + 40, title, 13, "#263238", "end", 700)
        text(xc - 140, top + 58, "push the two prongs into the soil", 11, "#607d8b", "end")
        return [(x, top + 2) for x in xs]

    # ------------------------------------------------------------ wires
    def wire(self, kind, num, pts, badge_at, end_marks=True):
        d = rounded(pts)
        self.add(f'<path d="{d}" fill="none" stroke="{DARK[kind]}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>')
        self.add(f'<path d="{d}" fill="none" stroke="{COL[kind]}" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>')
        if end_marks:
            for x, y in (pts[0], pts[-1]):
                self.add(f'<rect x="{x - 4.5}" y="{y - 4.5}" width="9" height="9" rx="1.5" fill="{DARK[kind]}"/>'
                         f'<rect x="{x - 2}" y="{y - 2}" width="4" height="4" fill="#d4af37"/>')
        if num is not None:
            self.badge(num, badge_at, kind)

    def uno_wire(self, kind, num, pin, pts_after, badge_at, to, symbols=()):
        """Wire that starts at Uno pin `pin`; records it for tools/check_pins.py.
        `symbols` = names of the constant for this pin in the sketches (any one of them must exist)."""
        p = pin_xy(pin)
        self.wire(kind, num, [p] + list(pts_after), badge_at)
        self.pins.append({"uno": PIN_LABEL.get(pin, pin), "to": to, "step": num, "symbols": list(symbols)})

    def between_rows(self, kind, num, pin, col, row, badge_at, to, symbols=()):
        """Uno digital pin -> straight right between two hole rows -> drop into the target hole."""
        p = pin_xy(pin)
        t = hole(col, row)
        self.uno_wire(kind, num, pin, [(t[0], p[1]), t], badge_at, to, symbols)

    def badge(self, num, at, kind):
        self.badges.append((num, at, kind))

    def draw_badges(self):
        for num, (x, y), kind in self.badges:
            self.add(f'<circle cx="{x}" cy="{y}" r="10" fill="#ffffff" stroke="{DARK[kind]}" stroke-width="2.5"/>')
            self.text(x, y + 4, num, 11, "#111", "middle", 700)

    # ------------------------------------------------------------ steps panel
    def panel(self, y0, steps, notes, colw=460, one_group_per_column=False,
              title="Build it in this order — numbers match the white circles on the wires"):
        H = self.H
        text = self.text
        self.add(f'<rect x="40" y="{y0}" width="{W - 80}" height="{H - y0 - 30}" rx="12" fill="#fafafa" stroke="#e0e0e0"/>')
        text(64, y0 + 36, title, 17, "#263238", "start", 700)
        notes_h = 20 * len(notes) + 30
        x, y = 64, y0 + 72
        for i, (head, rows) in enumerate(steps):
            need = 24 + len(rows) * 21
            if y + need > H - notes_h - 20 or (one_group_per_column and i > 0):
                x += colw
                y = y0 + 72
            text(x, y, head, 14, "#37474f", "start", 700)
            y += 22
            for n, s in rows:
                self.add(f'<circle cx="{x + 12}" cy="{y - 4}" r="10" fill="#fff" stroke="#607d8b" stroke-width="2"/>')
                text(x + 12, y, n, 10, "#111", "middle", 700)
                text(x + 30, y + 1, s, 13, "#37474f")
                if n.isdigit():
                    if int(n) in self.steps_nums:
                        raise SystemExit(f"step {n} listed twice")
                    self.steps_nums.add(int(n))
                y += 21
            y += 12
        if x + colw > W - 40:
            raise SystemExit("steps panel overflows the canvas: raise the sheet height")
        for i, s in enumerate(notes):
            text(64, H - 36 - 20 * (len(notes) - 1 - i), s, 12.5, "#546e7a")

    # ------------------------------------------------------------ output
    def save(self, svg_path, sketches, free=(), unknown=()):
        """Write the SVG and `<name>.pins.json`. Refuses on badge/step mismatch."""
        nums = [n for n, _, _ in self.badges]
        dup = sorted({n for n in nums if nums.count(n) > 1})
        if dup:
            raise SystemExit(f"duplicate circles: {dup}")
        if set(nums) != self.steps_nums:
            raise SystemExit(f"circles {sorted(set(nums) - self.steps_nums)} have no step, "
                             f"steps {sorted(self.steps_nums - set(nums))} have no circle")
        self.draw_badges()
        self.add("</svg>")
        svg_path = Path(svg_path)
        svg_path.write_text("\n".join(self.out), encoding="utf-8", newline="\n")
        meta = {"svg": svg_path.name, "sketches": list(sketches), "pins": self.pins,
                "free_code_pins": list(free), "unknown": list(unknown)}
        svg_path.with_suffix(".pins.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                                                     encoding="utf-8", newline="\n")
        print(f"wrote {svg_path} ({len(nums)} numbered wires/steps)")
