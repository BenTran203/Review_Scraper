/**
 * URL validation and platform detection for supported e-commerce sites.
 */

interface PlatformPattern {
  name: string;
  patterns: RegExp[];
}

const PLATFORMS: PlatformPattern[] = [
  {
    name: "Amazon",
    patterns: [
      /amazon\.(com|co\.uk|de|fr|co\.jp|in|com\.au|ca|com\.br)/i,
    ],
  },
  {
    name: "Shopee",
    patterns: [
      /shopee\.(vn|co\.id|com\.my|com\.ph|co\.th|sg|com\.br|tw)/i,
    ],
  },
  {
    name: "eBay",
    patterns: [/ebay\.(com|co\.uk|de|fr|com\.au|ca)/i],
  },
  {
    name: "Lazada",
    patterns: [
      /lazada\.(vn|co\.id|com\.my|com\.ph|co\.th|sg)/i,
    ],
  },
  {
    name: "Tiki",
    patterns: [/tiki\.vn/i],
  },
];

/**
 * Detect the platform from a URL string.
 * Returns the platform display name, or null if unsupported.
 */
export function detectPlatform(url: string): string | null {
  if (!url) return null;

  for (const platform of PLATFORMS) {
    for (const pattern of platform.patterns) {
      if (pattern.test(url)) {
        return platform.name;
      }
    }
  }

  return null;
}

/**
 * Check whether a URL belongs to a supported platform.
 */
export function isSupportedUrl(url: string): boolean {
  return detectPlatform(url) !== null;
}
