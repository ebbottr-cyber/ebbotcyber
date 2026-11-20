import { shouldForceTurkishUi } from './uiLanguage';

/**
 * Presentation-only bridge while existing multilingual legacy Vitest contracts
 * are migrated. Production is forcibly Turkish. No API or domain data changes.
 */
export function operatorText(legacyText: string, turkishText: string): string {
  return shouldForceTurkishUi() ? turkishText : legacyText;
}
