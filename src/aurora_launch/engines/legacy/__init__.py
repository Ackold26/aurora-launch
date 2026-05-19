"""Legacy local engine copies preserved during Sprint 0 cutover к aurora-platform-core shared library.

Activated only при USE_SHARED_ENGINES=0 env override. Default execution path
uses shared aurora_engines.* canonical implementations.

Files:
- bayesian_engine.py — local train_model (was at engines/bayesian_engine.py)
- decompose.py — local decompose (was at engines/decompose.py)
- ols_engine.py — local train_ols (was at engines/ols_engine.py)

Removal: Sprint Buffer per feature flag rollout.
"""
