"""Workstream resolution.

A *workstream* is any labelled stream of work. For git repos we auto-detect a
stable ``owner/repo`` (or repo-dir) name; otherwise the caller supplies an
explicit ``--workstream`` label. Works for code and non-code work alike.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Workstream:
    name: str          # canonical, human-readable (e.g. "acme/api-gateway")
    slug: str          # filesystem-safe (e.g. "acme__api-gateway")
    type: str          # "repo" | "manual" | "research" | ...

    @property
    def filename(self) -> str:
        return f"{self.slug}.md"


def slugify(name: str) -> str:
    """Map a workstream name to a filesystem-safe slug.

    ``/`` becomes ``__`` so the canonical name is recoverable; everything else
    outside ``[a-z0-9._-]`` collapses to ``-``.
    """
    s = name.strip().lower().replace("/", "__")
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-_")
    return s or "default"


def unslugify(slug: str) -> str:
    """Best-effort inverse of :func:`slugify` for display."""
    return slug.replace("__", "/")


def _git_remote_name(cwd: Path) -> str | None:
    try:
        url = subprocess.check_output(
            ["git", "-C", str(cwd), "config", "--get", "remote.origin.url"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    if not url:
        return None
    # Strip protocol/host + .git → owner/repo
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?/?$", url)
    if m:
        return m.group(1)
    return None


def _git_toplevel_name(cwd: Path) -> str | None:
    try:
        top = subprocess.check_output(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return Path(top).name if top else None


def resolve(label: str | None = None, cwd: Path | None = None,
            type_hint: str | None = None) -> Workstream:
    """Resolve a workstream.

    Precedence: explicit ``label`` > git remote owner/repo > git toplevel dir
    name. Raises if none can be determined and no label is given.
    """
    cwd = cwd or Path.cwd()

    if label:
        return Workstream(name=label, slug=slugify(label), type=type_hint or "manual")

    name = _git_remote_name(cwd) or _git_toplevel_name(cwd)
    if name:
        return Workstream(name=name, slug=slugify(name), type=type_hint or "repo")

    raise ValueError(
        "Could not auto-detect a git workstream; pass --workstream <label>."
    )
