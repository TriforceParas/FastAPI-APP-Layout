import { useEffect, useRef, useState } from "react";

type TurnstileApi = {
  render: (el: HTMLElement, options: Record<string, unknown>) => string;
  remove: (id: string) => void;
};
declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
let scriptPromise: Promise<void> | null = null;

function loadScript(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  scriptPromise ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      scriptPromise = null; // allow a retry
      reject(new Error("Could not load the verification widget."));
    };
    document.head.appendChild(script);
  });
  return scriptPromise;
}

/**
 * Cloudflare Turnstile widget. Calls `onToken` with a one-time token when the
 * challenge is solved, and with null when it expires or fails. Tokens are
 * single-use: change `resetKey` after every submit to get a fresh challenge.
 */
export function Turnstile({
  siteKey,
  action,
  onToken,
  resetKey = 0,
}: {
  siteKey: string;
  /** Which form this protects; the server rejects tokens issued for another action. */
  action: "login" | "setup" | "forgot";
  onToken: (token: string | null) => void;
  resetKey?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const callback = useRef(onToken);
  callback.current = onToken;
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    let widgetId: string | undefined;
    let cancelled = false;
    setFailed(null);
    loadScript()
      .then(() => {
        if (cancelled || !ref.current || !window.turnstile) return;
        widgetId = window.turnstile.render(ref.current, {
          sitekey: siteKey,
          action,
          size: "flexible", // stretch to the form width, like the inputs and button
          theme: document.documentElement.dataset.theme === "light" ? "light" : "dark",
          callback: (token: string) => callback.current(token),
          "expired-callback": () => callback.current(null),
          "error-callback": () => callback.current(null),
        });
      })
      .catch((err: Error) => !cancelled && setFailed(err.message));
    return () => {
      cancelled = true;
      if (widgetId) window.turnstile?.remove(widgetId);
      callback.current(null);
    };
  }, [siteKey, action, resetKey]);

  return (
    <div>
      <div ref={ref} className="min-h-[65px] w-full" data-testid="turnstile" />
      {failed && (
        <p role="alert" className="mt-1.5 text-[11px] text-rose-400">
          {failed} Check your connection and reload the page.
        </p>
      )}
    </div>
  );
}
