import { Line } from "@react-three/drei";
import type { TrajectoryNode } from "../types/scene";

export function Trajectories({ items }: { items: TrajectoryNode[] }) {
  return (
    <>
      {items
        .filter((item) => item.visible)
        .map((item) => {
          const points = item.points.map((p) => [p[0], p[1], p[2]] as [number, number, number]);
          if (item.closed && points.length > 2) {
            points.push(points[0]);
          }
          return (
            <Line
              key={item.id}
              points={points}
              color={item.color}
              lineWidth={item.lineWidth}
            />
          );
        })}
    </>
  );
}
