"""AEO Audit CLI - Click command definitions.

Commands:
    scan     : Single-site AEO readiness audit
    batch    : Batch scan from URL list file
    diff     : Compare two scan results
    config   : Configuration management (init, validate, show)
    monitor  : Continuous monitoring daemon
"""

from __future__ import annotations

import asyncio
import functools
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
import yaml
from rich.console import Console

from aeo_audit import __version__
from aeo_audit.engine import BatchEngine, ConfigLoader, ReporterFactory, ScanEngine

if TYPE_CHECKING:
    from aeo_audit.core.models import Config

console = Console()


def coro(f: Any) -> Any:
    """Decorator to run async Click commands."""

    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(f(*args, **kwargs))

    return wrapper


def get_config(ctx: click.Context) -> Config:
    """Retrieve or load global configuration."""
    config_path = ctx.obj.get("config_path")
    try:
        return ConfigLoader.load(config_path)
    except Exception as e:
        console.print(f"[bold red]Configuration Error:[/] {e}")
        sys.exit(2)


@click.group(
    name="aeo-audit",
    help="Scan websites and score their Agent/Engine Optimization (AEO) readiness.",
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(version=__version__, prog_name="aeo-audit")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False, path_type=Path),
    default=None,
    help="Path to custom config.yaml file.",
)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable verbose output.")
@click.option("--quiet", "-q", is_flag=True, default=False, help="Suppress all terminal output.")
@click.pass_context
def main(ctx: click.Context, config_path: Path | None, verbose: bool, quiet: bool) -> None:
    """AEO Audit CLI entry point."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


@main.command()
@click.argument("url", type=str)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["terminal", "json", "html", "pdf"], case_sensitive=False),
    default="terminal",
    help="Output format for the scan report.",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (required for html/pdf/json formats).",
)
@click.option(
    "--checks",
    "check_filter",
    type=str,
    default=None,
    help="Comma-separated list of check names to run (default: all).",
)
@click.option(
    "--timeout",
    type=int,
    default=None,
    help="Override default timeout in seconds.",
)
@click.option(
    "--user-agent",
    "user_agent",
    type=str,
    default=None,
    help="Custom User-Agent header.",
)
@click.option(
    "--headers",
    "headers_json",
    type=str,
    default=None,
    help='Additional headers in JSON format (e.g. \'{\\"Authorization\\": \\"Bearer x\\"}\').',
)
@click.option(
    "--concurrency",
    type=int,
    default=10,
    help="Max concurrent checks.",
)
@click.option(
    "--no-cache",
    is_flag=True,
    default=False,
    help="Disable caching for this scan.",
)
@click.option(
    "--color",
    type=click.Choice(["auto", "always", "never"]),
    default="auto",
    help="Color support.",
)
@click.option(
    "--fail-on-grade",
    "fail_on_grade",
    type=click.Choice(["A", "B", "C", "D"]),
    default=None,
    help="Exit 1 if overall grade is below threshold.",
)
@click.pass_context
@coro
async def scan(
    ctx: click.Context,
    url: str,
    output_format: str,
    output_path: Path | None,
    check_filter: str | None,
    timeout: int | None,
    user_agent: str | None,
    headers_json: str | None,
    concurrency: int,
    no_cache: bool,
    color: str,
    fail_on_grade: str | None,
) -> None:
    """Scan a single URL for AEO readiness."""
    # 1. Parse headers if provided
    headers = None
    if headers_json:
        try:
            headers = json.loads(headers_json)
        except Exception as e:
            console.print(f"[bold red]Error parsing --headers:[/] {e}")
            sys.exit(1)

    # 2. Get configuration
    config = get_config(ctx)

    # 3. Perform scan
    if not ctx.obj.get("quiet", False):
        console.print(f"[bold blue]AEO Audit[/bold blue] - Scanning [cyan]{url}[/cyan]")
    try:
        result = await ScanEngine.scan(
            url=url,
            config=config,
            check_filter=check_filter,
            timeout=timeout,
            user_agent=user_agent,
            headers=headers,
            concurrency=concurrency,
            no_cache=no_cache,
        )
    except Exception as e:
        console.print(f"[bold red]Scan failed with error:[/] {e}")
        sys.exit(1)

    # 4. Render output
    reporter = ReporterFactory.get_reporter(output_format)
    verbose = ctx.obj.get("verbose", False)

    if output_format == "terminal":
        if not ctx.obj.get("quiet", False):
            reporter.render_scan_result(result, verbose=verbose)
    else:
        if not output_path:
            console.print(
                f"[bold red]Error:[/] Output file path (-o / --output) is required for '{output_format}' format."
            )
            sys.exit(1)
        reporter.write(result, output_path)
        if not ctx.obj.get("quiet", False):
            console.print(f"[bold green]Report written to:[/] {output_path}")

    # 5. Check fail-on-grade threshold
    if fail_on_grade:
        grade_map = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
        actual_grade = result.scorecard.grade.value
        if grade_map.get(actual_grade, 0) < grade_map.get(fail_on_grade, 0):
            console.print(
                f"[bold red]Fail-on-grade triggered:[/] Grade {actual_grade} is below {fail_on_grade}."
            )
            sys.exit(2)


@main.command()
@click.argument("urls_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "jsonl", "html", "pdf"], case_sensitive=False),
    default="jsonl",
    help="Output format.",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path),
    required=True,
    help="Output file path.",
)
@click.option(
    "--concurrency",
    type=int,
    default=3,
    help="Number of concurrent scans.",
)
@click.option(
    "--fail-fast",
    is_flag=True,
    default=False,
    help="Stop on first scan error.",
)
@click.option(
    "--progress",
    "show_progress",
    is_flag=True,
    default=False,
    help="Show progress bar.",
)
@click.option(
    "--no-cache",
    is_flag=True,
    default=False,
    help="Disable caching for scans.",
)
@click.option(
    "--timeout",
    type=int,
    default=None,
    help="Override default timeout in seconds.",
)
@click.pass_context
@coro
async def batch(
    ctx: click.Context,
    urls_file: Path,
    output_format: str,
    output_path: Path,
    concurrency: int,
    fail_fast: bool,
    show_progress: bool,
    no_cache: bool,
    timeout: int | None,
) -> None:
    """Batch scan URLs from a file (one URL per line)."""
    # 1. Load config
    config = get_config(ctx)

    # 2. Read URLs from input file
    urls = []
    with open(urls_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("{"):
                try:
                    data = json.loads(line)
                    if "url" in data:
                        urls.append(data["url"])
                except Exception:
                    pass
            else:
                urls.append(line)

    if not urls:
        console.print("[bold red]Error:[/] No URLs found in input file.")
        sys.exit(1)

    # 3. Setup output file and stream scans
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results = []

    total = len(urls)
    passed = 0
    failed = 0
    score_sum = 0.0

    from contextlib import nullcontext

    with (
        open(output_path, "w", encoding="utf-8")
        if output_format == "jsonl"
        else nullcontext() as jsonl_file
    ):
        if show_progress and not ctx.obj.get("quiet", False):
            from rich.progress import (
                BarColumn,
                Progress,
                SpinnerColumn,
                TaskProgressColumn,
                TextColumn,
            )

            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            )
            with progress:
                task = progress.add_task("[blue]Batch scanning...", total=total)
                async for result in BatchEngine.batch(
                    urls=urls,
                    config=config,
                    concurrency=concurrency,
                    fail_fast=fail_fast,
                    no_cache=no_cache,
                    timeout=timeout,
                ):
                    results.append(result)
                    score_sum += result.scorecard.overall_score
                    if result.scorecard.overall_score >= 75:
                        passed += 1
                    else:
                        failed += 1

                    if jsonl_file is not None:
                        jsonl_file.write(result.model_dump_json() + "\n")
                        jsonl_file.flush()

                    progress.update(task, advance=1, description=f"[blue]Scanned: {result.url}[/]")
        else:
            async for result in BatchEngine.batch(
                urls=urls,
                config=config,
                concurrency=concurrency,
                fail_fast=fail_fast,
                no_cache=no_cache,
                timeout=timeout,
            ):
                results.append(result)
                score_sum += result.scorecard.overall_score
                if result.scorecard.overall_score >= 75:
                    passed += 1
                else:
                    failed += 1

                if jsonl_file is not None:
                    jsonl_file.write(result.model_dump_json() + "\n")
                    jsonl_file.flush()

                if not ctx.obj.get("quiet", False):
                    console.print(
                        f"Scanned [cyan]{result.url}[/cyan] — Score: [green]{result.scorecard.overall_score:.1f}[/]"
                    )

    # Write other formats at end
    if output_format == "json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump([r.model_dump(mode="json") for r in results], f, indent=2)
    elif output_format in ("html", "pdf"):
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>AEO Batch Scan Report</title>
    <style>
        body {{ font-family: sans-serif; background-color: #0b0f19; color: #fff; padding: 2rem; }}
        h1 {{ color: #6366f1; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 1.5rem; }}
        th, td {{ border: 1px solid #2d3748; padding: 0.75rem; text-align: left; }}
        th {{ background-color: #1a202c; }}
    </style>
</head>
<body>
    <h1>Batch Scan Results</h1>
    <p>Total: {total} | Passed: {passed} | Failed: {failed} | Avg Score: {score_sum / total:.1f}</p>
    <table>
        <thead>
            <tr>
                <th>URL</th>
                <th>Score</th>
                <th>Grade</th>
                <th>Timestamp</th>
            </tr>
        </thead>
        <tbody>"""
        for r in results:
            html_content += f"""
            <tr>
                <td>{r.url}</td>
                <td>{r.scorecard.overall_score:.1f}/100</td>
                <td>{r.scorecard.grade.value}</td>
                <td>{r.timestamp}</td>
            </tr>"""
        html_content += "</tbody></table></body></html>"

        if output_format == "html":
            output_path.write_text(html_content, encoding="utf-8")
        elif output_format == "pdf":
            from weasyprint import HTML
            from weasyprint.text.fonts import FontConfiguration

            font_config = FontConfiguration()
            HTML(string=html_content).write_pdf(output_path, font_config=font_config)

    # 4. Render summary
    if not ctx.obj.get("quiet", False):
        console.print("\n[bold green]Batch Scan Completed![/]")
        console.print(
            f"Total: {total} | Passed: {passed} | Failed: {failed} | Avg: {score_sum / total:.1f}"
        )


