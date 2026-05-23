//! Similarity computation IPC — sub-30ms warm per PERFORMANCE_BUDGETS §1.3.
//!
//! For Block 2 we ship the closed-form similarity (8 dimensions × match-rate)
//! that runs purely в Rust. Real ML-grade similarity (proxy training etc.)
//! lives в Python sidecar Block 4. This Rust path enables real-time radar
//! fill while user moves wizard sliders.

use serde::{Deserialize, Serialize};

use crate::errors::{AuroraError, AuroraResult};

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct SimilarityDimensionScores {
    pub category_l1_match: f64,
    pub category_l2_match: f64,
    pub category_l3_match: f64,
    pub pricing_tier_match: f64,
    pub brand_size_match: f64,
    pub distribution_match: f64,
    pub media_maturity_match: f64,
    pub lifecycle_match: f64,
    pub weights_used: std::collections::BTreeMap<String, f64>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ProxyVsRecipient {
    pub proxy_category_l1: String,
    pub proxy_category_l2: String,
    pub proxy_category_l3: String,
    pub proxy_pricing_tier: String,
    pub proxy_brand_size: String,
    pub proxy_distribution: String,
    pub proxy_media_maturity: String,
    pub proxy_lifecycle: String,
    pub recipient_category_l1: String,
    pub recipient_category_l2: String,
    pub recipient_category_l3: String,
    pub recipient_pricing_tier: String,
    pub recipient_brand_size: String,
    pub recipient_distribution: String,
    pub recipient_media_maturity: String,
    pub recipient_lifecycle: String,
}

fn match_rate(a: &str, b: &str) -> f64 {
    if a == b {
        1.0
    } else {
        0.0
    }
}

#[tauri::command]
pub async fn compute_similarity_dimensions(
    pair: ProxyVsRecipient,
) -> AuroraResult<SimilarityDimensionScores> {
    Ok(SimilarityDimensionScores {
        category_l1_match: match_rate(&pair.proxy_category_l1, &pair.recipient_category_l1),
        category_l2_match: match_rate(&pair.proxy_category_l2, &pair.recipient_category_l2),
        category_l3_match: match_rate(&pair.proxy_category_l3, &pair.recipient_category_l3),
        pricing_tier_match: match_rate(&pair.proxy_pricing_tier, &pair.recipient_pricing_tier),
        brand_size_match: match_rate(&pair.proxy_brand_size, &pair.recipient_brand_size),
        distribution_match: match_rate(&pair.proxy_distribution, &pair.recipient_distribution),
        media_maturity_match: match_rate(&pair.proxy_media_maturity, &pair.recipient_media_maturity),
        lifecycle_match: match_rate(&pair.proxy_lifecycle, &pair.recipient_lifecycle),
        weights_used: Default::default(),
    })
}

#[derive(Serialize, Deserialize, Debug)]
pub struct AggregateScoreInput {
    pub dimensions: SimilarityDimensionScores,
    pub weights: std::collections::BTreeMap<String, f64>,
}

/// Block 3 HIGH-9 fix: validate weights mirror Python
/// `SimilarityDimensionScores.weights_sum_to_unity_if_present` validator.
/// If weights non-empty, sum must be ~1.0 ±0.05 — otherwise frontend submits
/// invalid data, Rust accepts, Python rejects later (silent UX failure).
fn validate_weights(weights: &std::collections::BTreeMap<String, f64>) -> Result<(), AuroraError> {
    if weights.is_empty() {
        return Ok(());
    }
    // Reject NaN/Inf weights upfront
    for (k, v) in weights {
        if !v.is_finite() {
            return Err(AuroraError::Other(format!(
                "weight {k} not finite: {v}"
            )));
        }
        if *v < 0.0 {
            return Err(AuroraError::Other(format!(
                "weight {k} negative: {v}"
            )));
        }
    }
    let total: f64 = weights.values().sum();
    // Sprint 6 D3 #40 — explicit 1e-9 epsilon margin против FP rounding на
    // 0.05 boundary. Production weights summing к 0.95 ± FP epsilon (boundary
    // case of ±5% tolerance) могут produce (sum - 1.0).abs() = 0.050000000000000044
    // (IEEE 754 imprecision, e.g., 0.5 + 0.45). Без epsilon → false-positive
    // reject в некоторых input orderings. Epsilon 1e-9 (~10⁻⁹) safely absorbs
    // FP imprecision (~10⁻¹⁶ scale) без widening real tolerance к legitimate
    // over-budget cases (next reject threshold remains effectively 5.0000001%).
    const TOLERANCE_EPSILON: f64 = 1e-9;
    if (total - 1.0).abs() > 0.05 + TOLERANCE_EPSILON {
        return Err(AuroraError::Other(format!(
            "weights_used must sum to ~1.0 (±0.05), got {total:.4}"
        )));
    }
    Ok(())
}

#[tauri::command]
pub async fn aggregate_score(input: AggregateScoreInput) -> AuroraResult<f64> {
    // Mirrors Python similarity_calculator.compute_aggregate_score
    validate_weights(&input.weights)?;

    let total_weight: f64 = input.weights.values().sum();
    if total_weight <= 0.0 {
        return Ok(0.0);
    }

    let dim = &input.dimensions;
    let contributions = [
        ("category", dim.category_l3_match * input.weights.get("category").copied().unwrap_or(0.0)),
        ("pricing_tier", dim.pricing_tier_match * input.weights.get("pricing_tier").copied().unwrap_or(0.0)),
        ("brand_size", dim.brand_size_match * input.weights.get("brand_size").copied().unwrap_or(0.0)),
        ("distribution", dim.distribution_match * input.weights.get("distribution").copied().unwrap_or(0.0)),
        ("media_maturity", dim.media_maturity_match * input.weights.get("media_maturity").copied().unwrap_or(0.0)),
        ("lifecycle", dim.lifecycle_match * input.weights.get("lifecycle").copied().unwrap_or(0.0)),
    ];
    let weighted_sum: f64 = contributions.iter().map(|(_, v)| v).sum();
    Ok(weighted_sum / total_weight)
}

#[cfg(test)]
mod block_3_tests {
    use super::*;
    use std::collections::BTreeMap;

    fn weights(pairs: &[(&str, f64)]) -> BTreeMap<String, f64> {
        pairs.iter().map(|(k, v)| (k.to_string(), *v)).collect()
    }

    #[test]
    fn validate_weights_empty_passes() {
        assert!(validate_weights(&BTreeMap::new()).is_ok());
    }

    #[test]
    fn validate_weights_sum_one_passes() {
        let w = weights(&[("a", 0.5), ("b", 0.3), ("c", 0.2)]);
        assert!(validate_weights(&w).is_ok());
    }

    #[test]
    fn validate_weights_within_tolerance_passes() {
        // Sprint 6 D3 #40 — restored к original 0.5 + 0.45 (sum 0.95) тест-case
        // что hit FP-edge case в Sprint 4. После epsilon fix эти inputs passes
        // deterministically. Sprint Buffer #40 closed: underlying tolerance
        // check теперь FP-safe.
        let w = weights(&[("a", 0.5), ("b", 0.45)]); // sum 0.95 (5% off, FP-edge)
        assert!(validate_weights(&w).is_ok());
    }

    #[test]
    fn validate_weights_fp_edge_0_95_passes_after_epsilon_fix() {
        // Sprint 6 D3 #40 — INV-48 attack scenario: production weights summing
        // к 0.95 ± FP epsilon (boundary case of ±5% tolerance) могут produce
        // (sum - 1.0).abs() = 0.050000000000000044 due к IEEE 754 imprecision.
        // Без epsilon margin → false-positive reject в некоторых orderings.
        // С +1e-9 epsilon → deterministic accept.
        //
        // Test premise verify'ит actual FP edge surfaces; assertion verify'ит
        // fix accepts.
        let w = weights(&[("a", 0.5), ("b", 0.45)]);
        let sum: f64 = w.values().sum();
        assert!(
            (sum - 1.0).abs() > 0.05,
            "test premise: (sum - 1.0).abs() should hit FP edge above raw 0.05 \
             boundary (got {:.20})",
            (sum - 1.0).abs()
        );
        assert!(
            validate_weights(&w).is_ok(),
            "FP-edge 0.95 sum must pass tolerance check after epsilon fix"
        );
    }

    #[test]
    fn validate_weights_clearly_off_still_rejects_after_epsilon_fix() {
        // Sanity: real over-tolerance (6% off) MUST still reject after epsilon
        // widening. Verifies +1e-9 epsilon не silently broadens tolerance к
        // legitimate-reject ranges.
        let w = weights(&[("a", 0.53), ("b", 0.53)]); // sum 1.06 (6% off)
        assert!(validate_weights(&w).is_err());
    }

    #[test]
    fn validate_weights_off_rejects() {
        let w = weights(&[("a", 0.3), ("b", 0.3)]); // sum 0.6
        assert!(validate_weights(&w).is_err());
    }

    #[test]
    fn validate_weights_nan_rejects() {
        let w = weights(&[("a", f64::NAN), ("b", 0.5)]);
        assert!(validate_weights(&w).is_err());
    }

    #[test]
    fn validate_weights_negative_rejects() {
        let w = weights(&[("a", -0.1), ("b", 1.1)]); // sum 1.0 but negative
        assert!(validate_weights(&w).is_err());
    }
}
