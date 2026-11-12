"""Follow inside the guide band; stop before aligning, never search blindly."""
from dataclasses import dataclass
import math

from yolov8n.target_alignment import AlignmentConfig

AI_FORWARD_SPEED_PERCENT = 50
AI_TURN_SPEED_PERCENT = 50
AI_MIN_TURN_SPEED_PERCENT = 40


@dataclass(frozen=True)
class Decision:
    state: str
    movement: str = "STOPPED"
    speed: int = 0
    reason: str = ""


class Follower:
    def __init__(self, *, alignment=None, stop_pause=0.15, lock_frames=3):
        self.alignment = (alignment if isinstance(alignment, AlignmentConfig)
                          else AlignmentConfig.from_dict(alignment))
        if not math.isfinite(stop_pause) or stop_pause < 0:
            raise ValueError("Thời gian dừng phải hữu hạn và không âm.")
        if isinstance(lock_frames, bool) or not isinstance(lock_frames, int) or lock_frames < 1:
            raise ValueError("Số ảnh xác nhận phải là số nguyên dương.")
        self.stop_pause, self.lock_frames = stop_pause, lock_frames
        self.state = "WAIT_TARGET"
        self.last_frame = None
        self.confirmed = 0
        self.candidate = None
        self.locked = False
        self.aligning = False
        self.centered = 0
        self.distance_hold = False
        self.last_movement = "STOPPED"
        self.actual_movement = None
        self.stopped_since = None
        self.pause_frame = None
        self.turn_direction = None
        self.target_id = None

    def feedback(self, movement, *, now):
        self.actual_movement = movement
        if self.last_movement == "STOPPED" and movement == "STOPPED":
            if self.stopped_since is None:
                self.stopped_since = now
        else:
            self.stopped_since = None

    def _pause(self, frame_id):
        self.state = "STOPPING"
        self.pause_frame = frame_id
        self.stopped_since = None
        self.turn_direction = None
        self.centered = 0

    def step(self, observation, frame_id, now, distance):
        fresh = frame_id != self.last_frame
        self.last_frame = frame_id
        error = observation.get("error_normalized")
        found = (bool(observation.get("found")) and isinstance(error, (int, float))
                 and not isinstance(error, bool) and math.isfinite(error) and abs(error) <= 0.5)
        target_id = observation.get("target_id")
        if found and target_id is not None and target_id != self.target_id:
            self.target_id = target_id
            self.locked = self.aligning = False
            self.confirmed = self.centered = 0
            self.candidate = self.turn_direction = None
            self.state = "WAIT_TARGET"

        def result(reason, movement="STOPPED", speed=0):
            self.last_movement = movement
            if movement != "STOPPED":
                self.stopped_since = None
            return Decision(self.state, movement, speed, reason)

        if not found:
            self.state = "WAIT_TARGET" if self.state == "WAIT_TARGET" else "LOST"
            self.locked = self.aligning = False
            self.confirmed = self.centered = 0
            self.candidate = self.turn_direction = None
            return result("Chờ mục tiêu xuất hiện" if self.state == "WAIT_TARGET"
                          else "Mất mục tiêu; dừng tại chỗ và chờ, không quay tìm")

        if fresh:
            continuous = self.candidate is None or abs(error - self.candidate) < 0.18
            self.confirmed = self.confirmed + 1 if continuous else 1
            self.candidate = error
        if not self.locked:
            if self.confirmed < self.lock_frames:
                return result("Đang xác nhận mục tiêu qua các ảnh mới")
            self.locked = True

        valid_distance = (isinstance(distance, (int, float)) and not isinstance(distance, bool)
                          and math.isfinite(distance) and 2 <= distance <= 400)
        if not valid_distance:
            self.state, self.centered = "SENSOR_HOLD", 0
            return result("Dừng: cảm biến siêu âm chưa có số đo hợp lệ")
        if distance <= 20:
            self.distance_hold = True
        elif distance > 25:
            self.distance_hold = False
        if self.distance_hold:
            self.state, self.centered = "DISTANCE_HOLD", 0
            return result("Dừng ở 20 cm; chờ khoảng cách lớn hơn 25 cm")

        if not self.aligning:
            if abs(error) <= self.alignment.start_threshold:
                self.state = "TRACK"
                return result("Mục tiêu trong hai line; giữ hướng đi thẳng",
                              "FORWARD", AI_FORWARD_SPEED_PERCENT)
            self.aligning = True
            self._pause(frame_id)
            return result("Mục tiêu vượt line; dừng trước khi xoay căn tâm")

        if self.state not in ("STOPPING", "ALIGN", "CENTERING"):
            self._pause(frame_id)
            return result("Dừng trước khi tiếp tục căn tâm")
        if self.state == "STOPPING":
            if (self.actual_movement != "STOPPED" or self.stopped_since is None
                    or now - self.stopped_since < self.stop_pause
                    or not fresh or frame_id == self.pause_frame):
                return result("Chờ xác nhận dừng và ảnh mới trước khi xoay")

        if abs(error) <= self.alignment.stop_threshold:
            self.state = "CENTERING"
            if fresh:
                self.centered += 1
            if self.centered >= self.lock_frames:
                self.aligning = False
                self.state = "TRACK"
                self.turn_direction = None
                return result(f"Đã căn giữa qua {self.lock_frames} ảnh mới; dừng quay trước khi tiến")
            return result(f"Đang xác nhận căn giữa: {self.centered}/{self.lock_frames} ảnh mới")

        self.centered = 0
        direction = "LEFT" if error < 0 else "RIGHT"
        if (self.state == "CENTERING"
                or self.turn_direction is not None and direction != self.turn_direction):
            self._pause(frame_id)
            return result("Dừng để đo lại trước khi chỉnh hướng quay")
        self.state, self.turn_direction = "ALIGN", direction
        # Reach minimum PWM at the stop band, before momentum carries us past it.
        remaining = abs(error) - self.alignment.stop_threshold
        band_width = self.alignment.start_threshold - self.alignment.stop_threshold
        ratio = min(1.0, max(0.0, remaining / band_width))
        speed = round(AI_MIN_TURN_SPEED_PERCENT
                      + (AI_TURN_SPEED_PERCENT - AI_MIN_TURN_SPEED_PERCENT) * ratio)
        return result("Xoay tại chỗ về line giữa; giảm tốc khi gần tâm", direction, speed)
