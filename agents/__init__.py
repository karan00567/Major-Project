"""Local-model side-car for ResearchGPT. Nothing here is on the pipeline path.

The folder is deliberately a sibling of ``src/`` rather than a package inside
``src/researchgpt/``. Two reasons:

1. ``src/researchgpt/agents/`` already exists and holds the six pipeline agents
   (planner, retriever, ranker, extractor, writer, verifier, critic). **This is
   not that.** These are throwaway experiment scripts for a second machine.
2. Keeping it outside the installed package means it can never be imported by
   accident from inside the pipeline, so the ``ALLOWED_MODELS`` allowlist in
   ``core/models.py`` stays the single enforcement point for hosted calls.

Importing ``researchgpt`` from here works without ``pip install -e .`` - the
path bootstrap below adds ``src/`` when it is missing, so the scripts run on a
freshly cloned repo on someone else's laptop.
"""

from __future__ import annotations

import pathlib
import sys

_SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
