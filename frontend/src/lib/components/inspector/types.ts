/**
 * Shared types for Inspector tab components.
 */

export type EngineMode =
  | 'pure_transfer'
  | 'transfer_with_bias_check'
  | 'ols_with_proxy_priors'
  | 'bayesian_with_proxy_priors';

export interface ForecastData {
  points: { weekIndex: number; point: number; ciLower: number; ciUpper: number }[];
  horizonWeeks: number;
  engineMode?: EngineMode | undefined;
  methodologySignature?: string | undefined;
  warnings?: string[] | undefined;
  nRecipient?: number | undefined;
  granularity?: 'monthly' | 'weekly' | undefined;
  anchors?: Record<string, unknown> | null | undefined;
  spendPlan?: Record<string, number[]> | null | undefined;
}

export interface SimilarityData {
  dimensions: { label: string; value: number }[];
  score: number;
}
