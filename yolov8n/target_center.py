"""Confirm a target center from at least three distinct concentric ring edges.

This is an image-geometry check after YOLO, not an additional learned class.
Unresolved, heavily occluded or very small targets are deliberately rejected.
"""
from dataclasses import dataclass
import math

import cv2
import numpy as np


@dataclass(frozen=True)
class TargetCenter:
    x: float
    y: float
    rings: int


def _ellipse(contour, width, height):
    if len(contour) < 24:
        return None
    def coordinates(ellipse):
        (cx, cy), (dw, dh), angle = ellipse
        if min(dw, dh) <= 0:
            return None
        points = contour[:, 0, :].astype(np.float32) - [cx, cy]
        radians = math.radians(angle)
        cosine, sine = math.cos(radians), math.sin(radians)
        u = (points[:, 0] * cosine + points[:, 1] * sine) / (dw / 2)
        v = (-points[:, 0] * sine + points[:, 1] * cosine) / (dh / 2)
        return u, v, np.abs(np.hypot(u, v) - 1)

    fitted = cv2.fitEllipse(contour)
    for _ in range(6):
        normalized = coordinates(fitted)
        if normalized is None:
            return None
        _, _, residual = normalized
        if np.quantile(residual, .85) <= .04:
            break
        # A crossing arrow contributes straight outliers to an otherwise curved edge.
        keep = residual <= .10
        if keep.mean() < .65 or keep.sum() < 24:
            return None
        fitted = cv2.fitEllipse(contour[keep])
    (cx, cy), (dw, dh), angle = fitted
    if not np.isfinite([cx, cy, dw, dh, angle]).all() or min(dw, dh) < 8:
        return None
    minor, major = min(dw, dh), max(dw, dh)
    if (minor / major < .35 or major > 1.35 * max(width, height)
            or not .08 * width < cx < .92 * width
            or not .08 * height < cy < .92 * height):
        return None
    u, v, residual = coordinates(fitted)
    # Rectangular borders can have the same center but do not follow ellipses.
    inliers = residual <= .07
    if np.quantile(residual, .85) > .04 and (
            inliers.mean() < .75 or np.quantile(residual[inliers], .85) > .025):
        return None
    bins = ((np.arctan2(v[inliers], u[inliers]) + np.pi) * (36 / (2 * np.pi))).astype(int) % 36
    if len(np.unique(bins)) < 27:
        return None
    normalized_contour = np.column_stack((u, v)).astype(np.float32).reshape(-1, 1, 2)
    # Fit residual alone accepts nested polygons. At 3% normalized tolerance a
    # curved ring still needs many vertices; long straight sides need few.
    if len(cv2.approxPolyDP(normalized_contour, .03, True)) < 13:
        return None
    return dict(x=float(cx), y=float(cy), radius=math.sqrt(dw * dh) / 2,
                ratio=minor / major, minor=minor, major=major, angle=angle)


def find_target_center(frame, box_xyxy):
    """Return an image-coordinate center only when nested ring evidence agrees."""
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = box_xyxy
    if not np.isfinite([x1, y1, x2, y2]).all():
        return None
    left, top = max(0, math.floor(x1)), max(0, math.floor(y1))
    right, bottom = min(width, math.ceil(x2)), min(height, math.ceil(y2))
    if min(right - left, bottom - top) < 40:
        return None
    crop = frame[top:bottom, left:right]
    scale = min(1.0, 384 / max(crop.shape[:2]))
    if scale < 1:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    h, w = crop.shape[:2]
    blurred = cv2.GaussianBlur(crop, (5, 5), 0)
    gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
    lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)
    ellipses = []
    # Chroma edges recover colored rings with nearly identical gray brightness.
    channels = [(gray, 25, 75), (gray, 10, 35), (lab[:, :, 1], 15, 45), (lab[:, :, 2], 15, 45)]
    for channel, low, high in channels:
        edges = cv2.Canny(channel, low, high)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        for contour in sorted(contours, key=len, reverse=True)[:120]:
            candidate = _ellipse(contour, w, h)
            if candidate is not None:
                ellipses.append(candidate)
    # Arrow shafts break edge contours. Fit the filled color bands as a second
    # source of curved boundaries, keeping the same ellipse/concentric checks.
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
    saturated = ((hsv[:, :, 1] >= 85) & (hsv[:, :, 2] >= 55)).astype(np.uint8) * 255
    hue = hsv[:, :, 0]
    kernel = np.ones((3, 3), np.uint8)
    for lower, upper in ((0, 12), (12, 42), (80, 135), (160, 180)):
        band = ((hue >= lower) & (hue < upper)).astype(np.uint8) * saturated
        band = cv2.morphologyEx(band, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(band, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        for contour in sorted(contours, key=len, reverse=True)[:30]:
            candidate = _ellipse(contour, w, h)
            if candidate is not None:
                ellipses.append(candidate)
    best = None
    for anchor in ellipses:
        # Centers of perspective ellipses can differ slightly across ring sizes.
        tolerance = max(3.0, .035 * anchor['major'])
        group = []
        for candidate in ellipses:
            if (math.hypot(candidate['x'] - anchor['x'], candidate['y'] - anchor['y']) > tolerance
                    or abs(candidate['ratio'] - anchor['ratio']) > .15):
                continue
            angle_delta = abs(candidate['angle'] - anchor['angle']) % 180
            if min(candidate['ratio'], anchor['ratio']) < .85 and min(angle_delta, 180-angle_delta) > 18:
                continue
            group.append(candidate)
        distinct = []
        for candidate in sorted(group, key=lambda e: e['radius']):
            # Inner/outer edges of one stroke and repeated channels are one ring.
            if not distinct or candidate['radius'] / distinct[-1]['radius'] >= 1.14:
                distinct.append(candidate)
        if len(distinct) < 3:
            continue
        inner, outer = distinct[0], distinct[-1]
        if (outer['radius'] / inner['radius'] < 1.8
                or outer['minor'] < .30 * min(w, h)
                or outer['major'] < .40 * max(w, h)):
            continue
        # Perspective shifts the fitted centers with ring size. Extrapolate
        # their smooth radius-squared trend to the zero-radius bullseye.
        radii_squared = np.array([(e['radius'] / outer['radius']) ** 2 for e in distinct])
        design = np.column_stack((np.ones(len(distinct)), radii_squared))
        centers = np.array([[e['x'], e['y']] for e in distinct])
        trend = np.linalg.lstsq(design, centers, rcond=None)[0]
        projected_center = trend[0]
        residual = np.linalg.norm(design @ trend - centers, axis=1)
        if (residual.max() > max(2.0, .015 * outer['major'])
                or np.linalg.norm(projected_center - centers[0]) > .15 * outer['major']
                or not 0 <= projected_center[0] < w or not 0 <= projected_center[1] < h):
            continue
        # Favor a larger family of agreeing rings; do not use the YOLO box center.
        score = (len(distinct), outer['radius'] / inner['radius'])
        if best is None or score > best[0]:
            best = (score, float(projected_center[0]), float(projected_center[1]))
    if best is None:
        return None
    return TargetCenter(left + best[1] / scale, top + best[2] / scale, best[0][0])
