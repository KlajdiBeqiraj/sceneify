import type { ReactNode } from "react";

export function AppShell({
  toolbar,
  rail,
  left,
  viewport,
  inspector,
  status,
  leftOpen,
  inspectorOpen,
  playing,
  embed = false,
}: {
  toolbar: ReactNode;
  rail: ReactNode;
  left: ReactNode;
  viewport: ReactNode;
  inspector: ReactNode;
  status: ReactNode;
  leftOpen: boolean;
  inspectorOpen: boolean;
  playing: boolean;
  embed?: boolean;
}) {
  if (playing || embed) {
    return <main className="run-shell">{viewport}</main>;
  }

  return (
    <div
      className={`app-shell ${leftOpen ? "left-open" : ""} ${inspectorOpen ? "inspector-open" : ""}`}
    >
      <header className="top-toolbar">{toolbar}</header>
      <nav className="icon-rail" aria-label="Workspace tools">{rail}</nav>
      <aside className="left-panel" aria-label="Scene tools">{left}</aside>
      <main className="viewport">{viewport}</main>
      <aside className="inspector-panel" aria-label="Inspector">{inspector}</aside>
      <footer className="status-bar">{status}</footer>
    </div>
  );
}
