import type { EditableNode, ScenePayload } from "../types/scene";

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
  onSelect,
  onChangeNode,
  onSave,
  savePath,
  onSavePathChange,
}: {
  scene: ScenePayload;
  selectedId: string | null;
  editMode: boolean;
  onSelect: (id: string | null) => void;
  onChangeNode: (id: string, patch: { position?: number[]; rotation?: number[]; scale?: number[] }) => void;
  onSave: () => void;
  savePath: string;
  onSavePathChange: (value: string) => void;
}) {
  const node = findNode(scene, selectedId);
  const entries = [
    ...scene.meshes.map((m) => ({ id: m.id, kind: "mesh" })),
    ...scene.objects.map((o) => ({ id: o.id, kind: "object" })),
    ...scene.annotations.map((a) => ({ id: a.id, kind: "annotation" })),
  ];

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
        <h2>Objects</h2>
        <ul className="node-list">
          {entries.map((entry) => (
            <li key={entry.id}>
              <button
                type="button"
                className={selectedId === entry.id ? "node active" : "node"}
                onClick={() => onSelect(entry.id)}
              >
                <span>{entry.id}</span>
                <em>{entry.kind}</em>
              </button>
            </li>
          ))}
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
