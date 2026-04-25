#!/usr/bin/env python3
"""Crop the book page spreads from each Devotional Booklet screen image.

Strategy: two crop regions —
  SAFE_BOX  = the original tight crop (always fully opaque)
  CROP_BOX  = a wider region around it
Only the border between the two gets background color removal.
Then add drop shadow and edge fade.
"""

import os
import numpy as np
from PIL import Image, ImageFilter

SRC_DIR = "/home/rbs/Sites/pages"
OUT_DIR = os.path.join(SRC_DIR, "cropped")
os.makedirs(OUT_DIR, exist_ok=True)

# Wider crop — generous but skip title text and bottom label
CROP_BOX = (20, 120, 810, 825)

# Safe zone — the original tight crop, fully opaque (relative to original image)
SAFE_BOX = (44, 137, 800, 800)

# Background color samples
BG_SAMPLES = [
    (170, 136, 102),
    (175, 141, 108),
    (193, 169, 141),
    (182, 153, 122),
    (165, 145, 123),
]
BG_TOLERANCE = 32
BG_FADE = 14             # soft blend range beyond tolerance

# Shadow settings
SHADOW_OFFSET = (8, 8)
SHADOW_COLOR_A = 120
SHADOW_BLUR = 15
SHADOW_PAD = 40

# Edge fade
FADE_WIDTH = 25


def color_distance(arr, ref):
    return np.sqrt(np.sum((arr.astype(np.float32) - np.array(ref, dtype=np.float32)) ** 2, axis=-1))


def remove_border_background(img, safe_rect):
    """Remove background only in the border zone outside the safe area."""
    w, h = img.size
    arr = np.array(img.convert("RGB"), dtype=np.float32)

    # Compute min distance to any background sample for every pixel
    min_dist = np.full((h, w), 999.0, dtype=np.float32)
    for sample in BG_SAMPLES:
        dist = color_distance(arr, sample)
        min_dist = np.minimum(min_dist, dist)

    # Alpha from color distance: 0=background, 255=content
    # Smooth ramp between BG_TOLERANCE and BG_TOLERANCE + BG_FADE
    alpha = np.clip((min_dist - BG_TOLERANCE) / BG_FADE, 0.0, 1.0)
    alpha = (alpha * 255).astype(np.uint8)

    # Safe zone: force fully opaque
    sx1, sy1, sx2, sy2 = safe_rect
    alpha[sy1:sy2, sx1:sx2] = 255

    # Feather the border slightly
    alpha_img = Image.fromarray(alpha)
    alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(radius=2))

    # Re-enforce safe zone after blur
    alpha_arr = np.array(alpha_img)
    alpha_arr[sy1:sy2, sx1:sx2] = 255
    alpha_img = Image.fromarray(alpha_arr)

    rgba = img.convert("RGBA")
    rgba.putalpha(alpha_img)
    return rgba


def make_edge_fade_mask(w, h, fade, skip_side=None):
    """skip_side='left'|'right' leaves that edge fully opaque (no fade)."""
    mask = np.ones((h, w), dtype=np.float32)
    for i in range(fade):
        t = i / fade
        if skip_side != "left":
            mask[:, i] *= t
        if skip_side != "right":
            mask[:, w - 1 - i] *= t
        mask[i, :] *= t
        mask[h - 1 - i, :] *= t
    return (mask * 255).astype(np.uint8)


