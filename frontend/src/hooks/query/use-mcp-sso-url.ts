import { useQuery } from "@tanstack/react-query";

import AuthService from "#/api/auth-service/auth-service.api";

const MCP_SSO_PATH = "/service/swat/mcp/sso";

/**
 * Builds the authenticated entry URL for the served-app preview iframe.
 *
 * The embedded app lives on a different origin, so OpenHands' session cookie
 * never reaches it. The app's only supported login is its MCP SSO hop:
 *   `<origin>/service/swat/mcp/sso?code=<handoff>&to=<destination>`
 * where `<handoff>` is a fresh single-use code (~60s TTL) minted by an
 * authenticated caller. OpenHands holds the user's session, so it mints the
 * code via the `/api/auth/handoff/issue` proxy; the SSO hop then redeems the
 * code for a session cookie on the app's origin and 302s to `to` — so the
 * iframe lands on the destination already authenticated.
 *
 * `refreshKey` is part of the query key so every manual iframe refresh mints a
 * new code (the previous one is single-use and short-lived).
 *
 * Returns `undefined` while the code is being minted (caller can hold off
 * rendering the iframe to avoid an unauthenticated flash), and falls back to
 * `destinationUrl` when no code can be minted — Better Auth not configured,
 * unauthenticated, or the issue endpoint errored — so the app still loads and
 * can run its own login.
 */
export const useMcpSsoUrl = (
  destinationUrl: string | null,
  refreshKey: number,
): string | undefined => {
  const { data } = useQuery({
    queryKey: ["mcp-sso-url", destinationUrl, refreshKey],
    queryFn: async () => {
      if (!destinationUrl) return null;

      let destination: URL;
      try {
        destination = new URL(destinationUrl);
      } catch {
        return destinationUrl;
      }

      try {
        const code = await AuthService.issueHandoffCode();
        if (!code) return destinationUrl;

        const to = `${destination.pathname}${destination.search}`;
        const sso = new URL(MCP_SSO_PATH, destination.origin);
        sso.searchParams.set("code", code);
        sso.searchParams.set("to", to);
        return sso.toString();
      } catch {
        // Not authenticated / not configured / network error — load the app
        // directly and let it handle its own auth.
        return destinationUrl;
      }
    },
    enabled: Boolean(destinationUrl),
    // Codes are single-use with a ~60s TTL — never reuse a cached one.
    staleTime: 0,
    gcTime: 0,
    refetchOnWindowFocus: false,
    retry: false,
    meta: { disableToast: true },
  });

  return data ?? undefined;
};
