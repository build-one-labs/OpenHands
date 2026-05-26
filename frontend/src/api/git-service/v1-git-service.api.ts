import axios from "axios";
import { buildSessionHeaders } from "#/utils/utils";
import { mapV1ToV0Status } from "#/utils/git-status-mapper";
import type {
  GitChange,
  GitChangeDiff,
  V1GitChangeStatus,
} from "../open-hands.types";

interface V1GitChange {
  status: V1GitChangeStatus;
  path: string;
}

class V1GitService {
  /**
   * Get git changes for a V1 conversation
   * Routes through the HTTP proxy: GET /api/conversations/{id}/git/changes/{path}
   *
   * The repo path is sent as a trailing path SEGMENT on purpose: the legacy V0
   * route is the exact path `/api/conversations/{id}/git/changes`, registered
   * before the proxy catch-all, so a query-param form (`?path=`) would be
   * intercepted by the V0 handler (which has no runtime for V1 conversations
   * and 404s). The extra segment misses the V0 route and falls through to the
   * http proxy, which translates it to the `?path=` query that agent-server
   * v1.21 expects.
   * Maps V1 status types (ADDED, DELETED, etc.) to V0 format (A, D, etc.)
   */
  static async getGitChanges(
    conversationUrl: string | null | undefined,
    sessionApiKey: string | null | undefined,
    path: string,
  ): Promise<GitChange[]> {
    const encodedPath = encodeURIComponent(path);
    const url = `${conversationUrl}/git/changes/${encodedPath}`;
    const headers = buildSessionHeaders(sessionApiKey);

    // V1 API returns V1GitChangeStatus types, we need to map them to V0 format
    const { data } = await axios.get<V1GitChange[]>(url, { headers });

    // Validate response is an array (could be HTML error page if runtime is dead)
    if (!Array.isArray(data)) {
      throw new Error(
        "Invalid response from runtime - runtime may be unavailable",
      );
    }

    // Map V1 statuses to V0 format for compatibility
    return data.map((change) => ({
      status: mapV1ToV0Status(change.status),
      path: change.path,
    }));
  }

  /**
   * Get git change diff for a specific file in a V1 conversation
   * Routes through the HTTP proxy: GET /api/conversations/{id}/git/diff/{path}
   * (sent as a path segment to bypass the V0 route; the proxy translates it to
   * the `?path=` query that agent-server v1.21 expects — see getGitChanges)
   */
  static async getGitChangeDiff(
    conversationUrl: string | null | undefined,
    sessionApiKey: string | null | undefined,
    path: string,
  ): Promise<GitChangeDiff> {
    const encodedPath = encodeURIComponent(path);
    const url = `${conversationUrl}/git/diff/${encodedPath}`;
    const headers = buildSessionHeaders(sessionApiKey);

    const { data } = await axios.get<GitChangeDiff>(url, { headers });
    return data;
  }
}

export default V1GitService;
