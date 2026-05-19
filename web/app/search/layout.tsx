// Search results vary per query and have no editorial content — every
// result is a thin redirect to the indexed page. Noindex via a layout
// because the page itself is a client component and can't export
// metadata directly.
export const metadata = {
  title: "Search",
  robots: { index: false, follow: true },
};

export default function SearchLayout({ children }: { children: React.ReactNode }) {
  return children;
}
