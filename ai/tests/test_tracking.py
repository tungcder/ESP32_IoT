from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from ai.follower import Follower
from ai.service import AIService
from yolov8n.robot_ai import TargetAI
from yolov8n.target_alignment import TargetAligner


def detection(x=500, score=0.8):
    return dict(xyxy=[x-100, 100, x+100, 300], confidence=score, class_id=11)


class TrackingTests(unittest.TestCase):
    def setUp(self):
        self.aligner = TargetAligner()

    def update(self, detections, stamp):
        return self.aligner.update(detections, 1000, 500, frame_time=stamp, now=stamp)

    def test_low_confidence_cannot_acquire_a_new_target(self):
        self.assertFalse(self.update([detection(score=0.2)], 0).found)
        self.assertTrue(self.update([detection(score=0.3)], 0.1).found)

    def test_matching_target_survives_confidence_fluctuations(self):
        first = self.update([detection()], 0)
        for i, confidence in enumerate((0.24, 0.18, 0.28, 0.16, 0.3), start=1):
            result = self.update([detection(500+i, confidence)], i*0.05)
            self.assertTrue(result.found)
            self.assertEqual(result.target_id, first.target_id)
            self.assertEqual(result.confidence, confidence)

    def test_even_a_matched_box_below_tracking_threshold_is_not_found(self):
        self.update([detection()], 0)
        result = self.update([detection(score=0.1)], 0.1)
        self.assertFalse(result.found)
        self.assertIsNone(result.box_xyxy)

    def test_single_missed_image_keeps_identity_but_returns_stop(self):
        first = self.update([detection()], 0)
        missing = self.update([], 0.1)
        self.assertFalse(missing.found)
        self.assertEqual(missing.command, "STOP")
        self.assertIsNone(missing.error_normalized)
        self.assertIsNone(missing.display_box_xyxy)
        recovered = self.update([detection(score=0.2)], 0.2)
        self.assertTrue(recovered.found)
        self.assertEqual(recovered.target_id, first.target_id)

    def test_unrelated_high_confidence_box_cannot_steal_remembered_target(self):
        first = self.update([detection(250)], 0)
        self.assertFalse(self.update([detection(800, 0.99)], 0.1).found)
        recovered = self.update([detection(255, 0.18), detection(800, 0.99)], 0.2)
        self.assertTrue(recovered.found)
        self.assertEqual(recovered.target_id, first.target_id)
        self.assertEqual(recovered.center_x, 255)

    def test_memory_is_bounded_and_reacquisition_requires_high_confidence(self):
        first = self.update([detection()], 0)
        self.update([], 0.1)
        self.assertFalse(self.update([detection(score=0.2)], 0.3).found)
        recovered = self.update([detection()], 0.4)
        self.assertNotEqual(recovered.target_id, first.target_id)

    def test_confidence_changes_do_not_switch_between_visible_objects(self):
        first = self.update([detection(250, 0.8), detection(800, 0.7)], 0)
        second = self.update([detection(250, 0.3), detection(800, 0.99)], 0.1)
        self.assertEqual(second.target_id, first.target_id)
        self.assertEqual(second.center_x, 250)

    def test_display_smoothing_does_not_delay_raw_boundary_crossing(self):
        self.update([detection(649)], 0)
        result = self.update([detection(651)], 0.1)
        drawn_center = (result.display_box_xyxy[0]+result.display_box_xyxy[2])/2
        self.assertEqual(drawn_center, 650)
        self.assertEqual(result.center_x, 651)
        self.assertEqual(result.command, "TURN_RIGHT")

    def test_large_motion_does_not_drag_old_display_box(self):
        self.update([detection(500)], 0)
        result = self.update([detection(580)], 0.1)
        self.assertEqual(result.display_box_xyxy, result.box_xyxy)

    def test_stale_or_out_of_order_results_cannot_reuse_track(self):
        self.update([detection()], 0)
        self.assertFalse(self.aligner.current_command(now=0.6).found)
        self.update([detection()], 1)
        result = self.update([detection()], 0.9)
        self.assertEqual(result.reason, "out_of_order_frame")
        self.assertFalse(result.found)

    def test_identity_change_requires_three_new_images_in_follower(self):
        follower = Follower()
        for i in range(3):
            decision = follower.step(dict(found=True, error_normalized=0, target_id=1), i, i/10, 100)
        self.assertEqual(decision.movement, "FORWARD")
        for i, expected in ((3, "STOPPED"), (4, "STOPPED"), (5, "FORWARD")):
            decision = follower.step(dict(found=True, error_normalized=0, target_id=2), i, i/10, 100)
            self.assertEqual(decision.movement, expected)

    def test_detector_preserves_weak_candidates_for_matched_tracks_only(self):
        raw = np.zeros((1, 16, 1), dtype=np.float32)
        raw[0, :4, 0] = [50, 50, 20, 20]
        raw[0, 15, 0] = 0.2

        class Session:
            def run(self, *_args):
                return [raw]

        ai = TargetAI.__new__(TargetAI)
        ai.width = ai.height = 100
        ai.input_name, ai.session = "images", Session()
        ai.aligner = TargetAligner()
        ai.confidence, ai.tracking_confidence, ai.iou = 0.25, 0.15, 0.7
        detections, _ = ai._detect(np.zeros((100, 100, 3), dtype=np.uint8))
        self.assertEqual(len(detections), 1)
        self.assertFalse(ai.aligner.update(detections, 100, 100, now=0).found)

    def test_renderer_draws_only_selected_target(self):
        ai = TargetAI.__new__(TargetAI)
        ai.aligner = TargetAligner()
        choices = [detection(250, 0.8), detection(800, 0.7)]
        with patch.object(ai, "_detect", return_value=(choices, 1)), \
                patch("yolov8n.robot_ai.time.monotonic", return_value=10):
            result = ai.process_frame(np.zeros((500, 1000, 3), dtype=np.uint8), captured_at=10)
        self.assertEqual(result.annotated_frame[100, 150].tolist(), [70, 210, 70])
        self.assertEqual(result.annotated_frame[100, 700].tolist(), [0, 0, 0])


