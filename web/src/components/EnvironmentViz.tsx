import type { EnvironmentPayload, ZoneNode } from "../types/scene";

function BoxHelper({
  min,
  max,
  color,
  opacity = 0,
  wireframe = true,
}: {
  min: number[];
  max: number[];
  color: string;
  opacity?: number;
  wireframe?: boolean;
}) {
  const cx = (min[0] + max[0]) / 2;
  const cy = (min[1] + max[1]) / 2;
  const cz = (min[2] + max[2]) / 2;
  const sx = Math.max(max[0] - min[0], 0.001);
  const sy = Math.max(max[1] - min[1], 0.001);
  const sz = Math.max(max[2] - min[2], 0.001);

  return (
    <mesh position={[cx, cy, cz]}>
      <boxGeometry args={[sx, sy, sz]} />
      <meshBasicMaterial
        color={color}
        wireframe={wireframe}
        transparent={opacity > 0}
        opacity={opacity > 0 ? opacity : 1}
        depthWrite={opacity <= 0}
      />
    </mesh>
  );
}

function ZoneMesh({ zone }: { zone: ZoneNode }) {
  if (!zone.visible) {
    return null;
  }
  return (
    <BoxHelper
      min={zone.min}
      max={zone.max}
      color={zone.color}
      opacity={zone.opacity}
      wireframe={false}
    />
  );
}

export function EnvironmentViz({ environment }: { environment: EnvironmentPayload | null | undefined }) {
  if (!environment) {
    return null;
  }

  return (
    <group>
      {environment.bounds?.visible && (
        <BoxHelper
          min={environment.bounds.min}
          max={environment.bounds.max}
          color={environment.bounds.color}
          wireframe
        />
      )}
      {environment.ground?.visible && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, environment.ground.y, 0]}>
          <planeGeometry args={[40, 40]} />
          <meshStandardMaterial color={environment.ground.color} transparent opacity={0.35} />
        </mesh>
      )}
      {environment.zones.map((zone) => (
        <ZoneMesh key={zone.id} zone={zone} />
      ))}
      {environment.showAxes && (
        <axesHelper args={[1.5]} />
      )}
    </group>
  );
}
