/**
 * Page footer.
 *
 * Server component — no interactivity, no JavaScript shipped.
 */

export function Footer() {
  return (
    <footer className="border-t border-hairline bg-surface/40">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center justify-between gap-4 px-6 text-sm text-fg-muted sm:px-8 lg:px-12">
        <p>SEC Semantic Search</p>
        <p className="text-fg-subtle">Built by Eren Yanic</p>
      </div>
    </footer>
  );
}