@main.command()
@click.argument("before_file", type=click.Path(exists=True, path_type=Path))
@click.argument("after_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["terminal", "json", "html"], case_sensitive=False),
    default="terminal",
    help="Output format for the diff report.",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path.",
)
@click.option(
    "--threshold",
    type=float,
    default=0.05,
    help="Only show changes > threshold (default: 0.05).",
)
@click.pass_context
def diff(
    ctx: click.Context,
    before_file: Path,
    after_file: Path,
    output_format: str,
    output_path: Path | None,
    threshold: float,
) -> None:
    """Compare two scan results (before/after)."""
    try:
        with open(before_file, encoding="utf-8") as f:
            before_data = json.load(f)
            before_scorecard = before_data.get("scorecard", before_data)

        with open(after_file, encoding="utf-8") as f:
            after_data = json.load(f)
            after_scorecard = after_data.get("scorecard", after_data)
    except Exception as e:
        console.print(f"[bold red]Error loading scan files:[/] {e}")
        sys.exit(1)

    before_score = before_scorecard["overall_score"]
    after_score = after_scorecard["overall_score"]
    delta = after_score - before_score

    cat_changes = {}
    for cat_name in ("discovery", "identity", "capabilities", "commerce", "trust"):
        b_cat = before_scorecard["categories"].get(
            cat_name, before_scorecard["categories"].get(cat_name.upper(), {})
        )
        a_cat = after_scorecard["categories"].get(
            cat_name, after_scorecard["categories"].get(cat_name.upper(), {})
        )
        b_score = b_cat.get("score", 0.0)
        a_score = a_cat.get("score", 0.0)
        cat_changes[cat_name] = {"before": b_score, "after": a_score, "delta": a_score - b_score}

    # Format output
    if output_format == "json":
        diff_data = {
            "before_score": before_score,
            "after_score": after_score,
            "delta": delta,
            "categories": cat_changes,
        }
        if not output_path:
            console.print(json.dumps(diff_data, indent=2))
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(diff_data, f, indent=2)
            console.print(f"[bold green]Diff written to:[/] {output_path}")

    elif output_format == "html":
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>AEO Comparison Report</title>
    <style>
        body {{ font-family: sans-serif; background-color: #0b0f19; color: #fff; padding: 2rem; }}
        h1 {{ color: #6366f1; }}
        .delta-pos {{ color: #10b981; }}
        .delta-neg {{ color: #ef4444; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 1.5rem; }}
        th, td {{ border: 1px solid #2d3748; padding: 0.75rem; text-align: left; }}
        th {{ background-color: #1a202c; }}
    </style>
</head>
<body>
    <h1>AEO Score Comparison</h1>
    <h2>Overall Score: {before_score:.1f} &rarr; {after_score:.1f} (<span class="{"delta-pos" if delta >= 0 else "delta-neg"}">{delta:+.1f}</span>)</h2>
    <table>
        <thead>
            <tr>
                <th>Category</th>
                <th>Before</th>
                <th>After</th>
                <th>Delta</th>
            </tr>
        </thead>
        <tbody>"""
        for cat, change in cat_changes.items():
            d = change["delta"]
            html_content += f"""
            <tr>
                <td style="text-transform: capitalize;">{cat}</td>
                <td>{change["before"]:.1f}%</td>
                <td>{change["after"]:.1f}%</td>
                <td><span class="{"delta-pos" if d >= 0 else "delta-neg"}">{d:+.1f}%</span></td>
            </tr>"""
        html_content += "</tbody></table></body></html>"

        if not output_path:
            console.print("[bold red]Error:[/] Output file path required for HTML format.")
            sys.exit(1)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding="utf-8")
        console.print(f"[bold green]Diff report written to:[/] {output_path}")

    else:
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        delta_col = "green" if delta >= 0 else "red"

        summary_text = Text()
        summary_text.append("Before: ", style="bold")
        summary_text.append(f"{before_score:.1f}/100\n")
        summary_text.append("After:  ", style="bold")
        summary_text.append(f"{after_score:.1f}/100\n")
        summary_text.append("Delta:  ", style="bold")
        summary_text.append(f"{delta:+.1f}", style=f"bold {delta_col}")

        console.print(
            Panel(summary_text, title="[bold]AEO Score Comparison[/bold]", border_style="blue")
        )

        table = Table(
            title="Category Delta Summary", show_header=True, header_style="bold magenta", box=None
        )
        table.add_column("Category")
        table.add_column("Before", justify="right")
        table.add_column("After", justify="right")
        table.add_column("Delta", justify="right")

        for cat, change in cat_changes.items():
            d = change["delta"]
            d_col = "green" if d >= 0 else "red"
            table.add_row(
                cat.capitalize(),
                f"{change['before']:.1f}%",
                f"{change['after']:.1f}%",
                f"[{d_col}]{d:+.1f}%[/]",
            )
        console.print(table)


@main.group()
@click.pass_context
def config(ctx: click.Context) -> None:
    """Configuration management commands."""
    pass


@config.command(name="init")
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path),
    default=Path("config.yaml"),
    help="Output path for the config template.",
)
@click.pass_context
def config_init(ctx: click.Context, output_path: Path) -> None:
    """Generate a default config.yaml template."""
    default_config_path = Path(__file__).parent / "config.yaml"
    if not default_config_path.exists():
        default_config_path = Path(__file__).parent.parent / "aeo_audit" / "config.yaml"

    try:
        content = default_config_path.read_text(encoding="utf-8")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        console.print(f"[bold green]Created default config at:[/] {output_path}")
    except Exception as e:
        console.print(f"[bold red]Failed to initialize config:[/] {e}")
        sys.exit(1)


@config.command(name="validate")
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to custom config.yaml file.",
)
@click.pass_context
def config_validate(ctx: click.Context, config_path: Path | None) -> None:
    """Validate a config.yaml file."""
    path = config_path or ctx.obj.get("config_path")
    try:
        ConfigLoader.load(path)
        console.print("[bold green]✓ Configuration is valid.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]✗ Configuration is invalid:[/] {e}")
        sys.exit(1)


@config.command(name="show")
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to custom config.yaml file.",
)
@click.pass_context
def config_show(ctx: click.Context, config_path: Path | None) -> None:
    """Print the resolved config."""
    path = config_path or ctx.obj.get("config_path")
    try:
        config = ConfigLoader.load(path)
        yaml_str = yaml.dump(config.model_dump(), default_flow_style=False)
        console.print(yaml_str)
    except Exception as e:
        console.print(f"[bold red]Error loading config:[/] {e}")
        sys.exit(1)


def parse_interval_to_seconds(interval: str) -> int:
    """Parse interval string into seconds."""
    try:
        if interval.endswith("s"):
            return int(interval[:-1])
        elif interval.endswith("m"):
            return int(interval[:-1]) * 60
        elif interval.endswith("h"):
            return int(interval[:-1]) * 3600
        elif interval.endswith("d"):
            return int(interval[:-1]) * 86400
        else:
            return int(interval) * 3600
    except Exception:
        return 168 * 3600


def init_db(db_path: Path) -> None:
    """Initialize SQLite database for monitor metrics."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            url TEXT,
            score REAL,
            grade TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_last_scan(db_path: Path, url: str) -> tuple[float, str] | None:
    """Retrieve score and grade of last scan."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT score, grade FROM scans WHERE url = ? ORDER BY timestamp DESC LIMIT 1", (url,)
    )
    row = cursor.fetchone()
    conn.close()
    return row  # type: ignore[no-any-return]


def save_scan(db_path: Path, url: str, score: float, grade: str) -> None:
    """Save score and grade to tracking table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO scans (url, score, grade, timestamp) VALUES (?, ?, ?, ?)",
        (url, score, grade, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


async def run_monitor_cycle(
    url: str,
    config: Config,
    db_path: Path,
    webhook_url: str | None,
    alert_threshold: str | None,
) -> None:
    """Perform monitor cycle: scan, log, alert."""
    try:
        result = await ScanEngine.scan(url, config)
    except Exception as e:
        console.print(f"[bold red]Monitor scan cycle failed:[/] {e}")
        return

    score = result.scorecard.overall_score
    grade = result.scorecard.grade.value

    last_scan = get_last_scan(db_path, url)
    save_scan(db_path, url, score, grade)

    if last_scan:
        last_score, last_grade = last_scan
        delta = score - last_score

        if last_grade != grade:
            console.print(
                f"[bold yellow]Alert:[/] Grade changed for {url} from {last_grade} to {grade} (Score delta: {delta:+.1f})"
            )

            if webhook_url:
                payload = {
                    "url": url,
                    "previous_grade": last_grade,
                    "current_grade": grade,
                    "delta": delta,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                import httpx

                try:
                    async with httpx.AsyncClient() as client:
                        await client.post(webhook_url, json=payload)
                except Exception as ex:
                    console.print(f"[bold red]Webhook notification failed:[/] {ex}")

    if alert_threshold:
        grade_map = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
        if grade_map.get(grade, 0) < grade_map.get(alert_threshold, 0):
            console.print(
                f"[bold red]ALERT:[/] Grade {grade} is below threshold {alert_threshold}!"
            )


@main.command()
@click.argument("url", type=str)
@click.option(
    "--interval",
    type=str,
    default="168h",
    help="Monitoring interval (e.g. 24h, 168h, 7d).",
)
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path),
    default=Path("monitor.db"),
    help="SQLite database path for storing results.",
)
@click.option(
    "--webhook",
    type=str,
    default=None,
    help="Alerting webhook URL.",
)
@click.option(
    "--alert-threshold",
    "alert_threshold",
    type=click.Choice(["A", "B", "C", "D"]),
    default="C",
    help="Alert if grade drops below threshold.",
)
@click.option(
    "--daemon",
    is_flag=True,
    default=False,
    help="Run as daemon in background.",
)
@click.pass_context
@coro
async def monitor(
    ctx: click.Context,
    url: str,
    interval: str,
    db_path: Path,
    webhook: str | None,
    alert_threshold: str | None,
    daemon: bool,
) -> None:
    """Monitor a URL for AEO readiness changes (daemon mode)."""
    console.print(
        f"[bold blue]AEO Audit[/bold blue] - Monitoring [cyan]{url}[/cyan] "
        f"every [green]{interval}[/green]"
    )
    init_db(db_path)
    config = get_config(ctx)
    seconds = parse_interval_to_seconds(interval)

    if daemon:
        console.print(f"[green]Daemon started monitoring {url} every {interval}...[/]")
        while True:
            await run_monitor_cycle(url, config, db_path, webhook, alert_threshold)
            await asyncio.sleep(seconds)
    else:
        await run_monitor_cycle(url, config, db_path, webhook, alert_threshold)


if __name__ == "__main__":
    main()
