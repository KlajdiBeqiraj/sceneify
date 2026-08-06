import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AssetBrowser } from "./AssetBrowser";

const { fetchCatalog } = vi.hoisted(() => ({ fetchCatalog: vi.fn() }));

vi.mock("../hooks/useScene", () => ({
  assetUrl: (source: string) => `/asset/${source}`,
  fetchCatalog,
}));

describe("AssetBrowser", () => {
  beforeEach(() => {
    fetchCatalog.mockReset();
  });

  it("shows typed metadata and creates the selected asset", async () => {
    const asset = {
      id: "robot",
      source: "https://example.com/robot.glb",
      format: "glb",
      license: "CC0",
      thumbnail: "assets/robot.png",
      byteSize: 2048,
      tags: ["character", "animated"],
    };
    fetchCatalog.mockResolvedValue([asset]);
    const onCreateFromAsset = vi.fn();

    render(
      <AssetBrowser onImport={vi.fn()} onCreateFromAsset={onCreateFromAsset} />,
    );

    expect(await screen.findByText("CC0", { exact: false })).toHaveTextContent("2.0 KiB");
    expect(screen.getByText("character, animated")).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAttribute("src", "/asset/assets/robot.png");
    fireEvent.doubleClick(screen.getByText("robot.glb").closest("button")!);
    expect(onCreateFromAsset).toHaveBeenCalledWith(asset);
  });
});
