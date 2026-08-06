import { ChevronLeft, Cloud, MousePointer2, Play, Redo2, RefreshCw, RotateCw, Save, Scale3D, Undo2 } from "lucide-react";
import type { ConnectionState, TransformMode } from "../types/scene";

export function TopToolbar({
  sceneName,
  revision,
  connection,
  transformMode,
  busy,
  onTransformMode,
  onUndo,
  onRedo,
  onSave,
  onReload,
  onToggleLeft,
  onPlay,
}: {
  sceneName: string;
  revision?: number;
  connection: ConnectionState;
  transformMode: TransformMode;
  busy: boolean;
  onTransformMode: (mode: TransformMode) => void;
  onUndo: () => void;
  onRedo: () => void;
  onSave: () => void;
  onReload: () => void;
  onToggleLeft: () => void;
  onPlay: () => void;
}) {
  const tools: Array<[TransformMode, string, React.ReactNode]> = [
    ["translate", "Move (W)", <MousePointer2 key="move" />],
    ["rotate", "Rotate (E)", <RotateCw key="rotate" />],
    ["scale", "Scale (R)", <Scale3D key="scale" />],
  ];
  return (
    <>
      <button className="icon-button panel-toggle" onClick={onToggleLeft} title="Toggle scene panel" aria-label="Toggle scene panel"><ChevronLeft /></button>
      <div className="brand-mark" aria-hidden="true"><img src="/logo.svg" alt="" width={28} height={28} draggable={false} /></div>
      <div className="scene-title"><strong>{sceneName}</strong><span>Revision {revision ?? "legacy"}</span></div>
      <div className="toolbar-group" aria-label="Transform tools">
        {tools.map(([mode, label, icon]) => (
          <button key={mode} className={`icon-button ${transformMode === mode ? "active" : ""}`} onClick={() => onTransformMode(mode)} title={label} aria-label={label}>{icon}</button>
        ))}
      </div>
      <div className="toolbar-group">
        <button className="icon-button" disabled={busy} onClick={onUndo} title="Undo" aria-label="Undo"><Undo2 /></button>
        <button className="icon-button" disabled={busy} onClick={onRedo} title="Redo" aria-label="Redo"><Redo2 /></button>
      </div>
      <div className="toolbar-spacer" />
      <span className={`connection ${connection}`}><Cloud size={14} />{connection}</span>
      <button className="icon-button" disabled={busy} onClick={onReload} title="Reload scene" aria-label="Reload scene"><RefreshCw /></button>
      <button className="primary-button run-button" disabled={busy} onClick={onPlay}><Play size={16} />Run</button>
      <button className="primary-button" disabled={busy} onClick={onSave}><Save size={16} />Save</button>
    </>
  );
}
