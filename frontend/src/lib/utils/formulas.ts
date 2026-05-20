/**
 * Aurora Launch — formulas.ts (Sprint 3 D2, A13)
 *
 * Central registry — single source of truth for math explanations
 * surfaced via drill-down UX (DrillDownModal, NumberWithDrillDown,
 * ChartWithDrillDown).
 *
 * Each FormulaEntry describes WHAT a number/chart computes, WHERE the
 * underlying methodology was published (provenance citation), HOW to
 * interpret it (inputs, output). Drill-down components look up entries
 * by `key` and render them — never inline math directly in component
 * source.
 *
 * KaTeX renders `latex` in displayMode (with strict: false to permit
 * cyrillic inside \text{}). `text_fallback` is the screen-reader
 * accessible representation AND the fallback string when KaTeX render
 * throws (cyrillic edge cases, malformed LaTeX caught by user-side
 * customisation in future).
 *
 * Provenance citations carry academic methodology references — keep
 * them short (≤120 chars) and link to canonical sources where freely
 * available.
 *
 * ADD A NEW FORMULA — checklist:
 *   1. Pick stable `key` in snake_case (must not change after ship —
 *      it's referenced by components).
 *   2. Write `latex` in KaTeX dialect; use \text{cyrillic} for any
 *      russian inside math expressions.
 *   3. Write `text_fallback` as plain-text math — this is what screen
 *      readers consume AND the render-failure fallback.
 *   4. `explanation` — 1–2 sentence russian explanation (1st-person
 *      neutral: "вычисляется как...").
 *   5. `inputs` — list every symbol appearing in `latex`/`text_fallback`.
 *   6. `output` — describe what the formula returns (units, range,
 *      interpretation).
 *   7. `provenance.citation` — short bibliographic reference (Author,
 *      Year, Title-snippet).
 *   8. `provenance.url` — optional but preferred when paper is freely
 *      accessible.
 */

export interface FormulaProvenance {
  /** Short academic citation, e.g. "Tibshirani et al. 2019, Conformal Inference of Counterfactuals". */
  citation: string;
  /** Optional URL to freely accessible source (preprint, journal page). */
  url?: string;
}

export interface FormulaInput {
  /** Mathematical symbol as it appears in `latex` (e.g. "X_t", "\\sigma"). */
  symbol: string;
  /** Plain-russian description of what this input represents. */
  description: string;
}

export interface FormulaEntry {
  /** Stable key (snake_case) — referenced by component prop `formula_key`. */
  key: string;
  /** Russian title (2–6 words). */
  title: string;
  /** KaTeX LaTeX source (use \text{...} for cyrillic). */
  latex: string;
  /** Plain-text representation — used by screen readers AND as KaTeX render-failure fallback. */
  text_fallback: string;
  /** 1–2 russian sentences explaining the formula. */
  explanation: string;
  /** Bibliographic + URL citation. */
  provenance: FormulaProvenance;
  /** Input variables (symbol + description). */
  inputs: FormulaInput[];
  /** Output description (units, range, interpretation). */
  output: string;
}

/**
 * Aurora Launch formula registry (Sprint 3 initial set — 12 entries).
 *
 * Append-only after Sprint 3 ships; do not rename existing keys.
 */
