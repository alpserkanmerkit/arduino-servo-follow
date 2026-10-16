"""servo-follow wiring diagram (Tinkercad/Fritzing style), drawn with ../../tools/wiring_kit.py.

Run:  python draw_wiring.py   -> wiring.svg (+ wiring.pins.json) next to this file
PNG:  python ../../tools/render_png.py

Pins come from servo-follow.ino: PIN_TRIG=D9, PIN_ECHO=D10, PIN_SERVO=D11.
Honesty note: Rewritten in 2026 · not tested with a servo — on the bench the same proximity loop drove a propeller motor in place of the servo.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
from wiring_kit import Sheet, BY, ROW, cx, hole, pin_xy  # noqa: E402

SENSOR = [50, 51, 52, 53]        # HC-SR04 VCC TRIG ECHO GND, row a
SERVO_SIG = 16                   # brown -> top − rail (14), red -> top + rail (15), orange -> column 16 row a


def main():
    s = Sheet("servo-follow — breadboard wiring",
              "Arduino Uno + HC-SR04 + hobby servo · the arm angle tracks the measured distance · same pins as servo-follow.ino",
              1150,
              "Rewritten in 2026 · not tested with a servo — on the bench the same proximity loop drove a propeller motor in place of the servo.")
    s.breadboard()
    s.uno({"5V", "GND", "D9", "D10", "D11"})
    s.hcsr04(SENSOR)
    s.servo(SERVO_SIG, "Hobby servo — arm angle follows the distance")

    # 1-2 Uno power -> bottom rails, 3-4 bottom rails -> top rails at the right end
    p = pin_xy("5V")
    s.uno_wire("5v", 1, "5V", [(30, p[1]), (30, BY + 458), (cx(3) + 10, BY + 458), (cx(3) + 10, ROW["B+"]),
                               hole(3, "B+")], (30, BY + 300), "bottom + rail")
    p = pin_xy("GND")
    s.uno_wire("gnd", 2, "GND", [(44, p[1]), (44, BY + 440), (cx(1), BY + 440), hole(1, "B-")],
               (180, BY + 440), "bottom − rail")
    a, b = hole(61, "B+"), hole(61, "T+")
    s.wire("5v", 3, [a, (a[0] + 10, a[1]), (a[0] + 10, b[1]), b], (a[0] + 10, ROW["h"]))
    a, b = hole(63, "B-"), hole(63, "T-")
    s.wire("gnd", 4, [a, (a[0] + 12, a[1]), (a[0] + 12, b[1]), b], (a[0] + 12, BY + 210))

    # HC-SR04 power drops through the (empty) centre channel
    a = hole(SENSOR[0], "e")
    s.wire("5v", 5, [a, hole(SENSOR[0], "B+")], (a[0] - 16, BY + 290))
    a = hole(SENSOR[3], "e")
    s.wire("gnd", 6, [a, hole(SENSOR[3], "B-")], (a[0] + 16, BY + 290))
    s.between_rows("trig", 7, "D9", SENSOR[1], "d", (cx(40), pin_xy("D9")[1]), "HC-SR04 TRIG", ["PIN_TRIG"])
    s.between_rows("echo", 8, "D10", SENSOR[2], "c", (cx(34), pin_xy("D10")[1]), "HC-SR04 ECHO", ["PIN_ECHO"])

    # servo leads (drawn by s.servo) + signal from D11
    s.between_rows("sig", 12, "D11", SERVO_SIG, "b", (cx(9), pin_xy("D11")[1]), "servo signal", ["PIN_SERVO"])
    s.badge(9, (cx(SERVO_SIG - 2) - 14, ROW["T+"] - 12), "gnd")
    s.badge(10, (cx(SERVO_SIG - 1) - 2, BY - 40), "5v")
    s.badge(11, (cx(SERVO_SIG) + 26, ROW["T-"] + 25), "sig")

    s.panel(BY + 500, [
        ("Power", [
            ("1", "Uno 5V → bottom + rail"), ("2", "Uno GND → bottom − rail"),
            ("3", "bottom + rail → top + rail (right end)"), ("4", "bottom − rail → top − rail (right end)")]),
        ("HC-SR04 (top half, columns 50-53)", [
            ("5", "VCC → bottom + rail"), ("6", "GND → bottom − rail"),
            ("7", "TRIG ← Uno D9"), ("8", "ECHO → Uno D10")]),
        ("Servo (3-wire lead)", [
            ("9", "brown / black (GND) → top − rail"), ("10", "red (+5 V) → top + rail"),
            ("11", "orange / yellow (signal) → column 16"), ("12", "Uno D11 → column 16")]),
    ], [
        "Closed loop: distance 5 cm → arm at 0°, 50 cm → 180°. Each reading is filtered "
        "(median of 3 + moving average + 2° dead band + 4° step limit) so the arm does not jitter.",
        "An SG90 micro servo can run from the Uno 5 V pin. Bigger servos (MG996R…) need their own 5-6 V supply: "
        "feed it into the top rails, leave out wire 3 and keep wire 4 (shared GND).",
        "Servo lead colours vary: brown/black = GND, red = +5 V, orange/yellow/white = signal. "
        "If the red/blue rail lines have a gap in the middle, bridge each rail with a short jumper.",
    ], colw=600, one_group_per_column=True)
    s.save(HERE / "wiring.svg", ["../servo-follow.ino"])


if __name__ == "__main__":
    main()
