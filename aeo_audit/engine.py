"""Engine module: orchestrates scans, batch jobs, configurations, and reporters."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from aeo_audit.core.crawler import Crawler
from aeo_audit.core.models import CheckStatus, Config, ScanResult
from aeo_audit.core.registry import registry
from aeo_audit.core.scoring import calculate_score
from aeo_audit.reporters import HtmlReporter, JsonReporter, PdfReporter, TerminalReporter

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class ConfigLoader:
    """Loads, merges, and validates configuration settings."""

    DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.yaml"

    @classmethod
    def load(cls, custom_path: Path | str | None = None) -> Config:
        """Load configuration from default and optional custom paths."""
        # 1. Load default config
        if not cls.DEFAULT_CONFIG_PATH.exists():
            # If the default config is not found in the current directory, check package level
            default_path = Path(__file__).parent.parent / "aeo_audit" / "config.yaml"
            if default_path.exists():
                cls.DEFAULT_CONFIG_PATH = default_path

        with open(cls.DEFAULT_CONFIG_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # 2. Merge with custom config if provided
        if custom_path:
            custom_path = Path(custom_path)
            if custom_path.exists():
                with open(custom_path, encoding="utf-8") as f:
                    custom_data = yaml.safe_load(f) or {}
                for k, v in custom_data.items():
                    if isinstance(v, dict) and k in data and isinstance(data[k], dict):
                        data[k].update(v)
                    else:
                        data[k] = v
            else:
                raise FileNotFoundError(f"Config file not found: {custom_path}")

        # 3. Construct model and validate weights
        config = Config(**data)
        cls.validate(config)
        return config

    @classmethod
    def validate(cls, config: Config) -> None:
        """Validate that weights sum to exactly 1.0."""
        # Validate category weights
        category_weights = config.weights
        total_cat_weight = sum(category_weights.values())
        if not abs(total_cat_weight - 1.0) < 1e-4:
            raise ValueError(f"Category weights must sum to 1.0 (got {total_cat_weight})")

        # Validate check weights
        for cat_name, check_weights in config.checks.items():
            total_check_weight = sum(check_weights.values())
            if not abs(total_check_weight - 1.0) < 1e-4:
                raise ValueError(
                    f"Check weights in category '{cat_name}' must sum to 1.0 (got {total_check_weight})"
                )


class ReporterFactory:
    """Factory to retrieve a reporter by name."""

    @staticmethod
    def get_reporter(format_name: str) -> Any:
        """Return reporter instance based on format name."""
        format_name = format_name.lower()
        if format_name == "html":
            return HtmlReporter()
        elif format_name == "pdf":
            return PdfReporter()
        elif format_name == "json":
            return JsonReporter()
        elif format_name == "terminal":
            return TerminalReporter()
        else:
            raise ValueError(f"Unknown reporter format: {format_name}")


class ScanEngine:
    """Orchestrates a single site scan."""

    @staticmethod
    async def scan(
        url: str,
        config: Config,
        check_filter: str | None = None,
        timeout: int | None = None,
        user_agent: str | None = None,
        headers: dict[str, str] | None = None,
        concurrency: int = 10,
        no_cache: bool = False,
    ) -> ScanResult:
        """Run all matching checks on a target site."""
        registry.discover_all()

        filter_list = None
        if check_filter:
            filter_list = [name.strip().lower() for name in check_filter.split(",")]

        check_classes = []
        for check_cls in registry.all_checks():
            if filter_list is None or check_cls.name.lower() in filter_list:
                check_classes.append(check_cls)

        crawler_settings = config.crawler
        ua = user_agent or crawler_settings.get("user_agent", "AEOAuditor/1.0")
        to = timeout or crawler_settings.get("timeout", 30)
        cache_enabled = not no_cache

        async with Crawler(
            user_agent=ua,
            timeout=to,
            cache_enabled=cache_enabled,
        ) as crawler:
            context = await crawler.fetch(url)

            if headers:
                context.headers.update(headers)

            sem = asyncio.Semaphore(concurrency)

            async def run_check(check_inst: Any) -> Any:
                async with sem:
                    start_time = asyncio.get_running_loop().time()
                    try:
                        res = await check_inst.run(context)
                    except Exception as e:
                        res = check_inst._make_result(
                            status=CheckStatus.ERROR,
                            score=0.0,
                            message=f"Check failed with error: {e}",
                            evidence={"error": str(e)},
                        )
                    end_time = asyncio.get_running_loop().time()
                    res.duration_ms = (end_time - start_time) * 1000.0
                    return res

            check_instances = [cls() for cls in check_classes]
            tasks = [run_check(inst) for inst in check_instances]
            check_results = await asyncio.gather(*tasks)

        scorecard = calculate_score(check_results, config)
        scorecard.url = url
        scorecard.scan_duration_ms = sum(r.duration_ms for r in check_results)

        return ScanResult(
            url=url,
            scorecard=scorecard,
            check_results=check_results,
            raw_data={"rendered_html": context.rendered_html},
            timestamp=scorecard.timestamp,
        )


class BatchEngine:
    """Orchestrates parallel scanning of multiple URLs."""

    @staticmethod
    async def batch(
        urls: list[str],
        config: Config,
        concurrency: int = 3,
        fail_fast: bool = False,
        **scan_options: Any,
    ) -> AsyncIterator[ScanResult]:
        """Perform concurrent scans over a list of URLs and yield results."""
        sem = asyncio.Semaphore(concurrency)

        async def scan_with_sem(url: str) -> ScanResult:
            async with sem:
                return await ScanEngine.scan(url, config, **scan_options)

        tasks = [asyncio.create_task(scan_with_sem(url)) for url in urls]

        for future in asyncio.as_completed(tasks):
            try:
                res = await future
                yield res
            except Exception:
                if fail_fast:
                    for t in tasks:
                        t.cancel()
                    raise
                else:
                    # Ignore and proceed with other URLs
                    pass