const FORMULAS: Record<string, FormulaEntry> = {
  trust_score_8d: {
    key: 'trust_score_8d',
    title: 'Trust Score (8 измерений)',
    latex:
      'T = \\sum_{i=1}^{8} w_i \\cdot s_i, \\quad \\sum w_i = 1, \\quad s_i \\in [0, 1]',
    text_fallback: 'T = Σ wᵢ · sᵢ, где Σ wᵢ = 1 и sᵢ ∈ [0, 1]',
    explanation:
      'Композитный показатель доверия к прогнозу — взвешенная сумма восьми независимых индикаторов (методология сертифицирована, бандл подписан, прогноз воспроизводим, и т.д.). Веса заданы экспертно и сохраняются вместе с бандлом.',
    provenance: {
      citation: 'Aurora Launch, методологическая записка (внутренний документ, 2026)',
    },
    inputs: [
      { symbol: 'T', description: 'итоговая оценка доверия (диапазон 0–1)' },
      { symbol: 'w_i', description: 'вес i-го индикатора (сумма всех весов = 1)' },
      { symbol: 's_i', description: 'значение i-го индикатора, нормализованное к [0, 1]' },
    ],
    output:
      'Число от 0 до 1, где 1 — все восемь индикаторов в зелёной зоне. В UI отображается как процент.',
  },

  similarity_jensen_shannon: {
    key: 'similarity_jensen_shannon',
    title: 'Сходство (Jensen–Shannon)',
    latex:
      'JS(P \\,\\Vert\\, Q) = \\tfrac{1}{2} D_{KL}(P \\Vert M) + \\tfrac{1}{2} D_{KL}(Q \\Vert M), \\quad M = \\tfrac{P + Q}{2}',
    text_fallback:
      'JS(P‖Q) = ½·KL(P‖M) + ½·KL(Q‖M), где M = (P + Q) / 2',
    explanation:
      'Симметричная мера расстояния между распределением нового бренда (P) и распределением прокси-бренда (Q). Чем ближе JS к 0, тем выше сходство; в Aurora Launch итоговое сходство = 1 − JS.',
    provenance: {
      citation: 'Lin 1991, Divergence Measures Based on the Shannon Entropy',
      url: 'https://www.cs.cmu.edu/~aarti/Class/10704_Fall16/lec18.pdf',
    },
    inputs: [
      { symbol: 'P', description: 'распределение метрик нового бренда' },
      { symbol: 'Q', description: 'распределение метрик прокси-бренда' },
      { symbol: 'M', description: 'смесь P и Q (среднее)' },
      { symbol: 'D_{KL}', description: 'Kullback–Leibler divergence' },
    ],
    output:
      'Число от 0 до log(2). После нормализации (1 − JS / log(2)) отображается в UI как процент сходства.',
  },

  conformal_prediction_interval: {
    key: 'conformal_prediction_interval',
    title: 'Доверительный интервал (Conformal)',
    latex:
      '\\hat{C}_{1-\\alpha}(x) = \\bigl[\\hat{y}(x) - q_{1-\\alpha}, \\; \\hat{y}(x) + q_{1-\\alpha}\\bigr]',
    text_fallback:
      'C̃₁₋α(x) = [ŷ(x) − q₁₋α, ŷ(x) + q₁₋α]',
    explanation:
      'Conformal prediction даёт интервал, который накрывает истинное значение с вероятностью не менее 1 − α (например 90 %), без предположений о форме распределения ошибок.',
    provenance: {
      citation: 'Vovk, Gammerman, Shafer 2005, Algorithmic Learning in a Random World',
      url: 'https://link.springer.com/book/10.1007/978-3-031-06649-8',
    },
    inputs: [
      { symbol: '\\hat{y}(x)', description: 'точечный прогноз модели' },
      { symbol: 'q_{1-\\alpha}', description: '(1−α)-квантиль модуля calibration-ошибок' },
      { symbol: '\\alpha', description: 'допустимая вероятность промаха (по умолчанию 0.1)' },
    ],
    output:
      'Интервал [нижняя граница, верхняя граница]. В Aurora отображается как «conus» вокруг центрального прогноза.',
  },

  mcmc_credible_interval: {
    key: 'mcmc_credible_interval',
    title: 'Байесовский интервал (HDI)',
    latex:
      '\\text{HDI}_{1-\\alpha} = \\bigl[\\theta_L, \\theta_U\\bigr] : P(\\theta_L \\leq \\theta \\leq \\theta_U \\mid \\mathcal{D}) = 1 - \\alpha',
    text_fallback:
      'HDI₁₋α = [θ_L, θ_U] : P(θ_L ≤ θ ≤ θ_U | D) = 1 − α',
    explanation:
      'Highest Density Interval — самый узкий интервал апостериорного распределения, который содержит 1 − α массы вероятности. Получается из выборок MCMC.',
    provenance: {
      citation: 'Kruschke 2014, Doing Bayesian Data Analysis (2nd ed.), §12.5',
      url: 'https://sites.google.com/site/doingbayesiandataanalysis/',
    },
    inputs: [
      { symbol: '\\theta', description: 'оцениваемый параметр' },
      { symbol: '\\mathcal{D}', description: 'наблюдаемые данные' },
      { symbol: '\\alpha', description: 'допустимая вероятность промаха (0.1 → 90 % HDI)' },
    ],
    output:
      'Пара чисел [нижняя граница, верхняя граница]. Уже нормирована к шкале исходного параметра.',
  },

  budget_optimizer_marginal_roi: {
    key: 'budget_optimizer_marginal_roi',
    title: 'Маржинальный ROI по каналу',
    latex:
      'mROI_c = \\frac{\\partial \\hat{y}}{\\partial b_c} = \\beta_c \\cdot \\bigl(1 - e^{-k_c b_c}\\bigr)\\cdot \\frac{1}{b_c} \\, ',
    text_fallback:
      'mROI_c = ∂ŷ/∂b_c = β_c · (1 − exp(−k_c · b_c)) / b_c',
    explanation:
      'Производная прогноза продаж по бюджету канала c — показывает, сколько дополнительных продаж приносит следующий рубль, вложенный в этот канал. Учитывает насыщение через экспоненциальную кривую.',
    provenance: {
      citation:
        'Hanssens, Parsons, Schultz 2001, Market Response Models: Econometric and Time Series Analysis',
    },
    inputs: [
      { symbol: 'b_c', description: 'текущий бюджет канала c (рубли)' },
      { symbol: '\\beta_c', description: 'коэффициент эффективности канала' },
      { symbol: 'k_c', description: 'параметр насыщения канала' },
    ],
    output:
      'Безразмерная величина (∆ продаж на ∆ рубля). В UI отображается округлённо до 4 знаков.',
  },

  forecast_baseline_projection: {
    key: 'forecast_baseline_projection',
    title: 'Базовая проекция прогноза',
    latex:
      '\\hat{y}_{new}(t) = \\hat{y}_{proxy}(t) \\cdot \\gamma_{scale} \\cdot \\bigl(1 + \\delta_{anchors}(t)\\bigr)',
    text_fallback:
      'ŷ_new(t) = ŷ_proxy(t) · γ_scale · (1 + δ_anchors(t))',
    explanation:
      'Прогноз продаж нового бренда строится как масштабированный прогноз прокси-бренда с поправкой на anchor-параметры запуска (интенсивность, траектория, паттерн).',
    provenance: {
      citation: 'Aurora Launch, описание методологии proxy → new baseline (внутренний документ, 2026)',
    },
    inputs: [
      { symbol: '\\hat{y}_{proxy}(t)', description: 'прогноз прокси-бренда в неделю t' },
      { symbol: '\\gamma_{scale}', description: 'масштабирующий коэффициент (по размеру рынка/бренда)' },
      { symbol: '\\delta_{anchors}(t)', description: 'поправка на anchor-параметры запуска' },
    ],
    output:
      'Прогноз продаж нового бренда в неделю t (целевые единицы — обычно штуки или рубли).',
  },

  contagion_temporal_decay: {
    key: 'contagion_temporal_decay',
    title: 'Adstock (временное затухание рекламы)',
    latex:
      'A_t = X_t + \\lambda \\cdot A_{t-1}, \\quad 0 \\le \\lambda < 1',
    text_fallback:
      'A_t = X_t + λ · A_{t−1}, где 0 ≤ λ < 1',
    explanation:
      'Adstock-преобразование переносит эффект рекламы в текущей неделе на последующие — следующая неделя получает долю λ от накопленного эффекта.',
    provenance: {
      citation: 'Broadbent 1979, One Way TV Advertisements Work',
      url: 'https://journals.sagepub.com/doi/10.1177/147078537902100302',
    },
    inputs: [
      { symbol: 'X_t', description: 'рекламные расходы в неделю t' },
      { symbol: 'A_t', description: 'накопленный adstock в неделю t' },
      { symbol: '\\lambda', description: 'коэффициент затухания (доля переноса)' },
    ],
    output:
      'Adstock-преобразованный ряд, который далее подаётся в response curve канала.',
  },

  transfer_score_kl: {
    key: 'transfer_score_kl',
    title: 'Transfer-score (KL divergence)',
    latex:
      'TS(P_{src} \\Vert P_{tgt}) = D_{KL}(P_{tgt} \\Vert P_{src}) = \\sum_i P_{tgt}(i) \\log \\frac{P_{tgt}(i)}{P_{src}(i)}',
    text_fallback:
      'TS(P_src ‖ P_tgt) = KL(P_tgt ‖ P_src) = Σ P_tgt · log(P_tgt / P_src)',
    explanation:
      'Оценивает, насколько распределение целевого бренда отличается от исходного прокси — высокое значение означает, что прокси плохо переносится и нужна другая база.',
    provenance: {
      citation: 'Kullback, Leibler 1951, On Information and Sufficiency',
    },
    inputs: [
      { symbol: 'P_{src}', description: 'распределение метрик прокси-бренда' },
      { symbol: 'P_{tgt}', description: 'распределение метрик нового (целевого) бренда' },
    ],
    output:
      'Неотрицательное число. В Aurora Launch порог 0.25 — выше требуется ручная проверка transfer-validation.',
  },

  proxy_score_composite: {
    key: 'proxy_score_composite',
    title: 'Композитный proxy-score',
    latex:
      'PS = \\prod_{i=1}^{8} s_i^{w_i}, \\quad s_i \\in (0, 1], \\quad \\sum w_i = 1',
    text_fallback:
      'PS = ∏ sᵢ^(wᵢ), где sᵢ ∈ (0, 1] и Σ wᵢ = 1',
    explanation:
      'Взвешенное геометрическое среднее восьми измерений сходства — штрафует прокси, у которого хотя бы одно измерение очень слабое (произведение даёт ноль, если любой sᵢ → 0).',
    provenance: {
      citation: 'Aurora Launch, формула композитного proxy-score (внутренний документ, 2026)',
    },
    inputs: [
      { symbol: 's_i', description: 'нормированная оценка i-го измерения' },
      { symbol: 'w_i', description: 'вес i-го измерения' },
    ],
    output:
      'Число от 0 до 1. Геометрическое среднее всегда не больше арифметического — поэтому PS более строгий, чем линейная сумма.',
  },

  methodology_cert_signature_ed25519: {
    key: 'methodology_cert_signature_ed25519',
    title: 'Подпись Ed25519 (сертификат)',
    latex:
      '\\sigma = \\text{Sign}_{sk}\\bigl(H(\\text{payload})\\bigr), \\quad \\text{Verify}_{pk}(\\sigma, H) \\in \\{0, 1\\}',
    text_fallback:
      'σ = Sign_sk(H(payload)); Verify_pk(σ, H) ∈ {0, 1}',
    explanation:
      'Сертификат подписывается приватным ключом по детерминированной схеме Ed25519. Проверка подписи доказывает, что сертификат не был изменён и подписан владельцем парного публичного ключа.',
    provenance: {
      citation: 'Bernstein, Duif, Lange, Schwabe, Yang 2012, High-speed High-security Signatures',
      url: 'https://ed25519.cr.yp.to/ed25519-20110926.pdf',
    },
    inputs: [
      { symbol: 'sk', description: 'приватный ключ подписанта (32 байта)' },
      { symbol: 'pk', description: 'парный публичный ключ (32 байта)' },
      { symbol: 'H', description: 'SHA-512 от канонического payload' },
      { symbol: '\\sigma', description: 'подпись (64 байта)' },
    ],
    output:
      'Подпись 64 байта, прикреплённая к бандлу как signature.bin. Verify возвращает 1 при успехе, 0 при провале.',
  },

  bundle_hash_sha256: {
    key: 'bundle_hash_sha256',
    title: 'Hash бандла (SHA-256)',
    latex:
      'H_{bundle} = \\text{SHA-256}\\bigl(\\text{JCS}(\\text{manifest}) \\,\\Vert\\, \\text{files\\_concat}\\bigr)',
    text_fallback:
      'H_bundle = SHA-256( JCS(manifest) ‖ concat(files) )',
    explanation:
      'Композитный hash файла .aurora — сначала канонизируется manifest через JCS (RFC 8785), затем хэшируется конкатенация с содержимым файлов в lexicographic-порядке. Гарантирует bit-equal-reproducibility.',
    provenance: {
      citation: 'RFC 8785, JSON Canonicalization Scheme (JCS), 2020',
      url: 'https://www.rfc-editor.org/rfc/rfc8785',
    },
    inputs: [
      { symbol: 'manifest', description: 'JSON-манифест бандла' },
      { symbol: 'files', description: 'содержимое всех файлов внутри бандла' },
    ],
    output:
      '32-байтовый hash, hex-кодированный в 64 символа. Сохраняется в манифесте и проверяется при загрузке.',
  },

  reproducibility_token: {
    key: 'reproducibility_token',
    title: 'Reproducibility token',
    latex:
      'R = \\text{SHA-256}\\bigl(H_{bundle} \\,\\Vert\\, \\text{aurora\\_launch\\_version} \\,\\Vert\\, \\text{seed}\\bigr)',
    text_fallback:
      'R = SHA-256( H_bundle ‖ aurora_launch_version ‖ seed )',
    explanation:
      'Производный токен, который позволяет CLI «aurora-launch-reproduce» одной командой проверить, что бандл собран из тех же входов и той же версией Aurora Launch.',
    provenance: {
      citation: 'Aurora Launch, спецификация D2.1 (Sprint 2, 2026)',
    },
    inputs: [
      { symbol: 'H_{bundle}', description: 'композитный hash бандла (формула выше)' },
      { symbol: 'aurora\\_launch\\_version', description: 'версия Aurora Launch, собравшей бандл' },
      { symbol: 'seed', description: 'random seed, использованный при сэмплировании MCMC' },
    ],
    output:
      '32-байтовый hash, hex-кодированный. Сохраняется как `reproducibility_token` в манифесте.',
  },
};

/**
 * Look up a FormulaEntry by key. Returns null if no entry exists —
 * components SHOULD treat null as "no drill-down available" and skip
 * showing drill-down affordance (not show an empty modal).
 */
export function getFormula(key: string): FormulaEntry | null {
  return FORMULAS[key] ?? null;
}

/**
 * Cheap existence check — avoids allocating the FormulaEntry. Useful
 * when wrapping a number and you only want to know whether to render
 * the drill-down affordance.
 */
export function hasFormula(key: string): boolean {
  return key in FORMULAS;
}

/**
 * All registered formula keys (stable order — insertion order is
 * preserved by `Object.keys` since ES2015). Used by tests and the
 * developer-facing transparency catalogue (potential future feature).
 */
export function getAllFormulaKeys(): string[] {
  return Object.keys(FORMULAS);
}

/**
 * Full registry export — primarily for tests + catalogue generation.
 * Avoid using in production code paths; prefer `getFormula(key)`.
 */
export function getAllFormulas(): FormulaEntry[] {
  return Object.values(FORMULAS);
}
