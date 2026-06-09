"""Regenerate benchmark percentile data from a results.jsonl corpus.

Recomputes each site's overall score under the *current* config weights so the
benchmark distribution always matches production scoring, then writes the sorted
score list to benchmarks/percentiles_v1.json.

Usage:
    python scripts/gen_benchmark.py results.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from aeo_audit.engine import ConfigLoader

ROOT = Path(__file__).resolve().parent.parent
# Packaged with the wheel so installed users get percentile grading too.
OUT = ROOT / "aeo_audit" / "benchmarks" / "percentiles_v1.json"


def main(corpus: str) -> None:
    config = ConfigLoader.load()
    cat_w = config.weights
    chk_w = config.checks

    scores: list[float] = []
    with open(corpus, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            d = json.loads(line)
            per_check: dict[str, float] = {}
            for _cat, cd in d["scorecard"]["categories"].items():
                for ch in cd["checks"]:
                    per_check[ch["name"]] = ch["score"]
            overall = 0.0
            for cat, cw in cat_w.items():
                cs = sum(per_check.get(n, 0.0) * w for n, w in chk_w[cat].items()) * 100.0
                overall += cs * cw
            scores.append(round(overall, 2))

    scores.sort()
    data = {
        "_comment": "Benchmark percentile data for AEO score normalization. "
        "Seeded from a developer-tools corpus scored under the current weights.",
        "version": "v1",
        "sample_size": len(scores),
        "percentiles": scores,
    }
    OUT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(scores)} scores to {OUT}")
    print(f"  min={min(scores)} max={max(scores)} median={scores[len(scores)//2]}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results.jsonl")
