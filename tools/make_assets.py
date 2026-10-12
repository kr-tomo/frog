#!/usr/bin/env python3
"""Procedural art generator for the "Frog Jump" (개구리 점프) seasonal maps.

Requirements: Python 3, numpy, scipy, Pillow (WebP support).
Everything is painted procedurally and deterministically (seeded per
theme/asset via crc32), supersampled and downscaled with LANCZOS.

Usage
-----
    python3 tools/make_assets.py                 # every theme + shark
    python3 tools/make_assets.py winter autumn   # only these themes
    python3 tools/make_assets.py shark           # only the shared shark sheet

Output (under assets/, all images are 2x of the 540x960 logical canvas)
-----------------------------------------------------------------------
    assets/shark.png                    1024x128 RGBA, 4 frames of 256x128, faces right
    assets/themes/<id>/water.webp       1080x1920 opaque river water
    assets/themes/<id>/island_start.webp 1080x340 RGBA, shoreline = top edge
    assets/themes/<id>/island_goal.webp  1080x220 RGBA, shoreline = bottom edge,
                                         checkered finish strip y=176..204
    assets/themes/<id>/stone.png        600x200 RGBA oval stepping stone (no shadow)
    assets/themes/<id>/stone_slippery.png 600x200 RGBA wet/slimy (ice in winter)
    assets/themes/<id>/shallow.png      240x160 RGBA faint shoal shadow (alpha<=0.45)
    assets/themes/<id>/particles.png    256x64 RGBA, four 64x64 frames
    assets/themes/<id>/icon.png         96x96 RGBA season icon

How to add a theme
------------------
Add an entry to the THEMES dict (bottom of the "themes" section):

    THEMES['monsoon'] = dict(
        pal=dict(water_top=(r,g,b), water_bot=(r,g,b), water_hi=(r,g,b),
                 water_var=3.0,                      # large-scale colour wobble
                 gnd_a=..., gnd_b=..., sand_a=..., sand_b=...,   # island ground / shore band
                 wet=..., foam=...,                  # shoreline line colours
                 tuft=[(r,g,b), ...],                # tiny ground strokes
                 stone=(r,g,b), shoal=(r,g,b), ring=(r,g,b),
                 algae=[(r,g,b), (r,g,b)]),
        ice=False,                                   # True -> glazed-ice slippery stone
        floaters=fn(img, rng),     # sparse tiny things on the water (paste_sprite helper)
        decor=fn(d, x, y, ss, rng),# one island decoration at (x, y) on an ImageDraw at scale ss
        stone_col=fn(ctx),         # tint / moss / snow on the stone colour array
        stone_over=fn(d, SS, rng), # sprites on the stone (petals, leaves, sparkles ...)
        particles=[fn(d, cx, cy, s)] * 4,   # four 64x64 particle frames (s = motif size)
        icon=fn(d, c, s),          # icon artwork (fills only; outline is auto-added)
        icon_outline=(r, g, b),
    )

Shape helpers (petal, blossom, daisy, sunflower, maple, ginkgo, oak, snowflake,
sparkle, mushroom, evergreen, ...) take (d, cx, cy, size, rot, ...) where d is a
PIL ImageDraw, and can be reused freely.  Then run `python3 tools/make_assets.py monsoon`.
"""
import math
import os
import sys
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'assets'))


# ----------------------------------------------------------------------------
# generic helpers
# ----------------------------------------------------------------------------
def rng_for(*parts):
    return np.random.default_rng(zlib.crc32('/'.join(parts).encode()))


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def col(c):
    return np.array(c, np.float32)


def lerp(a, b, t):
    return a + (b - a) * t


def vnoise(h, w, cell, rng):
    gh, gw = h // cell + 4, w // cell + 4
    g = rng.random((gh, gw)).astype(np.float32)
    big = np.asarray(Image.fromarray(g, 'F').resize((gw * cell, gh * cell), Image.BICUBIC))
    return big[cell:cell + h, cell:cell + w]


def fbm(h, w, rng, cells, weights=None):
    """Zero-mean unit-std multi-octave smooth noise."""
    weights = weights or [1.0] * len(cells)
    acc = np.zeros((h, w), np.float32)
    for c, wt in zip(cells, weights):
        n = vnoise(h, w, c, rng)
        acc += wt * (n - n.mean()) / (n.std() + 1e-6)
    return (acc - acc.mean()) / (acc.std() + 1e-6)


def to_img(a, mode='RGB'):
    return Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8), mode)


def save(img, path, **kw):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, **kw)


def lanczos(img, size):
    return img.resize(size, Image.LANCZOS)


# ----------------------------------------------------------------------------
# shape painters: f(d, cx, cy, s, rot, ...)   s = overall diameter in px
# ----------------------------------------------------------------------------
def T(pts, cx, cy, s, rot=0.0, sx=1.0):
    c, sn = math.cos(rot), math.sin(rot)
    return [(cx + (x * sx * c - y * sn) * s, cy + (x * sx * sn + y * c) * s) for x, y in pts]


def chaikin(pts, n=2):
    for _ in range(n):
        out = []
        m = len(pts)
        for i in range(m):
            p, q = pts[i], pts[(i + 1) % m]
            out.append((0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]))
            out.append((0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1]))
        pts = out
    return pts


_R = [(0, 0.5), (0.12, 0.36), (0.26, 0.08), (0.34, -0.2), (0.3, -0.4), (0.17, -0.5), (0.05, -0.47)]
PETAL = chaikin(_R + [(0, -0.43)] + [(-x, y) for x, y in reversed(_R[1:])], 2)


def ell(cx, cy, rx, ry, rot=0.0, n=24):
    c, s = math.cos(rot), math.sin(rot)
    out = []
    for k in range(n):
        t = 2 * math.pi * k / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cx + x * c - y * s, cy + x * s + y * c))
    return out


def circle(d, cx, cy, r, fill, outline=None):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill, outline=outline)


def petal(d, cx, cy, s, rot=0.0, fill=(255, 190, 205), hi=None, edge=None, sx=1.0):
    d.polygon(T(PETAL, cx, cy, s, rot, sx), fill=fill, outline=edge)
    if hi:
        d.polygon(T(PETAL, cx, cy - 0.04 * s, s * 0.58, rot, sx * 0.7), fill=hi)


def blossom(d, cx, cy, s, rot=0.0, fill=(255, 176, 198), hi=(255, 214, 224),
            center=(255, 226, 120), stamen=(214, 96, 140), edge=None):
    ps = s * 0.56
    for k in range(5):
        th = rot + k * 2 * math.pi / 5
        ox, oy = math.sin(th), -math.cos(th)
        petal(d, cx + ox * ps * 0.42, cy + oy * ps * 0.42, ps, th, fill, hi, edge, sx=1.22)
    circle(d, cx, cy, s * 0.10, center)
    for k in range(5):
        th = rot + k * 2 * math.pi / 5 + 0.3
        circle(d, cx + math.sin(th) * s * 0.17, cy - math.cos(th) * s * 0.17, s * 0.028, stamen)


def daisy(d, cx, cy, s, rot=0.0, fill=(250, 250, 244), center=(244, 200, 70), n=10):
    for k in range(n):
        th = rot + k * 2 * math.pi / n
        d.polygon(ell(cx + math.sin(th) * s * 0.30, cy - math.cos(th) * s * 0.30,
                      s * 0.21, s * 0.075, th + math.pi / 2), fill=fill)
    circle(d, cx, cy, s * 0.15, center)


