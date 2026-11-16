import apiClient from './index';
import {
  parseFourMarketBatchProgress,
  type FourMarketBatchProgress,
} from '../utils/fourMarketBatchProgress';

/** Only retrieves a server-approved saved --status report; never starts scans. */
export const fourMarketBatchProgressApi = {
  async getSavedReport(): Promise<FourMarketBatchProgress> {
    const response = await apiClient.get<unknown>('/api/v1/data/four-market/batch-progress');
    return parseFourMarketBatchProgress(response.data);
  },
};
