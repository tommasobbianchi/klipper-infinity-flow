#!/usr/bin/env python3
"""
configure.py — Interactive setup for Infinity Flow S1+ Klipper integration.

Run this after install.sh:
    python3 ~/klipper-infinity-flow/configure.py

Configures printer.cfg and moonraker.conf interactively.
No external dependencies beyond stdlib.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ── ANSI colours ────────────────────────────────────────────────────────────

def _supports_colour():
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_CLR = _supports_colour()

def _c(code, text):
    return f"\033[{code}m{text}\033[0m" if _CLR else text

def green(t):  return _c("32", t)
def cyan(t):   return _c("36", t)
def yellow(t): return _c("33", t)
def red(t):    return _c("31", t)
def bold(t):   return _c("1",  t)
def dim(t):    return _c("2",  t)

def ok(msg):   print(green("  ✓ ") + msg)
def info(msg): print(cyan( "  → ") + msg)
def warn(msg): print(yellow("  ! ") + msg)
def err(msg):  print(red(  "  ✗ ") + msg)

# ── Config file detection ────────────────────────────────────────────────────

_CFG_SEARCH = [
    "~/printer_data/config",
    "~/klipper_config",
    "/home/pi/printer_data/config",
    "/home/klipper/printer_data/config",
]

def _find_cfg(filename: str) -> Path | None:
    for base in _CFG_SEARCH:
        p = Path(base).expanduser() / filename
        if p.exists():
            return p
    return None

def find_file(name: str, label: str) -> Path:
    found = _find_cfg(name)
    if found:
        ok(f"{label}: {found}")
        return found
    warn(f"{label} not found in standard locations.")
    while True:
        raw = input(f"  Path to {name}: ").strip()
        p = Path(raw).expanduser()
        if p.exists():
            return p
        err(f"File not found: {p}")

# ── INI section helpers ──────────────────────────────────────────────────────

def _section_bounds(lines: list[str], section: str):
    """Return (start, end) line indices of [section] block, or (None, None)."""
    pat = re.compile(r"^\s*\[" + re.escape(section) + r"\]\s*$", re.IGNORECASE)
    any_section = re.compile(r"^\s*\[")
    start = None
    for i, line in enumerate(lines):
        if pat.match(line):
            start = i
        elif start is not None and any_section.match(line):
            return start, i
    if start is not None:
        return start, len(lines)
    return None, None

def read_section(path: Path, section: str) -> dict | None:
    """Parse key: value pairs from [section] in path. Returns None if absent."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start, end = _section_bounds(lines, section)
    if start is None:
        return None
    result = {}
    current_key = None
    for line in lines[start + 1:end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[0:1] in (" ", "\t") and current_key:
            result[current_key] = result.get(current_key, "") + "\n" + stripped
        elif ":" in line:
            k, _, v = line.partition(":")
            current_key = k.strip()
            result[current_key] = v.strip()
        else:
            current_key = None
    return result

def _build_block(section: str, pairs: list[tuple]) -> str:
    """Build an INI section string from (key, value) pairs."""
    lines = [f"[{section}]"]
    for key, value in pairs:
        if "\n" in str(value):
            lines.append(f"{key}:")
            for subline in value.splitlines():
                lines.append(f"    {subline}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"

def write_section(path: Path, section: str, pairs: list[tuple]) -> None:
    """Replace or append [section] in path with pairs. Atomic write."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    start, end = _section_bounds([l.rstrip("\n") for l in lines], section)
    block = "\n" + _build_block(section, pairs)
    if start is not None:
        lines[start:end] = [block]
    else:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(block)
    tmp = path.with_suffix(".cfg.tmp" if path.suffix == ".cfg" else ".conf.tmp")
    tmp.write_text("".join(lines), encoding="utf-8")
    shutil.move(str(tmp), str(path))

# ── Prompt helpers ───────────────────────────────────────────────────────────

def prompt(question: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        raw = input(f"  {question}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return raw if raw else default

def confirm(question: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    try:
        raw = input(f"  {question} [{hint}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    if not raw:
        return default
    return raw in ("y", "yes")

def choose(question: str, options: list[tuple[str, str]], default: int = 0) -> str:
    """Present a numbered menu, return the chosen value."""
    print(f"  {question}")
    for i, (val, label) in enumerate(options):
        marker = bold("▶") if i == default else " "
        print(f"    {marker} {i + 1}) {val:<14} {dim(label)}")
    while True:
        try:
            raw = input(f"  Choice [{default + 1}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if not raw:
            return options[default][0]
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        warn("Enter a number from the list above.")

# ── Token acquisition ────────────────────────────────────────────────────────

def _token_from_json() -> str | None:
    p = Path("~/flowq_tokens.json").expanduser()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        return data.get("refresh_token") or None
    except Exception:
        return None

def _token_from_conf(moonraker_conf: Path) -> str | None:
    section = read_section(moonraker_conf, "infinity_flow")
    if section:
        return section.get("refresh_token") or None
    return None

def get_token(moonraker_conf: Path) -> str:
    # 1. Already in moonraker.conf?
    t = _token_from_conf(moonraker_conf)
    if t:
        ok(f"FlowQ token already in {moonraker_conf.name} ({t[:12]}…)")
        if confirm("Keep existing token?", default=True):
            return t

    # 2. Saved from a previous flowq_setup_token.py run?
    t = _token_from_json()
    if t:
        ok(f"Found token in ~/flowq_tokens.json ({t[:12]}…)")
        if confirm("Use this token?", default=True):
            return t

    # 3. Offer to run setup script or paste manually
    script = Path(__file__).parent / "flowq_setup_token.py"
    print()
    print("  How do you want to get your FlowQ token?")
    print(f"    1) Run flowq_setup_token.py {dim('(login with email/password)')}")
    print(f"    2) Paste token manually       {dim('(e.g. from browser local storage)')}")
    while True:
        try:
            raw = input("  Choice [1]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        choice = raw or "1"
        if choice == "1":
            try:
                subprocess.run([sys.executable, str(script)], check=True)
            except subprocess.CalledProcessError:
                warn("Setup script exited with an error.")
            t = _token_from_json()
            if t:
                ok(f"Token saved ({t[:12]}…)")
                return t
            warn("Could not read token after running setup script.")
        elif choice == "2":
            break
        else:
            warn("Enter 1 or 2.")

    # Manual paste
    print()
    info("Paste your FlowQ refresh_token below.")
    info("(Get it from: flowq.infinityflow3d.com → F12 → Application → Local Storage)")
    while True:
        try:
            import getpass
            t = getpass.getpass("  Token (hidden): ").strip()
        except Exception:
            t = input("  Token: ").strip()
        if len(t) > 20:
            return t
        warn("Token looks too short. Paste the full value.")

# ── Extruder detection ───────────────────────────────────────────────────────

def detect_extruder(printer_cfg: Path) -> str:
    """Scan printer.cfg for [extruder] section names."""
    text = printer_cfg.read_text(encoding="utf-8", errors="ignore")
    matches = re.findall(r"^\s*\[(extruder\d*)\]", text, re.MULTILINE)
    unique = list(dict.fromkeys(matches))
    if len(unique) == 1:
        return unique[0]
    if unique:
        return unique[0]
    return "extruder"

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print()
    print(bold("╔══════════════════════════════════════════════╗"))
    print(bold("║   Infinity Flow S1+ — Klipper Configurator  ║"))
    print(bold("╚══════════════════════════════════════════════╝"))
    print()

    # ── Locate config files ──────────────────────────────────────────────────
    print(bold("Step 1/4 — Config files"))
    print()
    printer_cfg    = find_file("printer.cfg",    "printer.cfg")
    moonraker_conf = find_file("moonraker.conf", "moonraker.conf")
    print()

    # ── Check existing config ────────────────────────────────────────────────
    existing_p = read_section(printer_cfg,    "infinity_flow")
    existing_m = read_section(moonraker_conf, "infinity_flow")

    if existing_p or existing_m:
        print(bold("  Existing [infinity_flow] config found:"))
        if existing_m:
            for k, v in existing_m.items():
                print(f"    {cyan('moonraker.conf')}  {k}: {dim(v[:40])}")
        if existing_p:
            for k, v in existing_p.items():
                v_short = v.replace("\n", " ↵ ")[:50]
                print(f"    {cyan('printer.cfg')}     {k}: {dim(v_short)}")
        print()
        if not confirm("Update existing configuration?", default=True):
            print()
            info("No changes made. Exiting.")
            sys.exit(0)
        print()

    # ── FlowQ token ──────────────────────────────────────────────────────────
    print(bold("Step 2/4 — FlowQ token"))
    print()
    token = get_token(moonraker_conf)
    print()

    # ── Printer options ──────────────────────────────────────────────────────
    print(bold("Step 3/4 — Printer options"))
    print()

    detected_extruder = detect_extruder(printer_cfg)
    extruder = prompt("Extruder name", default=detected_extruder)

    print()
    pause_mode = choose(
        "Pause behavior:",
        [
            ("all_empty", "pause only when BOTH slots are empty (recommended)"),
            ("any_empty", "pause as soon as either slot empties"),
        ],
        default=0,
    )

    print()
    grace_raw = prompt("Swap grace period in seconds", default="30")
    try:
        grace = max(0, int(grace_raw))
    except ValueError:
        grace = 30

    runout_gcode = "M117 Filament exhausted — pausing\nPAUSE"
    print()
    info(f"Default runout_gcode:")
    for line in runout_gcode.splitlines():
        print(f"    {dim(line)}")
    if confirm("Customise runout_gcode?", default=False):
        print("  Enter GCode lines. Empty line to finish.")
        lines = []
        while True:
            try:
                line = input("    > ").rstrip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                break
            lines.append(line)
        if lines:
            runout_gcode = "\n".join(lines)
    print()

    # ── Write configs ────────────────────────────────────────────────────────
    print(bold("Step 4/4 — Writing configuration"))
    print()

    moonraker_pairs = [("refresh_token", token)]
    write_section(moonraker_conf, "infinity_flow", moonraker_pairs)
    ok(f"Wrote [infinity_flow] to {moonraker_conf}")

    printer_pairs = [
        ("extruder",          extruder),
        ("pause_mode",        pause_mode),
        ("swap_grace_period", str(grace)),
        ("runout_gcode",      runout_gcode),
    ]
    write_section(printer_cfg, "infinity_flow", printer_pairs)
    ok(f"Wrote [infinity_flow] to {printer_cfg}")
    print()

    # ── Restart ──────────────────────────────────────────────────────────────
    if confirm("Restart moonraker and klipper now?", default=True):
        print()
        for svc in ("moonraker", "klipper"):
            try:
                subprocess.run(
                    ["sudo", "systemctl", "restart", svc],
                    check=True, timeout=30
                )
                ok(f"Restarted {svc}")
            except Exception as e:
                warn(f"Could not restart {svc}: {e}")
                info(f"Run manually: sudo systemctl restart {svc}")

    print()
    print(bold("  ══════════════════════════════════════"))
    print(green(bold("  ✓ Configuration complete!")))
    print(bold("  ══════════════════════════════════════"))
    print()
    print(f"  Fluidd / Mainsail: look for {cyan('infinity_flow_a')} and {cyan('infinity_flow_b')} sensors.")
    if (Path("~/KlipperScreen").expanduser().exists() or
            Path("/home/pi/KlipperScreen").exists()):
        print(f"  KlipperScreen:     tap {cyan('Infinity Flow')} on the main menu.")
    print()


if __name__ == "__main__":
    main()
