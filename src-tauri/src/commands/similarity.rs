//! Similarity computation IPC — sub-30ms warm per PERFORMANCE_BUDGETS §1.3.
//!
//! For Block 2 we ship the closed-form similarity (8 dimensions × match-rate)
//! that runs purely в Rust. Real ML-grade similarity (proxy training etc.)
//! lives в Python sidecar Block 4. This Rust path enables real-time radar
//! fill while user moves wizard sliders.

use serde::{Deserialize, Serialize};

use crate::errors::AuroraResult;

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

#[tauri::command]
pub async fn aggregate_score(input: AggregateScoreInput) -> AuroraResult<f64> {
    // Mirrors Python similarity_calculator.compute_aggregate_score
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
