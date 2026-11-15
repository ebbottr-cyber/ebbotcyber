import apiClient from './index';
import {
  parseBist100CoverageReport,
  type Bist100CoverageReport,
} from '../utils/bist100CoverageReport';

/** No scan is triggered. The server only reads an existing, admin-gated audit. */
export const bist100CoverageApi = {
  async getSavedReport(): Promise<Bist100CoverageReport> {
    const response = await apiClient.get<unknown>('/api/v1/data/bist100/coverage');
    return parseBist100CoverageReport(response.data);
  },
};
