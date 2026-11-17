"""Horizontal target alignment shared by live YOLO and the robot ONNX API.

Coordinates refer to the original, unmirrored camera image. Error is a fraction
of the FULL image width. Positive angular velocity means turn left (rad/s).
This module computes commands only; it never connects to or drives hardware.
"""
from dataclasses import asdict, dataclass
import math
import time

ALIGNMENT_POLICY = "raw_center_hysteresis_v2"


@dataclass(frozen=True)
class AlignmentConfig:
    start_threshold: float = 0.15
    stop_threshold: float = 0.10
    smoothing_alpha: float = 0.4
    kp: float = 1.2
    min_angular_speed: float = 0.08
    max_angular_speed: float = 0.6
    frame_timeout: float = 0.5
    target_class: int = 11

    def __post_init__(self):
        for name in ("start_threshold", "stop_threshold", "smoothing_alpha", "kp",
                     "min_angular_speed", "max_angular_speed", "frame_timeout"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite.")
        if not 0 <= self.stop_threshold < self.start_threshold < 0.5:
            raise ValueError("Require 0 <= stop_threshold < start_threshold < 0.5.")
        if not 0 < self.smoothing_alpha <= 1 or self.kp <= 0 or self.frame_timeout <= 0:
            raise ValueError("Smoothing alpha, kp and frame_timeout must be positive; alpha <= 1.")
        if not 0 <= self.min_angular_speed <= self.max_angular_speed or self.max_angular_speed <= 0:
            raise ValueError("Require 0 <= min_angular_speed <= max_angular_speed, max > 0.")
        if isinstance(self.target_class, bool) or not isinstance(self.target_class, int) or self.target_class < 0:
            raise ValueError("target_class must be a nonnegative integer.")

    @classmethod
    def from_dict(cls, values=None, *, target_class=None):
        options = dict(values or {})
        if target_class is not None:
            options["target_class"] = target_class
        return cls(**options)


@dataclass(frozen=True)
class AlignmentResult:
    command: str = "STOP"
    reason: str = "no_frame"
    linear_velocity: float = 0.0
    angular_velocity: float = 0.0
    found: bool = False
    center_x: float | None = None
    center_y: float | None = None
    error_px: float | None = None
    error_normalized: float | None = None
    filtered_error_normalized: float | None = None
    confidence: float | None = None
    frame_time: float | None = None
    target_id: int | None = None
    box_xyxy: tuple | None = None
    display_box_xyxy: tuple | None = None
    center_verified: bool = False

    def as_dict(self):
        return asdict(self)


def _iou(a, b):
    x = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    y = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    intersection = x * y
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
    return intersection / union if union > 0 else 0.0


def detections_from_result(result):
    """Convert Ultralytics boxes to portable original-image pixel detections."""
    if result.boxes is None:
        return []
    rows = result.boxes.data.detach().cpu().tolist()
    return [dict(xyxy=row[:4], confidence=float(row[-2]), class_id=int(row[-1])) for row in rows]


class TargetAligner:
    def __init__(self, config=None, *, confidence=0.25, tracking_confidence=0.15,
                 target_memory=0.25, box_smoothing=0.5):
        self.config = config if isinstance(config, AlignmentConfig) else AlignmentConfig.from_dict(config)
        if (not all(math.isfinite(v) for v in (confidence, tracking_confidence, target_memory, box_smoothing))
                or not 0 <= tracking_confidence <= confidence <= 1
                or not 0 <= target_memory <= self.config.frame_timeout
                or not 0 < box_smoothing <= 1):
            raise ValueError("Invalid confidence, target memory or box smoothing.")
        self.confidence, self.tracking_confidence = confidence, tracking_confidence
        self.target_memory, self.box_smoothing = target_memory, box_smoothing
        self._next_target_id = 0
        self.reset()

    def reset(self, reason="no_frame"):
        self._box = None
        self._filtered = None
        self._turning = False
        self._display_box = None
        self._last_seen = None
        self._frame_size = None
        self._target_id = None
        self.result = AlignmentResult(reason=reason)
        return self.result

    def _missing(self, stamp):
        # Retain association briefly, never invent a detection for motor control.
        if self._last_seen is not None and stamp - self._last_seen > self.target_memory:
            self.reset("target_lost")
        self._filtered, self._turning = None, False
        self.result = AlignmentResult(reason="target_lost", frame_time=stamp,
                                      target_id=self._target_id)
        return self.result

    def current_command(self, now=None):
        """Call each control tick, even if no new image arrives; stale output is STOP."""
        now = time.monotonic() if now is None else now
        stamp = self.result.frame_time
        if stamp is not None and (not math.isfinite(now) or now - stamp > self.config.frame_timeout
                                  or now < stamp - 0.02):
            return self.reset("stale_frame")
        return self.result

    def update(self, detections, width, height, *, frame_time=None, now=None):
        now = time.monotonic() if now is None else now
        stamp = now if frame_time is None else frame_time
        if width <= 0 or height <= 0:
            raise ValueError("Image dimensions must be positive.")
        if not math.isfinite(stamp) or not math.isfinite(now) or now-stamp > self.config.frame_timeout or stamp > now+0.02:
            return self.reset("stale_frame")
        if self.result.frame_time is not None and stamp <= self.result.frame_time:
            return self.reset("out_of_order_frame")
        if self.result.frame_time is not None and stamp-self.result.frame_time > self.config.frame_timeout:
            self.reset("stale_frame")
        if self._frame_size is not None and self._frame_size != (width, height):
            self.reset("image_size_changed")
        if self._last_seen is not None and stamp-self._last_seen > self.target_memory:
            self.reset("target_lost")
        self._frame_size = (width, height)
        candidates = []
        for detection in detections:
            if detection.get("class_id") != self.config.target_class:
                continue
            box = [float(v) for v in detection["xyxy"]]
            score = float(detection["confidence"])
            if len(box) != 4 or not all(math.isfinite(v) for v in box+[score]) or not 0 <= score <= 1:
                continue
            box = [max(0.0,min(float(width),box[0])), max(0.0,min(float(height),box[1])),
                   max(0.0,min(float(width),box[2])), max(0.0,min(float(height),box[3]))]
            center = detection.get('center_xy')
            if center is not None:
                if (len(center) != 2 or not all(math.isfinite(v) for v in center)
                        or not box[0] <= center[0] <= box[2]
                        or not box[1] <= center[1] <= box[3]):
                    continue
            if box[2] > box[0] and box[3] > box[1] and score >= self.tracking_confidence:
                candidates.append((box, score, center))
        if not candidates:
            return self._missing(stamp)
        # Keep the overlapping board rather than switching when confidences fluctuate.
        overlapping = [(box, score, center) for box, score, center in candidates
                       if self._box is not None and _iou(self._box, box) >= 0.2
                       and 0.5 <= ((box[2]-box[0])*(box[3]-box[1])) /
                       ((self._box[2]-self._box[0])*(self._box[3]-self._box[1])) <= 2.0]
        if overlapping:
            box, score, center = max(overlapping, key=lambda item: _iou(self._box, item[0]))
        else:
            # An unrelated object cannot steal a temporarily uncertain track.
            if self._box is not None:
                return self._missing(stamp)
            candidates = [(box, score, center) for box, score, center in candidates if score >= self.confidence]
            if not candidates:
                return self._missing(stamp)
            box, score, center = max(candidates, key=lambda item: item[1])
            self._filtered, self._turning = None, False
            self._next_target_id += 1
            self._target_id = self._next_target_id
        # Smooth only the drawn rectangle. Raw centers still control boundary
        # crossings and stopping, so smoothing adds no delay to motor decisions.
        alpha = self.box_smoothing
        if (self._display_box is None
                or abs((box[0]+box[2])-(self._box[0]+self._box[2])) > width*0.1
                or abs((box[1]+box[3])-(self._box[1]+self._box[3])) > height*0.1):
            self._display_box = list(box)
        else:
            self._display_box = [alpha*x+(1-alpha)*old for x, old in zip(box, self._display_box)]
        self._last_seen = stamp
        cx, cy = center if center is not None else ((box[0]+box[2])/2, (box[1]+box[3])/2)
        error = (cx-width/2)/width
        if self._filtered is None or error*self._filtered < 0:
            # Do not keep turning toward the old side after crossing the center.
            filtered = error
        else:
            a = self.config.smoothing_alpha
            filtered = a*error+(1-a)*self._filtered
        if abs(error) <= self.config.stop_threshold:
            filtered = error
        self._box, self._filtered = box, filtered
        magnitude = abs(filtered)
        # Decide on the RAW center every fresh frame. EMA must not delay a
        # threshold crossing or stop a turn while the actual center is outside.
        if abs(error) <= self.config.stop_threshold:
            self._turning = False
        elif abs(error) > self.config.start_threshold:
            self._turning = True
        if self._turning:
            speed = min(self.config.max_angular_speed,
                        max(self.config.min_angular_speed, self.config.kp*magnitude))
            command = "TURN_LEFT" if error < 0 else "TURN_RIGHT"
            angular = speed if error < 0 else -speed
            reason = "off_center"
        else:
            command, angular, reason = "STOP", 0.0, "within_deadband"
        self.result = AlignmentResult(command=command, reason=reason, angular_velocity=angular,
            found=True, center_x=cx, center_y=cy, error_px=cx-width/2,
            error_normalized=error, filtered_error_normalized=filtered,
            confidence=score, frame_time=stamp, target_id=self._target_id,
            box_xyxy=tuple(box), display_box_xyxy=tuple(self._display_box),
            center_verified=center is not None)
        return self.result


def draw_alignment_guides(image, config=None):
    """Draw the same fixed guides on processed and camera-only previews."""
    import cv2
    cfg = config if isinstance(config, AlignmentConfig) else AlignmentConfig.from_dict(config)
    canvas = image.copy()
    h, w = canvas.shape[:2]
    middle = round(w / 2)
    left = max(0, min(w-1, round(w * (0.5-cfg.start_threshold))))
    right = max(0, min(w-1, round(w * (0.5+cfg.start_threshold))))
    threshold_color = (0, 165, 255)  # Orange, BGR.
    for boundary in (left, right):
        cv2.line(canvas,(boundary,0),(boundary,h-1),threshold_color,2,cv2.LINE_AA)
    cv2.line(canvas,(middle,0),(middle,h-1),(255,220,0),2,cv2.LINE_AA)
    if h >= 100:
        for label,x,color in ((f"L {left}",left,threshold_color),
                              ("CENTER",middle,(255,220,0)),
                              (f"R {right}",right,threshold_color)):
            # Use staggered heights so the three nearby labels do not overlap.
            y = h-12 if label == "CENTER" else h-36
            cv2.putText(canvas,label,(max(2,min(w-65,x+4)),y),
                        cv2.FONT_HERSHEY_SIMPLEX,0.4,(0,0,0),3,cv2.LINE_AA)
            cv2.putText(canvas,label,(max(2,min(w-65,x+4)),y),
                        cv2.FONT_HERSHEY_SIMPLEX,0.4,color,1,cv2.LINE_AA)
    return canvas


def draw_alignment(image, result, config=None):
    """Draw the center, two raw trigger boundaries, selected center and command."""
    import cv2
    cfg = config if isinstance(config, AlignmentConfig) else AlignmentConfig.from_dict(config)
    canvas = draw_alignment_guides(image, cfg)
    h, w = canvas.shape[:2]
    middle = round(w / 2)
    color = (60,220,80) if result.command == "STOP" and result.found else (30,150,255)
    if result.found:
        point = (round(result.center_x),round(result.center_y))
        cv2.line(canvas,(middle,point[1]),point,color,2,cv2.LINE_AA)
        cv2.circle(canvas,point,6,color,-1,cv2.LINE_AA)
    error = "--" if result.error_px is None else f"{result.error_px:+.1f}px ({100*result.error_normalized:+.1f}%)"
    texts = [f"{result.command}  error: {error}",
             f"w: {result.angular_velocity:+.2f} rad/s  start: {100*cfg.start_threshold:g}%  stop: {100*cfg.stop_threshold:g}%"]
    scale = max(0.35,min(0.7,w/1000))
    for i,text in enumerate(texts):
        origin=(10,24+i*25)
        cv2.putText(canvas,text,origin,cv2.FONT_HERSHEY_SIMPLEX,scale,(0,0,0),4,cv2.LINE_AA)
        cv2.putText(canvas,text,origin,cv2.FONT_HERSHEY_SIMPLEX,scale,color,1,cv2.LINE_AA)
    return canvas