def sunflower(d, cx, cy, s, rot=0.0, fill=(246, 200, 50), disc=(120, 76, 36), n=16):
    for ring, (rr, ln) in enumerate(((0.33, 0.20), (0.27, 0.19))):
        for k in range(n):
            th = rot + (k + 0.5 * ring) * 2 * math.pi / n
            d.polygon(ell(cx + math.sin(th) * s * rr, cy - math.cos(th) * s * rr,
                          s * ln, s * 0.062, th + math.pi / 2, 16),
                      fill=tuple(int(c * (0.92 + 0.08 * ring)) for c in fill))
    circle(d, cx, cy, s * 0.24, disc)
    circle(d, cx, cy, s * 0.16, tuple(int(c * 0.78) for c in disc))
    for k in range(7):
        th = k * 2.4
        circle(d, cx + math.cos(th) * s * 0.10, cy + math.sin(th) * s * 0.10, s * 0.018,
               tuple(min(255, int(c * 1.25)) for c in disc))


def maple_pts():
    peaks = [(0, 0.50, 26), (56, 0.48, 26), (-56, 0.48, 26), (112, 0.36, 24), (-112, 0.36, 24)]
    pts = []
    for k in range(0, 360, 3):
        a = k if k <= 180 else k - 360
        r = 0.22
        for pa, pr, hw in peaks:
            dd = abs(((a - pa + 180) % 360) - 180)
            r = max(r, 0.22 + (pr - 0.22) * max(0.0, 1 - dd / hw) ** 0.9)
        r += 0.018 * math.cos(math.radians(a) * 11)
        t = math.radians(a)
        pts.append((r * math.sin(t), -r * math.cos(t) + 0.03))
    return pts


MAPLE = maple_pts()


def maple(d, cx, cy, s, rot=0.0, fill=(214, 60, 40), vein=(150, 30, 28), stem=True, vw=1.0):
    if stem:
        d.line(T([(0, 0.18), (0, 0.52)], cx, cy, s, rot), fill=vein, width=max(1, int(s * 0.045 * vw)))
    d.polygon(T(MAPLE, cx, cy, s, rot), fill=fill)
    w = max(1, int(s * 0.03 * vw))
    for a in (0, 52, -52, 108, -108):
        t = math.radians(a)
        d.line(T([(0, 0.2), (0.30 * math.sin(t), 0.03 - 0.30 * math.cos(t))], cx, cy, s, rot), fill=vein, width=w)


def ginkgo(d, cx, cy, s, rot=0.0, fill=(240, 196, 52), vein=(196, 150, 30)):
    pts = [(0, 0.40)]
    for a in range(-64, 65, 2):
        t = math.radians(a)
        r = 0.80 * (1 - 0.30 * math.exp(-(a / 6.0) ** 2)) * (0.97 + 0.03 * math.cos(a * 0.7))
        pts.append((r * math.sin(t), 0.40 - r * math.cos(t)))
    d.line(T([(0, 0.4), (0, 0.55)], cx, cy, s, rot), fill=vein, width=max(1, int(s * 0.05)))
    d.polygon(T(pts, cx, cy, s, rot), fill=fill)
    for a in range(-48, 49, 16):
        t = math.radians(a)
        d.line(T([(0, 0.38), (0.6 * math.sin(t), 0.40 - 0.6 * math.cos(t))], cx, cy, s, rot), fill=vein,
               width=max(1, int(s * 0.022)))


def oak(d, cx, cy, s, rot=0.0, fill=(150, 98, 52), vein=(104, 64, 34)):
    right, left = [], []
    for i in range(41):
        u = i / 40
        hw = 0.26 * math.sin(math.pi * u ** 0.85) * (0.70 + 0.30 * math.cos(2 * math.pi * 3 * u + 0.4))
        y = -0.5 + 0.95 * u
        right.append((hw, y))
        left.append((-hw, y))
    d.line(T([(0, 0.4), (0, 0.55)], cx, cy, s, rot), fill=vein, width=max(1, int(s * 0.05)))
    d.polygon(T(right + left[::-1], cx, cy, s, rot), fill=fill)
    d.line(T([(0, 0.42), (0, -0.44)], cx, cy, s, rot), fill=vein, width=max(1, int(s * 0.03)))
    for yy in (-0.25, -0.05, 0.15):
        for sg in (-1, 1):
            d.line(T([(0, yy + 0.1), (sg * 0.16, yy)], cx, cy, s, rot), fill=vein, width=max(1, int(s * 0.02)))


def snowflake(d, cx, cy, s, rot=0.0, fill=(255, 255, 255), w=None, variant=0):
    R = s * 0.5
    w = w or max(1, int(s * 0.07))
    ends = []

    def seg(p, q, ww=w):
        d.line([p, q], fill=fill, width=int(ww))
        circle(d, p[0], p[1], ww / 2, fill)
        circle(d, q[0], q[1], ww / 2, fill)

    for k in range(6):
        th = rot + k * math.pi / 3
        ux, uy = math.sin(th), -math.cos(th)
        tip = (cx + ux * R, cy + uy * R)
        seg((cx, cy), tip)
        branches = {0: [(0.55, 0.30)], 1: [(0.4, 0.22), (0.7, 0.26)], 2: [(0.62, 0.34)], 3: [(0.5, 0.2)]}[variant % 4]
        for pos, ln in branches:
            bx, by = cx + ux * R * pos, cy + uy * R * pos
            for sg in (-1, 1):
                a2 = th + sg * math.radians(58)
                seg((bx, by), (bx + math.sin(a2) * R * ln, by - math.cos(a2) * R * ln), w * 0.85)
        if variant % 4 == 2:
            d.polygon(ell(cx + ux * R * 0.93, cy + uy * R * 0.93, R * 0.1, R * 0.1, th, 4), fill=fill)
    if variant % 4 == 3:
        hexp = [(cx + math.sin(rot + k * math.pi / 3) * R * 0.42, cy - math.cos(rot + k * math.pi / 3) * R * 0.42)
                for k in range(7)]
        d.line(hexp, fill=fill, width=int(w * 0.9))
    circle(d, cx, cy, w * 0.9, fill)


def sparkle(d, cx, cy, s, rot=0.0, fill=(255, 255, 255), thin=1.0):
    pts = []
    for k in range(96):
        t = 2 * math.pi * k / 96
        x, y = (math.cos(t) ** 3) * thin, math.sin(t) ** 3
        pts.append((x * 0.5, y * 0.5))
    # concave 4-point star: x/y astroid (thin shrinks horizontal arm only if thin<1)
    d.polygon(T(pts, cx, cy, s, rot), fill=fill)


def mushroom(d, cx, cy, s, rot=0.0, cap=(200, 90, 70), stem=(240, 228, 206), dots=(250, 240, 226)):
    d.polygon(ell(cx, cy + s * 0.18, s * 0.11, s * 0.22, 0), fill=stem)
    d.pieslice((cx - s * 0.42, cy - s * 0.40, cx + s * 0.42, cy + s * 0.34), 180, 360, fill=cap)
    d.chord((cx - s * 0.42, cy - s * 0.40, cx + s * 0.42, cy + s * 0.34), 0, 180, fill=tuple(int(c * 0.82) for c in cap))
    d.polygon([(cx - s * 0.42, cy - s * 0.03), (cx + s * 0.42, cy - s * 0.03), (cx + s * 0.38, cy + s * 0.07),
               (cx - s * 0.38, cy + s * 0.07)], fill=tuple(int(c * 0.82) for c in cap))
    for dx, dy, rr in ((-0.2, -0.17, 0.07), (0.05, -0.27, 0.06), (0.22, -0.13, 0.065)):
        circle(d, cx + dx * s, cy + dy * s, rr * s, dots)


