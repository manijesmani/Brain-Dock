import { BrainIcon } from "@phosphor-icons/react";
import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { useCurrentUser, useLogin } from "@/shared/api/queries";
import { useTheme } from "@/shared/hooks/useTheme";

export function LoginPage() {
  const navigate = useNavigate();
  const login = useLogin();
  const { data: user, isPending } = useCurrentUser();

  // Reading the theme here keeps the login screen on the same setting as the
  // rest of the app, even though it sits outside the shell.
  useTheme();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (!isPending && user) return <Navigate to={ROUTES.dashboard} replace />;

  const submit = async () => {
    setError(null);

    try {
      await login.mutateAsync({ username, password });
      void navigate(ROUTES.dashboard, { replace: true });
    } catch (caught) {
      const status = (caught as { response?: { status?: number } }).response?.status;
      setError(
        status === 429
          ? "تعداد تلاش‌ها زیاد بود. کمی بعد دوباره امتحان کن."
          : "نام کاربری یا رمز عبور درست نیست.",
      );
    }
  };

  return (
    <div
      dir="rtl"
      className="flex min-h-screen flex-1 flex-col items-center justify-center gap-[26px] bg-bd-bg p-10 text-bd-text"
    >
      <div className="flex flex-col items-center gap-3">
        <div className="grid size-[46px] place-items-center rounded-[13px] bg-bd-accent text-bd-accent-ink">
          <BrainIcon size={26} />
        </div>
        <span className="font-wordmark text-[22px] font-bold tracking-tight">BrainDock</span>
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
        className="flex w-[360px] flex-col gap-3.5 rounded-dialog border border-bd-border bg-bd-surface p-6 shadow-bd-lg"
      >
        <div className="flex flex-col gap-[7px]">
          <label htmlFor="username" className="text-[12.5px] text-bd-text-2">
            نام کاربری
          </label>
          <input
            id="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="mani"
            autoComplete="username"
            className="h-10 rounded-button border border-bd-border-2 bg-bd-bg px-3 text-[13.5px] text-bd-text outline-none focus:border-bd-accent"
          />
        </div>

        <div className="flex flex-col gap-[7px]">
          <label htmlFor="password" className="text-[12.5px] text-bd-text-2">
            رمز عبور
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
            className="h-10 rounded-button border border-bd-border-2 bg-bd-bg px-3 text-[13.5px] text-bd-text outline-none focus:border-bd-accent"
          />
        </div>

        {error ? <div className="text-[12.5px] text-bd-danger">{error}</div> : null}

        <button
          type="submit"
          disabled={login.isPending}
          className="mt-1 h-[42px] cursor-pointer rounded-button border-0 bg-bd-accent text-[14px] font-semibold text-bd-accent-ink hover:bg-bd-accent-hover disabled:opacity-60"
        >
          ورود
        </button>
      </form>
    </div>
  );
}
