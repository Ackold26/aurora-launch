/**
 * Heuristic auto-mapping XLSX/CSV source columns → Aurora canonical fields.
 * BTA-6: уменьшает время Step 1 wizard с ~3 минут до ~30 секунд.
 *
 * Approach: lowercase + normalise + check ENG/RUS synonym tables.
 * Если несколько synonyms matchят одну source column → берётся первый.
 */

export interface CanonicalFieldOption {
  id: string;           // canonical field id (brand_name)
  label_ru: string;     // human label («Бренд»)
  group: 'identity' | 'period' | 'sales' | 'media' | 'category';
}

/** Полный реестр канонических полей известных Aurora adapters. */
export const CANONICAL_FIELDS: readonly CanonicalFieldOption[] = [
  // identity
  { id: 'brand_name',        label_ru: 'Бренд',                  group: 'identity' },
  { id: 'manufacturer_name', label_ru: 'Производитель',           group: 'identity' },
  { id: 'advertiser_name',   label_ru: 'Рекламодатель',           group: 'identity' },
  { id: 'sku',               label_ru: 'SKU',                     group: 'identity' },
  // period
  { id: 'period_date',       label_ru: 'Период / Дата',           group: 'period'   },
  // sales
  { id: 'sales_volume_packs', label_ru: 'Продажи (упаковки)',     group: 'sales'    },
  { id: 'sales_value_rub',   label_ru: 'Продажи (рубли)',         group: 'sales'    },
  { id: 'market_share_pct',  label_ru: 'Доля рынка, %',           group: 'sales'    },
  { id: 'spend_thousand_rub', label_ru: 'Затраты (тыс. руб)',     group: 'sales'    },
  // media
  { id: 'channel_name',      label_ru: 'Канал',                   group: 'media'    },
  { id: 'media_type',        label_ru: 'Тип медиа',               group: 'media'    },
  { id: 'grp',               label_ru: 'GRP',                     group: 'media'    },
  { id: 'tvr',               label_ru: 'TVR',                     group: 'media'    },
  { id: 'reach_pct',         label_ru: 'Reach, %',                group: 'media'    },
  { id: 'audience_group',    label_ru: 'Аудитория',               group: 'media'    },
  // category
  { id: 'region',            label_ru: 'Регион',                  group: 'category' },
  { id: 'pricing_segment',   label_ru: 'Ценовой сегмент',         group: 'category' },
  { id: 'atc_code',          label_ru: 'АТХ-код',                 group: 'category' },
];

/** Synonym table: lowercase normalised source name → canonical id. */
const SYNONYM_MAP: Record<string, string> = {
  // brand
  'бренд':              'brand_name',
  'brand':              'brand_name',
  'brand_name':         'brand_name',
  'название бренда':    'brand_name',
  // manufacturer
  'производитель':      'manufacturer_name',
  'manufacturer':       'manufacturer_name',
  'компания':           'manufacturer_name',
  // advertiser
  'рекламодатель':      'advertiser_name',
  'advertiser':         'advertiser_name',
  // sku
  'sku':                'sku',
  'артикул':            'sku',
  // period
  'дата':               'period_date',
  'date':               'period_date',
  'период':             'period_date',
  'period':             'period_date',
  'дата_продажи':       'period_date',
  'дата продажи':       'period_date',
  'дата_время':         'period_date',
  'datetime':           'period_date',
  'неделя':             'period_date',
  'week':               'period_date',
  'месяц':              'period_date',
  'month':              'period_date',
  // sales packs
  'продажи_упаковки':   'sales_volume_packs',
  'продажи упаковки':   'sales_volume_packs',
  'упаковки':           'sales_volume_packs',
  'packs':              'sales_volume_packs',
  'volume_packs':       'sales_volume_packs',
  // sales rub
  'продажи_рубли':      'sales_value_rub',
  'продажи рубли':      'sales_value_rub',
  'продажи':            'sales_value_rub',
  'sales':              'sales_value_rub',
  'revenue':            'sales_value_rub',
  'выручка':            'sales_value_rub',
  // market share
  'доля_рынка':         'market_share_pct',
  'доля рынка':         'market_share_pct',
  'market_share':       'market_share_pct',
  'share':              'market_share_pct',
  // spend
  'затраты_тыс_руб':    'spend_thousand_rub',
  'затраты':            'spend_thousand_rub',
  'spend':              'spend_thousand_rub',
  'бюджет':             'spend_thousand_rub',
  // channel
  'канал':              'channel_name',
  'channel':            'channel_name',
  'channek':            'channel_name', // legacy typo from AdEx
  // media
  'медиа_тип':          'media_type',
  'медиа':              'media_type',
  'media_type':         'media_type',
  'media':              'media_type',
  // grp / tvr / reach / audience
  'grp':                'grp',
  'tvr':                'tvr',
  'reach':              'reach_pct',
  'reach_1+':           'reach_pct',
  'reach %':            'reach_pct',
  'охват':              'reach_pct',
  'audience':           'audience_group',
  'аудитория':          'audience_group',
  // region
  'регион':             'region',
  'region':             'region',
  // pricing
  'ценовой_сегмент':    'pricing_segment',
  'ценовой сегмент':    'pricing_segment',
  'pricing':            'pricing_segment',
  'pricing_tier':       'pricing_segment',
  // atc
  'атх_код':            'atc_code',
  'атх':                'atc_code',
  'atc':                'atc_code',
  'atc_code':           'atc_code',
};

function normalise(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, ' ');
}

/**
 * Возвращает Map source column → canonical field id (или null если не нашли).
 * Sidecar suggested mapping имеет приоритет (adapter знает точно). Heuristic —
 * fallback для столбцов которые adapter не покрыл.
 */
export function autoMapColumns(
  sourceColumns: readonly string[],
  sidecarSuggested: Readonly<Record<string, string>> = {},
): Map<string, string | null> {
  const result = new Map<string, string | null>();
  for (const src of sourceColumns) {
    // priority 1: adapter уже знает
    if (sidecarSuggested[src]) {
      result.set(src, sidecarSuggested[src]);
      continue;
    }
    // priority 2: heuristic synonym table
    const key = normalise(src);
    const canonical = SYNONYM_MAP[key];
    result.set(src, canonical ?? null);
  }
  return result;
}

/** Group canonical fields для select dropdown с группами. */
export function groupedCanonicalFields(): Record<string, CanonicalFieldOption[]> {
  const groups: Record<string, CanonicalFieldOption[]> = {
    identity: [],
    period:   [],
    sales:    [],
    media:    [],
    category: [],
  };
  for (const f of CANONICAL_FIELDS) {
    (groups[f.group] as CanonicalFieldOption[]).push(f);
  }
  return groups;
}
