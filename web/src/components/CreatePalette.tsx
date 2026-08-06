import { Box, Circle, Cylinder, Square } from "lucide-react";
import type { PrimitiveNode } from "../types/scene";

export function CreatePalette({ onCreate }: { onCreate: (kind: PrimitiveNode["primitive"]) => void }) {
  const primitives: Array<[PrimitiveNode["primitive"], React.ReactNode, string]> = [
    ["box", <Box key="box" />, "Box"],
    ["sphere", <Circle key="sphere" />, "Sphere"],
    ["capsule", <Cylinder key="capsule" />, "Capsule"],
    ["plane", <Square key="plane" />, "Plane"],
  ];
  return (
    <section className="panel-section">
      <div className="panel-heading"><div><h2>Create</h2><p>Add a primitive to the world</p></div></div>
      <div className="create-grid">
        {primitives.map(([kind, icon, label]) => (
          <button key={kind} onClick={() => onCreate(kind)}>{icon}<span>{label}</span></button>
        ))}
      </div>
    </section>
  );
}
