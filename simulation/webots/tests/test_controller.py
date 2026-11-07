import json
import os
from pathlib import Path
import socket
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "controllers/esp32_car"))
from esp32_car import (BridgeState, ControllerServer, WHEEL_DIRECTIONS,
                       scanner_position_radians, server_port)
from autopilot import AutoPilot


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.state = BridgeState(clock=lambda: self.now)

    def advance_until(self, predicate, distance, limit=3):
        until = self.state.sim_time + limit
        while self.state.sim_time < until:
            self.state.update_simulation(self.state.sim_time + 0.016, distance)
            if predicate():
                return
        self.fail("Simulation condition not reached")

    def test_lost_manual_commands_stop_and_turn_leds_off(self):
        self.state.command("/forward")
        self.assertEqual(self.state.snapshot()["leds"], [True, True, False, False])
        self.now += 0.51
        self.state.update_simulation(1, 100)
        snapshot = self.state.snapshot()
        self.assertEqual(snapshot["movement"], "STOPPED")
        self.assertEqual(snapshot["leds"], [False] * 4)
        self.assertIn("timeout", snapshot["events"][-1]["message"])

    def test_commands_refresh_watchdog(self):
        self.state.command("/left")
        self.now += 0.4
        self.state.command("/left")
        self.now += 0.4
        self.assertEqual(self.state.snapshot()["movement"], "LEFT")

    def test_manual_stop_cannot_cancel_auto(self):
        self.state.command("/driveauto")
        self.state.update_simulation(0, 10)
        self.advance_until(lambda: self.state.pilot.state == "ScanLeft45", 10)
        self.assertEqual(self.state.pilot.angle, 45)
        self.assertIsNone(self.state.command("/stop"))
        movement, angle, _ = self.state.update_simulation(self.state.sim_time + 0.016, 10)
        self.assertEqual(self.state.drive_mode, "AUTO")
        self.assertEqual(self.state.pilot.state, "ScanLeft45")
        self.assertEqual(angle, 45)

    def test_auto_ignores_manual_watchdog_and_reentry_resets(self):
        self.state.command("/driveauto")
        self.state.update_simulation(0, 100)
        self.advance_until(lambda: self.state.movement == "FORWARD", 100)
        self.now += 5
        self.assertEqual(self.state.snapshot()["movement"], "FORWARD")
        self.advance_until(lambda: self.state.pilot.state == "Reverse", 10)
        self.state.command("/driveauto")
        self.state.update_simulation(2, 100)
        self.advance_until(lambda: self.state.movement == "FORWARD", 100)
        self.assertEqual(self.state.pilot.state, "CheckFront")
        self.assertEqual(self.state.movement, "FORWARD")

    def test_leds_follow_movement_without_led_controls(self):
        self.assertFalse(self.state.command("/ledon"))
        self.state.command("/forward")
        self.assertEqual(self.state.snapshot()["leds"], [True, True, False, False])
        self.state.command("/stop")
        self.assertEqual(self.state.snapshot()["leds"], [False] * 4)

    def test_no_echo_front_reverses_instead_of_stalling(self):
        self.state.command("/driveauto")
        self.state.update_simulation(1, float("nan"))
        self.assertEqual(self.state.pilot.state, "Reverse")
        self.assertEqual(self.state.movement, "BACKWARD")
        self.advance_until(lambda: self.state.pilot.state == "ScanLeft45", float("nan"))
        self.assertEqual(self.state.distance_cm, 0)
        self.assertEqual(self.state.movement, "STOPPED")

    def test_auto_scans_left_first_then_right_and_turns(self):
        cases = (
            (100, 100, 10, 10, "LEFT", 0.78),
            (10, 100, 100, 100, "RIGHT", 0.78),
            (100, 10, 100, 100, "RIGHT", 0.78),
        )
        for left45, left0, right135, right180, expected, duration in cases:
            with self.subTest(expected=expected, duration=duration):
                pilot = AutoPilot(40)
                pilot.reset(10)
                for step in range(400):
                    distance = {
                        "ScanLeft45": left45, "ScanLeft0": left0,
                        "ScanRight135": right135, "ScanRight180": right180,
                    }.get(pilot.state, 10)
                    pilot.update(10 + step * 0.016, distance)
                    if pilot.state == "Turn":
                        break
                self.assertEqual(pilot.state, "Turn")
                self.assertEqual((pilot.movement, pilot.angle), (expected, 90))
                self.assertAlmostEqual(pilot.turn_duration, duration)

    def test_scanner_stays_centered_while_driving(self):
        pilot = AutoPilot(25)
        readings = [pilot.update(step * 0.016, 100) for step in range(100)]
        self.assertTrue(all(angle == 90 for _, angle in readings))
        self.assertTrue(all(movement == "FORWARD" for movement, _ in readings))

    def test_distance_validation_treats_lost_echo_as_blocked(self):
        pilot = AutoPilot(40)
        self.assertFalse(pilot.clear(float("nan")))
        self.assertFalse(pilot.clear(0))
        self.assertFalse(pilot.clear(40))
        self.assertTrue(pilot.clear(41))
        self.assertTrue(pilot.clear(300))

    def test_turn_resumes_forward_with_sensor_centered(self):
        pilot = AutoPilot(25)
        pilot.start_turn(10, right=False)
        self.assertEqual(pilot.update(10.79, 100), ("FORWARD", 90))
        self.assertEqual(pilot.state, "CheckFront")

    def test_wall_at_40_cm_starts_20_cm_reverse_before_scan(self):
        pilot = self.state.pilot
        self.assertEqual(pilot.update(0, 41), ("FORWARD", 90))
        self.assertEqual(pilot.update(0.08, 40), ("BACKWARD", 90))
        self.assertAlmostEqual(pilot.reverse_duration, 20 * 50 / 1000)
        self.assertEqual(pilot.update(1.07, 100), ("BACKWARD", 90))
        self.assertEqual(pilot.update(1.09, 100), ("STOPPED", 45))

    def test_both_sides_blocked_reverse_30_cm_and_repeat_without_turning(self):
        pilot = AutoPilot(40)
        retries = 0
        for step in range(1000):
            previous = pilot.state
            movement, angle = pilot.update(step * 0.016, 10)
            self.assertNotIn(movement, ("LEFT", "RIGHT"))
            if previous == "ScanRight180" and pilot.state == "Reverse":
                retries += 1
                self.assertEqual((movement, angle), ("BACKWARD", 90))
                self.assertAlmostEqual(pilot.reverse_duration, 30 * 50 / 1000)
        self.assertGreaterEqual(retries, 3)

    def test_manual_mode_cancels_each_auto_phase_and_does_not_resume(self):
        for phase in ("CheckFront", "Reverse", "ScanLeft45", "ScanLeft0",
                      "ScanRight135", "ScanRight180", "Turn"):
            with self.subTest(phase=phase):
                state = BridgeState(clock=lambda: self.now)
                state.command("/driveauto")
                state.update_simulation(0, 100)
                state.pilot.state = phase
                state.command("/drivemanual")
                for now in (1, 5, 20):
                    movement, angle, _ = state.update_simulation(now, 100)
                    self.assertEqual((movement, angle), ("STOPPED", 90))

    def test_turn_wheel_directions(self):
        self.assertEqual(WHEEL_DIRECTIONS["LEFT"], (-1, 1))
        self.assertEqual(WHEEL_DIRECTIONS["RIGHT"], (1, -1))

    def test_scanner_angles_match_real_left_right_orientation(self):
        self.assertGreater(scanner_position_radians(0), 0)
        self.assertEqual(scanner_position_radians(90), 0)
        self.assertLess(scanner_position_radians(180), 0)

    def test_port_override_and_invalid_configuration(self):
        with patch.dict(os.environ, {"ESP32_WEBOTS_PORT": "8082"}):
            self.assertEqual(server_port(), 8082)
        for value in ("0", "65536", "abc"):
            with self.subTest(value=value), patch.dict(os.environ, {"ESP32_WEBOTS_PORT": value}):
                with self.assertRaisesRegex(ValueError, "ESP32_WEBOTS_PORT"):
                    server_port()

    def test_idle_browser_connection_does_not_block_stop(self):
        server = ControllerServer(("127.0.0.1", 0), self.state)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        idle = socket.create_connection(server.server_address, timeout=1)
        try:
            # Browser preconnections and unfinished headers must not delay /stop
            # beyond the firmware's 500 ms manual watchdog.
            idle.sendall(b"GET /state HTTP/1.1\r\nHost: localhost\r\n")
            self.state.command("/forward")
            with urlopen(f"http://127.0.0.1:{server.server_port}/stop", timeout=0.4) as response:
                self.assertEqual(response.status, 200)
            self.assertEqual(self.state.snapshot()["movement"], "STOPPED")
        finally:
            idle.close()
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_http_page_commands_status_and_unknown_path(self):
        server = ControllerServer(("127.0.0.1", 0), self.state)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        root = "http://127.0.0.1:" + str(server.server_port)
        try:
            with urlopen(root, timeout=2) as response:
                page = response.read().decode()
            self.assertIn('id="forward"', page)
            self.assertIn('id="sim-panel"', page)
            self.assertIn("setPointerCapture", page)
            self.assertIn('id="autoPanel"', page)
            self.assertIn('id="manualPanel" hidden', page)
            self.assertNotIn("LED LIGHT CONTROL", page)
            with urlopen(root + "/forward", timeout=2) as response:
                self.assertEqual(response.status, 200)
            with urlopen(root + "/state", timeout=2) as response:
                self.assertEqual(json.load(response)["movement"], "FORWARD")
            with urlopen(root + "/driveauto", timeout=2) as response:
                self.assertEqual(response.status, 200)
            with self.assertRaises(HTTPError) as conflict:
                urlopen(root + "/forward", timeout=2)
            self.assertEqual(conflict.exception.code, 409)
            conflict.exception.close()
            with urlopen(root + "/status", timeout=2) as response:
                state = json.load(response)
            self.assertEqual(state["drive_mode"], "AUTO")
            self.assertTrue(any(event["mode"] == "AUTO" for event in state["events"]))
            with self.assertRaises(HTTPError) as error:
                urlopen(root + "/unknown", timeout=2)
            self.assertEqual(error.exception.code, 404)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
