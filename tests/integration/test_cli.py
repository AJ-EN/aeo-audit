"""Integration tests for CLI commands."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from click.testing import CliRunner

from aeo_audit.cli import main as cli

if TYPE_CHECKING:
    from pathlib import Path


def test_scan_command(mock_server: str, tmp_path: Path) -> None:
    """Test standard scan command generating JSON output."""
    runner = CliRunner()
    perfect_url = f"{mock_server}/perfect/"
    output_file = tmp_path / "out.json"

    result = runner.invoke(
        cli,
        [
            "scan",
            perfect_url,
            "--format",
            "json",
            "--output",
            str(output_file),
        ],
    )

    assert result.exit_code == 0
    assert output_file.exists()

    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert "overall_score" in data
    assert data["overall_score"] > 70.0


def test_batch_command(mock_server: str, tmp_path: Path) -> None:
    """Test batch scan command processing a list of URLs."""
    runner = CliRunner()
    perfect_url = f"{mock_server}/perfect/"
    input_file = tmp_path / "urls.txt"
    input_file.write_text(f"{perfect_url}\n{perfect_url}\n", encoding="utf-8")

    output_file = tmp_path / "out.jsonl"

    result = runner.invoke(
        cli,
        [
            "batch",
            str(input_file),
            "--format",
            "jsonl",
            "--output",
            str(output_file),
        ],
    )

    assert result.exit_code == 0
    assert output_file.exists()

    lines = output_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2

    for line in lines:
        data = json.loads(line)
        assert "scorecard" in data
        assert data["scorecard"]["overall_score"] > 70.0


def test_diff_command(mock_server: str, tmp_path: Path) -> None:
    """Test diff command comparing two scan results."""
    runner = CliRunner()
    perfect_url = f"{mock_server}/perfect/"

    # 1. Run first scan
    before_file = tmp_path / "before.json"
    runner.invoke(cli, ["scan", perfect_url, "--format", "json", "--output", str(before_file)])

    # 2. Run second scan
    after_file = tmp_path / "after.json"
    runner.invoke(cli, ["scan", perfect_url, "--format", "json", "--output", str(after_file)])

    # 3. Diff them
    result = runner.invoke(cli, ["diff", str(before_file), str(after_file), "--format", "json"])
    assert result.exit_code == 0

    data = json.loads(result.output)
    assert "before_score" in data
    assert "after_score" in data
    assert "delta" in data
    assert data["delta"] == 0.0


def test_config_commands(tmp_path: Path) -> None:
    """Test config init, validate, and show commands."""
    runner = CliRunner()
    config_file = tmp_path / "config.yaml"

    # Init config
    result = runner.invoke(cli, ["config", "init", "--output", str(config_file)])
    assert result.exit_code == 0
    assert config_file.exists()

    # Validate config
    result = runner.invoke(cli, ["config", "validate", "--config", str(config_file)])
    assert result.exit_code == 0

    # Show config
    result = runner.invoke(cli, ["config", "show", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "weights:" in result.output


def test_monitor_command(mock_server: str, tmp_path: Path) -> None:
    """Test monitor command in non-daemon mode."""
    runner = CliRunner()
    perfect_url = f"{mock_server}/perfect/"
    db_file = tmp_path / "monitor.db"

    result = runner.invoke(
        cli,
        [
            "monitor",
            perfect_url,
            "--db",
            str(db_file),
        ],
    )
    assert result.exit_code == 0
    assert db_file.exists()
