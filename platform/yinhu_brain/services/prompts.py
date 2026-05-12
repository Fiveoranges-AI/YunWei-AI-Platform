"""Locate prompt files across pip-install and source-tree deployments.

The Railway container does a non-editable ``pip install`` so the
``yinhu_brain`` package lands in site-packages, but ``prompts/`` is copied
to ``/app/prompts`` during the Dockerfile build. When the web service
runs ``uvicorn`` from ``/app`` the package is imported from ``/app``
(CWD on ``sys.path``) and prompts resolve via ``Path(__file__).parents[N]``.
When the RQ worker runs via the ``yinhu-ingest-worker`` console script,
``__file__`` lives under site-packages and ``parents[N]`` no longer
reaches the prompts directory — every prompt load blew up with
``FileNotFoundError: /usr/local/lib/python3.13/site-packages/prompts/...``.

This helper centralizes the lookup so callers don't have to know which
deployment shape they're running under.
"""

from __future__ import annotations

import os
from pathlib import Path


def find_prompt(filename: str) -> Path:
    """Return the on-disk path to a prompt file, or raise.

    Search order:

    1. ``$PROMPTS_DIR`` env (operator override; handy in tests + future
       container layouts).
    2. ``yinhu_brain/../prompts/<filename>`` — works when the package
       lives in a source tree where ``prompts/`` sits next to
       ``yinhu_brain/`` (local dev and the ``/app`` layout).
    3. ``/app/prompts/<filename>`` — the Railway container layout, used
       when ``yinhu_brain`` is imported from site-packages.

    Raises FileNotFoundError when nothing matches, with the list of
    candidates so deployments can diagnose at a glance.
    """
    candidates: list[Path] = []
    env_dir = os.environ.get("PROMPTS_DIR", "").strip()
    if env_dir:
        candidates.append(Path(env_dir) / filename)
    here = Path(__file__).resolve()
    # parents[1] = yinhu_brain/, then ../prompts is the source-tree layout.
    candidates.append(here.parents[1].parent / "prompts" / filename)
    candidates.append(Path("/app/prompts") / filename)
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"prompt {filename!r} not found; searched: "
        + ", ".join(str(c) for c in candidates)
    )
