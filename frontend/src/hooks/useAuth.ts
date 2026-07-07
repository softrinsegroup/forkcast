import { useEffect, useState } from "react";
import { getMe, UnauthorizedError } from "@/lib/api";
import type { User } from "@/lib/types";

type AuthState =
  | { status: "loading" }
  | { status: "authed"; user: User }
  | { status: "anon" }
  | { status: "error"; message: string };

export function useAuth(): AuthState {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    let active = true;
    getMe()
      .then((user) => active && setState({ status: "authed", user }))
      .catch((err) => {
        if (!active) return;
        if (err instanceof UnauthorizedError) setState({ status: "anon" });
        else setState({ status: "error", message: String(err) });
      });
    return () => {
      active = false;
    };
  }, []);

  return state;
}
