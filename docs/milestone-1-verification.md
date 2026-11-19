# Milestone 1 — Real 2D Animation & Local Video Export

Koma Studio **v0.4.0** adds an Animation Studio to the existing Windows-local app. The planner, project and character libraries, and still-image storyboard are unchanged workflows. Animation Studio works with prepared art; it is not an image or video generator.

## Try the short

In the live demo, open **Animation Studio → Open Blue Flower**. For a private Windows copy, rerun `setup.bat` after updating, follow the [FFmpeg setup](../README.md#ffmpeg-setup-for-export), then run `start.bat`. Rendering works without a network after setup.

1. **Play** below the preview for the full 9.8-second film. The cuts start at **0.00s**, **3.20s**, and **7.20s**.
2. Select **Mina notices the light**. The **Locked camera** indicator should remain on for this entire 4-second shot. Use **Jump to blink**, the timeline scrubber, or frame-step buttons. Compare **frame 96** (eyes open), **126** (closed), and **164** (eyes open, hand raised). All three are in the same shot. The forest and flower should hold steady.
3. Follow it with **Into the bloom**. This is a separate flower insert, not a zoom from the character shot. The petals turn slightly and their halo breathes.
4. **Export MP4 → Render MP4** renders the saved timeline. The complete row shows its encoder and, for the private installation, the local file path. **Watch export** plays the saved file, not the Canvas preview. **Download MP4** returns those same bytes. You can cancel an active render from that dialog.

**Retained verification output:** `.runtime/milestone-1/blue-flower-1080x1920.mp4` in the Arena workspace (not tracked in Git). Copy or download it before the sandbox is discarded. The proof strip and numeric results are beside it as `locked-camera-proof.png` and `blue-flower-proof.json`. A Windows rerender normally lives at `%LOCALAPPDATA%\AnimeStudio\outputs\blue-flower-r1-<job>.mp4`, or the configured **Outputs** folder. The sample is silent.

| Stream check | Observed |
|---|---|
| Container and codec | MP4, H.264 High, 4:2:0 (`yuv420p`), BT.709 |
| Video | 1080 × 1920, 9:16, square pixels, 30/1 FPS |
| Decoded frames | 294; 9.800 seconds; no audio stream |
| Encoded file | 1,487,119 bytes; SHA-256 `9114eeeb6b2fd792681efa35acad02d7806085f77469fee746ac6db095fc65cf` |

## Acceptance A–G

| Criterion | Result and evidence |
|---|---|
| **A — Character moves independently** | **Pass.** The blink swaps eye/eyelid states without moving the body or projection. Mina then leans, tilts her head, changes her expression, and reaches using the shoulder and wrist transforms. Verified on Canvas and decoded MP4. |
| **B — Camera and background remain locked during the action** | **Pass.** All 120 frames of the middle shot had exactly the same camera matrix and forest, foreground and flower transforms. The compared forest and flower regions had **zero changed pixels** both on Canvas and in the lossless compositor. Small decoded MP4 differences are compression, not motion. |
| **C — Establishing shot, action, insert** | **Pass.** Wide path (96 frames), locked action (120), bloom insert (78). Frame 95→96 and 215→216 are hard cuts and were checked in the decoded video. The opening camera push and the insert’s camera motion are separate from the character action. |
| **D — Play, pause and scrub** | **Pass.** Chromium exercised play, pause (frame remains fixed), stepping, scrub, cut and keyframe clicks, preview speed, and shot switching. It also imported artwork, edited transform/visibility keys, parent/order, camera and timing, saved and reopened the edits across server restart. |
| **E — Offline portrait H.264 export** | **Pass on Linux.** API, UI, FFmpeg, full-file decode, download, playback and seek all ran in a loopback-only network namespace with no default route. Export used `libx264` in **Auto** mode, completed in **38.86 seconds** and was decoded by FFprobe and Chromium. A running encode was cancelled with no partial file, a concurrent export was refused, and a killed render recovered as Failed on restart. The test tools were FFmpeg 7.0.2, FFprobe N-66595-gc2b38619c0 and Chromium 153. |
| **F — Native Windows player playback** | **Pending native check.** The exported file played and sought correctly in Linux Chromium. H.264/MP4, `yuv420p`, SAR 1:1 and `faststart` were chosen for Windows compatibility, but no Windows player or Windows driver was available here. On Windows, double-click the retained MP4 in **Media Player** while disconnected, play to the end, and seek across 3.20s/7.20s. Confirm portrait aspect, blink, reach, and insert; run one new local Software export and open that too. |
| **G — Existing features continue working** | **Pass on tested paths.** The 40 existing Python tests and the three prior Chromium workflows passed, including story import/reopen/archive, planning approval/retiming, cast pins, storyboard versions and approvals after restart. SQLite v4→v5 adds motion tables; existing data is not moved. |

### Locked camera: pixel evidence

Mean absolute RGB difference, each channel on a 0–255 scale. Measurements use regions in the same coordinates at every frame (top forest, full flower, eyes, and reaching arm). The two comparisons start from frame 96:

| Comparison | Canvas forest / flower | Canvas moving part | Decoded MP4 forest / flower | Decoded MP4 moving part |
|---|---:|---:|---:|---:|
| 96 → 126: blink | 0 / 0 | 41.60 | 0.064 / 0.154 | 42.14 |
| 96 → 164: reach | 0 / 0 | 29.60 | 0.057 / 0.196 | 29.71 |

Across nine paired sample frames, Canvas and the 540 × 960 Pillow render agreed within **0.72** mean RGB difference; decoded MP4 and the 1080 × 1920 lossless render within **1.47**. The rasterizers and H.264 encoder are not bit-identical. The exact-equality claim is for the stationary regions before encode, not the entire lossy video.

## Architecture and files

- **Timeline contract and engine:** `backend/motion/{models,engine}.py` and `frontend/src/{motionApi,motionMath}.ts`. A 540 × 960 logical stage with 2× art, full-pose keys, smooth/linear/hold interpolation, stepped visibility, affine parent transforms, inherited opacity, edit-time layer order, and a separate camera matrix. Source frame time is output frame × shot speed, clamped to the shot. A tracking camera centers a layer’s transformed pivot plus the authored offset. The Canvas player uses the same timing/transform rules as the offline Pillow renderer.
- **Editor:** `frontend/src/{AnimationStudio,MotionStage,MotionTimeline,MotionInspector,MotionExport}.tsx`, `motion.css`, and `assets/blue-flower.webp`. Integrated with the existing shell in `main.tsx` and `ui.tsx`. Use layer groups to drive several child sprites, and visibility keys to set an individual layer’s in/out timing. Linear or eased x/y, scale, rotation, and opacity remain independent of pan/zoom.
- **Persistence:** `backend/motion/{schema,store,routes}.py`, `backend/{app,storage,images}.py`. Local API at `/api/animation`, optimistic SQLite revisions, single install of the sample per workspace, scoped normalized WebP artwork, and separate exports. A saved storyboard is not overwritten by a motion edit. Version metadata: `backend/__init__.py`, `frontend/package*.json`.
- **Renderer:** `backend/motion/export.py`. Loads one shot’s prepared artwork and keeps at most 32 MiB of transformed-image patches. Composites on CPU and streams RGBA frames to one FFmpeg child at a time. The job owns a saved revision and a per-workspace lease. Auto tries compiled QSV/NVENC/AMF encoders using a three-frame 1080p test, retries with software if a hardware attempt fails, and reports the actual encoder. It validates metadata with FFprobe before publishing a unique file. Cancel kills the encoder and discards the partial output; startup marks interrupted jobs failed rather than resuming automatically.
- **Original sample:** `backend/motion/sample.py`, [`backend/motion/art/`](../backend/motion/art/README.md), and `tools/{draw_motion.py,rasterize_motion.mjs}`. Art and rig are separate; the 18 sprites include opaque backgrounds, alpha-separated features/limbs, flower elements, and foreground/effects.
- **Verification:** `tests/test_motion.py`, `tests/browser/{animation.test.mjs,studio.mjs,smoke.test.mjs,package.json}`, migration fixtures in `tests/{test_planning,test_visuals}.py`, and `tools/verify_motion_export.py`. README and local-engine instructions document the Windows workflow.

## Hardware and boundaries

- The sample was tested on Linux with 2 logical Xeon CPUs, about 3.8 GiB RAM, and **no GPU**. A second export in the demo sampled about **416 MiB peak combined RSS** for the server and encoder (0.4s sampling; browser/OS excluded). The software path is the right starting point on a machine without a dedicated GPU. A recent 64-bit Windows 10/11 PC with **8 GiB RAM and 1 GiB free on a local SSD** is a practical starting recommendation, not a measured minimum. Large scenes or slower CPUs will take longer. CPU compositing is not accelerated by hardware encode.
- Exports have a 60-second timeline limit, 12 shots, 40 layers per shot, 96 keys per track / 2,400 per sequence, 72 imported images per timeline, and 12 megapixels of distinct source art per shot. Import fits artwork into 1080 × 1920 while retaining aspect and alpha; raw import limits are 16 MiB, 12 MP, 6,000 px per side. Render time is capped at 30 minutes. On slow hardware, shorten shots or use cropped art rather than making every part a full-frame image.
- Retime shots or adjust review speed independently. At speeds above 1× an output frame can skip source keys; author or revise those keys at 1×, then set the final speed. Layers move using prepared sprites, not automatic rigging, lip-sync, deformation or generated movement. No audio, subtitles, voice synthesis, character generation, or image-to-video work is included.
- Actual QSV/NVENC/AMF encoding on the user’s hardware was **not verified**. Auto selected software on Linux, and the hardware-failure retry path was tested with a simulated encoder error. If a Windows build or driver cannot use hardware encoding, use a build with `libx264` and select Software.

## Reproduce the checks

Run from the repository root, with dependencies and the production bundle installed. On Windows use `.venv\Scripts\python.exe` in place of `.venv/bin/python`:

```sh
.venv/bin/python -m pip install -r backend/requirements-test.txt
.venv/bin/python -m unittest discover -s tests -q  # 52 tests
npm --prefix frontend run build
npm --prefix tests/browser ci --no-audit --no-fund
```

Set `KOMA_CHROMIUM_EXECUTABLE` to a local Chromium, Chrome or Edge executable. Then `npm --prefix tests/browser test` runs the four UI workflows; the fifth, full-media test runs when `KOMA_TEST_EXPORT=1` and FFmpeg/FFprobe are on PATH. Set `KOMA_TEST_MEDIA_DIR` to the **absolute path** of `.runtime/milestone-1` to retain the original sample MP4 and Canvas captures (for example, `export KOMA_TEST_MEDIA_DIR="$PWD/.runtime/milestone-1"` on Linux). The test opens an isolated workspace, not your library. For the strict offline test on Linux, run the command inside a network namespace with only loopback up, for example `unshare -Urn sh -c 'ip link set lo up && npm --prefix tests/browser test'` after exporting the variables.

After exporting the unedited sample, recheck any compatible file using your local media tools:

```sh
.venv/bin/python -m tools.verify_motion_export .runtime/milestone-1/blue-flower-1080x1920.mp4 --canvas-dir .runtime/milestone-1 --evidence-dir .runtime/milestone-1
```

Omit `--canvas-dir` for a file rendered manually in the app. `--ffmpeg` and `--ffprobe` take absolute paths if those tools are not on PATH. The verifier decodes all 294 frames, compares selected frames and crop statistics, and records the results. Software/driver differences can change the output bytes; the hash above is for the retained file only.
