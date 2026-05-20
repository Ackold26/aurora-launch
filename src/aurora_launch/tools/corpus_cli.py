"""aurora-corpus CLI — synthetic corpus generation tool.

Per PHASE_B_REQUIREMENTS.md §4.1 — `aurora corpus generate <category> <variant> --seed <N>`.

Examples:
    aurora-corpus list-categories
    aurora-corpus generate FMCG_food.snacks_savoury baseline --seed 42
    aurora-corpus generate-all --output-dir tests/fixtures/synthetic_corpus
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from aurora_launch import __version__
from aurora_launch.engines.corpus_generator import (
    generate_synthetic_project,
    list_corpus_categories,
)
from aurora_launch.schemas.synthetic_corpus import (
    SyntheticProjectSpec,
)


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """Aurora Launch corpus generator CLI."""


@main.command("list-categories")
def list_categories_cmd() -> None:
    """List all supported synthetic corpus categories."""
    cats = list_corpus_categories()
    click.echo("Supported categories:")
    for c in cats:
        click.echo(f"  - {c}")


@main.command("generate")
@click.argument("category_l3", type=str)
@click.argument(
    "variant",
    type=click.Choice(["baseline", "high_seasonality", "volatile", "low_data", "cross_category_edge"]),
)
@click.option("--seed", type=int, default=42, help="Random seed (deterministic).")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output bundle path. Default: ./<category>_<variant>_seed<N>.aurora.json",
)
@click.option("--n-weeks", type=int, default=104, help="Number of weeks (≥104).")
@click.option("--n-channels", type=int, default=6, help="Number of media channels (≥4).")
@click.option(
    "--pricing-tier",
    type=click.Choice(["ECONOMY", "MAINSTREAM", "PREMIUM", "LUXURY"]),
    default="MAINSTREAM",
)
@click.option(
    "--brand-size",
    type=click.Choice(["LEADER", "CHALLENGER", "NICHE"]),
    default="CHALLENGER",
)
@click.option(
    "--media-maturity",
    type=click.Choice(["ALWAYS_ON", "PULSING", "PROMO_DRIVEN", "DORMANT"]),
    default="ALWAYS_ON",
)
def generate_cmd(
    category_l3: str,
    variant: str,
    seed: int,
    output: Path | None,
    n_weeks: int,
    n_channels: int,
    pricing_tier: str,
    brand_size: str,
    media_maturity: str,
) -> None:
    """Generate single synthetic corpus project."""
    valid = list_corpus_categories()
    if category_l3 not in valid:
        click.secho(f"✗ Unknown category: {category_l3}", fg="red")
        click.echo("Valid categories:")
        for c in valid:
            click.echo(f"  - {c}")
        raise click.Abort()

    spec = SyntheticProjectSpec(
        seed=seed,
        category_l3=category_l3,  # type: ignore[arg-type]
        variant=variant,  # type: ignore[arg-type]
        n_weeks=n_weeks,
        n_channels=n_channels,
        pricing_tier=pricing_tier,  # type: ignore[arg-type]
        brand_size=brand_size,  # type: ignore[arg-type]
        media_maturity=media_maturity,  # type: ignore[arg-type]
    )

    output_dir = output.parent if output else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle_path = generate_synthetic_project(spec, output_dir)

    if output and output != bundle_path:
        bundle_path.rename(output)
        bundle_path = output

    # Read computed hash for display
    with bundle_path.open("r", encoding="utf-8") as f:
        bundle = json.load(f)

    click.secho("✓ ", fg="green", nl=False)
    click.echo(f"Generated: {bundle_path}")
    click.echo(f"  manifest_sha256: {bundle['manifest_sha256']}")
    click.echo(f"  reproducibility_token: {bundle['reproducibility_token']}")
    click.echo(f"  Reproduce: aurora-launch-reproduce {bundle_path} {bundle['manifest_sha256']}")


@main.command("generate-all")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("tests/fixtures/synthetic_corpus"),
)
@click.option("--seed-base", type=int, default=42)
def generate_all_cmd(output_dir: Path, seed_base: int) -> None:
    """Generate full synthetic corpus (5 representative projects)."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Curated representative set (5 projects across diverse categories + variants)
    targets = [
        ("FMCG_food.snacks_savoury", "baseline", "ALWAYS_ON", "MAINSTREAM"),
        ("FMCG_beverage.beverage_energy", "high_seasonality", "PULSING", "PREMIUM"),
        ("OTC_pharma.OTC_cold_flu", "baseline", "PROMO_DRIVEN", "MAINSTREAM"),
        ("Cosmetics.skincare_premium", "volatile", "ALWAYS_ON", "PREMIUM"),
        ("awareness.brand_awareness_only", "low_data", "DORMANT", "ECONOMY"),
    ]

    for idx, (category, variant, maturity, pricing) in enumerate(targets):
        spec = SyntheticProjectSpec(
            seed=seed_base + idx,
            category_l3=category,  # type: ignore[arg-type]
            variant=variant,  # type: ignore[arg-type]
            media_maturity=maturity,  # type: ignore[arg-type]
            pricing_tier=pricing,  # type: ignore[arg-type]
        )
        path = generate_synthetic_project(spec, output_dir)
        click.echo(f"  ✓ {path.name}")

    click.secho(f"\n✓ Generated {len(targets)} corpus projects in {output_dir}", fg="green")


