"""Command-line surface. `readiness --help`."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from readiness.config import get_settings

app = typer.Typer(help="Network security, cloud readiness and agentic-AI readiness assessor.", no_args_is_help=True)


@app.command()
def assess(
    source: str = typer.Argument(
        ..., help="Folder path, or gs://bucket/prefix, s3://bucket/prefix, gdrive://<folder-id-or-url>"
    ),
    profile: str = typer.Option("default", help="Scoring profile id from config/profiles"),
    out: Path | None = typer.Option(None, help="Workspace directory (default READINESS_WORKSPACE_DIR)"),
    snippets: bool | None = typer.Option(
        None,
        "--snippets/--no-snippets",
        help="Include evidence snippets (default: READINESS_INCLUDE_EVIDENCE_SNIPPETS)",
    ),
    llm_judge: bool | None = typer.Option(
        None,
        "--llm-judge/--no-llm-judge",
        help="Refine rule verdicts with the model (default: READINESS_USE_LLM_JUDGE)",
    ),
    llm_classifier: bool | None = typer.Option(
        None,
        "--llm-classifier/--no-llm-classifier",
        help="Re-classify unsure documents with the model (default: READINESS_USE_LLM_CLASSIFIER)",
    ),
    print_md: bool = typer.Option(True, "--print/--no-print", help="Print the markdown report"),
):
    """Assess a document source. Flags override the environment only when given explicitly."""
    from readiness.pipeline import run_assessment

    overrides: dict[str, object] = {}
    if snippets is not None:
        overrides["include_evidence_snippets"] = snippets
    if llm_judge is not None:
        overrides["use_llm_judge"] = llm_judge
    if llm_classifier is not None:
        overrides["use_llm_classifier"] = llm_classifier
    if out:
        overrides["workspace_dir"] = out
    settings = get_settings(**overrides)
    report, md = run_assessment(source, settings, profile)
    if print_md:
        typer.echo(md)
    typer.echo(
        f"[done] run={report.id} score={report.overall_score} coverage={report.overall_coverage} "
        f"llm={report.llm_provider} -> {Path(settings.workspace_dir) / settings.tenant_id / report.id}",
        err=True,
    )


@app.command()
def profiles():
    """List scoring profiles."""
    from readiness.scoring.profiles import list_profiles

    for p in list_profiles(get_settings().config_dir):
        typer.echo(f"{p.id:16} {p.name}  domains={[d.id for d in p.domains]}")


@app.command()
def checks(domain: str = typer.Argument("network_security")):
    """List checks in a scoring domain."""
    from readiness.scoring.profiles import load_domain

    d = load_domain(get_settings().config_dir, domain)
    for p in d.pillars:
        typer.echo(f"\n{p.id} ({p.name}, weight {p.weight})")
        for c in p.checks:
            typer.echo(f"  {c.id:12} {c.points:>3g} pts  {c.title}  [{', '.join(c.ccm)}]")


@app.command()
def controls(term: str):
    """Search the CSA CCM v4.1 control catalog."""
    from readiness.scoring.catalog import search

    for c in search(term):
        typer.echo(f"{c['id']:10} {c['title']}  ({len(c['questions'])} CAIQ questions)")


@app.command()
def redact(path: Path, mode: str = "pseudonymize"):
    """Show what the redactor would do to a text file (useful to tune config/redaction.yaml)."""
    from readiness.guardrails.redaction import Redactor

    r = Redactor.from_config(mode, get_settings().config_dir / "redaction.yaml")
    typer.echo(r.redact(path.read_text(errors="replace")))
    typer.echo(json.dumps(r.summary()), err=True)


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8080):  # noqa: S104 - container entrypoint
    """Run the HTTP API."""
    import uvicorn

    uvicorn.run("readiness.api.app:app", host=host, port=port)


if __name__ == "__main__":
    app()
