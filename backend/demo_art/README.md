# Koma Studio demo artwork

These original, hand-authored vector illustrations were drawn for this repository. The bundled WebP files are 540 × 960 raster copies, not outputs from a local or hosted AI model. They are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).

| Files | Use |
|---|---|
| `flower.webp`, `old-tree.webp`, `forest-lights.webp` | The three blue-flower sample storyboard stills |
| `old-tree-study.webp` | Earlier illustration of the second shot, retained as an example of version history |
| `traveler-reference.webp`, `creature-reference.webp` | Design references for the chibi traveler and tiny forest creature |

Source: [`tools/draw_preview.py`](../../tools/draw_preview.py). The script makes deterministic SVG drawings using only Python’s standard library. The WebPs were rasterized in local Chromium and encoded with Pillow. The studio ships the small raster files; drawing and rasterization do not run at normal startup. Only the isolated `--preview` demo automatically imports the illustrations.
