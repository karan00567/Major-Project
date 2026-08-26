"""ResearchGPT CLI entry point.

``run`` currently wires config + TraceLogger only; later phases fill in the
pipeline. Declared as the ``researchgpt`` console script in pyproject.toml.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version as pkg_version

import typer

from researchgpt.core.config import load_config
from researchgpt.core.logging import TraceLogger

app = typer.Typer(add_completion=False)


@app.command()
def version() -> None:
    try:
        ver = pkg_version("researchgpt")
    except PackageNotFoundError:
        ver = "0.0.0-dev"
    typer.echo(ver)


@app.command()
def run(
    question: str = typer.Option(..., "--question", "-q"),
    max_papers: int = typer.Option(None, "--max-papers"),
    config: str = typer.Option("configs/default.yaml", "--config"),
    fixture: bool = typer.Option(False, "--fixture"),
) -> None:
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    overrides: dict | None = None
    if max_papers is not None:
        overrides = {"review": {"max_papers": max_papers}}
    cfg = load_config(config, overrides=overrides)

    with TraceLogger(run_id, runs_dir=cfg.output.runs_dir) as trace:
        trace.event(
            agent="cli",
            event="run_start",
            payload={
                "question": question,
                "fixture": fixture,
                "config": cfg.model_dump(),
            },
        )
        typer.echo(f"run_id={run_id}")
        typer.echo(f"run_dir={trace.run_dir}")
        trace.event(agent="cli", event="run_end", payload={"ok": True})


if __name__ == "__main__":
    app()
