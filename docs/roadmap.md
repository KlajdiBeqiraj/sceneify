# Roadmap (public, high level)

`sceneify` is a PyPI library: author interactive 3D web worlds from Python
with a Streamlit-like API (`pip install sceneify`, then `scene.run()` /
`scene.play()`).

## Shipped

- Multi-asset scenes (GLB and related formats)
- Geometric environment rules and world mesh
- Browser world editor with primitives, GLB import, hierarchy, inspector, and save
- uv-based packaging workflow
- WebSocket play loop and browser input
- Translate, rotate, scale, snap, hierarchy, undo, and redo
- Versioned scene schema and asset catalog
- Provider-neutral coding agent actions
- Optional Gymnasium environment interface
- Declarative game manifests, browser physics, third-person controls, and HUD
- Reusable prefabs with overrides
- Additional player controller presets (`simple` / `ecctrl`)
- Episode recording and replay (versioned JSON + WebSocket protocol)
- Dirty pose frame deltas for the play WebSocket loop
- Static web export (hostable viewer frontend + live backend)

## Next

1. Rendering polish (WebGPURenderer on the existing Three.js viewer)
2. Optional RL/headless extras when there is a concrete need

## Stack decisions (do / don't)

sceneify is a Python authoring API plus a bundled web viewer, not a native game
engine. Optimize for authoring speed and shipping, not for getting closer to the
metal. In the browser, "closer to hardware" means WebGPU and WASM, and both are
reachable inside the current stack.

### Do

- Stay on **Three.js + React Three Fiber + Rapier**. This is the right stack for
  a `pip install` library with a Streamlit-like Python API.
- Treat **WebGPU** as an upgrade path on the same Three.js scene graph
  (`WebGPURenderer` with WebGL2 fallback), not as a reason to rewrite the viewer.
- Build next features on top of the current stack:
  - Prefabs as sceneify schema subtrees with overrides
  - Controller presets via **ecctrl** (wrapped by the Python `Game` API)
  - Complex object interactions via Rapier joints/sensors declared from Python
  - Game episode replay on the existing WebSocket protocol; **Minari** only as an
    optional RL dataset extra
  - Static web export via the Vite viewer build plus **glTF Transform** /
    `trimesh` for asset packing where needed
- Keep editor chrome and in-game HUD as **DOM/HTML**. Use **leva** for edit/debug
  tweaks. Consider Mantine or Radix only if the editor UI grows enough to need it.
- Watch **Rapier Python** (`rapier3d`) for an optional headless extra once it is
  published on PyPI. Do not make it a core dependency today.

### Don't

- Do not migrate the viewer to **Babylon.js**, **PlayCanvas**, **Bevy**,
  **Godot**, or **Unity WASM**. Those can be closer to native performance, but
  they break the Python authoring / PyPI wheel product shape.
- Do not rewrite on raw **WebGPU / wgpu**. Too low-level; months of non-product
  work for materials, GLB, gizmos, and editor tooling that Three already covers.
- Do not put **MuJoCo**, **PyBullet**, or **Genesis** on the `scene.play()` path.
  They are fine for robotics/RL research, not for browser gameplay latency.
- Do not replace Rapier with **Cannon-es** or **Ammo.js** (downgrade or legacy).
- Do not use in-world 3D UI kits (for example `@react-three/uikit`) for the editor
  sidebar/inspector. Those belong to XR/spatial UI, not desktop editor chrome.
- Do not replace the viewer with **Viser** or **Meshcat**. They are visualization
  peers, not drop-in dependencies for a game runtime.
- Do not run a second authoritative physics world in Python and keep it in sync
  with the browser for interactive play. Keep Rapier in the browser as the
  gameplay source of truth.

### Priority order

1. Product features: prefabs → controller presets → recording/replay → static export
2. Rendering polish: WebGPURenderer on the existing Three.js viewer
3. Optional RL/headless: Rapier Python and Minari only when there is a concrete need
