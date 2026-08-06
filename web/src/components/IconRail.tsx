import { Box, FolderSearch, ListTree, PanelRight, Play, Square } from "lucide-react";
import type { EditorState } from "../store/editorStore";

function RailButton({
  label,
  active,
  onClick,
  children,
}: {
  label: string;
  active?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button className={`icon-button ${active ? "active" : ""}`} onClick={onClick} aria-label={label} title={label}>
      {children}
      <span className="tooltip" role="tooltip">{label}</span>
    </button>
  );
}

export function IconRail({
  panel,
  playing,
  onPanel,
  onToggleInspector,
  onPlay,
}: {
  panel: EditorState["leftPanel"];
  playing: boolean;
  onPanel: (panel: EditorState["leftPanel"]) => void;
  onToggleInspector: () => void;
  onPlay: () => void;
}) {
  return (
    <>
      <div className="rail-logo" title="sceneify" aria-label="sceneify">
        <img src="/logo.svg" alt="" width={36} height={36} draggable={false} />
      </div>
      <RailButton label="Hierarchy" active={panel === "outliner"} onClick={() => onPanel("outliner")}><ListTree /></RailButton>
      <RailButton label="Create" active={panel === "create"} onClick={() => onPanel("create")}><Box /></RailButton>
      <RailButton label="Assets" active={panel === "assets"} onClick={() => onPanel("assets")}><FolderSearch /></RailButton>
      <div className="rail-spacer" />
      <RailButton label="Toggle inspector" onClick={onToggleInspector}><PanelRight /></RailButton>
      <RailButton label={playing ? "Stop game" : "Play game"} active={playing} onClick={onPlay}>
        {playing ? <Square /> : <Play />}
      </RailButton>
    </>
  );
}
