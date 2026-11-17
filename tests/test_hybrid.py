"""Hybrid policy, Webots contract and service integration without moving hardware.

Run: python -m unittest discover -s tests -v
"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "simulation/webots/controllers/esp32_car"))
from esp32_car import BridgeState
from ai.hybrid import HybridFollower
from ai.service import AIService


def observation(found=True, target_id=1, error=0):
    return dict(found=found, target_id=target_id, error_normalized=error)


class Clock:
    def __init__(self):
        self.now = 10.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = HybridFollower()

    def test_initial_absence_searches_without_motor_commands(self):
        result = self.policy.step(observation(False), 1, 10, 100)
        self.assertEqual((result.behavior, result.movement, result.speed), ("SEARCH", "STOPPED", 0))

    def test_three_distinct_frames_and_acknowledged_stop_are_required(self):
        self.policy.feedback("FORWARD", now=10)
        for frame, stamp in ((1, 10), (1, 10.1), (1, 10.2), (2, 10.3), (3, 10.4)):
            result = self.policy.step(observation(), frame, stamp, 100)
            self.assertEqual(result.behavior, "HOLD")
        self.policy.feedback("STOPPED", now=10.4)
        self.assertEqual(self.policy.step(observation(), 4, 10.5, 100).behavior, "HOLD")
        self.assertEqual(self.policy.step(observation(), 5, 10.6, 100).state, "HANDOFF")

    def lock_target(self):
        self.policy.feedback("STOPPED", now=10)
        for frame in range(1, 4):
            result = self.policy.step(observation(), frame, 10 + frame * .1, 100)
        self.assertEqual(result.state, "HANDOFF")

    def test_handoff_waits_for_settle_new_frame_and_valid_sonar(self):
        self.lock_target()
        self.assertEqual(self.policy.step(observation(), 4, 10.4, 100).movement, "STOPPED")
        self.assertEqual(self.policy.step(observation(), 4, 10.7, 100).movement, "STOPPED")
        self.assertEqual(self.policy.step(observation(), 5, 10.8, 0).movement, "STOPPED")
        self.assertEqual(self.policy.step(observation(), 6, 10.9, 100).movement, "FORWARD")
        # Reusing a still-fresh result after handoff must not cause pulsing stops.
        self.assertEqual(self.policy.step(observation(), 6, 11, 100).movement, "FORWARD")

    def test_loss_stops_immediately_then_returns_to_search(self):
        self.lock_target()
        result = self.policy.step(observation(False), 4, 10.4, 100)
        self.assertEqual((result.state, result.behavior, result.movement), ("LOST_HOLD", "HOLD", "STOPPED"))
        self.assertEqual(self.policy.step(observation(False), 5, 11.8, 100).behavior, "HOLD")
        self.assertEqual(self.policy.step(observation(False), 6, 12, 100).behavior, "SEARCH")

    def test_duplicate_absence_cannot_trigger_search(self):
        self.lock_target()
        self.policy.step(observation(False), 4, 10.4, 100)
        self.assertEqual(self.policy.step(observation(False), 4, 12, 100).behavior, "HOLD")

    def test_transient_candidate_returns_to_search(self):
        self.policy.step(observation(), 1, 10, 100)
        self.policy.step(observation(False), 2, 10.1, 100)
        self.assertEqual(self.policy.step(observation(False), 3, 11.7, 100).behavior, "SEARCH")

    def test_changing_target_restarts_confirmation(self):
        self.policy.feedback("STOPPED", now=10)
        for frame, target in ((1, 1), (2, 1), (3, 2), (4, 2)):
            result = self.policy.step(observation(target_id=target), frame, 10 + frame * .1, 100)
            self.assertEqual(result.behavior, "HOLD")
        self.assertEqual(self.policy.step(observation(target_id=2), 5, 10.5, 100).behavior, "TRACK")

    def test_nan_and_invalid_positions_do_not_acquire(self):
        for frame, error in enumerate((float("nan"), float("inf"), True, .6), 1):
            self.assertEqual(self.policy.step(observation(error=error), frame, 10 + frame * .1, 100).behavior, "SEARCH")

    def test_distance_hold_never_falls_back_to_search(self):
        self.lock_target()
        for frame in range(4, 30):
            result = self.policy.step(observation(), frame, 10 + frame * .1, 15)
            self.assertEqual((result.behavior, result.movement), ("TRACK", "STOPPED"))

    def test_tracking_stops_at_50_cm_and_resumes_only_above_55_cm(self):
        self.lock_target()
        readings = ((100, "FORWARD"), (51, "FORWARD"), (50, "STOPPED"),
                    (49, "STOPPED"), (51, "STOPPED"), (55, "STOPPED"),
                    (56, "FORWARD"))
        for frame, (distance, expected) in enumerate(readings, 4):
            with self.subTest(distance=distance, frame=frame):
                result = self.policy.step(observation(), frame, 11 + frame * .1, distance)
                self.assertEqual((result.behavior, result.movement), ("TRACK", expected))

    def test_handoff_handles_missing_and_malformed_sonar(self):
        self.lock_target()
        for frame, distance in enumerate((None, True, float("nan"), float("inf"), "100"), 4):
            result = self.policy.step(observation(), frame, 11 + frame * .1, distance)
            self.assertEqual((result.behavior, result.movement), ("TRACK", "STOPPED"))


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.state = BridgeState(clock=self.clock)
        self.session = self.state.claim_ai(self.state.mode_epoch, hybrid=True)["session"]
        self.seq = 0

    def command(self, behavior, movement="STOPPED", speed=0):
        self.seq += 1
        return self.state.command_ai(self.session, self.seq, movement, speed, behavior=behavior)

    def test_search_heartbeats_preserve_autopilot_movement(self):
        self.command("SEARCH")
        self.state.update_simulation(0, 100)
        self.clock.advance(.31)
        self.state.update_simulation(.31, 100)
        self.assertEqual(self.state.movement, "FORWARD")
        self.command("SEARCH")
        self.assertEqual(self.state.movement, "FORWARD")

    def test_auto_and_hybrid_search_start_avoidance_at_50_cm(self):
        for hybrid in (False, True):
            for distance, expected in ((51, "FORWARD"), (50, "BACKWARD"), (49, "BACKWARD")):
                with self.subTest(hybrid=hybrid, distance=distance):
                    bridge = BridgeState(clock=self.clock)
                    if hybrid:
                        session = bridge.claim_ai(bridge.mode_epoch, hybrid=True)["session"]
                        bridge.command_ai(session, 1, "STOPPED", 0, behavior="SEARCH")
                        self.clock.advance(.31)
                    else:
                        bridge.select_mode("AUTO")
                    bridge.update_simulation(self.clock(), distance)
                    self.assertEqual(bridge.movement, expected)

    def test_auto_turns_at_70_percent_and_manual_turns_at_80_percent(self):
        turn_paths = {
            "LEFT": ((0, 10), (.41, 100), (.26, 100), (.26, 100)),
            "RIGHT": ((0, 10), (.41, 100), (.26, 10), (.26, 10), (.36, 100), (.26, 100)),
        }
        for hybrid in (False, True):
            for direction, readings in turn_paths.items():
                with self.subTest(hybrid=hybrid, direction=direction):
                    bridge = BridgeState(clock=self.clock)
                    if hybrid:
                        session = bridge.claim_ai(bridge.mode_epoch, hybrid=True)["session"]
                        bridge.command_ai(session, 1, "STOPPED", 0, behavior="SEARCH")
                        self.clock.advance(.31)
                    else:
                        bridge.select_mode("AUTO")
                    for sequence, (elapsed, distance) in enumerate(readings, 2):
                        if hybrid:
                            bridge.command_ai(session, sequence, "STOPPED", 0, behavior="SEARCH")
                        self.clock.advance(elapsed)
                        bridge.update_simulation(self.clock(), distance)
                    self.assertEqual((bridge.movement, bridge.speed_percent), (direction, 70))
                    bridge.select_mode("MANUAL")
                    bridge.command("/" + direction.lower(), bridge.mode_epoch)
                    self.assertEqual((bridge.movement, bridge.speed_percent), (direction, 80))

    def test_search_timeout_stops_and_revokes_old_session(self):
        self.command("SEARCH")
        self.clock.advance(.51)
        status = self.state.snapshot()
        self.assertEqual((status["drive_mode"], status["movement"], status["ai_active"]), ("MANUAL", "STOPPED", False))
        self.assertIsNone(self.command("SEARCH"))

    def test_hold_interrupts_reverse_and_scanner(self):
        self.command("SEARCH")
        self.clock.advance(.31)
        self.state.update_simulation(.31, 10)
        self.assertEqual(self.state.movement, "BACKWARD")
        self.command("HOLD")
        self.assertEqual(self.state.update_simulation(.32, 10)[:2], ("STOPPED", 90))

    def test_new_search_restarts_front_check_instead_of_old_turn(self):
        self.command("SEARCH")
        self.state.pilot.state = "Turn"
        self.command("HOLD")
        self.command("SEARCH")
        self.state.update_simulation(1, 100)
        self.assertEqual(self.state.pilot.state, "CheckFront")
        self.assertEqual(self.state.movement, "STOPPED")

    def test_tracking_cannot_move_until_new_centered_sensor_read(self):
        self.command("TRACK", "LEFT", 62)
        self.assertEqual(self.state.movement, "STOPPED")
        self.assertEqual(self.state.snapshot()["distance_cm"], 0)
        self.clock.advance(.31)
        self.state.update_simulation(.31, 100)
        self.assertEqual(self.state.movement, "LEFT")

    def test_invalid_sonar_stops_search_instead_of_reversing(self):
        self.command("SEARCH")
        self.clock.advance(.31)
        self.state.update_simulation(.31, 0)
        self.assertEqual(self.state.movement, "STOPPED")
        self.assertEqual(self.state.pilot.state, "CheckFront")

    def test_ai_distance_guard_and_hysteresis_stay_active(self):
        self.command("TRACK", "FORWARD", 50)
        self.clock.advance(.31)
        for distance, expected in ((100, "FORWARD"), (51, "FORWARD"), (50, "STOPPED"),
                                   (49, "STOPPED"), (51, "STOPPED"), (55, "STOPPED"),
                                   (56, "FORWARD"), (0, "STOPPED")):
            self.clock.advance(.08)
            self.command("TRACK", "FORWARD", 50)
            self.state.update_simulation(self.clock(), distance)
            self.assertEqual(self.state.movement, expected)

    def test_manual_and_estop_prevent_reclaim(self):
        for stop in (lambda: self.state.command("/drivemanual", self.state.mode_epoch), self.state.emergency):
            stop()
            self.assertIsNone(self.command("SEARCH"))
        self.assertFalse(self.state.release_ai(self.session))

    def test_release_stops_search_and_returns_manual(self):
        self.command("SEARCH")
        self.assertTrue(self.state.release_ai(self.session))
        self.assertEqual(self.state.drive_mode, "MANUAL")
        self.assertEqual(self.state.update_simulation(5, 100)[0], "STOPPED")

    def test_repeated_sequence_and_cross_protocol_commands_are_rejected(self):
        self.command("SEARCH")
        self.assertIsNone(self.state.command_ai(self.session, self.seq, "STOPPED", 0, behavior="HOLD"))
        self.assertIsNone(self.state.command_ai(self.session, self.seq + 1, "FORWARD", 50))
        with self.assertRaises(ValueError):
            self.command("SEARCH", "FORWARD", 50)

    def test_legacy_auto_and_ai_still_work(self):
        self.state.select_mode("AUTO")
        self.assertEqual(self.state.update_simulation(0, 100)[0], "FORWARD")
        session = self.state.claim_ai(self.state.mode_epoch)["session"]
        self.assertEqual(self.state.command_ai(session, 1, "FORWARD", 50)["movement"], "FORWARD")
        self.assertIsNone(self.state.command_ai(session, 2, "STOPPED", 0, behavior="SEARCH"))


class LocalClient:
    def __init__(self, state):
        self.state = state
        self.claims = 0

    def status(self):
        return self.state.snapshot()

    def claim(self, epoch):
        self.claims += 1
        return self.state.claim_ai(epoch)

    def claim_hybrid(self, epoch):
        self.claims += 1
        return self.state.claim_ai(epoch, hybrid=True)

    def hybrid_command(self, session, sequence, behavior, movement, speed):
        return self.state.command_ai(session, sequence, movement, speed, behavior=behavior)

    def command(self, session, sequence, movement, speed):
        return self.state.command_ai(session, sequence, movement, speed)

    def release(self, session):
        if not self.state.release_ai(session):
            raise ValueError("Revoked session")
        return self.state.snapshot()


class ServiceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.state = BridgeState(clock=self.clock)
        self.client = LocalClient(self.state)
        log_patch = patch.object(AIService, "log")
        log_patch.start()
        self.addCleanup(log_patch.stop)
        config = ROOT / "tests" / "__missing_hybrid_config__.json"
        self.assertFalse(config.exists())
        self.service = AIService(config_path=config)
        client_patch = patch("ai.service.RobotClient", return_value=self.client)
        client_patch.start()
        self.addCleanup(client_patch.stop)
        time_patch = patch("ai.service.time.monotonic", self.clock)
        time_patch.start()
        self.addCleanup(time_patch.stop)
        self.service.model_ready = True
        self.service.camera_error = ""
        self.frame = 0
        self.feed(False)

    def feed(self, found):
        self.frame += 1
        self.service.result = observation(found)
        self.service.result_id = self.frame
        self.service.frame_at = self.service.result_at = self.clock()

    def tick(self, found, seconds=.1, distance=100):
        self.clock.advance(seconds)
        self.state.update_simulation(self.clock(), distance)
        self.feed(found)
        self.service.control_tick()
        self.state.update_simulation(self.clock(), distance)

    def test_full_search_follow_loss_search_cycle_uses_one_session(self):
        self.service.start("HYBRID")
        session = self.service.session
        self.assertEqual((self.state.hybrid_state, self.state.movement), ("HOLD", "STOPPED"))
        for _ in range(6):
            self.tick(False)
        self.assertEqual((self.state.hybrid_state, self.state.movement), ("SEARCH", "FORWARD"))
        self.tick(True)
        self.assertEqual((self.state.hybrid_state, self.state.movement), ("HOLD", "STOPPED"))
        for _ in range(9):
            self.tick(True)
        self.assertEqual((self.state.hybrid_state, self.state.movement, self.state.speed_percent),
                         ("TRACK", "FORWARD", 45))
        self.tick(False)
        self.assertEqual((self.state.hybrid_state, self.state.movement), ("HOLD", "STOPPED"))
        for _ in range(22):
            self.tick(False)
        self.assertEqual((self.state.hybrid_state, self.state.movement), ("SEARCH", "FORWARD"))
        self.assertEqual(self.service.session, session)
        self.assertEqual(self.client.claims, 1)

    def test_camera_stale_ends_search_and_never_restarts(self):
        self.service.start("HYBRID")
        self.tick(False)
        self.clock.advance(.51)
        self.service.control_tick()
        self.assertIsNone(self.service.session)
        self.assertEqual(self.state.drive_mode, "MANUAL")
        self.feed(False)
        self.service.control_tick()
        self.assertEqual(self.client.claims, 1)

    def test_old_firmware_cannot_be_claimed_as_hybrid(self):
        with patch.object(self.client, "status", return_value=dict(mode_epoch=1)):
            with self.assertRaisesRegex(ValueError, "firmware"):
                self.service.start("HYBRID")
        self.assertEqual(self.client.claims, 0)

    def test_stop_during_search_confirms_manual(self):
        self.service.start("HYBRID")
        self.tick(False)
        self.service.stop()
        self.assertEqual(self.service.robot_state["drive_mode"], "MANUAL")
        self.assertFalse(self.service.robot_state["ai_active"])

    def test_start_failure_releases_claim(self):
        with patch.object(self.client, "hybrid_command", side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                self.service.start("HYBRID")
        self.assertIsNone(self.service.session)
        self.assertEqual(self.state.drive_mode, "MANUAL")

    def test_ai_only_preserves_wait_target_behavior(self):
        self.service.start()
        self.tick(False)
        self.assertEqual(self.state.drive_mode, "AI")
        self.assertEqual(self.state.movement, "STOPPED")

    def test_network_fault_ends_session_without_reclaim(self):
        self.service.start("HYBRID")
        self.tick(False)
        with patch.object(self.client, "hybrid_command", side_effect=TimeoutError("Wi-Fi lost")), \
                patch.object(self.service.control_wake, "wait", side_effect=lambda _: self.service.shutdown_event.set()):
            self.service.control_loop()
        self.assertIsNone(self.service.session)
        self.assertEqual(self.service.decision["state"], "FAULT")
        self.assertEqual(self.state.drive_mode, "MANUAL")
        self.assertEqual(self.client.claims, 1)


if __name__ == "__main__":
    unittest.main()