class PreviewTests(unittest.TestCase):
    def setUp(self):
        with patch.object(AIService, "log"), patch("ai.service.Path.exists", return_value=False):
            self.service = AIService()
        self.service.camera_error = ""
        self.service.frame_at = 10
        self.service.model_ready = True
        self.service.jpeg, self.service.jpeg_at, self.service.jpeg_id = b"annotated", 9.76, 20
        self.service.raw_jpeg, self.service.raw_jpeg_at, self.service.raw_jpeg_id = b"raw", 9.99, 25

    def test_raw_frame_cannot_overtake_annotation_and_remove_box(self):
        with patch("ai.service.time.monotonic", return_value=10):
            self.assertEqual(self.service.preview(), (b"annotated", 20, 240))

    def test_no_switch_to_raw_if_annotation_is_too_old(self):
        self.service.jpeg_at = 9.49
        with patch("ai.service.time.monotonic", return_value=10):
            self.assertIsNone(self.service.preview())

    def test_valid_annotation_after_350ms_is_still_available(self):
        self.service.jpeg_at = 9.6
        with patch("ai.service.time.monotonic", return_value=10):
            self.assertEqual(self.service.preview(), (b"annotated", 20, 400))

    def test_wait_for_first_annotation_when_model_is_ready(self):
        self.service.jpeg = None
        with patch("ai.service.time.monotonic", return_value=10):
            self.assertIsNone(self.service.preview())

    def test_camera_only_preview_still_works_when_model_unavailable(self):
        self.service.model_ready = False
        with patch("ai.service.time.monotonic", return_value=10):
            self.assertEqual(self.service.preview(), (b"raw", 25, 10))

    def test_camera_timeout_still_hides_all_frames(self):
        self.service.frame_at = 9.49
        with patch("ai.service.time.monotonic", return_value=10):
            self.assertIsNone(self.service.preview())


if __name__ == "__main__":
    unittest.main()
