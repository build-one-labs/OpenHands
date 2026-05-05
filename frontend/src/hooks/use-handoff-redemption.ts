import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import AuthService from "#/api/auth-service/auth-service.api";

const HANDOFF_PARAM = "handoff_code";

// Module-level dedupe so React 19 StrictMode's double-effect doesn't redeem
// the same single-use code twice (the second call returns 410 and causes the
// redeem to look failed). Both mounts share the same in-flight Promise.
const inFlight = new Map<string, Promise<void>>();

/**
 * Detects ?handoff_code=<code> on initial page load, redeems it for a session
 * cookie at our origin, strips the param from the URL, and re-runs auth +
 * any errored queries so the layout re-evaluates with the new cookie.
 *
 * Returns { isRedeeming } — true until the redeem call settles AND any
 * 401-corpse queries have refetched. Callers should gate render so we don't
 * flash unauthenticated content (or worse, navigate away on stale errors)
 * before the cookie is established.
 *
 * In production the FastAPI middleware redeems before the SPA loads, so the
 * param is gone and this hook is a no-op. In dev (Vite serves the HTML) the
 * middleware never sees the request, so this hook is the redemption path.
 */
export const useHandoffRedemption = () => {
  const queryClient = useQueryClient();

  const [isRedeeming, setIsRedeeming] = useState(() => {
    if (typeof window === "undefined") return false;
    return new URLSearchParams(window.location.search).has(HANDOFF_PARAM);
  });

  useEffect(() => {
    if (!isRedeeming) return undefined;

    const code = new URLSearchParams(window.location.search).get(HANDOFF_PARAM);
    if (!code) {
      setIsRedeeming(false);
      return undefined;
    }

    const stripParam = () => {
      const p = new URLSearchParams(window.location.search);
      if (!p.has(HANDOFF_PARAM)) return;
      p.delete(HANDOFF_PARAM);
      const search = p.toString();
      const newUrl =
        window.location.pathname +
        (search ? `?${search}` : "") +
        window.location.hash;
      window.history.replaceState({}, "", newUrl);
    };

    let cancelled = false;

    // De-dupe across StrictMode double-mounts: both invocations await the
    // same single redeem network call.
    let promise = inFlight.get(code);
    if (!promise) {
      promise = (async () => {
        try {
          await AuthService.redeemHandoffCode(code);
        } catch {
          // Swallow — bad/expired/already-used codes fall through to sign-in.
        }
      })();
      inFlight.set(code, promise);
    }

    (async () => {
      await promise;
      if (cancelled) return;

      stripParam();

      // Refetch auth so isAuthed flips before any consumer reacts to it.
      await queryClient.refetchQueries({
        queryKey: ["user", "authenticated"],
      });

      // Any query that 401'd before the cookie landed is now stuck in error
      // state. Refetch them so consumers like conversation.tsx don't see a
      // stale "no data + authed" combo and bounce to /.
      await queryClient.refetchQueries({
        predicate: (query) => query.state.status === "error",
      });

      if (cancelled) return;
      setIsRedeeming(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [isRedeeming, queryClient]);

  return { isRedeeming };
};
