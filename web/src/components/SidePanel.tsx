import type {
  EditableNode,
  ScenePayload,
  SnapSettings,
  TransformMode,
} from "../types/scene";

type OutlinerEntry = {
  id: string;
  kind: string;
  label?: string | null;
};

function findNode(scene: ScenePayload, id: string | null): EditableNode | null {
  if (!id) {
    return null;
  }
  return (
    scene.meshes.find((m) => m.id === id) ||
    scene.objects.find((o) => o.id === id) ||
    scene.annotations.find((a) => a.id === id) ||
    null
  );
}

function VecFields({
  label,
  values,
  onChange,
}: {
  label: string;
  values: number[];
  onChange: (next: number[]) => void;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <div className="vec3">
        {(["x", "y", "z"] as const).map((axis, index) => (
          <input
            key={axis}
            type="number"
            step="0.01"
            value={Number(values[index] ?? 0)}
            onChange={(event) => {
              const next = [...values];
              next[index] = Number(event.target.value);
              onChange(next);
            }}
            aria-label={`${label} ${axis}`}
          />
        ))}
      </div>
    </label>
  );
}

export function SidePanel({
  scene,
  selectedId,
  editMode,
  transformMode,
  snap,
  canUndo,
  canRedo,
  busy,
  onSelect,
  onTransformModeChange,
  onSnapChange,
  onUndo,
  onRedo,
  onChangeNode,
  onSave,
  savePath,
  onSavePathChange,
}: {
  scene: ScenePayload;
  selectedId: string | null;
  editMode: boolean;
  transformMode: TransformMode;
  snap: SnapSettings;
  canUndo: boolean;
  canRedo: boolean;
  busy: boolean;
  onSelect: (id: string | null) => void;
  onTransformModeChange: (mode: TransformMode) => void;
  onSnapChange: (snap: SnapSettings) => void;
  onUndo: () => void;
  onRedo: () => void;
  onChangeNode: (id: string, patch: { position?: number[]; rotation?: number[]; scale?: number[] }) => void;
  onSave: () => void;
  savePath: string;
  onSavePathChange: (value: string) => void;
}) {
  const node = findNode(scene, selectedId);
  const entries: OutlinerEntry[] = [
    ...scene.meshes.map((item) => ({ id: item.id, kind: "mesh" })),
    ...scene.objects.map((item) => ({
      id: item.id,
      kind: "object",
      label: item.label,
    })),
    ...scene.annotations.map((item) => ({
      id: item.id,
      kind: "annotation",
      label: item.label,
    })),
    ...scene.trajectories.map((item) => ({
      id: item.id,
      kind: "trajectory",
    })),
  ];
  const entryById = new Map(entries.map((entry) => [entry.id, entry]));
  const objectById = new Map(scene.objects.map((item) => [item.id, item]));
  const childIds = new Set(scene.objects.flatMap((item) => item.children ?? []));
  const rootIds = entries
    .filter((entry) => !childIds.has(entry.id))
    .map((entry) => entry.id);
  const visibleRoots = rootIds.length > 0 ? rootIds : entries.map((entry) => entry.id);

  const renderEntry = (
    id: string,
    ancestors: ReadonlySet<string>,
  ): React.ReactNode => {
    const entry = entryById.get(id);
    const object = objectById.get(id);
    const circular = ancestors.has(id);
    const nextAncestors = new Set(ancestors).add(id);
    return (
      <li key={`${id}:${ancestors.size}`}>
        <button
          type="button"
          className={selectedId === id ? "node active" : "node"}
          onClick={() => entry && onSelect(id)}
          disabled={!entry}
        >
          <span>{entry?.label || id}</span>
          <em>{circular ? "cycle" : entry?.kind || "missing"}</em>
        </button>
        {object && !circular && (object.children?.length ?? 0) > 0 && (
          <ul className="node-list nested">
            {object.children?.map((childId) =>
              renderEntry(childId, nextAncestors),
            )}
          </ul>
        )}
      </li>
    );
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-block">
        <h2>Scene</h2>
        <p className="muted">{scene.name}</p>
        <label className="field">
          <span>Save path</span>
          <input value={savePath} onChange={(e) => onSavePathChange(e.target.value)} />
        </label>
        <button type="button" className="btn" onClick={onSave}>
          Save scene JSON
        </button>
      </div>

      <div className="sidebar-block">
        <h2>Tools</h2>
        <div className="tool-row" aria-label="Transform mode">
          {(["translate", "rotate", "scale"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              className={transformMode === mode ? "btn active" : "btn"}
              onClick={() => onTransformModeChange(mode)}
            >
              {mode[0].toUpperCase()}
              {mode.slice(1)}
            </button>
          ))}
        </div>
        <div className="tool-row">
          <button type="button" className="btn" disabled={!canUndo || busy} onClick={onUndo}>
            Undo
          </button>
          <button type="button" className="btn" disabled={!canRedo || busy} onClick={onRedo}>
            Redo
          </button>
        </div>
        <label className="field">
          <span>Move snap</span>
          <input
            type="number"
            min="0"
            step="0.05"
            value={snap.translation}
            onChange={(event) =>
              onSnapChange({
                ...snap,
                translation: Math.max(0, Number(event.target.value)),
              })
            }
          />
        </label>
        <label className="field">
          <span>Rotate snap in degrees</span>
          <input
            type="number"
            min="0"
            step="1"
            value={snap.rotationDegrees}
            onChange={(event) =>
              onSnapChange({
                ...snap,
                rotationDegrees: Math.max(0, Number(event.target.value)),
              })
            }
          />
        </label>
        <label className="field">
          <span>Scale snap</span>
          <input
            type="number"
            min="0"
            step="0.05"
            value={snap.scale}
            onChange={(event) =>
              onSnapChange({
                ...snap,
                scale: Math.max(0, Number(event.target.value)),
              })
            }
          />
        </label>
        <p className="muted">Set a snap value to 0 to disable it.</p>
      </div>

      <div className="sidebar-block">
        <h2>Hierarchy</h2>
        <ul className="node-list">
          {visibleRoots.map((id) => renderEntry(id, new Set()))}
        </ul>
      </div>

      {node && (
        <div className="sidebar-block">
          <h2>Inspector</h2>
          <p className="muted">{node.id}</p>
          {!editMode && <p className="muted">Enable Edit to transform.</p>}
          {"position" in node && (
            <VecFields
              label="Position"
              values={node.position}
              onChange={(position) => onChangeNode(node.id, { position })}
            />
          )}
          {"rotation" in node && (
            <VecFields
              label="Rotation"
              values={node.rotation}
              onChange={(rotation) => onChangeNode(node.id, { rotation })}
            />
          )}
          {"scale" in node && (
            <VecFields
              label="Scale"
              values={node.scale}
              onChange={(scale) => onChangeNode(node.id, { scale })}
            />
          )}
        </div>
      )}
    </aside>
  );
}
