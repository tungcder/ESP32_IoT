"""Fan-scan avoidance matching src/obstacle_avoid.cpp, using simulation time.

Sonar measurements are sampled three times, at least 8 ms apart, without
blocking Webots' main loop. Sensor noise and real HC-SR04 echo physics differ.
"""

import math


class AutoPilot:
    FRONT_ANGLES = (90, 60, 120)
    FRONT_SEQUENCE = (0, 1, 0, 2)

    def __init__(self, safe_distance):
        self.safe_distance = safe_distance
        self.reset(0)

    def reset(self, now):
        self.state = "CheckFront"
        self.started = now
        self.last_front = 0
        self.movement = "STOPPED"
        self.angle = 90
        self.right = self.left = 0
        self.avoid_streak = 0
        self.last_avoid_end = 0
        self.turn_duration = 0.4
        self.reset_front_scan()

    def reset_front_scan(self):
        self.front_step = 0
        self.front_angle_set = False
        self.last_valid = [-1] * 3
        self.last_valid_time = [0.0] * 3
        self.samples = []
        self.last_sample = 0.0

    def read_distance(self, now, distance):
        if self.samples and now - self.last_sample < 0.008 - 1e-9:
            return None
        if len(self.samples) < 3:
            self.samples.append(int(distance) if math.isfinite(distance) else 0)
            self.last_sample = now
            return None
        median = sorted(self.samples)[1]
        self.samples = []
        return median if 2 <= median <= 200 else -1

    def front_blocked(self, now, slot, distance):
        threshold = self.safe_distance if slot == 0 else self.safe_distance * 13 // 10
        if distance != -1:
            self.last_valid[slot] = distance
            self.last_valid_time[slot] = now
            return distance <= threshold
        return (self.last_valid[slot] != -1
                and self.last_valid[slot] <= self.safe_distance * 2
                and now - self.last_valid_time[slot] < 1.0)

    def enter(self, state, now):
        self.state = state
        self.started = now

    def update(self, now, distance):
        elapsed = now - self.started
        if self.state == "CheckFront":
            slot = self.FRONT_SEQUENCE[self.front_step]
            if not self.front_angle_set:
                self.angle = self.FRONT_ANGLES[slot]
                self.front_angle_set = True
                self.last_front = now
                return self.movement, self.angle
            if now - self.last_front < 0.12 - 1e-9:
                return self.movement, self.angle
            measured = self.read_distance(now, distance)
            if measured is None:
                return self.movement, self.angle
            blocked = self.front_blocked(now, slot, measured)
            self.front_angle_set = False
            self.front_step = (self.front_step + 1) % len(self.FRONT_SEQUENCE)
            if not blocked:
                self.movement = "FORWARD"
            else:
                self.reset_front_scan()
                self.movement = "BACKWARD"
                self.enter("Reverse", now)
        elif self.state == "Reverse" and elapsed >= 0.3:
            self.movement = "STOPPED"
            self.enter("StopBeforeScan", now)
        elif self.state == "StopBeforeScan" and elapsed >= 0.1:
            self.angle = 10
            self.enter("PointRight", now)
        elif self.state == "PointRight" and elapsed >= 0.3:
            measured = self.read_distance(now, distance)
            if measured is None:
                return self.movement, self.angle
            self.right = 0 if measured == -1 else measured
            self.angle = 90
            self.enter("CenterAfterRight", now)
        elif self.state == "CenterAfterRight" and elapsed >= 0.2:
            self.angle = 170
            self.enter("PointLeft", now)
        elif self.state == "PointLeft" and elapsed >= 0.3:
            measured = self.read_distance(now, distance)
            if measured is None:
                return self.movement, self.angle
            self.left = 0 if measured == -1 else measured
            self.angle = 90
            self.enter("CenterAfterLeft", now)
        elif self.state == "CenterAfterLeft" and elapsed >= 0.2:
            if self.right <= self.safe_distance and self.left <= self.safe_distance:
                self.movement = "RIGHT"
                self.turn_duration = 0.9
            else:
                if now - self.last_avoid_end < 2.5:
                    self.avoid_streak = min(self.avoid_streak + 1, 3)
                else:
                    self.avoid_streak = 0
                self.turn_duration = 0.4 + self.avoid_streak * 0.15
                self.movement = "RIGHT" if self.right > self.left else "LEFT"
            self.enter("Turn", now)
        elif self.state == "Turn" and elapsed >= self.turn_duration:
            self.movement = "STOPPED"
            self.enter("FinishTurn", now)
        elif self.state == "FinishTurn" and elapsed >= 0.1:
            self.last_avoid_end = now
            self.reset_front_scan()
            self.angle = 90
            self.enter("CheckFront", now)
        return self.movement, self.angle
