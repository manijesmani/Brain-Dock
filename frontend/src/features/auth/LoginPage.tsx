import { ArrowRightIcon, BrainIcon } from "@phosphor-icons/react";
import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { ROUTES } from "@/app/routes";
import { UpgradeButton } from "@/features/plans/UpgradeButton";
import { errorMessage, errorStatus } from "@/shared/api/errors";
import { useCurrentUser, useLogin, useSignup, useStartGuest } from "@/shared/api/queries";
import { useTheme } from "@/shared/hooks/useTheme";

const TOO_MANY = "تعداد تلاش‌ها زیاد بود. کمی بعد دوباره امتحان کن.";

/**
 * The one login page for every account (at /panel), and with `signup` the
 * place to make a regular account.
 *
 * Neither is needed to use the app: a first visit opens straight into a
 * guest account. A guest comes here to sign up and keep what it has written,
 * or to sign into an account it already has; someone with no session at all
 * can also carry on without one from here. Special accounts are not made
 * here -- only the owner makes those -- so sign-up offers a way to ask.
 */
export function LoginPage({ signup = false }: { signup?: boolean }) {
  const navigate = useNavigate();
  const login = useLogin();
  const register = useSignup();
  const startGuest = useStartGuest();
  const { data: user, isPending } = useCurrentUser();

  // Reading the theme here keeps the login screen on the same setting as the
  // rest of the app, even though it sits outside the shell.
  useTheme();

  const [firstName, setFirstName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  // An account has nothing to do here; a guest does.
  if (!isPending && user && user.plan !== "guest") {
    return <Navigate to={ROUTES.dashboard} replace />;
  }

  const guest = user?.plan === "guest";
  const busy = login.isPending || register.isPending || startGuest.isPending;

  const submit = async () => {
    setError(null);

    try {
      if (signup) await register.mutateAsync({ first_name: firstName, username, password });
      else await login.mutateAsync({ username, password });
      void navigate(ROUTES.dashboard, { replace: true });
    } catch (caught) {
      if (errorStatus(caught) === 429) setError(TOO_MANY);
      // Sign-up explains itself: a taken name, a weak password.
      else if (signup) setError(errorMessage(caught, "ساختن حساب ناموفق بود. دوباره امتحان کن."));
      else setError("نام کاربری یا رمز عبور درست نیست.");
    }
  };

  const continueWithoutAccount = async () => {
    setError(null);

    try {
      await startGuest.mutateAsync();
      void navigate(ROUTES.dashboard, { replace: true });
    } catch (caught) {
      setError(errorStatus(caught) === 429 ? TOO_MANY : "ادامه بدون حساب ناموفق بود.");
    }
  };

  return (
    <div
      dir="rtl"
      className="flex min-h-page flex-1 flex-col items-center justify-center gap-[26px] bg-bd-bg p-4 text-bd-text sm:p-10"
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
        className="flex w-full max-w-[360px] flex-col gap-3.5 rounded-dialog border border-bd-border bg-bd-surface p-5 shadow-bd-lg sm:p-6"
      >
        <div>
          <div className="text-[15px] font-semibold">{signup ? "ساخت حساب" : "ورود به حساب"}</div>
          {guest ? (
            <p className="m-0 mt-1.5 text-[12.5px] leading-[1.8] text-bd-text-2">
              {signup
                ? "ایده‌هایی که بدون حساب نوشته‌ای در حساب تازه می‌مانند."
                : user.idea_count > 0
                  ? "ایده‌هایی که بدون حساب نوشته‌ای به حسابی که واردش می‌شوی نمی‌روند. برای نگه داشتنشان، حساب تازه بساز."
                  : null}
            </p>
          ) : null}
        </div>

        {signup ? (
          <div className="flex flex-col gap-[7px]">
            <label htmlFor="first_name" className="text-[12.5px] text-bd-text-2">
              نام
            </label>
            <input
              id="first_name"
              value={firstName}
              onChange={(event) => setFirstName(event.target.value)}
              autoComplete="name"
              className="h-10 pointer-coarse:h-11 rounded-button border border-bd-border-2 bg-bd-bg px-3 text-[13.5px] text-bd-text outline-none focus:border-bd-accent"
            />
          </div>
        ) : null}

        <div className="flex flex-col gap-[7px]">
          <label htmlFor="username" className="text-[12.5px] text-bd-text-2">
            نام کاربری
          </label>
          <input
            id="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            dir="ltr"
            className="h-10 pointer-coarse:h-11 rounded-button border border-bd-border-2 bg-bd-bg px-3 text-[13.5px] text-bd-text outline-none focus:border-bd-accent"
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
            autoComplete={signup ? "new-password" : "current-password"}
            className="h-10 pointer-coarse:h-11 rounded-button border border-bd-border-2 bg-bd-bg px-3 text-[13.5px] text-bd-text outline-none focus:border-bd-accent"
          />
          {signup ? (
            <span className="text-[11.5px] text-bd-text-3">دست‌کم ۱۲ حرف، و نه فقط عدد</span>
          ) : null}
        </div>

        {error ? <div className="text-[12.5px] leading-[1.8] text-bd-danger">{error}</div> : null}

        <button
          type="submit"
          disabled={busy}
          className="mt-1 h-[42px] cursor-pointer rounded-button border-0 bg-bd-accent text-[14px] font-semibold text-bd-accent-ink hover:bg-bd-accent-hover disabled:opacity-60"
        >
          {signup ? "ساخت حساب" : "ورود"}
        </button>

        <div className="text-center text-[12.5px] text-bd-text-2">
          {signup ? "حساب داری؟ " : "حساب نداری؟ "}
          <Link
            to={signup ? ROUTES.login : ROUTES.signup}
            replace
            className="font-medium text-bd-accent no-underline hover:underline"
          >
            {signup ? "ورود" : "ساخت حساب"}
          </Link>
        </div>
      </form>

      {signup ? <UpgradeButton className="max-w-[360px]" /> : null}

      {guest ? (
        <Link
          to={ROUTES.dashboard}
          className="inline-flex items-center gap-1.5 text-[13px] text-bd-text-2 no-underline hover:text-bd-text"
        >
          <ArrowRightIcon size={15} />
          برگشت به BrainDock
        </Link>
      ) : !isPending && !user ? (
        <button
          type="button"
          onClick={() => void continueWithoutAccount()}
          disabled={busy}
          className="h-10 w-full max-w-[360px] cursor-pointer rounded-button border border-bd-border-2 bg-transparent text-[13px] text-bd-text hover:bg-bd-surface-2 disabled:opacity-60"
        >
          ادامه بدون حساب
        </button>
      ) : null}
    </div>
  );
}
