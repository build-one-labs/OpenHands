import { test, expect, vi, describe } from "vitest";
import type { QueryClient } from "@tanstack/react-query";
import { handleActionEventCacheInvalidation } from "#/utils/cache-utils";
import type { ActionEvent } from "#/types/v1/core/events/action-event";

const makeEvent = (kind: string, path?: string) =>
  ({ action: { kind, ...(path ? { path } : {}) } }) as unknown as ActionEvent;

const makeClient = () =>
  ({ invalidateQueries: vi.fn() }) as unknown as QueryClient;

describe("handleActionEventCacheInvalidation", () => {
  // agent-server >=1.21 renamed the bash action to "TerminalAction"; files
  // created via the shell must still invalidate the file_changes cache.
  test("invalidates file_changes for TerminalAction (SDK 1.21 bash)", () => {
    const queryClient = makeClient();
    handleActionEventCacheInvalidation(
      makeEvent("TerminalAction"),
      "conv-1",
      queryClient,
    );

    expect(queryClient.invalidateQueries).toHaveBeenCalledWith(
      { queryKey: ["file_changes", "conv-1"] },
      { cancelRefetch: false },
    );
  });

  test("invalidates file_changes for FileEditorAction", () => {
    const queryClient = makeClient();
    handleActionEventCacheInvalidation(
      makeEvent("FileEditorAction", "/workspace/project/a.txt"),
      "conv-1",
      queryClient,
    );

    expect(queryClient.invalidateQueries).toHaveBeenCalledWith(
      { queryKey: ["file_changes", "conv-1"] },
      { cancelRefetch: false },
    );
  });

  test("does not invalidate for unrelated actions", () => {
    const queryClient = makeClient();
    handleActionEventCacheInvalidation(
      makeEvent("BrowserNavigateAction"),
      "conv-1",
      queryClient,
    );

    expect(queryClient.invalidateQueries).not.toHaveBeenCalled();
  });
});
