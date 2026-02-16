import { api } from "./api";
import { useAppStore } from "../store";
import type { Token } from "../types";

export async function login(email: string, password: string) {
  const token = await api.login(email, password);
  api.setToken(token.access_token);

  const user = await api.getMe();
  useAppStore.getState().setAuth(user, token);

  return { user, token };
}

export async function logout() {
  api.setToken(null);
  useAppStore.getState().logout();
}

export async function refreshAuth(): Promise<Token | null> {
  const store = useAppStore.getState();
  if (!store.token?.refresh_token) return null;

  try {
    const token = await api.refreshToken(store.token.refresh_token);
    api.setToken(token.access_token);

    const user = await api.getMe();
    store.setAuth(user, token);
    return token;
  } catch {
    store.logout();
    return null;
  }
}

export function initAuth() {
  const store = useAppStore.getState();
  if (store.token?.access_token) {
    api.setToken(store.token.access_token);
  }
}
