"""Environment checks for the one-click launcher (start_wetstack.bat). Also works on Linux.

    python tools/check_env.py              exit 0 when Python is 3.10+, every dependency in
                                           pyproject.toml is installed, new enough and importable,
                                           and wetstack is installed from this folder; else exit 1
                                           (the launcher then runs pip install -e .).
    python tools/check_env.py --running N  exit 0 if this folder's workspace server already answers
                                           on port N, 1 if the port is free, 2 if another program
                                           (or a WetStack server from another folder) holds it.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.metadata as md
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 10)
IMPORT_NAME = {"scikit-learn": "sklearn", "opencv-python": "cv2", "opencv-python-headless": "cv2",
               "pyserial": "serial"}
REQ_RE = re.compile(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*([^;]*)(?:;(.*))?$")
SPEC_RE = re.compile(r"(~=|==|!=|<=|>=|<|>)\s*([0-9][0-9A-Za-z.*+!-]*)")


def requirements() -> list[str]:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    try:
        import tomllib
    except ImportError:                                   # Python 3.10
        block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text, re.S | re.M)
        return re.findall(r"[\"']([^\"']+)[\"']", block.group(1)) if block else []
    return list(tomllib.loads(text)["project"]["dependencies"])


def release(version: str) -> tuple[int, ...]:
    m = re.match(r"\d+(?:\.\d+)*", version)
    return tuple(int(x) for x in m.group(0).split(".")) if m else ()


def satisfies(installed: str, op: str, wanted: str) -> bool:
    """Compares release numbers only (2.1.0rc1 counts as 2.1.0), which is all pyproject.toml uses."""
    have = release(installed)
    if wanted.endswith(".*"):
        prefix = release(wanted[:-2])
        same = have[:len(prefix)] == prefix
        return same if op == "==" else not same if op == "!=" else False
    want = release(wanted)
    n = max(len(have), len(want))
    a, b = have + (0,) * (n - len(have)), want + (0,) * (n - len(want))
    if op == "~=":
        return a >= b and a[:len(want) - 1] == b[:len(want) - 1]
    return {">=": a >= b, ">": a > b, "<=": a <= b, "<": a < b, "==": a == b, "!=": a != b}[op]


def marker_applies(marker: str) -> bool:
    try:
        from pip._vendor.packaging.markers import Marker
    except ImportError:
        return True
    return Marker(marker).evaluate()


def check_requirement(req: str, found: list[str]) -> str | None:
    m = REQ_RE.match(req)
    if not m:
        return f"cannot read the requirement {req!r} in pyproject.toml"
    name, specs, marker = m.group(1), SPEC_RE.findall(m.group(2)), (m.group(3) or "").strip()
    if marker and not marker_applies(marker):
        return None
    try:
        have = md.version(name)
    except md.PackageNotFoundError:
        return f"{name} is not installed"
    bad = [op + v for op, v in specs if not satisfies(have, op, v)]
    if bad:
        return f"{name} {have} is installed but {','.join(bad)} is needed"
    module = IMPORT_NAME.get(name.lower(), name.replace("-", "_"))
    try:
        importlib.import_module(module)
    except Exception as exc:                              # e.g. a DLL that fails to load on Windows
        return f"{name} {have} is installed but 'import {module}' fails: {exc}"
    found.append(f"{name} {have}")
    return None


def check_wetstack() -> str | None:
    try:
        import wetstack
    except Exception as exc:
        return f"wetstack is not installed in this environment ({exc})"
    where = Path(wetstack.__file__).resolve().parent
    if where != (ROOT / "host" / "wetstack").resolve():
        return f"wetstack is installed from {where}, not from this folder"
    return None


def check() -> int:
    if sys.version_info < MIN_PYTHON:
        print(f"Python {sys.version.split()[0]} is too old; WetStack needs {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer.")
        return 1
    found: list[str] = []
    problems = [p for p in (check_requirement(r, found) for r in requirements()) if p]
    problems += [p for p in (check_wetstack(),) if p]
    if problems:
        print("Needs install or repair:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"Python {sys.version.split()[0]}: {', '.join(found)}; wetstack from this folder. All good.")
    return 0


def running(port: int) -> int:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # never send localhost via a proxy
    try:
        with opener.open(f"http://127.0.0.1:{port}/api/ping", timeout=2) as resp:
            info = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError:
        info = {}
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ConnectionRefusedError):
            return 1
        info = {}
    except ConnectionRefusedError:
        return 1
    except (OSError, ValueError):
        info = {}
    if not isinstance(info, dict) or info.get("server") != "wetstack":
        print(f"Port {port} is in use by another program.")
        return 2
    here = os.path.normcase(os.path.realpath(ROOT))
    there = os.path.normcase(os.path.realpath(str(info.get("repo", ""))))
    if here != there:
        print(f"Port {port} is in use by a WetStack workspace from another folder: {info.get('repo')}")
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--running", type=int, metavar="PORT", help="is this folder's workspace already served on PORT?")
    a = ap.parse_args(argv)
    return running(a.running) if a.running is not None else check()


if __name__ == "__main__":
    sys.exit(main())
