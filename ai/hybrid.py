"""One hybrid session: local obstacle search, acknowledged stop, then AI follow.

The service rejects stale camera/results before calling this policy. SEARCH is
an instruction to the ESP32 autopilot, never a laptop-generated motor command.
"""
from dataclasses import dataclass
import math

from .follower import Decision, Follower

LOST_TARGET_SECONDS = 1.5
SERVO_SETTLE_SECONDS = 0.3


@dataclass(frozen=True)
class HybridDecision(Decision):
    behavior: str = "HOLD"


class HybridFollower:
    def __init__(self, *, alignment=None):
        self.alignment = alignment
        self.follower = Follower(alignment=alignment)
        self.phase = "SEARCH"
        self.last_frame = None
        self.missing_since = None
        self.actual_movement = None
        self.stopped_since = None
        self.tracking_since = None
        self.handoff_frame = None
        self.handoff_pending = False

    def feedback(self, movement, *, now):
        self.actual_movement = movement
        if movement == "STOPPED":
            if self.stopped_since is None:
                self.stopped_since = now
        else:
            self.stopped_since = None
        self.follower.feedback(movement, now=now)

    def step(self, observation, frame_id, now, distance):
        fresh = self.last_frame is None or frame_id > self.last_frame
        # Never count an out-of-order result as another confirmation frame.
        if self.last_frame is not None and frame_id < self.last_frame:
            return HybridDecision("CONFIRM_TARGET", reason="Chờ kết quả ảnh đúng thứ tự")
        self.last_frame = frame_id
        error = observation.get("error_normalized")
        found = (bool(observation.get("found")) and isinstance(error, (int, float))
                 and not isinstance(error, bool) and math.isfinite(error) and abs(error) <= 0.5)
        observation = dict(observation, found=found)
        decision = self.follower.step(observation, frame_id, now, distance)

        if not found:
            if self.phase == "SEARCH":
                return HybridDecision("SEARCH", reason="Tự di chuyển và né vật cản; đang tìm mục tiêu", behavior="SEARCH")
            if self.missing_since is None:
                self.missing_since = now
            self.phase = "LOST"
            if fresh and now - self.missing_since >= LOST_TARGET_SECONDS:
                self.phase = "SEARCH"
                self.follower = Follower(alignment=self.alignment)
                return HybridDecision("SEARCH", reason="Mất mục tiêu 1,5 giây; tiếp tục tự né vật cản", behavior="SEARCH")
            return HybridDecision("LOST_HOLD", reason="Mất mục tiêu; dừng chờ tối đa 1,5 giây trước khi về Auto")

        self.missing_since = None
        if self.phase != "TRACK":
            self.phase = "CONFIRM"
            if (not self.follower.locked or self.actual_movement != "STOPPED"
                    or self.stopped_since is None or now - self.stopped_since < 0.15):
                self.follower.last_movement = "STOPPED"
                return HybridDecision("CONFIRM_TARGET", reason="Dừng và xác nhận mục tiêu qua 3 ảnh mới liên tiếp")
            self.phase = "TRACK"
            self.tracking_since, self.handoff_frame = now, frame_id
            self.handoff_pending = True
            self.follower.last_movement = "STOPPED"
            return HybridDecision("HANDOFF", reason="Đưa cảm biến về trước; chờ số đo mới trước khi bám", behavior="TRACK")

        if self.handoff_pending:
            valid_distance = (isinstance(distance, (int, float)) and not isinstance(distance, bool)
                              and math.isfinite(distance) and 2 <= distance <= 400)
            if (now - self.tracking_since < SERVO_SETTLE_SECONDS or not fresh
                    or frame_id == self.handoff_frame or not valid_distance):
                self.follower.last_movement = "STOPPED"
                return HybridDecision("HANDOFF", reason="Chờ cảm biến ổn định và ảnh mục tiêu mới", behavior="TRACK")
            self.handoff_pending = False
        return HybridDecision(decision.state, decision.movement, decision.speed, decision.reason, "TRACK")
