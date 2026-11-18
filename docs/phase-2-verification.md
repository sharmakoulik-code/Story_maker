# Phase 2 verification — 2026-11-18

Koma Studio 0.2.0. Executed on Linux with Python 3.11, SQLite 3.40, Node 22 and headless Chromium. The studio used a private temporary library and a real loopback server for the browser tests. No image model, voice model, or GPU was needed.

## Blue-flower acceptance through planning

The [exact requested story](../tests/fixtures/blue_flower.txt) was entered in **New story**, set to **30 seconds**, and generated locally. The original story remained intact. The starter Bible identified the little chibi girl, tiny magical creature, mysterious forest, old tree, glowing blue flower and magical lights. The plot analysis surfaced discovery, the trapped creature, the rescue, and the illuminated forest. The emotion cues progressed from curiosity to concern, relief and wonder.

| Generated scene | Allocated | Estimated speech |
|---|---:|---:|
| Glowing blue flower | 10 s | 7.5 s |
| Old tree | 10 s | 8.5 s |
| Magical lights | 10 s | 8.7 s |
| **Total** | **30 s** | **24.7 s** |

All 43 spoken words fit at the planning rate. These are text estimates, **not audio measurements**. The browser test then edited a shared character description and confirmed it appeared in the next scene’s automatic prompt. It saved an overlong script and saw approval blocked, repaired it, exercised scene add/reorder/remove, fitted the timing, edited a single image prompt, and approved the plan. It stopped and relaunched the backend, checked the persisted approval and prompt, downloaded the approved snapshot, then tested restoring it as a draft and switching to a 60-second target without discarding the script. The project media directory stayed empty after approval. A 390 px layout check passed.

## Regression and offline results

- **30 Python tests passed.** Coverage includes planning and timing, offline connection guards, Hindi/Bengali text and speaker parsing, compression of long input, prompt updates from shared character/location/prop references, approval and version history, archive and stale-source constraints, revision conflicts, and migrations. The v1 migration fixture started with a pre-existing story and settings but no plan tables. The v2 fixture verified backfilling an existing approval into version history. Phase 2 uses SQLite schema 3; migrations are transactional and there is no automatic downgrade.
- **Production build and both Chromium workflows passed.** The Foundation workflow covers Unicode TXT import and project/settings persistence. Both workflows blocked requests outside the local app origin and recorded zero external attempts. With Python socket connections guarded, planning and approval made no TCP connection attempts. Optional diagnostics still probe installed runtimes on loopback. This was not a physical network-disconnect test.
- **Planning CPU time only:** the warm `build_plan` plus `timing_for` path took a median **0.57 ms** for the 259-character story (100 runs). For a synthetic 99,840-character repeated draft at 180 seconds, the median was **106 ms** (10 runs). This was a 2-logical-core Linux sandbox with about 3.8 GiB RAM and no detected GPU. The timings exclude server startup, SQLite and browser work. They do not estimate rendering speed or the performance of the user’s Windows PC.

## Repeat the checks

See [test setup and commands](phase-1-verification.md#repeat-the-tests). The same commands now run both browser workflows and the planner tests. Use an existing Chrome, Edge, or Chromium executable; the test is not a runtime dependency.

## Limits and remaining acceptance

The planner extracts and ranks source passages; it does not translate, invent missing character details, or reliably infer complex relationships and speakers. Speech times must be checked again against real audio. The image prompt is editable text only. An approved plan is **not** an approved or generated shot.

Cross-project character references, visual storyboard and per-shot media versions, imported or generated illustrations, animation, narration, subtitles, music, timeline and MP4 rendering are still pending. No image was imported or generated for the blue-flower test, and no video or audio was created. Native Windows startup, media-job recovery, sound mix and subtitle sync, and final 720×1280/24 FPS H.264/AAC playback have not been verified.
