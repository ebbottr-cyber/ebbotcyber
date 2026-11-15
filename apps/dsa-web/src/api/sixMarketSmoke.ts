import apiClient from './index';
import {
  parseSixMarketEvidence,
  type SixMarketEvidence,
} from '../utils/sevenMarketEvidence';

/** Admin-only read of previously approved historical six-market sample report.
 * No data fetch, analysis, upload or trading operation is performed.
 */
export const sixMarketSmokeApi = {
  async getSavedReport(): Promise<SixMarketEvidence> {
    const response = await apiClient.get<unknown>('/api/v1/data/six-market/smoke-report');
    return parseSixMarketEvidence(response.data);
  },
};
