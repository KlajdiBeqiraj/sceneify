import { Html } from "@react-three/drei";
import type { AnnotationNode } from "../types/scene";

export function Annotations({ items }: { items: AnnotationNode[] }) {
  return (
    <>
      {items
        .filter((item) => item.visible)
        .map((item) => (
          <group key={item.id} position={item.position as [number, number, number]}>
            <mesh>
              <sphereGeometry args={[0.05, 16, 16]} />
              <meshStandardMaterial color={item.color} emissive={item.color} emissiveIntensity={0.35} />
            </mesh>
            {(item.label || item.description) && (
              <Html distanceFactor={8} style={{ pointerEvents: "none" }}>
                <div className="anno">
                  {item.label && <strong>{item.label}</strong>}
                  {item.description && <span>{item.description}</span>}
                </div>
              </Html>
            )}
          </group>
        ))}
    </>
  );
}
