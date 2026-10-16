"""Cross-check every wiring diagram against its sketch(es), and every local link in README.md.

Run:  python tools/check_pins.py        (exit code 1 on any mismatch)

For each */docs/*.pins.json (written by wiring_kit.Sheet.save):
  1. every drawn Uno wire that names a code symbol: the symbol exists in each sketch and its value is that pin
  2. every pin constant in each sketch (name contains "pin" or "led") is drawn, or listed as intentionally free
  3. the steps panel text in the SVG mentions "Uno <pin>" for every drawn Uno wire
README.md: every relative link / image target exists on disk.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONST = re.compile(r"^\s*(?:static\s+)?const\s+(?:int|uint8_t|byte)\s+(\w+)\s*=\s*(A?\d+)\s*;", re.M)
DEFINE = re.compile(r"^\s*#define\s+(\w+)\s+(A?\d+)\b", re.M)


def code_pins(ino):
    src = ino.read_text(encoding="utf-8")
    vals = {n: v for n, v in CONST.findall(src) + DEFINE.findall(src)}
    pins = {n: v for n, v in vals.items() if re.search(r"pin|led", n, re.I)}
    return vals, pins


def as_uno(v):
    return v if v.startswith("A") else f"D{v}"


def check_diagram(meta_path, problems, lines):
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    svg_text = re.sub(r"<[^>]+>", " ", (meta_path.parent / meta["svg"]).read_text(encoding="utf-8"))
    rel = meta_path.relative_to(ROOT).as_posix()
    for sk in meta["sketches"]:
        ino = (meta_path.parent / sk).resolve()
        if not ino.exists():
            problems.append(f"{rel}: sketch {sk} missing")
            continue
        vals, pins = code_pins(ino)
        covered = set()
        for w in meta["pins"]:
            if not w["symbols"]:
                continue
            found = [s for s in w["symbols"] if s in vals]
            if len(found) != 1:
                problems.append(f"{rel}: {ino.name}: wire {w['step']} ({w['uno']}) symbols {w['symbols']} found {found}")
                continue
            got = as_uno(vals[found[0]])
            ok = got == w["uno"]
            covered.add(found[0])
            lines.append(f"  {'OK ' if ok else 'BAD'} {ino.name:18s} {found[0]:13s} = {got:4s} | diagram wire {w['step']:>2}: "
                         f"Uno {w['uno']} -> {w['to']}")
            if not ok:
                problems.append(f"{rel}: {ino.name}: {found[0]} = {got} but wire {w['step']} starts at {w['uno']}")
        for f in meta["free_code_pins"]:
            hit = [s for s in f["symbols"] if s in pins]
            for s in hit:
                covered.add(s)
                ok = as_uno(pins[s]) == f["uno"]
                lines.append(f"  {'OK ' if ok else 'BAD'} {ino.name:18s} {s:13s} = {as_uno(pins[s]):4s} | intentionally "
                             f"not wired here: {f['why']}")
                if not ok:
                    problems.append(f"{rel}: {ino.name}: free pin {s} = {pins[s]}, expected {f['uno']}")
        for s in sorted(set(pins) - covered):
            problems.append(f"{rel}: {ino.name}: code pin {s} = {pins[s]} is not drawn")
    for w in meta["pins"]:
        if f"Uno {w['uno']}" not in svg_text:
            problems.append(f"{rel}: steps text never says 'Uno {w['uno']}'")
    for u in meta["unknown"]:
        lines.append(f"  UNKNOWN: {u}")


def check_readme(problems, lines):
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    targets = re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text)
    local = [t for t in targets if not re.match(r"[a-z]+:", t)]
    for t in local:
        ok = (ROOT / t).exists()
        if not ok:
            problems.append(f"README.md: link target missing: {t}")
    lines.append(f"README.md: {len(local)} local links checked, {sum(not (ROOT / t).exists() for t in local)} missing")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    problems, lines = [], []
    metas = sorted(ROOT.glob("*/docs/*.pins.json"))
    if not metas:
        problems.append("no *.pins.json found: run the draw_wiring.py scripts first")
    for m in metas:
        lines.append(m.relative_to(ROOT).as_posix())
        check_diagram(m, problems, lines)
    check_readme(problems, lines)
    print("\n".join(lines))
    print(f"\n{len(metas)} diagrams, {len(problems)} mismatches")
    for p in problems:
        print("MISMATCH:", p)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
