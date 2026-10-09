export type UserRole = "admin" | "consejo" | "muestra_insta";

export interface SessionUser {
  id: string;
  email: string;
  name: string | null;
  role: UserRole;
}

const TOKEN_KEY = "conversa_token";
const USER_KEY = "conversa_user";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getSessionUser(): SessionUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionUser;
  } catch {
    return null;
  }
}

export function saveSession(token: string, user: SessionUser) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Administración",
  consejo: "Consejo",
  muestra_insta: "Muestra Instagram",
};
