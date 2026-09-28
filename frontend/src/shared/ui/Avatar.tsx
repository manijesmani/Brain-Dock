import { useState } from "react";

import type { CurrentUser } from "@/types/domain";

/**
 * The account's picture, or its initial on the accent tint when there is
 * none -- or when the picture cannot be loaded.
 *
 * `className` carries the size and, for the initial, the type size.
 */
export function Avatar({ user, className }: { user: CurrentUser; className: string }) {
  // Remembers which address failed, so a new picture gets its own chance.
  const [broken, setBroken] = useState<string | null>(null);

  if (user.avatar_url && broken !== user.avatar_url) {
    return (
      <img
        src={user.avatar_url}
        alt=""
        onError={() => setBroken(user.avatar_url)}
        className={`flex-none rounded-full object-cover ${className}`}
      />
    );
  }

  return (
    <span
      className={`grid flex-none place-items-center rounded-full bg-bd-accent-soft font-semibold text-bd-accent ${className}`}
    >
      {user.display_name.charAt(0)}
    </span>
  );
}
