import { describe, it, expect } from "vitest";
import { extractBrowserUrl } from "#/utils/extract-browser-url";
import { BrowserObservation } from "#/types/v1/core/base/observation";

const makeObservation = (text: string): BrowserObservation => ({
  kind: "BrowserObservation",
  content: text ? [{ type: "text", text }] : [],
  is_error: false,
  screenshot_data: null,
});

describe("extractBrowserUrl", () => {
  it("extracts the url from browser_get_state JSON output", () => {
    const json = JSON.stringify({
      url: "https://example.com/page",
      title: "Example",
      tabs: [],
      interactive_elements: [],
    });

    expect(extractBrowserUrl(makeObservation(json))).toBe(
      "https://example.com/page",
    );
  });

  it("extracts the url from browser_get_content <url> block", () => {
    const text = `<url>\nhttps://example.com/article\n</url>\n<content>...</content>`;

    expect(extractBrowserUrl(makeObservation(text))).toBe(
      "https://example.com/article",
    );
  });

  it("returns null when there is no url in the content", () => {
    expect(extractBrowserUrl(makeObservation("Scrolled down"))).toBeNull();
  });

  it("returns null for empty content", () => {
    expect(extractBrowserUrl(makeObservation(""))).toBeNull();
  });

  it("ignores an empty url value in JSON", () => {
    const json = JSON.stringify({ url: "", title: "blank" });
    expect(extractBrowserUrl(makeObservation(json))).toBeNull();
  });
});
