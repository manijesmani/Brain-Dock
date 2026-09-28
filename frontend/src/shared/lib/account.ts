const STORAGE_KEY = "braindock:account";

/**
 * Whether someone has signed into an account in this browser before.
 *
 * With no session the app starts a guest one, so it can be used without an
 * account. Someone whose session has only expired should be asked to sign in
 * again instead, not handed an empty guest account in place of their own.
 */
export function hasSignedInHere(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    // Private windows and blocked site data both throw.
    return false;
  }
}

export function rememberSignIn(): void {
  try {
    localStorage.setItem(STORAGE_KEY, "1");
  } catch {
    // Without it, an expired session opens as a guest; nothing is lost.
  }
}
