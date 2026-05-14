"""Aurora Launch — pilot flow cold-start benchmark.

Measures wall-clock time for the critical path:
  1. Import aurora_launch (module-level cold start)
  2. Load a synthetic corpus bundle
  3. Run corpus_cli generate (in-process)

Exits with code 0 if cold start < COLD_START_LIMIT_S seconds.
Exits with code 1 if threshold exceeded (performance regression gate).

Usage:
    python tools/bench_pilot_flow.py [--limit SECONDS]

CI usage (bench.yml):
    python tools/bench_pilot_flow.py --limit 2.0
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

# Gate default: 2 seconds for module-level cold start + minimal bundle load.
# This is a smoke threshold, not a full forecast benchmark.
COLD_START_LIMIT_S = 2.0


def bench_import() -> float:
    """Time aurora_launch cold import (first import в process = cold start)."""
    t0 = time.perf_counter()
    import aurora_launch  # noqa: F401  # pylint: disable=import-outside-toplevel
    from aurora_launch.engines.corpus_generator import (  # noqa: F401
        list_corpus_categories,
    )
    return time.perf_counter() - t0


def bench_corpus_generate() -> float:
    """Time synthetic corpus single-project generation."""
    from aurora_launch.engines.corpus_generator import (  # noqa: PLC0415
        generate_synthetic_project,
        list_corpus_categories,
    )

    categories = list_corpus_categories()
    if not categories:
        print("WARN: no corpus categories found — skipping corpus bench")
        return 0.0

    # Use first available category for deterministic timing.
    category = categories[0]
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "bench.aurora.json"
        generate_synthetic_project(
            category_key=category,
            variant="baseline",
            seed=42,
            output_path=out_path,
        )
    return time.perf_counter() - t0


def main() -> None:
    parser = argparse.ArgumentParser(description="Aurora Launch pilot flow benchmark")
    parser.add_argument(
        "--limit",
        type=float,
        default=COLD_START_LIMIT_S,
        help=f"Cold start time limit in seconds (default: {COLD_START_LIMIT_S})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (for CI parsing)",
    )
    args = parser.parse_args()

    results: dict[str, float] = {}

    print("Aurora Launch pilot flow benchmark")
    print(f"Cold start limit: {args.limit:.1f}s")
    print("-" * 40)

    # 1. Import cold start
    t_import = bench_import()
    results["import_s"] = round(t_import, 4)
    status_import = "OK" if t_import < args.limit else "FAIL"
    print(f"  import cold start : {t_import:.3f}s  [{status_import}]")

    # 2. Corpus generate (not part of cold-start gate, informational only)
    t_corpus = bench_corpus_generate()
    results["corpus_generate_s"] = round(t_corpus, 4)
    print(f"  corpus generate   : {t_corpus:.3f}s  [INFO]")

    results["cold_start_limit_s"] = args.limit
    results["passed"] = t_import < args.limit

    print("-" * 40)
    if results["passed"]:
        print(f"PASS — cold start {t_import:.3f}s < {args.limit:.1f}s")
    else:
        print(
            f"FAIL — cold start {t_import:.3f}s >= {args.limit:.1f}s "
            f"(exceeded by {t_import - args.limit:.3f}s)"
        )

    if args.json:
        import json  # noqa: PLC0415

        print(json.dumps(results, indent=2))

    sys.exit(0 if results["passed"] else 1)


if __name__ == "__main__":
    main()
