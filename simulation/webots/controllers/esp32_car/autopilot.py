"""Obstacle avoidance matching src/obstacle_avoid.cpp, using simulation time.

The scanner stays centered while driving. After a front obstacle, the robot
reverses, checks the left at 135/180 degrees, then the right at 45/0 degrees.
"""

import math


class AutoPilot:
    FRONT_INTERVAL = 0.070
    SERVO_SETTLE = 0.250
    SERVO_CROSS_SETTLE = 0.350
    def __init__(self, safe_distance, reverse_cm=8, retry_reverse_cm=12,
                 reverse_ms_per_cm=50, left_90_ms=780, right_90_ms=780):
        self.safe_distance = safe_distance
        self.reverse_cm = reverse_cm
        self.retry_reverse_cm = retry_reverse_cm
        self.reverse_ms_per_cm = reverse_ms_per_cm
        self.left_turn_time = left_90_ms / 1000
        self.right_turn_time = right_90_ms / 1000
        self.reset(0)

    def reset(self, now):
        self.state = "CheckFront"
        self.started = now
        self.last_front = now - self.FRONT_INTERVAL
        self.movement = "STOPPED"
        self.angle = 90
        self.left135_clear = False
        self.right45_clear = False
        self.reverse_duration = 0
        self.turn_duration = self.left_turn_time

    def enter(self, state, now):
        self.state = state
        self.started = now

    def clear(self, distance):
        return math.isfinite(distance) and 2 <= distance <= 400 and distance > self.safe_distance

    def start_reverse(self, now, distance_cm):
        self.angle = 90
        self.left135_clear = self.right45_clear = False
        self.reverse_duration = distance_cm * self.reverse_ms_per_cm / 1000
        self.movement = "BACKWARD"
        self.enter("Reverse", now)

    def start_turn(self, now, right):
        self.angle = 90
        self.movement = "RIGHT" if right else "LEFT"
        self.turn_duration = self.right_turn_time if right else self.left_turn_time
        self.enter("Turn", now)

    def update(self, now, distance, *, strict=False):
        elapsed = now - self.started
        if strict and self.state not in ("Reverse", "Turn") and not (math.isfinite(distance) and 2 <= distance <= 400):
            self.movement = "STOPPED"
            return self.movement, self.angle
        if self.state == "CheckFront":
            if now - self.last_front < self.FRONT_INTERVAL - 1e-9:
                return self.movement, self.angle
            self.last_front = now
            if self.clear(distance):
                self.movement = "FORWARD"
            else:
                # A lost echo is unknown space; back away and scan.
                self.start_reverse(now, self.reverse_cm)
        elif self.state == "Reverse" and elapsed >= self.reverse_duration:
            self.movement = "STOPPED"
            self.angle = 135
            self.enter("ScanLeft135", now)
        elif self.state == "ScanLeft135" and elapsed >= self.SERVO_SETTLE:
            self.left135_clear = self.clear(distance)
            self.angle = 180
            self.enter("ScanLeft180", now)
        elif self.state == "ScanLeft180" and elapsed >= self.SERVO_SETTLE:
            if self.left135_clear and self.clear(distance):
                self.start_turn(now, right=False)
            else:
                self.angle = 45
                self.enter("ScanRight45", now)
        elif self.state == "ScanRight45" and elapsed >= self.SERVO_CROSS_SETTLE:
            self.right45_clear = self.clear(distance)
            self.angle = 0
            self.enter("ScanRight0", now)
        elif self.state == "ScanRight0" and elapsed >= self.SERVO_SETTLE:
            right_clear = self.right45_clear and self.clear(distance)
            if right_clear:
                self.start_turn(now, right=True)
            else:
                self.start_reverse(now, self.retry_reverse_cm)
        elif self.state == "Turn" and elapsed >= self.turn_duration:
            self.movement = "STOPPED" if strict else "FORWARD"
            self.last_front = now - self.FRONT_INTERVAL
            self.enter("CheckFront", now)
        return self.movement, self.angle
