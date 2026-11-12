import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from ai.follower import Follower
from ai.service import AIService
from yolov8n.target_alignment import AlignmentConfig, TargetAligner

sys.path.insert(0, str(Path(__file__).resolve().parents[2] /
                       "simulation/webots/controllers/esp32_car"))
from esp32_car import BridgeState


class FollowerTests(unittest.TestCase):
    def setUp(self):
        self.follower = Follower()
        self.now, self.frame = 10.0, 0

    def step(self, error=0, *, distance=100, found=True, fresh=True, dt=0.1, ack=True):
        self.now += dt
        self.frame += int(fresh)
        decision = self.follower.step(dict(found=found, error_normalized=error),
                                      self.frame, self.now, distance)
        if ack:
            self.follower.feedback(decision.movement, now=self.now)
        return decision

    def lock(self, error=0):
        self.step(error)
        self.step(error)
        return self.step(error)

    def start_turn(self, error=0.2):
        self.lock()
        self.assertEqual(self.step(error).state, "STOPPING")
        self.assertEqual(self.step(error).movement, "STOPPED")
        decision = self.step(error)
        self.assertEqual(decision.state, "ALIGN")
        return decision

    def test_initial_lock_needs_three_different_frames(self):
        self.assertEqual(self.step().movement, "STOPPED")
        for _ in range(4):
            self.assertEqual(self.step(fresh=False).movement, "STOPPED")
        self.assertEqual(self.step().movement, "STOPPED")
        self.assertEqual(self.step().movement, "FORWARD")

    def test_inside_band_and_exact_edges_keep_forward(self):
        self.lock()
        for error in (-0.15, -0.1, 0, 0.1, 0.15):
            with self.subTest(error=error):
                decision = self.step(error)
                self.assertEqual((decision.movement, decision.speed), ("FORWARD", 50))

    def test_both_edges_stop_then_turn_in_correct_direction(self):
        for error, direction in ((-0.151, "LEFT"), (0.151, "RIGHT")):
            with self.subTest(direction=direction):
                self.setUp()
                self.assertEqual(self.start_turn(error).movement, direction)

    def test_elapsed_time_alone_cannot_start_turn_without_stop_ack(self):
        self.lock()
        self.step(0.2, ack=False)
        for _ in range(4):
            self.assertEqual(self.step(0.2, dt=1, ack=False).movement, "STOPPED")
        self.follower.feedback("STOPPED", now=self.now)
        self.assertEqual(self.step(0.2, dt=0.14).movement, "STOPPED")
        self.assertEqual(self.step(0.2, dt=0.02).movement, "RIGHT")

    def test_turn_requires_new_image_after_pause(self):
        self.lock()
        self.step(0.2)
        self.assertEqual(self.step(0.2, fresh=False, dt=1).movement, "STOPPED")
        self.assertEqual(self.step(0.2).movement, "RIGHT")

    def test_entering_outer_band_does_not_end_alignment(self):
        self.start_turn()
        for error in (0.14, 0.12, 0.101):
            self.assertEqual(self.step(error).movement, "RIGHT")

    def test_turn_slows_near_center(self):
        for sign, direction in ((-1, "LEFT"), (1, "RIGHT")):
            with self.subTest(direction=direction):
                self.setUp()
                far = self.start_turn(sign * 0.2)
                self.assertEqual((far.movement, far.speed), (direction, 50))
                middle = self.step(sign * 0.125)
                near = self.step(sign * 0.101)
                self.assertEqual(middle.movement, direction)
                self.assertEqual(middle.speed, 45)
                self.assertEqual(near.movement, direction)
                self.assertLess(near.speed, middle.speed)
                self.assertLess(middle.speed, far.speed)
                self.assertEqual(near.speed, 40)
                centered = self.step(sign * 0.1)
                self.assertEqual((centered.movement, centered.speed), ("STOPPED", 0))

    def test_large_target_offset_cannot_exceed_turn_limit(self):
        for error in (-0.5, 0.5):
            with self.subTest(error=error):
                self.setUp()
                self.assertEqual(self.start_turn(error).speed, 50)

    def test_turn_slowdown_uses_custom_alignment_band(self):
        self.follower = Follower(alignment=AlignmentConfig(start_threshold=0.2,
                                                          stop_threshold=0.05))
        self.assertEqual(self.start_turn(0.25).speed, 50)
        self.assertEqual(self.step(0.125).speed, 45)
        self.assertEqual(self.step(0.051).speed, 40)
        self.assertEqual(self.step(0.05).movement, "STOPPED")

    def test_three_centered_images_stop_before_resuming_forward(self):
        self.start_turn()
        self.assertEqual(self.step(0.1).state, "CENTERING")
        for _ in range(3):
            self.assertEqual(self.step(0.1, fresh=False).state, "CENTERING")
        self.assertEqual(self.step(-0.1).movement, "STOPPED")
        self.assertEqual(self.step(0).movement, "STOPPED")
        self.assertFalse(self.follower.aligning)
        self.assertEqual(self.step(0.12).movement, "FORWARD")

    def test_center_confirmation_resets_if_target_drifts(self):
        self.start_turn()
        self.step(0)
        self.assertEqual(self.step(0.11).state, "STOPPING")
        self.step(0.11)
        self.assertEqual(self.step(0.11).movement, "RIGHT")
        self.assertEqual(self.step(0).state, "CENTERING")
        self.assertEqual(self.step(0).state, "CENTERING")

    def test_overshoot_stops_before_reversing_turn(self):
        self.start_turn()
        self.assertEqual(self.step(-0.14).state, "STOPPING")
        self.assertEqual(self.step(-0.14).movement, "STOPPED")
        self.assertEqual(self.step(-0.14).movement, "LEFT")

    def test_lost_target_never_searches_or_expires(self):
        self.start_turn()
        for delay in (0.1, 0.5, 3, 10, 300):
            decision = self.step(found=False, dt=delay)
            self.assertEqual((decision.state, decision.movement), ("LOST", "STOPPED"))
        self.assertEqual(self.step().movement, "STOPPED")
        self.assertEqual(self.step().movement, "STOPPED")
        self.assertEqual(self.step().movement, "FORWARD")

    def test_invalid_errors_stop_instead_of_turning(self):
        self.lock()
        for error in (None, math.nan, math.inf, "0.2", True, 0.6):
            with self.subTest(error=error):
                self.assertEqual(self.step(error).movement, "STOPPED")

    def test_distance_hold_and_release_thresholds_are_preserved(self):
        self.lock()
        self.assertEqual(self.step(distance=20).state, "DISTANCE_HOLD")
        self.assertEqual(self.step(distance=25).movement, "STOPPED")
        self.assertEqual(self.step(distance=26).movement, "FORWARD")
        for distance in (0, math.nan, 401):
            self.assertEqual(self.step(distance=distance).state, "SENSOR_HOLD")

    def test_sensor_hold_requires_new_pause_before_resuming_alignment(self):
        self.start_turn()
        self.assertEqual(self.step(0.12, distance=0).movement, "STOPPED")
        self.assertEqual(self.step(0.12).state, "STOPPING")
        self.assertEqual(self.step(0.12).movement, "STOPPED")
        self.assertEqual(self.step(0.12).movement, "RIGHT")


