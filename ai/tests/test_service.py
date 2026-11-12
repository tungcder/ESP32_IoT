import unittest
from unittest.mock import Mock, patch

from ai.service import AIService


class ServiceTests(unittest.TestCase):
    def setUp(self):
        with patch.object(AIService, "log"), patch("ai.service.Path.exists", return_value=False):
            self.service = AIService()
        self.service.log = Mock()
        self.service.model_ready = True
        self.service.camera_error = ""
        self.service.result = dict(found=False)
        self.service.result_at = self.service.frame_at = 10

    def client(self):
        client = Mock()
        client.status.return_value = dict(mode_epoch=4, movement="STOPPED")
        client.claim.return_value = dict(session="new-session", mode_epoch=5)
        client.command.return_value = dict(mode_epoch=5, movement="STOPPED", ai_active=True)
        return client

    def test_claim_is_followed_immediately_by_acknowledged_stop(self):
        client = self.client()
        with patch("ai.service.time.monotonic", return_value=10), \
                patch("ai.service.RobotClient", return_value=client):
            self.service.start()
        client.command.assert_called_once_with("new-session", 1, "STOPPED", 0)
        self.assertEqual(self.service.sequence, 1)
        self.assertEqual(self.service.robot_state["mode_epoch"], 5)
        self.assertTrue(self.service.control_wake.is_set())

    def test_failed_initial_command_releases_claim_without_activating_ai(self):
        client = self.client()
        client.command.side_effect = TimeoutError("network timeout")
        with patch("ai.service.time.monotonic", return_value=10), \
                patch("ai.service.RobotClient", return_value=client):
            with self.assertRaises(TimeoutError):
                self.service.start()
        client.release.assert_called_once_with("new-session")
        self.assertIsNone(self.service.session)

    def test_stale_camera_cannot_claim_or_refresh_watchdog(self):
        client = self.client()
        with patch("ai.service.time.monotonic", return_value=10.51), \
                patch("ai.service.RobotClient", return_value=client):
            with self.assertRaises(ValueError):
                self.service.start()
        client.claim.assert_not_called()
        self.service.session = "old-session"
        with patch("ai.service.time.monotonic", return_value=10.51), \
                patch("ai.service.RobotClient", return_value=client):
            self.service.control_tick()
        client.command.assert_not_called()
        self.assertIsNone(self.service.session)
        self.assertEqual(self.service.decision["state"], "FAULT")

    def test_network_time_counts_toward_control_period(self):
        clock = [10.0]
        self.service.session = "active-session"

        def tick():
            clock[0] += 0.08

        wake = Mock()
        wake.wait.side_effect = lambda timeout: self.service.shutdown_event.set()
        self.service.control_wake = wake
        with patch.object(self.service, "control_tick", side_effect=tick), \
                patch("ai.service.time.monotonic", side_effect=lambda: clock[0]):
            self.service.control_loop()
        self.assertAlmostEqual(wake.wait.call_args.args[0], 0.02)

    def test_claim_while_waiting_for_lock_preempts_idle_poll(self):
        service = self.service

        class ClaimCompletesBeforeLock:
            def __enter__(self):
                service.session = "just-claimed"

            def __exit__(self, *_):
                pass

        service.operation_lock = ClaimCompletesBeforeLock()
        wake = Mock()
        wake.wait.side_effect = lambda timeout: service.shutdown_event.set()
        service.control_wake = wake
        with patch.object(service, "control_tick") as tick, \
                patch("ai.service.RobotClient") as client:
            service.control_loop()
        tick.assert_called_once()
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
