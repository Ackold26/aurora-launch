"""Synthetic corpus generator (B0.5 §4.1).

Generates synthetic .aurora-equivalent project structures с deterministic seeds
for BC test corpus + onboarding template library (Phase B B6).
"""

from aurora_launch.engines.corpus_generator.generator import (
    generate_synthetic_project,
    list_corpus_categories,
)

__all__ = ["generate_synthetic_project", "list_corpus_categories"]
