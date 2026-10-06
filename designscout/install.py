"""Install the bundled skill for Claude Code, Codex and Cursor (Agent Skills standard)."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

SKILL_SRC = Path(__file__).parent / "skill"
NAME = "design-scout"

# Claude Code reads ~/.claude/skills; Codex reads ~/.agents/skills; Cursor reads both of those
# plus ~/.cursor/skills, so "all" installs into the first two (Cursor may list it from both; harmless).
TARGETS = {
    "claude": Path.home() / ".claude" / "skills",
    "codex": Path.home() / ".agents" / "skills",
    "cursor": Path.home() / ".cursor" / "skills",
}


def install(targets: list[str], link: bool = False, project: Path | None = None) -> list[str]:
    done = []
    roots = []
    if project:
        roots = [project / ".claude" / "skills", project / ".agents" / "skills"]
    else:
        names = ["claude", "codex"] if "all" in targets else targets
        roots = [TARGETS[n] for n in names]
    for root in roots:
        dest = root / NAME
        root.mkdir(parents=True, exist_ok=True)
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        elif dest.exists():
            shutil.rmtree(dest)
        if link:
            os.symlink(SKILL_SRC.resolve(), dest, target_is_directory=True)
        else:
            shutil.copytree(SKILL_SRC, dest, ignore=shutil.ignore_patterns("__pycache__"))
        done.append(str(dest))
    return done
