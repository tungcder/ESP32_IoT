"""Exercise the real robot HTTP client against the Webots API contract."""
import sys
from pathlib import Path
import threading
import unittest
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "simulation/webots/controllers/esp32_car"))
from esp32_car import BridgeState, ControllerServer
from ai.robot_client import RobotClient


class HybridHTTPTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.state = BridgeState(clock=lambda: self.now)
        self.server = ControllerServer(("127.0.0.1", 0), self.state)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.close_server)
        self.client = RobotClient("http://127.0.0.1:" + str(self.server.server_port), timeout=1)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)

    def claim(self):
        status = self.client.status()
        self.assertTrue(status["hybrid_supported"])
        return self.client.claim_hybrid(status["mode_epoch"])["session"]

    def assert_http(self, expected, callback):
        with self.assertRaises(HTTPError) as caught:
            callback()
        self.assertEqual(caught.exception.code, expected)

    def test_claim_search_track_release_over_http(self):
        session = self.claim()
        status = self.client.hybrid_command(session, 1, "HOLD", "STOPPED", 0)
        self.assertEqual((status["drive_mode"], status["hybrid_state"], status["movement"]), ("HYBRID", "HOLD", "STOPPED"))
        self.client.hybrid_command(session, 2, "SEARCH", "STOPPED", 0)
        self.now += .31
        self.state.update_simulation(.31, 100)
        status = self.client.hybrid_command(session, 3, "SEARCH", "STOPPED", 0)
        self.assertEqual(status["movement"], "FORWARD")
        status = self.client.hybrid_command(session, 4, "TRACK", "STOPPED", 0)
        self.assertEqual(status["movement"], "STOPPED")
        self.assertEqual(self.client.release(session)["drive_mode"], "MANUAL")

    def test_duplicate_command_and_stale_epoch_are_rejected(self):
        epoch = self.client.status()["mode_epoch"]
        session = self.claim()
        self.assert_http(409, lambda: self.client.claim_hybrid(epoch))
        self.client.hybrid_command(session, 1, "SEARCH", "STOPPED", 0)
        self.assert_http(409, lambda: self.client.hybrid_command(session, 1, "TRACK", "FORWARD", 50))

    def test_timeout_and_estop_prevent_late_commands(self):
        session = self.claim()
        self.client.hybrid_command(session, 1, "SEARCH", "STOPPED", 0)
        self.now += .51
        self.assert_http(409, lambda: self.client.hybrid_command(session, 2, "SEARCH", "STOPPED", 0))
        self.assertEqual(self.client.status()["drive_mode"], "MANUAL")
        session = self.claim()
        self.client.emergency()
        self.assert_http(409, lambda: self.client.hybrid_command(session, 1, "TRACK", "FORWARD", 50))

    def test_manual_takeover_does_not_allow_old_session_to_resume(self):
        session = self.claim()
        self.client.mode("MANUAL", self.client.status()["mode_epoch"])
        self.assert_http(409, lambda: self.client.hybrid_command(session, 1, "SEARCH", "STOPPED", 0))
        self.assertFalse(self.client.status()["ai_active"])


if __name__ == "__main__":
    unittest.main()
