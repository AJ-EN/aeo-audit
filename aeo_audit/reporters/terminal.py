"""Rich terminal reporter - tables, progress, trees, syntax highlighting."""

from __future__ import annotations

from rich.console import Console

from aeo_audit.core.models import CheckStatus, Grade, ScanResult, Scorecard


class TerminalReporter:
    """Renders scan results to the terminal using Rich.

    Features:
    - Summary table: Category | Score | Grade | Top 3 Findings
    - Color-coded: 🟢 Pass, 🟡 Warn, 🔴 Fail, ⚪ Skip
    - Progress bar with per-check status
    - Expandable finding details
    """

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def render_scorecard(self, scorecard: Scorecard) -> None:
        """Render the full scorecard to terminal."""
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        grade = scorecard.grade
        grade_col = self.grade_color(grade)

        # Build score text
        overall_text = Text()
        overall_text.append("URL: ", style="bold")
        overall_text.append(scorecard.url + "\n")
        overall_text.append("Score: ", style="bold")
        overall_text.append(f"{scorecard.overall_score:.1f}/100", style=f"bold {grade_col}")
        overall_text.append("  Grade: ", style="bold")
        overall_text.append(grade.value, style=f"bold {grade_col}")

        if scorecard.percentile is not None:
            overall_text.append("  Percentile: ", style="bold")
            overall_text.append(f"{scorecard.percentile:.0f}th")

        overall_text.append("  CI: ", style="bold")
        overall_text.append(
            f"[{scorecard.confidence_interval.lower:.1f}, {scorecard.confidence_interval.upper:.1f}]"
        )

        self.console.print(
            Panel(overall_text, title="[bold]AEO Audit Report[/bold]", border_style="blue")
        )

        # Print Categories table
        category_table = Table(
            title="[bold]Category Score Breakdown[/bold]",
            show_header=True,
            header_style="bold magenta",
            box=None,
        )
        category_table.add_column("Category", width=15)
        category_table.add_column("Score Bar", width=15)
        category_table.add_column("Score", justify="right")
        category_table.add_column("Grade", justify="center")
        category_table.add_column("Weight", justify="right")

        for cat, cat_score in scorecard.categories.items():
            # Build bar (using 10 blocks)
            filled_len = int(cat_score.score / 10)
            bar_text = "█" * filled_len + "░" * (10 - filled_len)

            # Determine color based on score
            score_col = (
                "green" if cat_score.score >= 75 else ("yellow" if cat_score.score >= 40 else "red")
            )

            category_table.add_row(
                cat.value.capitalize(),
                f"[{score_col}]{bar_text}[/]",
                f"{cat_score.score:.1f}%",
                f"[{self.grade_color(cat_score.grade)}]{cat_score.grade.value}[/]",
                f"{cat_score.weight * 100:.0f}%",
            )

        self.console.print(category_table)

        # Print top findings if they exist
        if scorecard.findings:
            findings_table = Table(
                title="[bold]Top Findings / Issues[/bold]",
                show_header=True,
                header_style="bold magenta",
                box=None,
            )
            findings_table.add_column("Severity", width=10)
            findings_table.add_column("Check Name", width=25)
            findings_table.add_column("Finding Title")

            sorted_findings = sorted(
                scorecard.findings,
                key=lambda f: {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(
                    f.severity.value, 5
                ),
            )
            for f in sorted_findings[:5]:
                sev_color = (
                    "red"
                    if f.severity.value in ("critical", "high")
                    else ("yellow" if f.severity.value == "medium" else "blue")
                )
                findings_table.add_row(
                    f"[{sev_color}]{f.severity.value.upper()}[/]", f.check_name, f.title
                )
            self.console.print(findings_table)

    def render_progress(self, current: int, total: int, check_name: str) -> None:
        """Update progress bar."""
        # This can be used in CLI dynamically
        pass

    def render_scan_result(self, result: ScanResult, verbose: bool = False) -> None:
        """Render full scan result."""
        self.render_scorecard(result.scorecard)

        if verbose:
            self.console.print("\n[bold]Detailed Check Results & Evidence:[/bold]")
            for check in result.check_results:
                icon = self.status_icon(check.status)
                status_color = self.status_color(check.status)
                self.console.print(
                    f"\n{icon} [bold {status_color}]{check.name}[/] ({check.category.value}) — Score: {check.score:.2f} (w: {check.weight})"
                )
                if check.message:
                    self.console.print(f"  [italic]{check.message}[/italic]")
                if check.findings:
                    for f in check.findings:
                        self.console.print(
                            f"    - [bold red]Finding:[/] {f.title}: {f.description}"
                        )
                        if f.recommendation:
                            self.console.print(f"      [bold green]Fix:[/] {f.recommendation}")
                if check.evidence:
                    import json

                    from rich.json import JSON

                    try:
                        evidence_str = json.dumps(check.evidence, indent=2)
                        self.console.print("    [bold]Evidence:[/bold]")
                        self.console.print(JSON(evidence_str))
                    except Exception:
                        self.console.print(f"    [bold]Evidence:[/bold] {check.evidence}")

    @staticmethod
    def status_color(status: CheckStatus) -> str:
        """Map check status to Rich color."""
        colors = {
            CheckStatus.PASS: "green",
            CheckStatus.WARN: "yellow",
            CheckStatus.FAIL: "red",
            CheckStatus.SKIP: "grey50",
            CheckStatus.ERROR: "red",
        }
        return colors.get(status, "white")

    @staticmethod
    def status_icon(status: CheckStatus) -> str:
        """Map check status to colored icon."""
        icons = {
            CheckStatus.PASS: "🟢",
            CheckStatus.WARN: "🟡",
            CheckStatus.FAIL: "🔴",
            CheckStatus.SKIP: "⚪",
            CheckStatus.ERROR: "❌",
        }
        return icons.get(status, "❓")

    @staticmethod
    def grade_color(grade: Grade) -> str:
        """Map grade to Rich color."""
        colors = {
            Grade.A: "green",
            Grade.B: "blue",
            Grade.C: "yellow",
            Grade.D: "dark_orange",
            Grade.F: "red",
        }
        return colors.get(grade, "white")
