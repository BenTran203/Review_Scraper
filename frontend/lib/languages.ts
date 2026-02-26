/**
 * Supported output languages for AI analysis.
 * Extensible: add entries here to support more languages.
 */

export interface Language {
  code: string;
  label: string;
  flag: string;
}

export const SUPPORTED_LANGUAGES: Language[] = [
  { code: "en", label: "English", flag: "🇺🇸" },
  { code: "vi", label: "Tiếng Việt", flag: "🇻🇳" },
  { code: "es", label: "Español", flag: "🇪🇸" },
  { code: "ja", label: "日本語", flag: "🇯🇵" },
];

export const DEFAULT_LANGUAGE = "en";
