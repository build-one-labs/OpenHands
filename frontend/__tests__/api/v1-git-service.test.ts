import { test, expect, vi } from "vitest";
import axios from "axios";
import V1GitService from "../../src/api/git-service/v1-git-service.api";

vi.mock("axios");

test("getGitChanges throws when response is not an array (dead runtime returns HTML)", async () => {
  const htmlResponse = "<!DOCTYPE html><html>...</html>";
  vi.mocked(axios.get).mockResolvedValue({ data: htmlResponse });

  await expect(
    V1GitService.getGitChanges(
      "http://localhost:3000/api/conversations/123",
      "test-api-key",
      "/workspace",
    ),
  ).rejects.toThrow("Invalid response from runtime");
});

// The repo/file path is sent as a trailing path SEGMENT (not a ?path= query)
// so the request misses the exact V0 `/git/changes` route and falls through to
// the http proxy, which converts it to the ?path= query agent-server v1.21 wants.
test("getGitChanges sends the repo path as a trailing path segment (bypasses V0 route)", async () => {
  vi.mocked(axios.get).mockResolvedValue({ data: [] });

  await V1GitService.getGitChanges(
    "http://localhost:3000/api/conversations/123",
    "test-api-key",
    "/workspace/project",
  );

  expect(axios.get).toHaveBeenCalledWith(
    "http://localhost:3000/api/conversations/123/git/changes/%2Fworkspace%2Fproject",
    expect.anything(),
  );
});

test("getGitChangeDiff sends the file path as a trailing path segment (bypasses V0 route)", async () => {
  vi.mocked(axios.get).mockResolvedValue({
    data: { modified: "", original: "" },
  });

  await V1GitService.getGitChangeDiff(
    "http://localhost:3000/api/conversations/123",
    "test-api-key",
    "/workspace/project/src/main.py",
  );

  expect(axios.get).toHaveBeenCalledWith(
    "http://localhost:3000/api/conversations/123/git/diff/%2Fworkspace%2Fproject%2Fsrc%2Fmain.py",
    expect.anything(),
  );
});
