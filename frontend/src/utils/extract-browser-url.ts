import { BrowserObservation } from "#/types/v1/core/base/observation";

/**
 * Extract the current page URL from a BrowserObservation.
 *
 * The browser tools don't expose a dedicated URL field on the observation, but
 * the current URL is embedded in the text content depending on the tool:
 * - `browser_get_state` returns JSON with a top-level `"url"` field.
 * - `browser_get_content` wraps it in a `<url>...</url>` block.
 *
 * Returns the extracted URL, or `null` if none could be found.
 */
export function extractBrowserUrl(
  observation: BrowserObservation,
): string | null {
  const text = observation.content
    .filter((c) => c.type === "text")
    .map((c) => c.text)
    .join("\n");

  if (!text) {
    return null;
  }

  // browser_get_content format: <url>\n{url}\n</url>
  const urlTagMatch = text.match(/<url>\s*([\s\S]*?)\s*<\/url>/);
  if (urlTagMatch?.[1]?.trim()) {
    return urlTagMatch[1].trim();
  }

  // browser_get_state format: JSON object with a top-level "url" field
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed.url === "string" && parsed.url) {
      return parsed.url;
    }
  } catch {
    // Not JSON — fall through.
  }

  return null;
}
