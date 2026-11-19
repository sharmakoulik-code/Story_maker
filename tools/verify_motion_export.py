"""Reproducible visual and media checks for an unedited Blue Flower sample export."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

from backend.hardware import binary
from backend.motion.engine import FrameRenderer, evaluate
from backend.motion.export import verify_video
from backend.motion.sample import ART, blue_flower

FRAMES = (0, 95, 96, 126, 164, 215, 216, 251, 293)
# Logical-stage rectangles; output crops use 2× the coordinates.
FOREST = (40, 40, 500, 290)
FLOWER = (348, 526, 470, 744)
EYES = (87, 450, 230, 500)
ARM = (207, 498, 321, 642)


def check(ok: bool, why: str) -> None:
    if not ok:
        raise ValueError(why)


def rgb(file: Path) -> Image.Image:
    with Image.open(file) as image:
        return image.convert('RGB')


def difference(a: Image.Image, b: Image.Image, rect=None, *, scale=2) -> dict:
    diff = ImageChops.difference(a, b)
    if rect:
        diff = diff.crop(tuple(x * scale for x in rect))
    r, g, b = diff.split()
    peaks = ImageChops.lighter(ImageChops.lighter(r, g), b).histogram()
    pixels = diff.width * diff.height
    return {
        'rgb_mae': round(sum(ImageStat.Stat(diff).mean) / 3, 6),
        'pixels_changed': pixels - peaks[0],
        'percent_over_8': round(100 * sum(peaks[9:]) / pixels, 5),
    }


def sample_deltas(views: dict[int, Image.Image], scale: int) -> dict:
    return {
        'blink': {name: difference(views[96], views[126], roi, scale=scale)
                  for name, roi in [('forest', FOREST), ('flower', FLOWER), ('eyes', EYES)]},
        'reach': {name: difference(views[96], views[164], roi, scale=scale)
                  for name, roi in [('forest', FOREST), ('flower', FLOWER), ('arm', ARM)]},
    }


def frame_for(positions: tuple[int, ...], scale: int) -> dict[int, Image.Image]:
    stills: dict[int, Image.Image] = {}
    files = {path.stem: path for path in ART.glob('bf-*.webp')}
    start = 0
    for cut in blue_flower().shots:
        end = start + cut.output_frames
        wanted = [at for at in positions if start <= at < end]
        if wanted:
            renderer = FrameRenderer(cut, files, scale=scale)
            for at in wanted:
                stills[at] = renderer.frame(at-start).convert('RGB')
            del renderer
        start = end
    return stills


def frozen_pose() -> bool:
    cut = blue_flower().shots[1]
    invariant = {'forest', 'ferns', 'petals', 'stem', 'halo'}
    camera, draws = evaluate(cut, 0)
    fixed = [draw for draw in draws if draw.id in invariant]
    for frame in range(cut.output_frames):
        other, next_draws = evaluate(cut, frame)
        if camera != other or fixed != [draw for draw in next_draws if draw.id in invariant]:
            return False
    return True


def proof_image(stills: dict[int, Image.Image], output: Path) -> None:
    sheet = Image.new('RGB', (852, 570), '#121922')
    draw = ImageDraw.Draw(sheet)
    draw.text((14, 12), 'BLUE FLOWER  /  LOCKED CAMERA CHECK', fill='#baeed7', font=ImageFont.load_default(size=19))
    draw.text((14, 37), 'Decoded frames from one shot. The character moves; the background does not.', fill='#adbdcf', font=ImageFont.load_default(size=14))
    for i, (frame, label) in enumerate(((96, 'Eyes open'), (126, 'Blink'), (164, 'Hand raised'))):
        x = 14 + i*279
        sheet.paste(stills[frame].resize((266, 473), Image.Resampling.LANCZOS), (x,61))
        draw.text((x, 543), f'{label}  /  frame {frame}  /  {frame/30:.2f}s', fill='#deebf3', font=ImageFont.load_default(size=14))
    sheet.save(output)


def inspect(mp4: Path, ffmpeg: str, ffprobe: str, *, canvas_dir: Path | None = None, evidence_dir: Path | None = None) -> dict:
    mp4 = mp4.resolve(strict=True)
    verify_video(ffprobe, mp4, 294)
    stream = json.loads(subprocess.check_output([
        ffprobe, '-v', 'error', '-protocol_whitelist', 'file,pipe', '-count_frames', '-show_streams', '-of', 'json', str(mp4),
    ], timeout=60))['streams']
    check(len(stream) == 1 and stream[0].get('nb_read_frames') == '294', 'Expected 294 decodable video frames and no audio.')
    with TemporaryDirectory(prefix='Koma decoded frames ') as temp:
        select = '+'.join(f'eq(n,{n})' for n in FRAMES)
        subprocess.run([ffmpeg, '-hide_banner', '-v', 'error', '-xerror', '-nostdin', '-threads', '2', '-filter_threads', '1',
                        '-protocol_whitelist', 'file,pipe', '-i', str(mp4), '-vf', f"select='{select}'", '-fps_mode', 'vfr',
                        '-threads', '2', str(Path(temp) / '%02d.png')], check=True, timeout=60)
        decoded = {n: rgb(Path(temp) / f'{i:02}.png') for i, n in enumerate(FRAMES, start=1)}
    check(frozen_pose(), 'Camera/forest/foreground unexpectedly changed inside the locked shot.')
    raw = frame_for(FRAMES, scale=2)
    raw_deltas = sample_deltas(raw, scale=2)
    encoded_deltas = sample_deltas(decoded, scale=2)
    for step, moving in [('blink', 'eyes'), ('reach', 'arm')]:
        for fixed in ('forest', 'flower'):
            check(raw_deltas[step][fixed]['pixels_changed'] == 0, f'Lossless {step}: {fixed} changed.')
            check(encoded_deltas[step][fixed]['rgb_mae'] < 3, f'Encoded {step}: {fixed} drifted.')
        check(raw_deltas[step][moving]['rgb_mae'] > 9, f'Lossless {step}: character did not move enough.')
        check(encoded_deltas[step][moving]['rgb_mae'] > 8, f'Encoded {step}: character action missing.')
    align = {n: difference(decoded[n], raw[n])['rgb_mae'] for n in FRAMES}
    check(max(align.values()) < 5, 'One or more encoded frames did not match the source render.')
    cuts = {f'{a}–{b}': difference(decoded[a], decoded[b])['rgb_mae'] for a,b in [(95,96),(215,216)]}
    check(min(cuts.values()) > 9, 'The 3-shot sequence did not produce two distinct cuts.')
    video = stream[0]
    with mp4.open('rb') as file:
        sha256 = hashlib.file_digest(file, 'sha256').hexdigest()
    result = {
        'media': {key: video.get(key) for key in ('codec_name','profile','width','height','avg_frame_rate','pix_fmt',
                                                  'sample_aspect_ratio','color_space','nb_read_frames','duration')},
        'bytes': mp4.stat().st_size, 'sha256': sha256, 'locked_transforms_120_frames': 'identical',
        'lossless_deltas': raw_deltas, 'mp4_deltas': encoded_deltas,
        'mp4_to_lossless_rgb_mae': align, 'cut_rgb_mae': cuts,
    }
    if canvas_dir:
        browser = {n: rgb(canvas_dir / f'canvas-{n}.png') for n in FRAMES}
        logical = frame_for(FRAMES, scale=1)
        canvas_delta = {n: difference(browser[n], logical[n])['rgb_mae'] for n in FRAMES}
        check(max(canvas_delta.values()) < 2.5, 'The browser drew a different pose, cut or camera.')
        stats = sample_deltas(browser, scale=1)
        for step, moving in [('blink', 'eyes'), ('reach', 'arm')]:
            for fixed in ('forest', 'flower'):
                check(stats[step][fixed]['pixels_changed'] == 0, f'Canvas {step}: {fixed} changed.')
            check(stats[step][moving]['rgb_mae'] > 9, f'Canvas {step}: character action missing.')
        result.update(canvas_deltas=stats, canvas_to_lossless_rgb_mae=canvas_delta)
    if evidence_dir:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        proof_image(decoded, evidence_dir / 'locked-camera-proof.png')
        (evidence_dir / 'blue-flower-proof.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mp4', type=Path)
    parser.add_argument('--ffmpeg', default='', help='Explicit path to your local FFmpeg binary.')
    parser.add_argument('--ffprobe', default='', help='Explicit path to your local FFprobe binary.')
    parser.add_argument('--canvas-dir', type=Path, help='Optional screenshots captured by the browser export test.')
    parser.add_argument('--evidence-dir', type=Path, help='Save verification metrics and a decoded comparison strip here.')
    args = parser.parse_args()
    ffmpeg, ffprobe = binary('ffmpeg', args.ffmpeg), binary('ffprobe', args.ffprobe)
    if not ffmpeg or not ffprobe:
        parser.error('FFmpeg and FFprobe must be present on PATH or specified by absolute paths.')
    print(json.dumps(inspect(args.mp4, ffmpeg, ffprobe, canvas_dir=args.canvas_dir, evidence_dir=args.evidence_dir), indent=2))


if __name__ == '__main__':
    main()
