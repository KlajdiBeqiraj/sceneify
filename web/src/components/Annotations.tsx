import { Html } from "@react-three/drei";
import { useEffect, useState } from "react";
import type { AnnotationNode } from "../types/scene";

export function Annotations({
  items,
  focusedId,
  editing,
  onFocusChange,
  onSemanticEvent,
}: {
  items: AnnotationNode[];
  focusedId: string | null;
  editing: boolean;
  onFocusChange: (id: string | null) => void;
  onSemanticEvent?: (name: string, nodeId: string) => void;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const activeCardId = editing ? selected : null;

  useEffect(() => {
    if (editing) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && focusedId) {
        event.preventDefault();
        onFocusChange(null);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [editing, focusedId, onFocusChange]);

  return (
    <>
      {items
        .filter((item) => item.visible)
        .map((item) => {
          const isFocused = focusedId === item.id && !editing;
          const revealAlways = item.meta?.interaction?.reveal !== "hover";
          const showFloatingCard =
            !isFocused &&
            (item.label || item.description) &&
            (revealAlways || hovered === item.id || activeCardId === item.id);
          return (
            <group key={item.id} position={item.position as [number, number, number]}>
              <mesh>
                <sphereGeometry args={[0.13, 20, 20]} />
                <meshStandardMaterial
                  color={item.color}
                  emissive={item.color}
                  emissiveIntensity={isFocused ? 0.7 : 0.35}
                />
              </mesh>
              <Html center distanceFactor={8} style={{ pointerEvents: "auto" }} zIndexRange={[20, 0]}>
                <div className={`poi-anchor ${isFocused ? "focused" : ""}`}>
                  <button
                    className="poi-hit"
                    aria-label={`Point of interest: ${item.label ?? item.id}`}
                    data-poi-id={item.id}
                    data-poi-focused={isFocused ? "true" : "false"}
                    onMouseEnter={() => {
                      setHovered(item.id);
                      document.body.style.cursor = item.meta?.interaction?.cursor ?? "pointer";
                    }}
                    onMouseLeave={() => {
                      setHovered((current) => (current === item.id ? null : current));
                      document.body.style.cursor = "";
                    }}
                    onClick={() => {
                      onSemanticEvent?.(
                        item.meta?.interaction?.clickEvent ?? "poi_selected",
                        item.id,
                      );
                      if (editing) {
                        setSelected((current) => (current === item.id ? null : item.id));
                        return;
                      }
                      onFocusChange(item.id);
                    }}
                  />
                  {showFloatingCard && (
                    <div
                      className={`anno poi-card ${activeCardId === item.id ? "selected" : ""}`}
                    >
                      {item.meta?.category && <small>{item.meta.category}</small>}
                      {item.label && <strong>{item.label}</strong>}
                      {item.description &&
                        (hovered === item.id || activeCardId === item.id) && (
                          <span>{item.description}</span>
                        )}
                    </div>
                  )}
                </div>
              </Html>
            </group>
          );
        })}
    </>
  );
}
