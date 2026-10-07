// Restore the palette before the first paint. A separate script also works
// with the production Content Security Policy, which disallows inline scripts.
try {
  document.documentElement.classList.toggle(
    "bd-light",
    localStorage.getItem("braindock:theme") === "light",
  );
} catch {
  // New visits and unavailable browser storage both use dark.
}
