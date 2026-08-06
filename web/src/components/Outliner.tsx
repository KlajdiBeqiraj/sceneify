import { Box, BoxIcon, ChevronRight, Circle, Eye, EyeOff, Layers3 } from "lucide-react";
import { canReparent } from "../store/editorStore";
import type { EditableNode, ScenePayload } from "../types/scene";

export function getOutlinerNodes(scene: ScenePayload): EditableNode[] {
  return [...scene.objects, ...scene.meshes, ...(scene.primitives ?? []), ...scene.annotations];
}

export function Outliner({
  scene,
  selectedId,
  onSelect,
  onReparent,
  onVisibility,
}: {
  scene: ScenePayload;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onReparent: (id: string, parentId: string | null) => void;
  onVisibility: (id: string, visible: boolean) => void;
}) {
  const nodes = getOutlinerNodes(scene);
  const childIds = new Set<string>();
  scene.objects.forEach((object) => object.children?.forEach((id) => childIds.add(id)));
  nodes.forEach((node) => "parentId" in node && node.parentId && childIds.add(node.id));
  const roots = nodes.filter((node) => !childIds.has(node.id));
  const childrenOf = (id: string) => nodes.filter((node) =>
    ("parentId" in node && node.parentId === id) || Boolean(scene.objects.find((object) => object.id === id)?.children?.includes(node.id)),
  );

  const renderNode = (node: EditableNode, ancestors: Set<string>): React.ReactNode => {
    if (ancestors.has(node.id)) return null;
    const children = childrenOf(node.id);
    const next = new Set(ancestors).add(node.id);
    const label = "label" in node && node.label ? node.label : node.id;
    const visible = "visible" in node ? node.visible : true;
    const Icon = node.kind === "object" ? Layers3 : node.kind === "primitive" ? BoxIcon : node.kind === "annotation" ? Circle : Box;
    return (
      <li key={node.id}>
        <div
          className={`outliner-row ${selectedId === node.id ? "selected" : ""}`}
          draggable
          onDragStart={(event) => event.dataTransfer.setData("text/scene-node", node.id)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            const source = event.dataTransfer.getData("text/scene-node");
            if (source && canReparent(scene, source, node.id)) onReparent(source, node.id);
          }}
        >
          <button className="node-main" onClick={() => onSelect(node.id)}>
            <ChevronRight size={13} className={children.length ? "" : "invisible"} />
            <Icon size={15} />
            <span>{label}</span>
          </button>
          <button className="visibility-button" aria-label={`${visible ? "Hide" : "Show"} ${label}`} onClick={() => onVisibility(node.id, !visible)}>
            {visible ? <Eye size={14} /> : <EyeOff size={14} />}
          </button>
        </div>
        {children.length > 0 && <ul className="outliner-children">{children.map((child) => renderNode(child, next))}</ul>}
      </li>
    );
  };

  return (
    <section className="panel-section outliner">
      <div className="panel-heading"><div><h2>Hierarchy</h2><p>{nodes.length} entities</p></div></div>
      <div
        className="outliner-root"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          const id = event.dataTransfer.getData("text/scene-node");
          if (id) onReparent(id, null);
        }}
      >
        <ul>{roots.map((node) => renderNode(node, new Set()))}</ul>
      </div>
    </section>
  );
}
