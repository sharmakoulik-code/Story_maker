"""2D evaluator and streaming Pillow compositor. The Canvas preview mirrors the evaluator."""
from __future__ import annotations

from bisect import bisect_right
from collections import OrderedDict
from dataclasses import dataclass
from math import ceil, cos, floor, radians, sin
from pathlib import Path
from typing import NamedTuple

from PIL import Image

from .models import HEIGHT, MAX_SHOT_PIXELS, WIDTH, CameraPose, Pose, Shot

# Column-vector Canvas convention: x' = a*x + c*y + e, y' = b*x + d*y + f.
class Matrix(NamedTuple):
    a: float = 1
    b: float = 0
    c: float = 0
    d: float = 1
    e: float = 0
    f: float = 0

    def point(self, x: float, y: float) -> tuple[float, float]:
        return self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f

    def __matmul__(self, other: Matrix) -> Matrix:
        a, b, c, d, e, f = self
        u, v, w, z, x, y = other
        return Matrix(a*u + c*v, b*u + d*v, a*w + c*z, b*w + d*z, a*x + c*y + e, b*x + d*y + f)


def layer_transform(pose: Pose, px: float, py: float) -> Matrix:
    c, s = cos(radians(pose.rotation)), sin(radians(pose.rotation))
    a, b, c, d = c * pose.scale_x, s * pose.scale_x, -s * pose.scale_y, c * pose.scale_y
    return Matrix(a, b, c, d, pose.x - a*px - c*py, pose.y - b*px - d*py)


def sample(base, keys, frame: float):
    """Base is frame zero unless overridden. Easing belongs to the destination key; booleans step."""
    if not keys:
        return base
    index = bisect_right(keys, frame, key=lambda key: key.frame)
    before = keys[index - 1] if index else base
    if index == len(keys) or keys[index].ease == "hold":
        return before
    after = keys[index]
    start = before.frame if index else 0
    t = (frame - start) / (after.frame - start)
    if after.ease == "smooth":
        t = t*t*(3 - 2*t)
    values = {}
    for field in type(base).model_fields:
        a, b = getattr(before, field), getattr(after, field)
        values[field] = a if isinstance(a, bool) or a == b else a + (b - a)*t
    return type(base).model_construct(**values)


@dataclass(frozen=True)
class Draw:
    id: str
    asset: str
    matrix: Matrix  # Native source pixels → stage pixels (logical 540 × 960).
    opacity: float


def evaluate(shot: Shot, output_frame: int) -> tuple[Matrix, list[Draw]]:
    time = min(shot.frames - 1, max(0, output_frame) * shot.speed)
    by_id = {layer.id: layer for layer in shot.layers}
    resolved: dict[str, tuple[Matrix, float]] = {}

    def world(key: str) -> tuple[Matrix, float]:
        if key not in resolved:
            layer = by_id[key]
            pose = sample(layer.pose, layer.keys, time)
            matrix = layer_transform(pose, layer.pivot_x, layer.pivot_y)
            opacity = pose.opacity if pose.visible else 0
            if layer.parent:
                parent, alpha = world(layer.parent)
                matrix, opacity = parent @ matrix, alpha * opacity
            resolved[key] = matrix, opacity
        return resolved[key]

    camera = shot.camera
    view: CameraPose = camera.pose if camera.mode == "locked" else sample(camera.pose, camera.keys, time)
    x, y, z = view.x, view.y, view.zoom
    if camera.mode == "tracking" and camera.target in by_id:
        target = by_id[camera.target]
        tracked, _ = world(target.id)
        tx, ty = tracked.point(target.pivot_x, target.pivot_y)
        x, y = x + tx, y + ty
    projection = Matrix(z, 0, 0, z, WIDTH/2 - x*z, HEIGHT/2 - y*z)
    draws = []
    for layer in shot.layers:
        if layer.asset:
            matrix, opacity = world(layer.id)
            if opacity > 0:
                draws.append(Draw(layer.id, layer.asset, projection @ matrix @ Matrix(.5, 0, 0, .5), opacity))
    return projection, draws


class FrameRenderer:
    """Only the current shot's sources, one output frame, and a bounded patch cache are resident."""
    def __init__(self, shot: Shot, files: dict[str, Path], scale: int = 2) -> None:
        self.shot, self.scale = shot, scale
        self.size = (WIDTH*scale, HEIGHT*scale)
        self.assets: dict[str, Image.Image] = {}
        pixels = 0
        for key in {layer.asset for layer in shot.layers if layer.asset}:
            with Image.open(files[key], formats=("WEBP",)) as source:
                pixels += source.width * source.height
                if source.width > 2*WIDTH or source.height > 2*HEIGHT or pixels > MAX_SHOT_PIXELS or source.n_frames != 1:
                    raise ValueError("Managed artwork must be bounded still layers.")
                self.assets[key] = source.convert("RGBa")  # Premultiplied alpha for clean transformed edges.
        self.cache: OrderedDict[str, tuple[Draw, Image.Image, tuple[int, int]]] = OrderedDict()
        self.cached_bytes = 0

    def patch(self, draw: Draw) -> tuple[Image.Image, tuple[int, int]] | None:
        old = self.cache.pop(draw.id, None)
        if old:
            if old[0] == draw:
                self.cache[draw.id] = old
                return old[1], old[2]
            self.cached_bytes -= old[1].width * old[1].height * 4
        image = self.assets[draw.asset]
        matrix = Matrix(self.scale, 0, 0, self.scale) @ draw.matrix
        points = [matrix.point(x, y) for x in (0, image.width) for y in (0, image.height)]
        left, top = max(0, floor(min(p[0] for p in points))), max(0, floor(min(p[1] for p in points)))
        right = min(self.size[0], ceil(max(p[0] for p in points)))
        bottom = min(self.size[1], ceil(max(p[1] for p in points)))
        a,b,c,d,e,f = matrix
        det = a*d - b*c
        if right <= left or bottom <= top or abs(det) < 1e-10:
            return None
        size = right-left, bottom-top
        patch = image.transform(size, Image.Transform.AFFINE, (
            d/det, -c/det, (d*(left-e) - c*(top-f))/det,
            -b/det, a/det, (-b*(left-e) + a*(top-f))/det,
        ), resample=Image.Resampling.BILINEAR).convert("RGBA")
        if draw.opacity < 1:
            patch.putalpha(patch.getchannel("A").point([round(k*draw.opacity) for k in range(256)]))
        self.cache[draw.id] = (draw, patch, (left, top))
        self.cached_bytes += patch.width * patch.height * 4
        while self.cached_bytes > 32 * 1024**2:
            _, (_, removed, _) = self.cache.popitem(last=False)
            self.cached_bytes -= removed.width * removed.height * 4
        return patch, (left, top)

    def frame(self, index: int) -> Image.Image:
        _, draws = evaluate(self.shot, index)
        frame = Image.new("RGBA", self.size, (9, 16, 28, 255))
        for draw in draws:
            patch = self.patch(draw)
            if patch:
                image, position = patch
                frame.alpha_composite(image, dest=position)
        return frame
