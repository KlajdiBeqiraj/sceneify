import { BoxSelect, Copy, Trash2, X } from "lucide-react";
import type { EditableNode, GameplayRole, NodeFields, ScenePayload } from "../types/scene";
import type { NodePatch } from "../hooks/useScene";

export function findNode(scene: ScenePayload, id: string | null): EditableNode | null {
  if (!id) return null;
  return [...scene.meshes, ...scene.objects, ...(scene.primitives ?? []), ...scene.annotations].find((node) => node.id === id) ?? null;
}

function isGraphNode(node: EditableNode): boolean {
  return node.kind === "mesh" || node.kind === "object" || node.kind === "primitive";
}

function VectorInput({ label, values, onCommit }: { label: string; values: number[]; onCommit: (value: number[]) => void }) {
  return (
    <fieldset className="vector-field"><legend>{label}</legend>
      {["X", "Y", "Z"].map((axis, index) => (
        <label key={axis}><span>{axis}</span><input type="number" step="0.1" value={values[index] ?? 0} onChange={(event) => {
          const next = [...values];
          next[index] = Number(event.target.value);
          onCommit(next);
        }} /></label>
      ))}
    </fieldset>
  );
}

export function Inspector({
  scene,
  selectedId,
  onClose,
  onPatch,
  gameplayRole,
  onGameplayRole,
  onDuplicate,
  onDelete,
  onSavePrefab,
}: {
  scene: ScenePayload;
  selectedId: string | null;
  onClose: () => void;
  onPatch: (id: string, patch: NodePatch) => void;
  gameplayRole: GameplayRole;
  onGameplayRole: (id: string, role: GameplayRole) => void;
  onDuplicate: (id: string) => void;
  onDelete: (id: string) => void;
  onSavePrefab: (id: string) => void;
}) {
  const node = findNode(scene, selectedId);
  if (!node) return <div className="inspector-empty"><p>Select an entity to inspect it.</p></div>;
  const fields = node as EditableNode & NodeFields;
  const label = "label" in node ? node.label ?? node.id : node.id;
  const roles: GameplayRole[] = ["none", "player", "pickup", "hazard", "checkpoint", "goal"];
  return (
    <div className="inspector-content">
      <div className="inspector-header"><div><span>{node.kind}</span><h2>{label}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close inspector"><X /></button></div>
      <section>
        <h3>Entity</h3>
        <label className="form-field"><span>Name</span><input defaultValue={label} onBlur={(event) => onPatch(node.id, { label: event.target.value })} /></label>
        {"visible" in node && <label className="toggle"><input type="checkbox" checked={node.visible} onChange={(event) => onPatch(node.id, { visible: event.target.checked })} /><span>Visible</span></label>}
      </section>
      {"position" in node && <section><h3>Transform</h3>
        <VectorInput label="Position" values={node.position} onCommit={(position) => onPatch(node.id, { position })} />
        {"rotation" in node && <VectorInput label="Rotation" values={node.rotation} onCommit={(rotation) => onPatch(node.id, { rotation })} />}
        {"scale" in node && <VectorInput label="Scale" values={node.scale} onCommit={(scale) => onPatch(node.id, { scale })} />}
      </section>}
      <section><h3>Material</h3>
        <label className="form-field inline"><span>Color</span><input type="color" value={fields.material?.color ?? "#8aa7ff"} onChange={(event) => onPatch(node.id, { material: { ...fields.material, color: event.target.value } })} /></label>
        <label className="toggle"><input type="checkbox" checked={fields.material?.wireframe ?? false} onChange={(event) => onPatch(node.id, { material: { ...fields.material, wireframe: event.target.checked } })} /><span>Wireframe</span></label>
        <label className="form-field"><span>Opacity</span><input type="range" min="0" max="1" step="0.05" value={fields.material?.opacity ?? 1} onChange={(event) => onPatch(node.id, { material: { ...fields.material, opacity: Number(event.target.value) } })} /></label>
        <label className="form-field"><span>Roughness</span><input type="range" min="0" max="1" step="0.05" value={fields.material?.roughness ?? 0.65} onChange={(event) => onPatch(node.id, { material: { ...fields.material, roughness: Number(event.target.value) } })} /></label>
      </section>
      <section><h3>Physics and gameplay</h3>
        <label className="form-field"><span>Body</span><select value={fields.physics?.body ?? "fixed"} onChange={(event) => onPatch(node.id, { physics: { ...fields.physics, body: event.target.value as "fixed" | "dynamic" | "kinematic" } })}><option value="fixed">Fixed</option><option value="dynamic">Dynamic</option><option value="kinematic">Kinematic</option></select></label>
        <label className="form-field"><span>Collider</span><select value={fields.physics?.collider ?? "cuboid"} onChange={(event) => onPatch(node.id, { physics: { ...fields.physics, collider: event.target.value as "cuboid" | "ball" | "capsule" | "hull" } })}><option value="cuboid">Cuboid</option><option value="ball">Ball</option><option value="capsule">Capsule</option><option value="hull">Hull</option></select></label>
        <label className="toggle"><input type="checkbox" checked={fields.physics?.sensor ?? false} onChange={(event) => onPatch(node.id, { physics: { ...fields.physics, sensor: event.target.checked } })} /><span>Sensor</span></label>
        <label className="form-field"><span>Gameplay role</span><select value={gameplayRole} onChange={(event) => onGameplayRole(node.id, event.target.value as GameplayRole)}>{roles.map((role) => <option key={role}>{role}</option>)}</select></label>
        <label className="form-field"><span>Tags</span><input value={fields.tags?.join(", ") ?? ""} onChange={(event) => onPatch(node.id, { tags: event.target.value.split(",").map((tag) => tag.trim()).filter(Boolean) })} /></label>
      </section>
      <div className="danger-actions">
        {isGraphNode(node) && (
          <button onClick={() => onSavePrefab(node.id)} title="Save selection subtree as prefab">
            <BoxSelect size={15} />Save prefab
          </button>
        )}
        <button onClick={() => onDuplicate(node.id)}><Copy size={15} />Duplicate</button>
        <button className="danger" onClick={() => onDelete(node.id)}><Trash2 size={15} />Delete</button>
      </div>
    </div>
  );
}
