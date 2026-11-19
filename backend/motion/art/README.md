# Blue Flower — original animation artwork

The scene, character, poses and artwork are original to Koma Studio. No frames or designs from the reference reel are included. The bundled WebPs are raster copies of hand-authored vector shapes, not generated video. The `bf-*.webp` artwork and its derivative library cover `frontend/src/assets/blue-flower.webp` are dedicated to the public domain under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).

- `forest`, `foreground`, `glade-detail`: woodland plate, near ferns, and softer insert backdrop.
- `torso`, `face`, `fringe`, `brows`, `eyes`, `lids`, `smile`, `mouth`, `sleeve`, `hand`, `shadow`: Mina’s separable art and ground shadow. The head, shoulder, body and wrist transforms are authored in the timeline.
- `petals`, `stem`, `halo`, `spark`: flower details and lighting/glimmer layers.

The sources are [`tools/draw_motion.py`](../../../tools/draw_motion.py) (reuses local woodland drawing helpers from `draw_preview.py`) and [`sample.py`](../sample.py) (pivots, keyframes, camera and shot timings). The authoring script emits 2× SVG artwork. [`tools/rasterize_motion.mjs`](../../../tools/rasterize_motion.mjs) rasterizes it with the test-only Chromium driver. Bundled flat raster *layers* open at runtime; neither of these authoring tools is required to use the studio or render the short.
