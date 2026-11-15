/** Read-only client-side view over an already validated historical BIST100 report.
 *
 * Filtering and sorting are presentation only: never alter the original
 * ranking, its official rank numbers or the 100-stock analysis counters.
 */
import type { TechnicalRankedRow } from './bist100TechnicalReport';

export type Bist100RiskView = 'all' | 'ma5-clear' | 'chase-risk';
export type Bist100SortView = 'rank' | 'symbol' | 'rsi';
export type Bist100RankingViewOptions = {
  symbolQuery: string;
  risk: Bist100RiskView;
  minScore: number;
  sort: Bist100SortView;
};

export function selectBist100Ranking(
  ranking: readonly TechnicalRankedRow[],
  options: Bist100RankingViewOptions,
): TechnicalRankedRow[] {
  const query = options.symbolQuery.trim().toUpperCase();
  const minScore = Number.isFinite(options.minScore)
    ? Math.min(100, Math.max(0, options.minScore))
    : 0;

  const selected = ranking.filter(row =>
    row.symbol.includes(query) &&
    row.score >= minScore &&
    (options.risk === 'all' ||
      (options.risk === 'ma5-clear' && !row.chase_risk) ||
      (options.risk === 'chase-risk' && row.chase_risk))
  );

  return selected.sort((a, b) => {
    if (options.sort === 'symbol') {
      return a.symbol.localeCompare(b.symbol, 'en') || a.rank - b.rank;
    }
    if (options.sort === 'rsi') {
      return b.rsi12 - a.rsi12 || a.rank - b.rank;
    }
    // Retain the server-verified ranking, including equal-score tie order.
    return a.rank - b.rank;
  });
}