def add_shadow_and_fade(img_rgba, seam=None):
    """seam='left' or 'right' suppresses the shadow on the binding edge."""
    w, h = img_rgba.size
    pad = SHADOW_PAD
    ox, oy = SHADOW_OFFSET
    cw, ch = w + pad * 2, h + pad * 2

    shadow_alpha = img_rgba.split()[3]
    shadow_layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    shadow_img = Image.new("RGBA", (w, h), (0, 0, 0, SHADOW_COLOR_A))
    shadow_img.putalpha(shadow_alpha)
    shadow_layer.paste(shadow_img, (pad + ox, pad + oy), shadow_img)
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=SHADOW_BLUR))

    shadow_layer.paste(img_rgba, (pad, pad), img_rgba)

    # Wipe shadow from the seam edge so pages sit flush when placed together
    if seam in ("left", "right"):
        a_arr = np.array(shadow_layer.split()[3])
        # Content alpha from original image at the seam column
        content_alpha = np.array(img_rgba.split()[3])
        if seam == "right":
            # Zero shadow in the right pad; restore original content alpha
            shadow_layer_arr = np.array(shadow_layer)
            shadow_layer_arr[:, pad + w:, 3] = 0
            shadow_layer_arr[pad:pad + h, pad:pad + w, 3] = content_alpha
            shadow_layer = Image.fromarray(shadow_layer_arr)
        elif seam == "left":
            shadow_layer_arr = np.array(shadow_layer)
            shadow_layer_arr[:, :pad, 3] = 0
            shadow_layer_arr[pad:pad + h, pad:pad + w, 3] = content_alpha
            shadow_layer = Image.fromarray(shadow_layer_arr)

    fade_mask = make_edge_fade_mask(cw, ch, FADE_WIDTH, skip_side=seam)
    r, g, b, a = shadow_layer.split()
    a_arr = np.array(a, dtype=np.float32) * np.array(fade_mask, dtype=np.float32) / 255.0
    shadow_layer.putalpha(Image.fromarray(a_arr.astype(np.uint8)))

    # Crop the seam-side padding entirely so the edge is flush with no gap
    if seam == "right":
        shadow_layer = shadow_layer.crop((0, 0, cw - pad, ch))
    elif seam == "left":
        shadow_layer = shadow_layer.crop((pad, 0, cw, ch))

    return shadow_layer


def tight_page(img_rgba, seam=None):
    """No shadow, no padding — just a feathered edge. Seam side stays flush."""
    w, h = img_rgba.size
    fade_mask = make_edge_fade_mask(w, h, FADE_WIDTH, skip_side=seam)
    r, g, b, a = img_rgba.split()
    a_arr = np.array(a, dtype=np.float32) * np.array(fade_mask, dtype=np.float32) / 255.0
    result = img_rgba.copy()
    result.putalpha(Image.fromarray(a_arr.astype(np.uint8)))
    return result


# DB-01 is a centred cover image — skip it
SKIP = {"DB-01.png"}

SPREAD_DIR = os.path.join(SRC_DIR, "complex", "spread")
os.makedirs(SPREAD_DIR, exist_ok=True)

files = sorted(f for f in os.listdir(SRC_DIR) if f.endswith(".png") and f not in SKIP)

# Translate safe box into cropped image coordinates (constant)
SAFE_IN_CROP = (
    SAFE_BOX[0] - CROP_BOX[0],
    SAFE_BOX[1] - CROP_BOX[1],
    SAFE_BOX[2] - CROP_BOX[0],
    SAFE_BOX[3] - CROP_BOX[1],
)

for fname in files:
    stem = fname.replace(".png", "")
    path = os.path.join(SRC_DIR, fname)
    img = Image.open(path)
    cropped = img.crop(CROP_BOX)
    keyed = remove_border_background(cropped, SAFE_IN_CROP)

    # --- full spread ---
    result = add_shadow_and_fade(keyed)
    result.save(os.path.join(OUT_DIR, fname))

    # --- split into left and right pages ---
    mid = keyed.width // 2
    for side, seam, half in (("L", "right", keyed.crop((0, 0, mid, keyed.height))),
                              ("R", "left",  keyed.crop((mid, 0, keyed.width, keyed.height)))):
        page = tight_page(half, seam=seam)
        page.save(os.path.join(SPREAD_DIR, f"{stem}-{side}.png"))

    print(f"{fname} -> spread + L/R pages")

print(f"\nDone. {len(files)} images saved to {OUT_DIR} and {SPREAD_DIR}")