class AlignmentIntegrationTests(unittest.TestCase):
    def test_runtime_model_overrides_legacy_thresholds(self):
        from yolov8n.robot_ai import TargetAI
        root = Path(__file__).resolve().parents[2]
        ai = TargetAI(weights=root / "yolov8n/best.onnx", alignment=AlignmentConfig())
        self.assertEqual(ai.aligner.config.start_threshold, 0.15)
        self.assertEqual(ai.aligner.config.stop_threshold, 0.10)

    def test_raw_box_center_keeps_alignment_latched_until_ten_percent(self):
        aligner = TargetAligner()
        for i, (x, expected) in enumerate(((650, "STOP"), (651, "TURN_RIGHT"),
                                          (610, "TURN_RIGHT"), (601, "TURN_RIGHT"),
                                          (600, "STOP"), (610, "STOP"))):
            result = aligner.update([dict(xyxy=[x-100, 100, x+100, 300],
                                          confidence=0.9, class_id=11)],
                                    1000, 500, frame_time=i/10, now=i/10)
            self.assertEqual(result.command, expected)

    def test_guide_positions_use_the_same_runtime_thresholds(self):
        import numpy as np
        from yolov8n.target_alignment import draw_alignment_guides
        image = draw_alignment_guides(np.zeros((100, 1000, 3), dtype=np.uint8))
        self.assertEqual(image[10, 350].tolist(), [0, 165, 255])
        self.assertEqual(image[10, 500].tolist(), [255, 220, 0])
        self.assertEqual(image[10, 650].tolist(), [0, 165, 255])

    def test_control_tick_with_webots_ack_and_watchdog(self):
        clock = [10.0]
        bridge = BridgeState(clock=lambda: clock[0])
        claim = bridge.claim_ai(bridge.mode_epoch)
        bridge.update_simulation(0, 100)
        commands = []
        confirmed_speeds = []

        class Client:
            def command(self, session, sequence, movement, speed):
                commands.append((movement, speed))
                confirmed = bridge.command_ai(session, sequence, movement, speed)
                confirmed_speeds.append(confirmed["speed_percent"])
                return confirmed

            def release(self, session):
                return bridge.release_ai(session)

        with patch.object(AIService, "log"):
            with patch("ai.service.Path.exists", return_value=False):
                service = AIService()
            service.session = claim["session"]
            service.follower = Follower()
            service.robot_state = bridge.snapshot()
            service.camera_error = ""
            with patch("ai.service.RobotClient", return_value=Client()), \
                    patch("ai.service.time.monotonic", side_effect=lambda: clock[0]):
                for i, error in enumerate((0, 0, 0, 0.2, 0.2, 0.2, 0.125, 0.101, 0.1, 0, -0.1, 0.12)):
                    clock[0] += 0.1
                    service.result = dict(found=True, error_normalized=error)
                    service.result_id = i
                    service.frame_at = service.result_at = clock[0]
                    service.control_tick()
                self.assertEqual(commands, [("STOPPED", 0), ("STOPPED", 0), ("FORWARD", 50),
                                            ("STOPPED", 0), ("STOPPED", 0), ("RIGHT", 50),
                                            ("RIGHT", 45), ("RIGHT", 40), ("STOPPED", 0),
                                            ("STOPPED", 0), ("STOPPED", 0), ("FORWARD", 50)])
                self.assertEqual(confirmed_speeds, [speed for _, speed in commands])
                # Stale camera still releases its own session and stops Webots.
                clock[0] += 0.51
                service.control_tick()
                self.assertIsNone(service.session)
                self.assertEqual(bridge.snapshot()["movement"], "STOPPED")


if __name__ == "__main__":
    unittest.main()
