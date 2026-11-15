import apiClient from './index';
import {
  parseBist100TechnicalReport,
  type Bist100TechnicalReport,
} from '../utils/bist100TechnicalReport';

/** Read a previously generated and admin-gated JSON report; never launch a scan. */
export const bist100TechnicalApi = {
  async getSavedReport(): Promise<Bist100TechnicalReport> {
    const response = await apiClient.get<unknown>('/api/v1/data/bist100/technical-ranking');
    return parseBist100TechnicalReport(response.data);
  },
};
