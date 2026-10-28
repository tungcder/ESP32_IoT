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
from esp32_car import BridgeState, ControllerServer, WHEEL_DIRECTIONS, server_port
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
        self.assertIn("TIMEOUT", snapshot["events"][-1]["message"])

    def test_commands_refresh_watchdog(self):
        self.state.command("/left")
        self.now += 0.4
        self.state.command("/left")
        self.now += 0.4
        self.assertEqual(self.state.snapshot()["movement"], "LEFT")

    def test_stop_overrides_auto_and_centers_scanner(self):
        self.state.command("/driveauto")
        self.state.update_simulation(0, 10)
        self.advance_until(lambda: self.state.pilot.state == "PointRight", 10)
        self.assertEqual(self.state.pilot.angle, 10)
        self.state.command("/stop")
        movement, angle, _ = self.state.update_simulation(self.state.sim_time + 0.016, 10)
        self.assertEqual((movement, angle), ("STOPPED", 90))
        self.assertEqual(self.state.drive_mode, "MANUAL")

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

    def test_manual_leds_remain_on_after_stop(self):
        self.state.command("/ledon")
        self.state.command("/forward")
        self.state.command("/stop")
        self.assertEqual(self.state.snapshot()["leds"], [True] * 4)
        self.state.command("/ledoff")
        self.assertEqual(self.state.snapshot()["leds"], [False] * 4)

    def test_no_echo_front_without_recent_near_value_matches_new_firmware(self):
        self.state.command("/driveauto")
        self.state.update_simulation(1, float("nan"))
        self.advance_until(lambda: self.state.movement == "FORWARD", float("nan"))
        self.assertEqual(self.state.distance_cm, 0)
        self.assertEqual(self.state.movement, "FORWARD")

    def test_auto_scan_chooses_clear_side_or_u_turn_when_both_near(self):
        for right, left, expected in ((100, 10, "RIGHT"), (10, 100, "LEFT"),
                                      (10, 10, "RIGHT"), (0, 0, "RIGHT")):
            with self.subTest(right=right, left=left):
                pilot = AutoPilot(25)
                pilot.reset(10)
                for step in range(400):
                    distance = right if pilot.state == "PointRight" else left if pilot.state == "PointLeft" else 10
                    pilot.update(10 + step * 0.016, distance)
                    if pilot.state == "Turn":
                        break
                self.assertEqual(pilot.state, "Turn")
                self.assertEqual((pilot.movement, pilot.angle), (expected, 90))
                self.assertAlmostEqual(pilot.turn_duration, 0.9 if right <= 25 and left <= 25 else 0.4)

    def test_front_fan_scan_sequence(self):
        pilot = AutoPilot(25)
        seen = []
        previous_set = False
        for step in range(100):
            pilot.update(step * 0.016, 100)
            if pilot.front_angle_set and not previous_set:
                seen.append(pilot.angle)
            previous_set = pilot.front_angle_set
        self.assertEqual(seen[:5], [90, 60, 90, 120, 90])

    def test_median_rejects_single_bad_measurement_and_remembers_near_echo(self):
        pilot = AutoPilot(25)
        for now, distance in ((0, 100), (0.008, 0), (0.016, 110)):
            self.assertIsNone(pilot.read_distance(now, distance))
        self.assertEqual(pilot.read_distance(0.024, 0), 100)
        self.assertFalse(pilot.front_blocked(10, 0, 40))
        self.assertTrue(pilot.front_blocked(10.9, 0, -1))
        self.assertFalse(pilot.front_blocked(11.1, 0, -1))
        self.assertTrue(pilot.front_blocked(12, 1, 30))

    def test_repeated_avoidance_increases_turn_duration_with_a_cap(self):
        pilot = AutoPilot(25)
        durations = []
        for index in range(5):
            now = 10 + index
            pilot.last_avoid_end = now - 1
            pilot.right, pilot.left = 100, 10
            pilot.enter("CenterAfterLeft", now - 0.21)
            pilot.update(now, 100)
            durations.append(round(pilot.turn_duration, 2))
        self.assertEqual(durations, [0.55, 0.7, 0.85, 0.85, 0.85])

    def test_turn_wheel_directions(self):
        self.assertEqual(WHEEL_DIRECTIONS["LEFT"], (-1, 1))
        self.assertEqual(WHEEL_DIRECTIONS["RIGHT"], (1, -1))

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
            self.assertNotIn("let moveInterval = null", page)
            with urlopen(root + "/forward", timeout=2) as response:
                self.assertEqual(response.status, 200)
            with urlopen(root + "/state", timeout=2) as response:
                self.assertEqual(json.load(response)["movement"], "FORWARD")
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