@main.command("generate-pharma-pilot")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("tests/fixtures/pharma_pilot"),
    help="Output directory for 3 pharma pilot bundles.",
)
def generate_pharma_pilot_cmd(output_dir: Path) -> None:
    """Generate 3 pharma pilot bundles for Sprint 4 pilot scenarios.

    Outputs:
      - pharma_otc_immune.aurora.json (OTC immune defence, Кагоцел-class)
      - pharma_rx_cardio.aurora.json (Rx cardiology — uses OTC_pharma.OTC_cold_flu
        as closest available; Sprint Buffer item for proper Rx_pharma.* category
        in Sprint 5)
      - pharma_generic_painkiller.aurora.json (generic analgesic)

    Bundles are deterministic: same seed → identical bundle hash.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    pilots = [
        # (filename, spec_kwargs)
        ("pharma_otc_immune.aurora.json", {
            "seed": 1001,
            "category_l3": "OTC_pharma.OTC_cold_flu",
            "variant": "high_seasonality",
            "n_weeks": 156,
            "pricing_tier": "MAINSTREAM",
            "brand_size": "CHALLENGER",
            "media_maturity": "ALWAYS_ON",
            "lifecycle": "MATURE",
        }),
        ("pharma_rx_cardio.aurora.json", {
            "seed": 1002,
            "category_l3": "OTC_pharma.OTC_cold_flu",
            "variant": "baseline",
            "n_weeks": 104,
            "pricing_tier": "PREMIUM",
            "brand_size": "LEADER",
            "media_maturity": "DORMANT",
            "lifecycle": "MATURE",
        }),
        ("pharma_generic_painkiller.aurora.json", {
            "seed": 1003,
            "category_l3": "OTC_pharma.OTC_pain",
            "variant": "volatile",
            "n_weeks": 104,
            "pricing_tier": "ECONOMY",
            "brand_size": "NICHE",
            "media_maturity": "PROMO_DRIVEN",
            "lifecycle": "MATURE",
        }),
    ]

    for filename, kwargs in pilots:
        spec = SyntheticProjectSpec(**kwargs)  # type: ignore[arg-type]
        path = generate_synthetic_project(spec, output_dir)
        # Rename from default <category>_<variant>_seed<N>.aurora.json to pharma_*.aurora.json
        # Use replace() (atomic on POSIX; on Windows overwrites existing target).
        target = output_dir / filename
        if path != target:
            path.replace(target)
        click.echo(f"  ✓ {target.name}")

    click.secho(f"\n✓ Generated 3 pharma pilot bundles in {output_dir}", fg="green")
    click.echo("  Bundles deterministic — same seed = identical bundle hash")


if __name__ == "__main__":
    main()
