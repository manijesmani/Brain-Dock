/**
 * Temporary stand-in for the screens built in phase 5 from the design
 * reference. It exists so routing can be wired up and verified now.
 */
export function PlaceholderPage({ title }: { title: string }) {
  return (
    <main className="grid min-h-screen place-items-center p-8">
      <div className="text-center">
        <h1 className="text-2xl font-semibold text-bd-text">{title}</h1>
        <p className="mt-2 text-sm text-bd-text-3">این صفحه در فاز ۵ ساخته می‌شود.</p>
      </div>
    </main>
  );
}
