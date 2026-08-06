# Third-party demo assets

All binary assets under `examples/assets/` are distributed under CC0 1.0. They are
included for the public examples and are not part of the Sceneify Python wheel.

## KayKit

- Creator: Kay Lousberg
- Sources:
  - https://github.com/KayKit-Game-Assets/KayKit-Character-Pack-Adventures-1.0
  - https://github.com/KayKit-Game-Assets/KayKit-Dungeon-Remastered-1.0
- License: CC0 1.0 Universal
- Files: `examples/assets/kaykit/*.glb`
- Modifications: selected files were renamed for consistent paths. `knight.glb` and
  `mage.glb` use Meshopt geometry compression and WebP textures; rigs and clips are
  unchanged.

## Quaternius modular ruins

- Creator: Quaternius
- Source: https://poly.pizza/m/F2LAK03B0r
- License: Public Domain, CC0
- File: `examples/assets/roman/modular_ruins.glb`
- Modifications: none; original node names are retained for modular composition.

## Fountain

- Creator: Isa Lousberg
- Source: https://poly.pizza/m/WHc7dwttlk
- License: Public Domain, CC0
- File: `examples/assets/roman/fountain.glb`
- Modifications: none.

## Poly Haven

- Creator: Poly Haven contributors
- Sources:
  - https://polyhaven.com/a/marble_bust_01
  - https://polyhaven.com/a/horse_statue_01
  - https://polyhaven.com/a/colosseum
  - https://polyhaven.com/a/stone_pavers
- License: CC0, https://polyhaven.com/license
- Files:
  - `examples/assets/roman/marble_bust.glb`
  - `examples/assets/roman/horse_statue.glb`
  - `examples/assets/roman/colosseum_1k.hdr`
  - `examples/assets/roman/stone_pavers_*_1k.jpg`
- Modifications: 1K glTF materials were packed into GLB containers. The Colosseum
  environment map and Amal Kumar's Stone Pavers PBR maps are the original 1K files.

Downloaded and verified on 2026-08-06.