def evergreen(d, cx, cy, s, rot=0.0, dark=(70, 112, 102), light=(104, 146, 132), snow=(238, 246, 252)):
    mid = tuple((p + q) // 2 for p, q in zip(dark, light))
    for ring, (rad, c) in enumerate(((0.5, dark), (0.40, mid), (0.29, light))):
        n = 7
        pts = []
        for k in range(n * 2):
            r = rad if k % 2 == 0 else rad * 0.50
            t = rot + ring * math.pi / n + k * math.pi / n
            pts.append((cx + math.sin(t) * r * s, cy - math.cos(t) * r * s))
        d.polygon(chaikin(pts, 1), fill=c)
    for k in range(5):
        t = rot + k * 2 * math.pi / 5 + 0.4
        d.polygon(ell(cx + math.sin(t) * s * 0.18, cy - math.cos(t) * s * 0.18, s * 0.07, s * 0.045, t, 8), fill=snow)
    circle(d, cx, cy, s * 0.05, snow)


def snow_lump(d, cx, cy, s, rot=0.0, fill=(244, 249, 253), shade=(206, 222, 238)):
    d.polygon(ell(cx + s * 0.03, cy + s * 0.05, s * 0.5, s * 0.3, rot), fill=shade)
    d.polygon(ell(cx, cy, s * 0.48, s * 0.28, rot), fill=fill)


def sun_icon(d, c, s):
    for k in range(10):
        t = k * math.pi / 5
        pts = [(c + math.sin(t - 0.13) * s * 0.34, c - math.cos(t - 0.13) * s * 0.34),
               (c + math.sin(t) * s * 0.5, c - math.cos(t) * s * 0.5),
               (c + math.sin(t + 0.13) * s * 0.34, c - math.cos(t + 0.13) * s * 0.34)]
        d.polygon(pts, fill=(255, 168, 40))
    circle(d, c, c, s * 0.31, (255, 206, 60))
    circle(d, c, c, s * 0.23, (255, 226, 96))
    circle(d, c - s * 0.07, c - s * 0.08, s * 0.07, (255, 244, 170))


# ----------------------------------------------------------------------------
# sprite helpers
# ----------------------------------------------------------------------------
def sprite(fn, size, ss=4, pad=1.35):
    n = int(size * pad)
    im = Image.new('RGBA', (n * ss, n * ss), (0, 0, 0, 0))
    fn(ImageDraw.Draw(im), n * ss / 2, n * ss / 2, size * ss)
    return lanczos(im, (n, n))


def paste_sprite(img, fn, size, x, y, alpha=1.0, ss=4):
    sp = sprite(fn, size, ss)
    if alpha < 1:
        a = sp.getchannel('A').point(lambda v: int(v * alpha))
        sp.putalpha(a)
    img.paste(sp, (int(x - sp.width / 2), int(y - sp.height / 2)), sp)


def glow_layer(size, fn, glow_col, radius, strength=1.0):
    """RGBA layer with fn drawn sharp on top of a blurred glow copy."""
    base = Image.new('RGBA', size, (0, 0, 0, 0))
    g = Image.new('RGBA', size, (0, 0, 0, 0))
    fn(ImageDraw.Draw(g), glow_col)
    g = g.filter(ImageFilter.GaussianBlur(radius))
    a = g.getchannel('A').point(lambda v: min(255, int(v * strength)))
    g.putalpha(a)
    base = Image.alpha_composite(base, g)
    sharp = Image.new('RGBA', size, (0, 0, 0, 0))
    fn(ImageDraw.Draw(sharp), None)
    return Image.alpha_composite(base, sharp)


def scatter(rng, n, xr, yr, min_d, avoid=()):
    pts = []
    tries = 0
    while len(pts) < n and tries < n * 60:
        tries += 1
        p = (rng.uniform(*xr), rng.uniform(*yr))
        if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 > min_d ** 2 for q in pts):
            pts.append(p)
    return pts


# ----------------------------------------------------------------------------
# water
# ----------------------------------------------------------------------------
def paint_water(tid, th):
    W, H = 1080, 1920
    P = th['pal']
    rng = rng_for(tid, 'water')
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    base = col(P['water_top']) + (col(P['water_bot']) - col(P['water_top'])) * y
    base = np.broadcast_to(base, (H, W, 3)).copy()
    z = fbm(H, W, rng, (260, 130), (1, 0.5))
    base += z[..., None] * P['water_var'] * np.array([0.6, 1.0, 1.0], np.float32)
    hi = col(P['water_hi'])
    for cell, wid, amp in ((170, 0.014, 0.20), (95, 0.012, 0.13), (55, 0.010, 0.07)):
        d = vnoise(H, W, cell, rng) - vnoise(H, W, cell, rng)
        line = np.exp(-(d / wid) ** 2)
        patch = smooth(fbm(H, W, rng, (300, 150)), -0.3, 1.0)
        base += (hi - base) * (line * patch * amp)[..., None]
    base += (rng.normal(0, 0.9, (H, W, 1))).astype(np.float32)
    img = to_img(base)

    # thin ripple arcs, painted supersampled
    SS = 2
    lay = Image.new('L', (W * SS, H * SS), 0)
    dr = ImageDraw.Draw(lay)
    for _ in range(70):
        cx, cy = rng.uniform(40, W - 40), rng.uniform(300, H - 400)
        rx, ry = rng.uniform(26, 80), rng.uniform(7, 20)
        a0 = rng.uniform(0, 360)
        box = ((cx - rx) * SS, (cy - ry) * SS, (cx + rx) * SS, (cy + ry) * SS)
        dr.arc(box, a0, a0 + rng.uniform(80, 170), fill=int(rng.uniform(70, 130)), width=SS * 2)
    lay = lanczos(lay, (W, H)).filter(ImageFilter.GaussianBlur(0.8))
    rip = Image.new('RGB', (W, H), tuple(P['water_hi']))
    img = Image.composite(rip, img, lay.point(lambda v: int(v * 0.5)))

    th['floaters'](img, rng)
    return img


