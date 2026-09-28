import { CrownSimpleIcon, XIcon } from "@phosphor-icons/react";
import { useState } from "react";

import { errorMessage } from "@/shared/api/errors";
import { useChangeUserPlan, useCreateSpecialUser, usePanelUsers } from "@/shared/api/queries";
import { useToast } from "@/shared/hooks/useToast";
import { toPersianDigits } from "@/shared/lib/persian";
import { ConfirmDialog } from "@/shared/ui/ConfirmDialog";
import { Dialog } from "@/shared/ui/Dialog";
import type { PanelUser } from "@/types/domain";

/**
 * The owner's user panel: making special accounts, and turning a regular
 * account special or a special one regular again. Only ever rendered for the
 * owner, and the API refuses everyone else anyway. The owner's own account
 * is not listed, so its kind is never offered for change.
 */
export function UserPanelDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} width={580} scrollable label="پنل یوزر">
      <UserPanel onClose={onClose} />
    </Dialog>
  );
}

function UserPanel({ onClose }: { onClose: () => void }) {
  const { data, isPending } = usePanelUsers();
  const users = data?.results ?? [];
  const total = data?.pagination.count ?? 0;

  const change = useChangeUserPlan();
  const toast = useToast();
  const [changing, setChanging] = useState<PanelUser | null>(null);
  const [changeError, setChangeError] = useState<string | null>(null);
  const toPremium = changing?.plan !== "premium";

  const confirmChange = () => {
    if (!changing) return;
    const { id, display_name: name } = changing;
    setChangeError(null);
    change.mutate(
      { id, to: toPremium ? "premium" : "free" },
      {
        onSuccess: () => {
          setChanging(null);
          toast.show(`نقش «${name}» به ${toPremium ? "ویژه" : "عادی"} تغییر کرد`);
        },
        onError: (caught) =>
          setChangeError(errorMessage(caught, "تغییر نقش ناموفق بود. دوباره امتحان کن.")),
      },
    );
  };

  return (
    <div className="p-5 sm:p-6">
      <div className="mb-4 flex items-center gap-2">
        <h2 className="m-0 flex-1 text-[16px] font-semibold">پنل یوزر</h2>
        <button
          type="button"
          title="بستن"
          onClick={onClose}
          className="grid size-8 cursor-pointer place-items-center rounded-full border-0 bg-transparent text-bd-text-3 hover:bg-bd-surface-2 hover:text-bd-text"
        >
          <XIcon size={16} />
        </button>
      </div>

      <NewSpecialUser />

      <div className="mt-6 mb-2.5 flex items-center gap-2">
        <h3 className="m-0 text-[14px] font-semibold">کاربران</h3>
        <span className="text-[12px] text-bd-text-3">{toPersianDigits(total)}</span>
      </div>
      <div className="overflow-hidden rounded-[9px] border border-bd-border">
        {isPending ? (
          <div className="px-3.5 py-6 text-center text-[13px] text-bd-text-3">در حال بارگذاری…</div>
        ) : users.length === 0 ? (
          <div className="px-3.5 py-6 text-center text-[13px] text-bd-text-3">
            هنوز کسی حساب نساخته
          </div>
        ) : (
          users.map((user, index) => (
            <UserRow
              key={user.id}
              user={user}
              first={index === 0}
              onChange={() => {
                setChangeError(null);
                setChanging(user);
              }}
            />
          ))
        )}
      </div>
      {total > users.length ? (
        <div className="mt-2 text-[12px] text-bd-text-3">
          {toPersianDigits(users.length)} حساب تازه‌تر از {toPersianDigits(total)} حساب
        </div>
      ) : null}

      <ConfirmDialog
        open={changing !== null}
        title={
          toPremium ? "این کاربر به کاربر ویژه تبدیل شود؟" : "این کاربر به کاربر عادی تبدیل شود؟"
        }
        confirmLabel={toPremium ? "تبدیل به ویژه" : "تبدیل به عادی"}
        pending={change.isPending}
        error={changeError}
        onConfirm={confirmChange}
        onClose={() => {
          setChanging(null);
          setChangeError(null);
        }}
      >
        <span className="font-semibold text-bd-text">
          {changing?.display_name}{" "}
          <span dir="ltr" className="font-normal text-bd-text-3">
            @{changing?.username}
          </span>
        </span>
        <span className="mt-1 block">
          {toPremium
            ? "بدون محدودیت ایده می‌سازد و می‌تواند عکس و صدا اضافه کند."
            : "همهٔ ایده‌هایش می‌ماند، اما محدودیت‌های حساب عادی دوباره برایش اعمال می‌شود: تعداد ایده محدود، و بدون عکس و صدا."}
        </span>
      </ConfirmDialog>
    </div>
  );
}

