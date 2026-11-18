# Phase 1 verification — 2026-11-18

## Results from the Linux sandbox

| Check | Result |
|---|---|
| TypeScript production build | Passed. The UI, fonts and artwork load from the same local server. |
| Python suite | **14 tests passed.** Covers draft validation and Unicode, SQLite reopens, non-destructive archive/restore, settings persistence, invalid paths, schema preservation, loopback/preview request guards, and hardware-diagnostics behavior. |
| Chromium smoke workflow | **Passed.** Created a project from a UTF-16 TXT containing Bengali and Hindi text, cancelled a navigation away from unsaved changes, saved preferences, edited, archived, searched, restored, changed a storage setting, stopped and relaunched the backend, and reopened the saved data. Also checked for horizontal overflow at 390 px. |
| Offline foundation checks | Browser smoke test blocked all requests outside loopback and recorded zero attempts. API tests blocked non-loopback Python socket connections and exercised hardware reporting, creation, and reads; the only TCP probes attempted were to the two documented loopback engine ports. This is not a claim that the host OS was physically disconnected. |
| Media-tool detection | Verified both the missing-tool state and real portable FFmpeg 7.0.2 / FFprobe version detection from a path with spaces. The FFmpeg probe detected `libx264`, AAC and the libass `subtitles` filter. No project media was rendered. |
| Windows dependencies | Python 3.11 x64 Windows wheels resolved, including `pydantic-core`. The frontend lockfile contains the Windows x64 native packages used by the build toolchain. Windows CIM output mapping was tested with a fixture. **The `.bat` scripts and live Windows probes have not been run on native Windows.** |

The test machine exposed two logical CPU threads, approximately 3.8 GiB total RAM, and no detected GPU. Those figures are not measurements of the creator’s Windows PC. Phase 1 has no CUDA dependency and always reports CPU-first mode. Hardware estimates will need a local sample workload before they can be used for render or generation timing.

## Repeat the tests

From a Command Prompt at the repository root after setup:

```bat
.venv\Scripts\python.exe -m pip install -r backend\requirements-test.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
npm --prefix frontend run build
```

The extra test requirements and browser driver are developer-only. To run the browser test, install the locked test driver once and point it at an existing Chromium-family executable:

```bat
npm --prefix tests/browser ci --no-audit --no-fund
set "KOMA_CHROMIUM_EXECUTABLE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
npm --prefix tests/browser test
```

Change the executable path if Edge or Chrome is installed elsewhere. The smoke test launches the private app on a spare loopback port, with a temporary library; it does not affect your own projects. On Linux, use `.venv/bin/python` and set `KOMA_CHROMIUM_EXECUTABLE` to the installed browser path.

### Native Windows acceptance still to run

Run `setup.bat` from a folder with spaces. Disconnect the network, run `start.bat`, then create, save and reopen a draft after stopping the console. Check the CPU/RAM/GPU and disk readings against the device, and test local FFmpeg paths if available. Do not infer a passing Windows launch from the Linux build or the wheel check.

## Not part of Phase 1

Story analysis, Story Bible and character extraction; storyboard, shot versions and approvals; media imports and local generation; animation; recorded or synthesized audio; subtitle timing and burn-in; timeline; resumable media jobs and MP4 export. The glowing-blue-flower story-to-MP4 acceptance test will be meaningful once those stages exist. The Phase 1 editor only saves the text and production preferences.
