# Koma Studio

A private, CPU-first workspace for making vertical anime story videos on your own Windows computer. Write a timed story plan, pin reusable character references, review local illustrations, then animate prepared layers in **Animation Studio** and render a portrait MP4. No model or cloud service is needed.

## Start on Windows

1. Install [64-bit Python 3.11 or newer](https://www.python.org/downloads/windows/) (3.11 or 3.12 recommended) and [Node.js 22.12 or newer with npm](https://nodejs.org/) on Windows 10 or 11. Make them available on `PATH` or use the Python `py` launcher.
2. Put this checkout in a writable folder on a local drive. Run **`setup.bat`** once while online. It creates a Python virtual environment and builds the React interface. It does not install FFmpeg, AI runtimes or model weights.
3. Run **`start.bat`**. Leave its console window open while working. It opens [http://127.0.0.1:8765](http://127.0.0.1:8765/) when the studio is ready. Use `Ctrl+C` in the console to stop it.

Updating an existing checkout? Stop the studio, back up your data folder, and rerun `setup.bat` to rebuild the UI and pick up dependencies. `start.bat` migrates the SQLite library in place without moving your projects.

Only the one-time setup needs internet access. You can disconnect after setup and run `start.bat` as usual. Node and npm are build-time tools; the launcher does not run them. There is no account, API key, remote inference, upload endpoint to a third party, or telemetry exporter. The interface, illustrations and fonts are served locally. Local runtime checks only ask Ollama/ComfyUI on loopback for status, not for generation.

In the development demo, select **Open sample storyboard** on the overview to see the Phase 3 example. For the animated short, use **Animation Studio → Open Blue Flower**. The demo uses a temporary sandbox, not your Windows library. Use sample content only; any files you import into it are copied into that sandbox and the library resets on restart.

## Develop a first story

1. Open **New story**. Enter a title; paste a draft or use **Import TXT**. UTF-8 and BOM-marked UTF-16 text files are accepted. Draft text is optional, and you can edit it later.
2. Choose a duration, language (English/Hindi/Bengali), visual style, resolution, frame rate and motion intensity. Planning uses the duration, language, style and intensity; selecting them does not render media. The default canvas is 9:16 at 720 × 1280 and 24 FPS.
3. Select **Generate story plan**, or use **Create project** to keep an unplanned draft. To try the verified example, use the [blue-flower story](tests/fixtures/blue_flower.txt) with a **30s** target. The planner needs no model, GPU, FFmpeg, or internet.
4. Open **Story analysis** to review plot beats and emotional cues. In **Story Bible**, edit the shared character, location and prop descriptions. In **Scene plan**, edit and reorder scenes, check narration and dialogue, and refine camera, motion, transitions and sound notes. Automatic portrait prompts are updated on save from the linked references; you can override a prompt in one scene without changing the others.
5. **Save plan** checks the script against the scene and project durations. **Fit to target** redistributes time without cutting any lines. If the script cannot fit, shorten the lines or change the duration in **Story draft**. When duration is the only source change, **Keep script & use … target** applies it without replacing manual edits. **Approve plan** records a reviewed version; it does not start any media work.

The planner uses local rules to select whole passages from the story. A short target may omit some passages from the initial spoken script; the original story and source excerpts remain available. Review all suggestions, especially character names and dialogue attribution. Use `Name: Dialogue` on its own line for explicit speakers. English, Hindi, and Bengali text are retained, not translated. Timing is an estimate, not a measured voice recording, and no voices are installed by the studio.

**Saved versions** keeps approved plans and copies of saved plans changed by scene removal, regeneration, or restoration. A version with matching story text and production settings can be restored as a new draft. Versions with different inputs can be downloaded as JSON for reference. The original story is not overwritten. Changing the story or production settings makes the active plan out of date; changing only its title does not.

**My projects** reopens saved drafts and plans. **Archive project** hides a project without deleting data; use the Archived filter and **Restore project** to edit again. **System & models** shows CPU, RAM, graphics, disk space and detected media tools. Missing tools do not block planning.

## Build the cast and storyboard

1. In **Character Library**, create a design with face, hair, eyes, proportions, outfits, accessories and generation notes. Save it, then **Import reference**. **Replace reference** creates a new version; select an earlier image under **Reference versions** if you prefer it. A design has one active reference at a time; you can import an existing multi-angle sheet as a single image.
2. In a project’s **Story Bible**, use **Add from Character Library** to add a saved design, or open **Library design** on an existing character and apply one there without changing scene links or story relationships. **Copy to library** converts a project character into a separate reusable design. Save the plan to pin the design and its chosen image; library edits and archiving do not change existing project pins.
3. Open **Storyboard**, pick a scene, then **Import frame**. Choose a still PNG, JPEG or WebP (up to 16 MiB, 12 megapixels, and 6,000 px on either side). Note the source and license or usage rights for your records. The original is untouched. The studio saves a normalized, metadata-stripped WebP and a smaller thumbnail. It does not retrieve files from URLs.
4. Approve the Story plan first, then use **Approve frame** for a single still or select multiple cards and **Approve selected**. **Replace frame** affects only the selected scene. **Image versions** lets you inspect, download, or reselect earlier versions; selecting an earlier image requires a fresh approval. A still’s approval is not approval of future motion, audio, or a finished video.
5. **Scene details** edits the shared Story plan. Add, move, or remove scenes, then **Save scene edits**. Reordering keeps the same artwork. A change to a scene’s visual instructions or pinned cast needs re-review for the affected scene(s); other still approvals are retained. Removed or replaced plan scenes keep their media under **Off-board images**. To restore a compatible sequence, use **Saved versions** on the Story plan.

You can try the whole workflow with the [blue-flower story](tests/fixtures/blue_flower.txt) and the [original CC0 demo art](backend/demo_art/README.md). The Windows app starts with an empty library. You do not need a GPU, FFmpeg, internet, or an image engine to import stills and review them. No character-sheet generation or automatic image regeneration is available yet.

## Animate and export Blue Flower

1. Open **Animation Studio → Open Blue Flower**. On a new library, this installs the original layered sample once. Press **Play** beneath **Camera preview**; the film cuts from a wide forest path to Mina’s reaction, then to the flower insert. The sample runs 9.8 seconds.
2. Select **Mina notices the light** in **Shots**. The camera badge reads **Locked camera**. Play from the start of that shot, or use **Jump to blink** and the arrow-step controls. At output frames **96**, **126**, and **164** you can see eyes open, eyes shut, then the raised hand. The global scrubber and clickable shot/keyframe tracks are in the timeline below the editor. Frame numbering starts at zero.
3. For your own work, create a **New animation** and **Import artwork**. Use PNG or WebP with transparent edges for separated parts. Layers listed at the top draw in front. Use **Layer setup & ordering** to set the parent, pivot and order. At source frame 0 set the starting pose; later edits set a keyframe at the playhead. The **Camera** tab supports static framing, pan/zoom keys, and following a layer. In **Shot**, set the source duration and motion speed. **Preview speed** only affects playback, not your MP4. Save the timeline to keep your changes.
4. After installing the [local media tools](#ffmpeg-setup-for-export), choose **Export MP4 → Render MP4**. The app exports the saved revision, at **1080 × 1920, 30 FPS, H.264 MP4**, without audio. Once complete, use **Watch export**, **Download MP4**, or open the displayed local file path. The default folder is `%LOCALAPPDATA%\AnimeStudio\outputs`.

Animation Studio is a separate timeline library. It does not automatically convert a story plan or storyboard into a rig. Import prepared backgrounds, faces, hands, and other parts as needed. The built-in sample is editable; use a separate timeline to practice if you want to preserve the original verification example. See the [Milestone 1 verification report](docs/milestone-1-verification.md) for the engine limits, native Windows playback check, evidence, and test commands.

## Data folders and backups

Windows defaults to `%LOCALAPPDATA%\AnimeStudio`, outside this Git checkout:

```text
AnimeStudio/
├── database/studio.sqlite3  # drafts, plans, approvals, timelines, and export jobs
├── animation/               # normalized artwork imported into Animation Studio
├── characters/              # versioned Character Library reference images
├── projects/                # per-project stills and thumbnails
├── models/                  # optional model files for later phases
├── outputs/                 # finished animation MP4s
└── logs/                    # reserved for later job logs
```

Change the default project, model, export and log folders in **System & models**. A new Projects folder applies only to new projects. Existing projects retain their absolute media paths; the app does not move your files. For a different data root or port, run from Command Prompt, for example:

```bat
set "ANIMESTUDIO_DATA_DIR=D:\Koma Data"
set "ANIMESTUDIO_PORT=8766"
start.bat
```

Use a non-synced local disk. To back up a library, stop the studio and copy the whole data folder plus any folders you configured outside it. Restore to the same locations if you want existing project media paths to remain valid. Changing the data root alone does not migrate a library. Keep the database and its media together when backing up; downloaded versions are not a full backup. Image versions are retained and take additional disk space.

## FFmpeg setup for export

Use a trusted [Windows build listed by FFmpeg](https://ffmpeg.org/download.html#build-windows) that includes software H.264 (`libx264`). Keep `ffmpeg.exe` and `ffprobe.exe` from the same build. Editing and preview do not need these tools; the MP4 renderer needs both. You can disconnect after installing them.

- Add the build’s `bin` folder to `PATH` and restart the studio, **or** enter full paths to both `.exe` files under **System & models → Workspace paths**.
- Use **Refresh diagnostics**. “Detected” means the executable responded to a version probe; it does not mean a video was rendered.
- **Auto** tries an available Intel QSV, NVIDIA NVENC, or AMD AMF H.264 encoder only after a local encode test. If none pass, or a hardware render fails, it uses CPU `libx264`. Choose **Software / libx264** to force CPU encoding. Compositing always runs on the CPU.
- See [optional local engines](docs/local-engines.md) for future model and voice runtimes. These are not needed here.

## Troubleshooting

| Problem | What to try |
|---|---|
| `setup.bat` cannot find Node or Python | Open a new Command Prompt after installing them. Check `node -v`, `npm -v`, and `py -3 --version`. If a stale `.venv` uses an older Python, stop the studio, rename that virtual environment and rerun setup. |
| Browser did not open | Wait for `Uvicorn running` in the console. Open the launcher URL manually. If the port is in use, close the other process or set `ANIMESTUDIO_PORT`. |
| Cannot write a project folder | Select an absolute, writable, local folder under System & models. Mapped network drives and UNC shares are not accepted. |
| TXT import rejects the file | In Notepad, save it as UTF-8, then import again. The editor accepts up to 100,000 characters. |
| The plan will not approve | Save your changes, check the Pacing desk for scenes that exceed their allocation, and make sure the scene durations total the target. Shorten the script or use a longer target if Fit to target cannot fit it. |
| A frame or reference says its file is unavailable | Keep managed media at the original path. Restore the missing copy from your backup, or choose another version or import a replacement. |
| Visual review was reopened | Save and approve the current Story plan, then check only the frames marked Needs review or Direction changed. Pick the intended version before approving it again. |
| Graphics memory is unknown | Windows adapter-memory values are approximate. The auto encoder tests the executable and driver rather than relying on the detected name or memory. No GPU is needed for CPU export. |
| Render is disabled or fails | Save the timeline, add artwork to each shot, check both executable paths and the writable Outputs folder, and try Software encoding. If another studio is rendering, cancel or finish there first. Failed or cancelled jobs do not publish an MP4. |
| A draft seems missing | Check the Archived filter and confirm the `DATA ROOT` in System & models. The demo uses a different, temporary library. |

## Source and testing

- `backend/` — loopback launcher and API, SQLite migrations and project storage, offline planning and timing, versioned local still imports, a layered animation compositor, and a bounded FFmpeg worker.
- `frontend/` — TypeScript, React, Vite and Tailwind; original, decorative SVG illustrations and locally bundled DM Sans and Fraunces ([SIL OFL notices](frontend/public/licenses/)).
- `tests/` — Python API, planner, image storage and diagnostics tests; optional Chromium workflows with a real local server restart.
- [Milestone 1 verification report](docs/milestone-1-verification.md) — original sample, frame comparisons, local export, and Windows follow-up.
- [Phase 3 verification report](docs/phase-3-verification.md) — visual workflow, image limits, restart checks and remaining work.
- [Phase 2 verification report](docs/phase-2-verification.md) — blue-flower walkthrough results, timing, offline checks and outstanding media work.
- [Phase 1 verification report](docs/phase-1-verification.md) — test commands, measured sandbox hardware, and what has not been verified on Windows.

For development on Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend ci --no-audit --no-fund
npm --prefix frontend run build
.venv/bin/python -m backend --open-browser
```

`--preview` is a development-only launcher flag. It binds on all interfaces **with a fresh temporary library containing sample drafts and storyboard images**, ignores the private data-root environment setting, and makes device settings read-only. `start.bat` never uses it.