/** The form for a new special account: name, username and password. */
function NewSpecialUser() {
  const create = useCreateSpecialUser();
  const toast = useToast();
  const [firstName, setFirstName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setError(null);

    try {
      const user = await create.mutateAsync({ first_name: firstName, username, password });
      toast.show(`«${user.display_name}» به‌عنوان کاربر ویژه ساخته شد`);
      setFirstName("");
      setUsername("");
      setPassword("");
    } catch (caught) {
      setError(errorMessage(caught, "ساختن کاربر ناموفق بود. دوباره امتحان کن."));
    }
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
      className="rounded-card border border-bd-border bg-bd-surface-2 p-4"
    >
      <div className="mb-3 flex items-center gap-2">
        <CrownSimpleIcon size={15} weight="fill" className="flex-none text-bd-warn" />
        <h3 className="m-0 text-[14px] font-semibold">ساخت کاربر ویژه</h3>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Field id="panel-first-name" label="نام" value={firstName} onChange={setFirstName} />
        <Field id="panel-username" label="نام کاربری" value={username} onChange={setUsername} ltr />
        {/* new-password, so the browser offers a fresh one rather than
            filling in the owner's own. */}
        <Field
          id="panel-password"
          label="رمز عبور"
          value={password}
          onChange={setPassword}
          type="password"
          autoComplete="new-password"
          ltr
        />
      </div>
      <div className="mt-1.5 text-[11.5px] text-bd-text-3">رمز دست‌کم ۱۲ حرف، و نه فقط عدد</div>

      {error ? (
        <div className="mt-2.5 text-[12.5px] leading-[1.8] text-bd-danger">{error}</div>
      ) : null}

      <button
        type="submit"
        disabled={create.isPending}
        className="mt-3.5 h-[38px] cursor-pointer rounded-button border-0 bg-bd-accent px-[15px] text-[13px] font-medium text-bd-accent-ink hover:bg-bd-accent-hover disabled:opacity-60"
      >
        ساخت کاربر ویژه
      </button>
    </form>
  );
}

function Field({
  id,
  label,
  value,
  onChange,
  type = "text",
  autoComplete = "off",
  ltr = false,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  autoComplete?: string;
  ltr?: boolean;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-[7px]">
      <label htmlFor={id} className="text-[12.5px] text-bd-text-2">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
        dir={ltr ? "ltr" : undefined}
        className="h-10 min-w-0 rounded-button border pointer-coarse:h-11 border-bd-border-2 bg-bd-bg px-3 text-[13.5px] text-bd-text outline-none focus:border-bd-accent"
      />
    </div>
  );
}

/** One account, with its kind and the button that changes it either way. */
function UserRow({
  user,
  first,
  onChange,
}: {
  user: PanelUser;
  first: boolean;
  onChange: () => void;
}) {
  const special = user.plan === "premium";

  return (
    <div
      className="flex items-center gap-3 px-3.5 py-[11px]"
      style={{ borderTop: first ? "0" : "1px solid var(--color-bd-border)" }}
    >
      <span className="grid size-8 flex-none place-items-center rounded-full bg-bd-accent-soft text-[13px] font-semibold text-bd-accent">
        {user.display_name.charAt(0)}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block overflow-hidden text-[13.5px] font-medium text-ellipsis whitespace-nowrap">
          {user.display_name}
        </span>
        <span
          dir="ltr"
          className="block overflow-hidden text-right text-[11.5px] text-ellipsis whitespace-nowrap text-bd-text-3"
        >
          @{user.username}
        </span>
      </span>
      <span className="hidden flex-none text-[12px] text-bd-text-3 sm:inline">
        {toPersianDigits(user.idea_count)} ایده
      </span>

      {special ? (
        <span
          className="inline-flex flex-none items-center gap-1 rounded-full px-2 py-0.5 text-[11.5px] font-semibold"
          style={{ background: "var(--color-bd-warn-bg)", color: "var(--color-bd-warn)" }}
        >
          <CrownSimpleIcon size={11} weight="fill" />
          ویژه
        </span>
      ) : (
        <span className="flex-none rounded-full bg-bd-surface-3 px-2 py-0.5 text-[11.5px] font-semibold text-bd-text-2">
          عادی
        </span>
      )}
      <button
        type="button"
        onClick={onChange}
        className="h-8 flex-none cursor-pointer rounded-button border border-bd-border-2 bg-transparent px-3 text-[12.5px] text-bd-text hover:border-bd-accent hover:text-bd-accent pointer-coarse:h-9"
      >
        {special ? "تبدیل به عادی" : "تبدیل به ویژه"}
      </button>
    </div>
  );
}
