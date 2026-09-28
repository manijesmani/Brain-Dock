import type { ReactNode } from "react";

/**
 * The column every screen with a page header sits in. The padding narrows
 * with the screen, and the bottom keeps clear of the capture button.
 *
 * It is also a size container, so what is inside can respond to the width it
 * is actually given rather than to the window: the idea table decides which
 * columns fit from its own width, whatever the sidebar beside it is doing.
 */
export function PageMain({ children }: { children: ReactNode }) {
  return (
    <main className="@container min-w-0 flex-1 px-4 pt-3 pb-[96px] sm:px-6 sm:pt-5 lg:px-[38px] lg:pt-[26px] lg:pb-[110px]">
      {children}
    </main>
  );
}