# ----------------------------------------------------------------------------
# islands
# ----------------------------------------------------------------------------
def paint_island(tid, th, kind):
    W, H = 1080, (340 if kind == 'start' else 220)
    SS = 2
    P = th['pal']
    rng = rng_for(tid, 'island_' + kind)
    Ws, Hs = W * SS, H * SS
    xs = (np.arange(Ws, dtype=np.float32) + 0.5) / SS
    ys = (np.arange(Hs, dtype=np.float32) + 0.5) / SS
    ph = rng.uniform(0, 6.28, 3)
    shore = 6 + 1.9 * np.sin(xs / 41 + ph[0]) + 1.0 * np.sin(xs / 17 + ph[1]) + 0.6 * np.sin(xs / 9 + ph[2])
    dep = ys[:, None] - shore[None, :]

    z1 = fbm(Hs, Ws, rng, (300, 110), (1, 0.6))
    z2 = fbm(Hs, Ws, rng, (12, 6), (1, 0.6))
    z3 = fbm(Hs, Ws, rng, (60, 25), (1, 0.7))
    gnd = lerp(col(P['gnd_a']), col(P['gnd_b']), smooth(z1, -1, 1)[..., None])
    gnd = gnd + (z3 * 2.2 + z2 * 1.6)[..., None]
    sand = lerp(col(P['sand_a']), col(P['sand_b']), smooth(z3, -1, 1)[..., None]) + (z2 * 1.2)[..., None]
    deff = dep + z1 * 7
    band = (1 - smooth(deff, 34, 84))[..., None]
    c = lerp(gnd, sand, band)
    wet = (1 - smooth(dep, 0, 15))[..., None]
    c = lerp(c, col(P['wet']), wet * 0.75)
    wave2 = np.exp(-((dep - 9.5 - 2.0 * np.sin(xs / 23)[None, :]) / 1.5) ** 2) * smooth(z3, -0.6, 0.4) * 0.45
    c = lerp(c, col(P['foam']), wave2[..., None])
    foam = (1 - smooth(dep, 1.0, 5.5))[..., None]
    c = lerp(c, col(P['foam']), foam * 0.95)
    alpha = np.clip(dep * SS + 0.5, 0, 1)

    # ground tufts / strokes
    tl = Image.new('RGBA', (Ws, Hs), (0, 0, 0, 0))
    td = ImageDraw.Draw(tl)
    for _ in range(int(2600 * H / 340)):
        x, yy = rng.uniform(0, W), rng.uniform(34, H)
        cc = P['tuft'][int(rng.integers(len(P['tuft'])))]
        ln = rng.uniform(5, 10)
        for k in (-1, 0, 1):
            a = k * 0.45 + rng.uniform(-0.15, 0.15)
            td.line([(x * SS, yy * SS), ((x + math.sin(a) * ln) * SS, (yy - math.cos(a) * ln) * SS)],
                    fill=cc + (120,), width=SS * 2 - 1)
    tuft = np.asarray(tl).astype(np.float32)
    ta = tuft[..., 3:4] / 255 * (1 - band) * (smooth(dep, 14, 36)[..., None])
    c = lerp(c, tuft[..., :3], ta)

    rgba = np.dstack([np.clip(c, 0, 255), alpha * 255]).astype(np.uint8)
    if kind == 'goal':
        rgba = rgba[::-1].copy()
    im = Image.fromarray(rgba, 'RGBA')

    # decorations
    ov = Image.new('RGBA', (Ws, Hs), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    if kind == 'start':
        pts = scatter(rng, 30, (40, W - 40), (72, 218), 56)
    else:
        pts = scatter(rng, 14, (40, W - 40), (92, 164), 62)
    for x, yy in pts:
        th['decor'](od, x * SS, yy * SS, SS, rng)
    ova = ov.getchannel('A').point(lambda v: int(v * 0.88))
    ov.putalpha(ova)
    im = Image.alpha_composite(im, ov)

    if kind == 'goal':
        d = ImageDraw.Draw(im)
        for row in range(2):
            for i in range(78):
                dark = (i + row) % 2 == 0
                x0, y0 = i * 14, 176 + row * 14
                d.rectangle(((x0 * SS, y0 * SS), ((x0 + 14) * SS - 1, (y0 + 14) * SS - 1)),
                            fill=(26, 26, 30, 255) if dark else (252, 252, 252, 255))
    return lanczos(im, (W, H))


# ----------------------------------------------------------------------------
# stones
# ----------------------------------------------------------------------------
def lambert(h, k=1.0):
    gy, gx = np.gradient(h)
    n = np.stack([-gx * k, -gy * k, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    L = np.array([-0.6, -0.6, 0.55], np.float32)
    L /= np.linalg.norm(L)
    return (n @ L) / L[2]


def paint_stone(tid, th, slippery):
    SS = 4
    W, H = 600 * SS, 200 * SS
    rng = rng_for(tid, 'stone_slip' if slippery else 'stone')
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    a, b = 297.0 * SS, 97.0 * SS
    u, v = (xx - W / 2 + 0.5) / a, (yy - H / 2 + 0.5) / b
    r = np.sqrt(u * u + v * v)
    gr = np.sqrt((u / a) ** 2 + (v / b) ** 2) / np.maximum(r, 1e-6)
    dist = (1 - r) / np.maximum(gr, 1e-9)  # px to the edge (supersampled)
    mask = np.clip(dist + 0.5, 0, 1)
    Wb = 15 * SS
    t = np.clip(dist / Wb, 0, 1)
    hgt = Wb * 0.85 * np.sqrt(1 - (1 - t) ** 2) + 0.22 * b * (1 - np.minimum(r, 1) ** 2)
    hgt = gaussian_filter(hgt, 1.6 * SS)
    shade = np.clip(lambert(hgt, 1.0), 0.45, 1.5)

    ice = th['ice'] and slippery
    z = fbm(H, W, rng, (220, 90, 34), (1, 0.7, 0.3))
    base = np.broadcast_to(col(th['pal']['stone']), (H, W, 3)).copy()
    base *= (1 + 0.009 * z)[..., None]
    base *= (1 + 0.012 * rng.standard_normal((H, W)).astype(np.float32))[..., None]
    ctx = dict(u=u, v=v, r=r, dist=dist, z=z, col=base, SS=SS, a=a, b=b, rng=rng, W=W, H=H)
    if not ice:
        th['stone_col'](ctx)
    base = ctx['col']
    sh = shade[..., None]
    c = base * (0.80 + 0.20 * sh) * np.where(sh > 1, 1 + (sh - 1) * 0.0, 1)  # base lit
    c = c + (sh - 1) * 46 * np.where(sh > 1, 1.0, 0.8)                        # rim light / dark
    # dark thin outline, heavier on the lower right so stones pop from water
    lr = np.clip(0.55 + 0.45 * (u * 0.6 + v * 0.9), 0, 1.2)
    ol = (1 - smooth(dist, 0, 3.4 * SS)) * (0.38 + 0.4 * lr)
    c = lerp(c, np.array([88, 96, 108], np.float32), ol[..., None])

    if slippery:
        if ice:
            cc = np.broadcast_to(col((178, 216, 242)), (H, W, 3)).copy() * (1 + 0.03 * z)[..., None]
            cc = cc * (0.84 + 0.16 * sh) + (sh - 1) * 44
            cc = lerp(cc, col((120, 170, 214)), (1 - smooth(dist, 0, 20 * SS))[..., None] * 0.35)
            c = lerp(cc, np.array([80, 112, 150], np.float32), ol[..., None])
        else:
            c = lerp(c, col((128, 178, 226)), 0.62)
            fres = (1 - smooth(dist, 0, 16 * SS))[..., None]
            c = lerp(c, col((110, 184, 236)), fres * 0.45)
        # glossy sheen
        blob = np.exp(-(((u + 0.40) / 0.22) ** 2 + ((v + 0.36) / 0.26) ** 2)) * 0.8
        band = np.exp(-(((u * 0.55 + v * 0.85) + 0.30) / 0.075) ** 2) * smooth(0.40 - u, 0.0, 0.55) * 0.45
        c = lerp(c, col((255, 255, 255)), np.clip(blob + band, 0, 0.95)[..., None])

    img = to_img(c)
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    if slippery:
        slippery_over(ov, od, th, SS, rng, ice)
    else:
        th['stone_over'](od, SS, rng)
        for _ in range(16):  # tiny pits / flecks
            x, y0 = rng.uniform(70, 530) * SS, rng.uniform(40, 160) * SS
            od.polygon(ell(x, y0, rng.uniform(2, 5) * SS, rng.uniform(1.2, 2.4) * SS, rng.uniform(0, 3)),
                       fill=(104, 108, 114, 60))
    out = img.convert('RGBA')
    out = Image.alpha_composite(out, ov)
    m = Image.fromarray((mask * 255).astype(np.uint8), 'L')
    out.putalpha(m)
    return lanczos(out, (600, 200))


def slippery_over(ov, od, th, SS, rng, ice):
    if ice:
        for _ in range(5):
            x, y = rng.uniform(150, 450) * SS, rng.uniform(60, 140) * SS
            pts = [(x, y)]
            for _ in range(7):
                x += rng.uniform(-30, 30) * SS
                y += rng.uniform(-14, 14) * SS
                pts.append((x, y))
                if rng.random() < 0.3:
                    od.line([(x, y), (x + rng.uniform(-24, 24) * SS, y + rng.uniform(-16, 16) * SS)],
                            fill=(255, 255, 255, 220), width=int(2.5 * SS))
            od.line(pts, fill=(255, 255, 255, 240), width=int(4.6 * SS))
        for _ in range(7):
            sparkle(od, rng.uniform(120, 480) * SS, rng.uniform(40, 160) * SS, rng.uniform(16, 34) * SS, 0,
                    (255, 255, 255, 255))
    else:
        al = Image.new('RGBA', ov.size, (0, 0, 0, 0))
        ad = Image.new('RGBA', ov.size, (0, 0, 0, 0))
        ald, add = ImageDraw.Draw(al), ImageDraw.Draw(ad)
        for k in range(5):
            x0 = rng.uniform(60, 330) * SS
            y0 = rng.uniform(52, 150) * SS
            ln = rng.uniform(150, 230) * SS
            wm = rng.uniform(9, 14) * SS
            top, bot, top2, bot2 = [], [], [], []
            for i in range(40):
                t = i / 39
                x = x0 + t * ln
                y = y0 + math.sin(t * 5 + k * 1.7) * 5 * SS
                w = wm * math.sin(math.pi * t) ** 0.6
                top.append((x, y - w)); bot.append((x, y + w))
                top2.append((x, y - w * 0.85)); bot2.append((x, y - w * 0.1))
            ald.polygon(top + bot[::-1], fill=th['pal']['algae'][0] + (215,))
            add.polygon(top2 + bot2[::-1], fill=th['pal']['algae'][1] + (190,))
        for layer in (al, ad):
            ov.alpha_composite(layer.filter(ImageFilter.GaussianBlur(0.9 * SS)))
    # droplets / specular dots
    for _ in range(14):
        x, y = rng.uniform(70, 530) * SS, rng.uniform(34, 166) * SS
        rr = rng.uniform(4, 8.5) * SS
        circle(od, x, y, rr, (255, 255, 255, 235))
        circle(od, x + rr * 0.3, y + rr * 0.3, rr * 0.45, (150, 205, 245, 160))
    for _ in range(3):
        sparkle(od, rng.uniform(120, 460) * SS, rng.uniform(46, 150) * SS, rng.uniform(26, 44) * SS, 0,
                (255, 255, 255, 255))


# ----------------------------------------------------------------------------
# shallow, particles, icon
# ----------------------------------------------------------------------------
def paint_shallow(tid, th):
    W, H = 240, 160
    rng = rng_for(tid, 'shallow')
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    n = fbm(H, W, rng, (40, 16), (1, 0.6))
    r = np.sqrt(((xx - W / 2 + 0.5) / (W * 0.40)) ** 2 + ((yy - H / 2 + 0.5) / (H * 0.40)) ** 2) + 0.045 * n
    core = smooth(1 - r, 0, 0.62) * 0.40
    ring = np.exp(-((r - 0.86) / 0.035) ** 2) * 0.55
    ring_a = ring * 0.34 * smooth(1.25 - r, 0, 0.2)
    A = np.maximum(core, ring_a) + 0.02 * core * n
    A = np.clip(A, 0, 0.45)
    c = lerp(col(th['pal']['shoal']), col(th['pal']['ring']), np.clip(ring * 1.2, 0, 1)[..., None])
    rgba = np.dstack([c, A * 255]).astype(np.uint8)
    return Image.fromarray(rgba, 'RGBA')


def paint_particles(tid, th):
    SS = 8
    sheet = Image.new('RGBA', (256, 64), (0, 0, 0, 0))
    for i, fn in enumerate(th['particles']):
        fr = Image.new('RGBA', (64 * SS, 64 * SS), (0, 0, 0, 0))
        fn(fr, 32 * SS, 32 * SS, 44 * SS, i, SS)
        sheet.alpha_composite(lanczos(fr, (64, 64)), (64 * i, 0))
    return sheet


def paint_icon(tid, th):
    SS = 8
    N = 96 * SS
    fg = Image.new('RGBA', (N, N), (0, 0, 0, 0))
    th['icon'](ImageDraw.Draw(fg), N / 2, 76 * SS)
    a = fg.getchannel('A')
    ol = a.filter(ImageFilter.GaussianBlur(3.4 * SS)).point(lambda v: 255 if v > 22 else 0)
    ol = ol.filter(ImageFilter.GaussianBlur(0.6 * SS))
    out = Image.new('RGBA', (N, N), tuple(th['icon_outline']) + (0,))
    out.putalpha(ol)
    out = Image.alpha_composite(out, fg)
    return lanczos(out, (96, 96))


# ----------------------------------------------------------------------------
# shark
# ----------------------------------------------------------------------------
def shark_frame(i):
    """물 밖으로 입을 벌린 머리만 내민 상어 (오른쪽을 봄). 4프레임: 턱이 벌어졌다 닫히며 살짝 출렁인다."""
    SS = 4
    W, H = 256 * SS, 128 * SS
    ph = 2 * math.pi * i / 4
    openv = 22 + 10 * math.sin(ph)            # 턱 벌어짐 (px)
    bob = 2.0 * math.sin(ph + 1.2)
    wl = (106 + bob) * SS                     # 수면 높이
    S = lambda pts: [(x * SS, (y + bob) * SS) for x, y in pts]
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 머리 윗부분(등~주둥이~윗턱 아랫선)
    top = chaikin(S([(52, 120), (66, 70), (96, 40), (140, 33), (186, 44), (222, 62), (232, 72), (206, 76),
                     (176, 74), (146, 80), (118, 84), (96, 112)]), 3)
    d.polygon(top, fill=(112, 138, 160, 255))
    # 등 쪽 어두운 음영
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).polygon(chaikin(S([(60, 80), (80, 50), (120, 36), (170, 40), (210, 58), (150, 54), (100, 66)]), 3),
                               fill=(64, 88, 112, 255))
    sh = sh.filter(ImageFilter.GaussianBlur(4 * SS))
    m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).polygon(top, fill=255)
    sh.putalpha(ImageChopsMin(sh.getchannel('A'), m)); img = Image.alpha_composite(img, sh)
    # 입 안쪽(붉은색)
    d = ImageDraw.Draw(img)
    jaw_tip = (214, 78 + openv)
    mouth = chaikin(S([(110, 86), (150, 82), (206, 78), jaw_tip, (170, 92 + openv * 0.6), (126, 100 + openv * 0.3)]), 2)
    d.polygon(mouth, fill=(150, 40, 52, 255))
    # 아랫턱
    low = chaikin(S([(104, 100), (126, 100 + openv * 0.3), (170, 92 + openv * 0.6), jaw_tip, (210, 84 + openv),
                     (190, 108 + openv), (140, 118 + openv * 0.4), (100, 122)]), 3)
    d.polygon(low, fill=(176, 198, 214, 255))
    # 이빨(윗니·아랫니)
    for k in range(6):
        x = 150 + k * 11; y0 = 78 - (x - 150) * 0.03
        d.polygon(S([(x, y0 + 1), (x + 8, y0 + 1), (x + 4, y0 + 12)]), fill=(255, 255, 255, 255))
    for k in range(5):
        x = 158 + k * 11; yb = 90 + openv * (0.5 + 0.04 * k)
        d.polygon(S([(x, yb + 3), (x + 8, yb + 1), (x + 4, yb - 10)]), fill=(250, 250, 250, 255))
    # 눈과 코
    circle(d, 168 * SS, (52 + bob) * SS, 6.2 * SS, (255, 255, 255, 255))
    circle(d, 170 * SS, (53 + bob) * SS, 4.2 * SS, (22, 30, 44, 255))
    circle(d, 171.5 * SS, (51.5 + bob) * SS, 1.4 * SS, (255, 255, 255, 255))
    d.line(S([(156, 40), (184, 46)]), fill=(40, 56, 78, 255), width=int(2.4 * SS))       # 화난 눈썹
    circle(d, 218 * SS, (64 + bob) * SS, 1.6 * SS, (60, 82, 104, 255))
    # 등지느러미 (머리 뒤로 살짝)
    d.polygon(S([(70, 74), (84, 22), (104, 50), (96, 62)]), fill=(50, 72, 96, 255))
    img = img.filter(ImageFilter.GaussianBlur(0.5 * SS))
    # 수면: 아래쪽은 물에 잠겨 사라진다
    mask = Image.new('L', (W, H), 255)
    md = ImageDraw.Draw(mask)
    for y in range(int(wl), H):
        md.line([(0, y), (W, y)], fill=max(0, 255 - int((y - wl) / (SS * 1.0) * 24)))
    img.putalpha(ImageChopsMin(img.getchannel('A'), mask))
    # 물보라 고리
    foam = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(foam)
    for k, (rx, ry, al) in enumerate([(104, 13, 200), (84, 9, 150)]):
        cx = 128 + 2 * math.sin(ph + k)
        fd.ellipse([(cx - rx) * SS, wl - ry * SS, (cx + rx) * SS, wl + ry * SS], outline=(255, 255, 255, al), width=int(2.6 * SS))
    foam = foam.filter(ImageFilter.GaussianBlur(0.8 * SS))
    img = Image.alpha_composite(foam, img)
    # 앞쪽 물결(몸 앞을 가린다)
    front = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(front).arc([(26) * SS, wl - 12 * SS, 230 * SS, wl + 14 * SS], 15, 165, fill=(255, 255, 255, 215), width=int(3 * SS))
    img = Image.alpha_composite(img, front.filter(ImageFilter.GaussianBlur(0.8 * SS)))
    return lanczos(img, (256, 128))


def ImageChopsMin(a, b):
    from PIL import ImageChops
    return ImageChops.darker(a, b)


def paint_shark():
    sheet = Image.new('RGBA', (1024, 128), (0, 0, 0, 0))
    for i in range(4):
        sheet.alpha_composite(shark_frame(i), (256 * i, 0))
    return sheet


# ----------------------------------------------------------------------------
# themes
# ----------------------------------------------------------------------------
def rc(rng, opts):
    return opts[int(rng.integers(len(opts)))]


# ---- spring -----------------------------------------------------------------
def spring_floaters(img, rng):
    for _ in range(26):
        x, y = rng.uniform(30, 1050), rng.uniform(250, 1620)
        s = rng.uniform(20, 34)
        rot = rng.uniform(0, 6.28)
        c = rc(rng, [(255, 184, 208), (255, 226, 234), (250, 150, 186)])
        paste_sprite(img, lambda d, cx, cy, ss, c=c, rot=rot: petal(d, cx, cy, ss, rot, c), s, x, y, 0.62)


def spring_decor(d, x, y, ss, rng):
    k = rng.random()
    s = rng.uniform(22, 32)
    if k < 0.28:
        blossom(d, x, y, s * ss, rng.uniform(0, 6.28), (232, 188, 192), (240, 208, 210), (232, 214, 130), (206, 140, 150))
    elif k < 0.58:
        daisy(d, x, y, s * 0.72 * ss, rng.uniform(0, 6.28), (240, 238, 222), (230, 196, 90), 9)
    else:
        petal(d, x, y, s * 0.62 * ss, rng.uniform(0, 6.28), (230, 186, 190))
        if rng.random() < 0.5:
            petal(d, x + 12 * ss, y + 6 * ss, s * 0.5 * ss, rng.uniform(0, 6.28), (238, 204, 206))


def spring_stone_col(ctx):
    z, dist, u, v, c = ctx['z'], ctx['dist'], ctx['u'], ctx['v'], ctx['col']
    mz = fbm(ctx['H'], ctx['W'], ctx['rng'], (120, 50), (1, 0.6))
    m = smooth(mz, 0.5, 1.3) * (1 - smooth(dist, 4 * ctx['SS'], 56 * ctx['SS'])) * np.clip(0.5 + 0.7 * (-u * 0.5 + v * 0.7), 0, 1.2)
    ctx['col'] = lerp(c, col((112, 156, 84)) * (1 + 0.1 * z[..., None]), np.clip(m, 0, 0.92)[..., None])


def spring_stone_over(d, SS, rng):
    for _ in range(5):
        petal(d, rng.uniform(150, 450) * SS, rng.uniform(55, 145) * SS, rng.uniform(22, 30) * SS, rng.uniform(0, 6.28),
              rc(rng, [(255, 186, 206, 255), (255, 222, 230, 255), (248, 164, 192, 255)]), (255, 232, 238, 255))






def spring_particle(d, cx, cy, s, idx, SS):
    rots = [0.5, 2.2, 4.0, 5.3]
    cols = [((255, 170, 196), (255, 214, 226)), ((255, 232, 238), (255, 255, 255)),
            ((250, 150, 184), (255, 200, 216)), ((255, 206, 220), (255, 240, 244))]
    c, hi = cols[idx]
    petal(d, cx, cy, s * 0.95, rots[idx], c, hi, (232, 120, 160), 0.9)
    d.line(T([(0, 0.32), (0.03, 0.05)], cx, cy, s * 0.9, rots[idx]), fill=(236, 130, 168), width=max(1, SS))


def spring_icon(d, c, s):
    blossom(d, c, c, s, 0.1, (255, 150, 184), (255, 196, 214), (255, 218, 96), (222, 84, 130))


# ---- summer -----------------------------------------------------------------
def summer_floaters(img, rng):
    for _ in range(46):
        x, y = rng.uniform(30, 1050), rng.uniform(250, 1650)
        s = rng.uniform(10, 24)
        paste_sprite(img, lambda d, cx, cy, ss: sparkle(d, cx, cy, ss, 0, (255, 255, 255)), s, x, y,
                     rng.uniform(0.35, 0.65))
    for _ in range(18):
        x, y = rng.uniform(30, 1050), rng.uniform(250, 1650)
        s = rng.uniform(28, 38)
        paste_sprite(img, lambda d, cx, cy, ss: sparkle(d, cx, cy, ss, 0, (255, 255, 255)), s, x, y, 0.3)


def summer_decor(d, x, y, ss, rng):
    k = rng.random()
    s = rng.uniform(22, 34)
    if k < 0.45:
        daisy(d, x, y, s * 0.8 * ss, rng.uniform(0, 6.28), (242, 242, 228), (236, 196, 80), 10)
    elif k < 0.62:
        sunflower(d, x, y, s * 1.05 * ss, rng.uniform(0, 6.28), (226, 190, 70), (128, 92, 52))
    else:
        for _ in range(3):
            xx, yy = x + rng.uniform(-9, 9) * ss, y + rng.uniform(-6, 6) * ss
            d.line([(xx, yy), (xx + rng.uniform(-4, 4) * ss, yy - 10 * ss)], fill=(104, 148, 70, 255), width=2 * ss)
            circle(d, xx, yy, 2.2 * ss, (240, 236, 210, 255))


def summer_stone_col(ctx):
    mz = fbm(ctx['H'], ctx['W'], ctx['rng'], (120, 50), (1, 0.6))
    dist, u, v, c = ctx['dist'], ctx['u'], ctx['v'], ctx['col']
    m = smooth(mz, 0.5, 1.3) * (1 - smooth(dist, 4 * ctx['SS'], 40 * ctx['SS'])) * np.clip(0.4 + 0.8 * (-u * 0.5 + v * 0.8), 0, 1.2)
    ctx['col'] = lerp(c, col((98, 190, 52)), np.clip(m, 0, 0.95)[..., None])


def summer_stone_over(d, SS, rng):
    for _ in range(6):
        x, y = rng.uniform(120, 480) * SS, rng.uniform(50, 150) * SS
        circle(d, x, y, rng.uniform(2, 5) * SS, (150, 120, 84, 70))




def make_sparkle_particle(fr_cols):
    def f(fr, cx, cy, s, idx, SS):
        c = fr_cols[idx]
        rot = [0, 0.3, 0, 0.5][idx]

        def draw(d, g):
            cc = g or c + (255,)
            sparkle(d, cx, cy, s, rot, cc)
            sparkle(d, cx, cy, s * 0.55, rot + math.pi / 4, cc)
            circle(d, cx, cy, s * 0.07, (255, 255, 255, 255))
        fr.alpha_composite(glow_layer(fr.size, draw, fr_cols[idx] + (255,), 3.2 * SS, 0.85))
    return f


def summer_icon(d, c, s):
    sun_icon(d, c, s)


# ---- autumn -----------------------------------------------------------------
def autumn_floaters(img, rng):
    for _ in range(12):
        x, y = rng.uniform(30, 1050), rng.uniform(250, 1620)
        s = rng.uniform(26, 38)
        rot = rng.uniform(0, 6.28)
        k = rng.random()
        if k < 0.5:
            f = lambda d, cx, cy, ss, rot=rot: maple(d, cx, cy, ss, rot, (190, 62, 48), (130, 40, 36))
        else:
            f = lambda d, cx, cy, ss, rot=rot: maple(d, cx, cy, ss, rot, (216, 128, 48), (160, 80, 34))
        paste_sprite(img, f, s, x, y, 0.78)


def autumn_decor(d, x, y, ss, rng):
    k = rng.random()
    s = rng.uniform(22, 32)
    rot = rng.uniform(0, 6.28)
    if k < 0.2:
        maple(d, x, y, s * ss, rot, (200, 94, 60), (150, 64, 44))
    elif k < 0.38:
        maple(d, x, y, s * ss, rot, (214, 140, 62), (164, 98, 46))
    elif k < 0.54:
        ginkgo(d, x, y, s * ss, rot, (222, 186, 84), (184, 146, 64))
    elif k < 0.70:
        oak(d, x, y, s * ss, rot, (158, 108, 66), (120, 80, 50))
    elif k < 0.84:
        mushroom(d, x, y, s * 0.9 * ss, 0, (188, 112, 84), (232, 218, 192), (244, 236, 220))
    else:
        for _ in range(3):
            circle(d, x + rng.uniform(-9, 9) * ss, y + rng.uniform(-6, 6) * ss, 3 * ss, (130, 92, 58, 255))


def autumn_stone_col(ctx):
    c = ctx['col']
    ctx['col'] = lerp(c, col((188, 176, 160)), 0.18)


def autumn_stone_over(d, SS, rng):
    specs = [((196, 56, 44, 255), (136, 36, 32, 255), 'm'), ((228, 130, 40, 255), (160, 82, 30, 255), 'm'),
             ((214, 70, 40, 255), (146, 40, 30, 255), 'm'), ((240, 170, 50, 255), (176, 120, 30, 255), 'g')]
    xs = [170, 270, 360, 440]
    for (f, vn, kind), x in zip(specs, xs):
        y = rng.uniform(70, 130)
        s = rng.uniform(40, 54) * SS
        if kind == 'm':
            maple(d, x * SS, y * SS, s, rng.uniform(0, 6.28), f, vn)
        else:
            ginkgo(d, x * SS, y * SS, s, rng.uniform(0, 6.28), f, vn)


def autumn_particle(d, cx, cy, s, idx, SS):
    if idx == 0:
        maple(d, cx, cy, s, 0.4, (206, 48, 40), (140, 28, 30), vw=1.2)
    elif idx == 1:
        maple(d, cx, cy, s, 2.5, (240, 134, 36), (176, 84, 28), vw=1.2)
    elif idx == 2:
        ginkgo(d, cx, cy, s * 1.0, 5.3, (246, 206, 60), (200, 152, 30))
    else:
        oak(d, cx, cy, s * 1.05, 1.0, (150, 96, 50), (100, 60, 30))


def autumn_icon(d, c, s):
    maple(d, c, c + s * 0.02, s * 1.02, 0.0, (232, 84, 36), (160, 36, 24), vw=1.5)


# ---- winter -----------------------------------------------------------------
def winter_floaters(img, rng):
    W, H = img.size
    mask = Image.new('L', (W, H), 0)
    md = ImageDraw.Draw(mask)
    for yr in ((226, 330), (1470, 1578)):
        for _ in range(9):
            cx, cy = rng.uniform(20, 1060), rng.uniform(*yr)
            rx, ry = rng.uniform(34, 90), rng.uniform(10, 24)
            n = int(rng.integers(7, 11))
            pts = []
            for k in range(n):
                t = 2 * math.pi * k / n + rng.uniform(-0.2, 0.2)
                rr = rng.uniform(0.75, 1.1)
                pts.append((cx + math.cos(t) * rx * rr, cy + math.sin(t) * ry * rr))
            md.polygon(pts, fill=255)
    m = mask.filter(ImageFilter.GaussianBlur(1.6))
    edge = Image.eval(Image.blend(m, mask.filter(ImageFilter.GaussianBlur(7)), 0.0), lambda v: v)
    inner = mask.filter(ImageFilter.GaussianBlur(6))
    rim = np.clip(np.asarray(m, np.float32) - np.asarray(inner, np.float32) * 0.9, 0, 255)
    fill = Image.new('RGB', (W, H), (232, 244, 252))
    img.paste(fill, (0, 0), m.point(lambda v: int(v * 0.42)))
    img.paste(Image.new('RGB', (W, H), (255, 255, 255)), (0, 0), Image.fromarray(rim.astype(np.uint8), 'L').point(lambda v: int(v * 0.6)))
    # frost haze toward both banks
    arr = np.asarray(img, np.float32)
    yy = np.arange(H, dtype=np.float32)[:, None, None]
    frost = np.maximum(1 - smooth(yy, 220, 420), 1 - smooth(H - yy, 340, 560))
    arr = arr + (np.array([240, 248, 255], np.float32) - arr) * frost * 0.22
    img.paste(to_img(arr), (0, 0))
    for _ in range(26):
        x, y = rng.uniform(30, 1050), rng.uniform(300, 1580)
        s = rng.uniform(12, 20)
        rot = rng.uniform(0, 6.28)
        paste_sprite(img, lambda d, cx, cy, ss, rot=rot: snowflake(d, cx, cy, ss, rot, (246, 252, 255), None, int(rng.integers(4))),
                     s, x, y, 0.55)


def winter_decor(d, x, y, ss, rng):
    k = rng.random()
    if k < 0.34:
        evergreen(d, x, y, rng.uniform(34, 44) * ss, rng.uniform(0, 6.28), (96, 132, 130), (128, 164, 156), (242, 248, 252))
    elif k < 0.64:
        snowflake(d, x, y, rng.uniform(20, 28) * ss, rng.uniform(0, 1), (176, 208, 232), None, int(rng.integers(4)))
    else:
        snow_lump(d, x, y, rng.uniform(26, 40) * ss, rng.uniform(-0.3, 0.3), (246, 250, 254), (208, 224, 240))


def winter_stone_col(ctx):
    z, u, v, c = ctx['z'], ctx['u'], ctx['v'], ctx['col']
    SS = ctx['SS']
    cr = np.sqrt(((u + 0.05) / 0.80) ** 2 + ((v + 0.16) / 0.72) ** 2)
    capm = smooth(1 - cr + 0.07 * z, 0.0, 0.05) * smooth(ctx['dist'], 5 * SS, 12 * SS)
    capm = np.clip(capm, 0, 1)
    h = gaussian_filter(capm * 14 * SS, 3 * SS)
    sh = np.clip(lambert(h, 1.0), 0.6, 1.3)
    snow = col((246, 250, 255))[None, None] * (0.93 + 0.07 * sh[..., None])
    snow = snow - (1 - sh[..., None]).clip(0, 1) * np.array([60, 36, 14], np.float32)
    ctx['col'] = lerp(c, snow, capm[..., None] * 0.97)


def winter_stone_over(d, SS, rng):
    for _ in range(6):
        sparkle(d, rng.uniform(110, 490) * SS, rng.uniform(40, 150) * SS, rng.uniform(16, 32) * SS, 0, (255, 255, 255, 255))
    for _ in range(14):
        circle(d, rng.uniform(80, 520) * SS, rng.uniform(40, 160) * SS, rng.uniform(1.5, 3) * SS, (255, 255, 255, 220))




def winter_particle_wrap(fr, cx, cy, s, idx, SS):
    def draw(d, g):
        c = g or (250, 253, 255, 255)
        snowflake(d, cx, cy, s, idx * 0.2, c, max(2, int(s * 0.07)), idx)
    fr.alpha_composite(glow_layer(fr.size, draw, (150, 196, 245, 255), 3 * SS, 0.9))


def winter_icon(d, c, s):
    snowflake(d, c, c, s, 0.0, (246, 252, 255, 255), int(s * 0.11), 1)


def spring_particle_wrap(fr, cx, cy, s, idx, SS):
    d = ImageDraw.Draw(fr)
    spring_particle(d, cx, cy, s, idx, SS)


def autumn_particle_wrap(fr, cx, cy, s, idx, SS):
    d = ImageDraw.Draw(fr)
    autumn_particle(d, cx, cy, s, idx, SS)


THEMES = {
    'spring': dict(
        pal=dict(water_top=(116, 214, 212), water_bot=(92, 196, 206), water_hi=(200, 244, 240), water_var=3.5,
                 gnd_a=(160, 184, 128), gnd_b=(176, 190, 134), sand_a=(236, 226, 184), sand_b=(228, 220, 180),
                 wet=(208, 200, 160), foam=(248, 252, 250),
                 tuft=[(134, 164, 104), (184, 202, 146), (150, 176, 112)],
                 stone=(208, 210, 206), shoal=(54, 150, 140), ring=(214, 246, 238), algae=[(70, 160, 70), (140, 210, 96)]),
        ice=False, floaters=spring_floaters, decor=spring_decor, stone_col=spring_stone_col, stone_over=spring_stone_over,
        particles=[spring_particle_wrap] * 4, icon=spring_icon, icon_outline=(176, 58, 104)),
    'summer': dict(
        pal=dict(water_top=(20, 168, 214), water_bot=(10, 140, 200), water_hi=(170, 236, 250), water_var=3.5,
                 gnd_a=(148, 170, 104), gnd_b=(160, 178, 110), sand_a=(242, 224, 164), sand_b=(234, 214, 150),
                 wet=(214, 196, 142), foam=(252, 252, 246),
                 tuft=[(120, 152, 84), (176, 196, 122), (132, 160, 90)],
                 stone=(226, 214, 190), shoal=(18, 126, 150), ring=(190, 242, 246), algae=[(62, 156, 64), (132, 208, 84)]),
        ice=False, floaters=summer_floaters, decor=summer_decor, stone_col=summer_stone_col, stone_over=summer_stone_over,
        particles=[make_sparkle_particle([(255, 255, 255), (255, 244, 176), (190, 242, 255), (255, 255, 255)])] * 4,
        icon=summer_icon, icon_outline=(196, 96, 18)),
    'autumn': dict(
        pal=dict(water_top=(46, 120, 118), water_bot=(34, 100, 106), water_hi=(112, 176, 164), water_var=3.0,
                 gnd_a=(172, 138, 86), gnd_b=(184, 150, 92), sand_a=(224, 200, 146), sand_b=(214, 190, 136),
                 wet=(190, 160, 110), foam=(244, 240, 226),
                 tuft=[(150, 116, 68), (204, 172, 100), (176, 138, 78)],
                 stone=(204, 202, 198), shoal=(28, 88, 80), ring=(172, 220, 200), algae=[(66, 140, 66), (130, 192, 84)]),
        ice=False, floaters=autumn_floaters, decor=autumn_decor, stone_col=autumn_stone_col, stone_over=autumn_stone_over,
        particles=[autumn_particle_wrap] * 4, icon=autumn_icon, icon_outline=(122, 30, 22)),
    'winter': dict(
        pal=dict(water_top=(168, 210, 232), water_bot=(148, 196, 224), water_hi=(236, 248, 255), water_var=3.0,
                 gnd_a=(220, 231, 241), gnd_b=(210, 224, 238), sand_a=(240, 246, 252), sand_b=(232, 241, 249),
                 wet=(196, 220, 238), foam=(255, 255, 255),
                 tuft=[(196, 212, 230), (234, 242, 250), (186, 204, 226)],
                 stone=(200, 208, 220), shoal=(234, 246, 255), ring=(255, 255, 255), algae=[(0, 0, 0), (0, 0, 0)]),
        ice=True, floaters=winter_floaters, decor=winter_decor, stone_col=winter_stone_col, stone_over=winter_stone_over,
        particles=[winter_particle_wrap] * 4, icon=winter_icon, icon_outline=(52, 104, 164)),
}


# ----------------------------------------------------------------------------
# driver
# ----------------------------------------------------------------------------
def build_theme(tid):
    th = THEMES[tid]
    out = os.path.join(ROOT, 'themes', tid)
    save(paint_water(tid, th), os.path.join(out, 'water.webp'), quality=80, method=6)
    save(paint_island(tid, th, 'start'), os.path.join(out, 'island_start.webp'), quality=82, method=6)
    save(paint_island(tid, th, 'goal'), os.path.join(out, 'island_goal.webp'), quality=82, method=6)
    save(paint_stone(tid, th, False), os.path.join(out, 'stone.png'), optimize=True)
    save(paint_stone(tid, th, True), os.path.join(out, 'stone_slippery.png'), optimize=True)
    save(paint_shallow(tid, th), os.path.join(out, 'shallow.png'), optimize=True)
    save(paint_particles(tid, th), os.path.join(out, 'particles.png'), optimize=True)
    save(paint_icon(tid, th), os.path.join(out, 'icon.png'), optimize=True)
    print('built', tid)


def main(argv):
    names = argv or list(THEMES) + ['shark']
    for n in names:
        if n == 'shark':
            save(paint_shark(), os.path.join(ROOT, 'shark.png'), optimize=True)
            print('built shark')
        elif n in THEMES:
            build_theme(n)
        else:
            sys.exit('unknown theme %r (known: %s, shark)' % (n, ', '.join(THEMES)))


if __name__ == '__main__':
    main(sys.argv[1:])
