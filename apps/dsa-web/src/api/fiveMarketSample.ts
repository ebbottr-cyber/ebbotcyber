import apiClient from './index';
import {
  parseFiveMarketSampleReport,
  type FiveMarketSampleReport,
} from '../utils/fiveMarketSampleReport';

/** Reads an already generated, operator-configured report; never triggers a scan. */
export const fiveMarketSampleApi = {
  async getSavedReport(): Promise<FiveMarketSampleReport> {
    const response = await apiClient.get<unknown>('/api/v1/data/five-market/samples');
    return parseFiveMarketSampleReport(response.data);
  },
};
