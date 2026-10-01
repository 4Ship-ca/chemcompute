"""CLI tests: python tests/test_cli.py (or pytest)."""
import fnmatch
import importlib.util
import os
import shlex
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
from wetstack import core, experiments  # noqa: E402
from wetstack.__main__ import build_parser  # noqa: E402


def _content():
    spec = importlib.util.spec_from_file_location("content", ROOT / "tools" / "content.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _documented_commands():
    cmds = []
    for ph in _content().PHASES:
        cmds += [s["cmd"] for s in ph["steps"] if s.get("cmd")] + [ph["gate"]["cmd"]]
    return [c for c in cmds if c.startswith("python -m wetstack")]


def test_every_documented_command_parses():
    parser = build_parser()
    cmds = _documented_commands()
    assert len(cmds) > 30
    for c in cmds:
        try:
            parser.parse_args(shlex.split(c)[3:])
        except SystemExit as exc:
            raise AssertionError(f"manual command does not parse: {c}") from exc


def test_sim_and_port_either_side_of_the_command():
    p = build_parser()
    a = p.parse_args(["g1-linearity", "--sim"])
    assert a.sim is True and a.port is None
    a = p.parse_args(["--sim", "g1-linearity"])
    assert a.sim is True
    a = p.parse_args(["g1-linearity"])
    assert a.sim is False
    assert p.parse_args(["ping", "--port", "COM5"]).port == "COM5"
    assert p.parse_args(["--port", "COM7", "ping"]).port == "COM7"
    assert p.parse_args(["serve", "--port", "9000"]).port == 9000
    assert p.parse_args(["serve"]).port == 8765


def test_sim_session_dirs_are_gitignored():
    os.chdir(tempfile.mkdtemp(prefix="wetstack-test-"))
    ignored = [ln.strip().rstrip("/") for ln in (ROOT / ".gitignore").read_text().splitlines() if ln.startswith("data/raw/")]
    sim_dir = core.session_dir("g1-linearity", True).as_posix()
    real_dir = core.session_dir("g1-linearity", False).as_posix()
    assert any(fnmatch.fnmatch(sim_dir, pat) for pat in ignored), sim_dir
    assert not any(fnmatch.fnmatch(real_dir, pat) for pat in ignored), real_dir


def test_g5_stack_without_trials_only_sets_gains():
    os.chdir(tempfile.mkdtemp(prefix="wetstack-test-"))
    st = experiments.g5_stack(True, None, 0, False, False)
    assert st["g_or"] and st["g_and"] and not Path("data/raw").exists()


if __name__ == "__main__":
    fns = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"ok  {fn.__name__}")
    print(f"{len(fns)} CLI tests passed")
