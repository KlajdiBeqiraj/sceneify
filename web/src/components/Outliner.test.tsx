import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Outliner } from "./Outliner";
import type { ScenePayload } from "../types/scene";

const scene: ScenePayload = {
  name: "Editor",
  background: "#000",
  meshes: [],
  annotations: [],
  trajectories: [],
  objects: [
    { kind: "object", id: "root", label: "Root", position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1], visible: true },
  ],
  primitives: [
    { kind: "primitive", id: "crate", parentId: "root", label: "Crate", primitive: "box", position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1], visible: true },
  ],
};

describe("Outliner", () => {
  it("selects nodes and reparents dropped entities", () => {
    const onSelect = vi.fn();
    const onReparent = vi.fn();
    render(<Outliner scene={scene} selectedId={null} onSelect={onSelect} onReparent={onReparent} onVisibility={vi.fn()} />);
    expect(screen.getByText("Crate").closest(".outliner-children")).not.toBeNull();
    fireEvent.click(screen.getByText("Crate"));
    expect(onSelect).toHaveBeenCalledWith("crate");
    const transfer = { getData: () => "crate", setData: vi.fn() };
    fireEvent.drop(screen.getByText("Root").closest(".outliner-row")!, { dataTransfer: transfer });
    expect(onReparent).toHaveBeenCalledWith("crate", "root");
  });
});
