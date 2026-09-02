"""P4-07: Version semver + guard (B1, packaging, Axiom #7)."""
import os, pathlib, re

def test_version_semver_packaging():
    from src.jefrey.skills.version import (
        check_skill_compatibility,
        get_skill_version,
        should_auto_upgrade,
    )
    # MAJOR increase requires HITL => False
    ok, msg = check_skill_compatibility("1.2.3", "2.0.0")
    assert ok is False and "HITL" in msg
    # same major, minor bump => compatible (auto upgrade minor)
    ok2, _ = check_skill_compatibility("1.2.3", "1.3.0")
    assert ok2 is True
    # downgrade not allowed
    ok3, _ = check_skill_compatibility("1.3.0", "1.2.3")
    assert ok3 is False
    # get_skill_version falls back to pyproject or 0.1.0, never crashes
    v = get_skill_version("nonexistent_skill_xyz")
    assert re.match(r"^\d+\.\d+\.\d+$", v)
    # should_auto_upgrade with no registry entry => (False, None)
    auto, ver = should_auto_upgrade("nonexistent_skill_xyz", "1.0.0")
    assert auto is False and ver is None


def test_guard_6_greps_zero():
    # Re-implements guard check in python to ensure pytest fails if regressions
    root = pathlib.Path(".")
    # GREP-5: b64encode without urlsafe (allow urlsafe_b64encode)
    import subprocess
    # Use git grep style but via python: search for b64encode not preceded by urlsafe_
    bad = []
    for p in root.rglob("src/**/*.py"):
        t = p.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(t.splitlines(), 1):
            if "b64encode" in line and "urlsafe" not in line and "base64" in line:
                # ignore comments mentioning wrong then correct
                if "without urlsafe" in line.lower():
                    continue
                bad.append(f"{p}:{i}:{line.strip()}")
    assert bad == [], f"b64encode without urlsafe found: {bad}"

    # GREP-6 overwrite=True must be 0 (except docs/archive which is ignored)
    bad2 = []
    for p in root.rglob("src/**/*.py"):
        if "docs/archive" in str(p):
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        if "overwrite=True" in t:
            bad2.append(str(p))
    assert bad2 == [], f"overwrite=True found: {bad2}"


def test_dotenv_env_literal_ok():
    # .env.example JEFREY_ENV must be dev|prod without trailing space
    txt = pathlib.Path(".env.example").read_text(encoding="utf-8")
    for line in txt.splitlines():
        if line.startswith("JEFREY_ENV="):
            assert line.strip() == "JEFREY_ENV=dev", f"JEFREY_ENV line bad: {repr(line)}"
            assert not line.endswith(" "), "trailing space in JEFREY_ENV"
