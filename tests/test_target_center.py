"""A detection may guide the robot only after the target rings confirm a center."""
from pathlib import Path
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from yolov8n.robot_ai import TargetAI
from yolov8n.target_alignment import AlignmentConfig


ROOT = Path(__file__).resolve().parents[1]


def target_frame(center=(350, 235), *, grayscale=False, occluded=False):
    image = np.full((480, 640, 3), 190, np.uint8)
    cv2.rectangle(image, (95, 50), (560, 430), (235, 235, 235), -1)
    colors = [(30, 30, 30), (200, 100, 20), (30, 30, 210), (20, 220, 230)]
    if grayscale:
        colors = [(25, 25, 25), (225, 225, 225), (50, 50, 50), (210, 210, 210)]
    for axes, color in zip(((165, 145), (125, 108), (85, 73), (40, 34)), colors):
        cv2.ellipse(image, center, axes, 12, 0, 360, color, -1, cv2.LINE_AA)
    if occluded:
        cv2.line(image, (330, 225), (530, 65), (75, 75, 75), 5, cv2.LINE_AA)
    return image


class CenterGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cv2.setNumThreads(1)
        cls.ai = TargetAI(weights=ROOT / 'yolov8n/best.onnx', alignment=AlignmentConfig(),
                          confidence=.7, tracking_confidence=.7, providers=['CPUExecutionProvider'])

    def setUp(self):
        self.ai.stop()
        self.clock = 10.0

    def process(self, image, detections=None, control=None):
        if detections is None:
            detections = [dict(xyxy=[95, 50, 560, 430], confidence=.95, class_id=11)]
        self.clock += .01
        with patch.object(self.ai, '_detect', return_value=(detections, 0.0)), \
                patch('yolov8n.robot_ai.time.monotonic', return_value=self.clock):
            return self.ai.process_frame(image, captured_at=self.clock, control=control)

    def test_confident_blank_wall_has_no_box_and_no_tracking(self):
        commands = []
        result = self.process(np.full((480, 640, 3), 230, np.uint8),
                              control=lambda v, w: commands.append((v, w)))
        self.assertFalse(result.alignment.found)
        self.assertIsNone(result.alignment.display_box_xyxy)
        self.assertEqual(result.detections, [])
        self.assertEqual(commands, [(0.0, 0.0)])

    def test_ring_center_is_used_instead_of_box_midpoint(self):
        result = self.process(target_frame())
        self.assertTrue(result.alignment.found)
        self.assertAlmostEqual(result.alignment.center_x, 350, delta=5)
        self.assertAlmostEqual(result.alignment.center_y, 235, delta=5)
        self.assertAlmostEqual(result.alignment.error_px, 30, delta=5)

    def test_monochrome_rings_confirm_the_center(self):
        result = self.process(target_frame(grayscale=True))
        self.assertTrue(result.alignment.found)
        self.assertAlmostEqual(result.alignment.center_x, 350, delta=5)

    def test_arrow_crossing_does_not_invent_a_different_center(self):
        result = self.process(target_frame(occluded=True))
        self.assertTrue(result.alignment.found)
        self.assertAlmostEqual(result.alignment.center_x, 350, delta=7)

    def test_several_arrows_crossing_colored_rings_still_confirm_center(self):
        image = target_frame()
        for start, end in [((340, 235), (520, 65)), ((345, 230), (475, 55)),
                           ((350, 235), (510, 360)), ((355, 240), (210, 80))]:
            cv2.line(image, start, end, (65, 65, 65), 4, cv2.LINE_AA)
        result = self.process(image)
        self.assertTrue(result.alignment.found)
        self.assertAlmostEqual(result.alignment.center_x, 350, delta=8)

    def test_nested_colored_rectangles_do_not_count_as_target_rings(self):
        frame = np.full((480, 640, 3), 230, np.uint8)
        for margin, color in zip((0, 40, 80), ((210, 80, 20), (20, 20, 210), (20, 220, 230))):
            cv2.rectangle(frame, (110+margin, 60+margin), (550-margin, 420-margin), color, -1)
        self.assertFalse(self.process(frame).alignment.found)

    def test_circles_with_different_centers_do_not_confirm_a_target(self):
        frame = np.full((480, 640, 3), 230, np.uint8)
        for point, radius in [((285, 230), 150), ((330, 200), 90), ((370, 270), 35)]:
            cv2.circle(frame, point, radius, (15, 15, 15), 3, cv2.LINE_AA)
        self.assertFalse(self.process(frame).alignment.found)

    def test_nested_hexagons_do_not_confirm_a_target(self):
        frame = np.full((480, 640, 3), 230, np.uint8)
        for radius in (130, 85, 40):
            angles = np.arange(6) * (np.pi / 3)
            points = np.column_stack((480+radius*np.cos(angles), 235+radius*np.sin(angles))).round().astype(np.int32)
            cv2.polylines(frame, [points], True, (20,20,20), 3)
        box = [dict(xyxy=[330,70,630,410], confidence=.95, class_id=11)]
        self.assertFalse(self.process(frame, box).alignment.found)

    def test_nested_octagons_do_not_confirm_a_target(self):
        frame = np.full((480, 640, 3), 230, np.uint8)
        for radius in (130, 85, 40):
            angles = np.arange(8) * (np.pi / 4)
            points = np.column_stack((480+radius*np.cos(angles), 235+radius*np.sin(angles))).round().astype(np.int32)
            cv2.polylines(frame, [points], True, (20,20,20), 3, cv2.LINE_AA)
        box = [dict(xyxy=[330,70,630,410], confidence=.95, class_id=11)]
        self.assertFalse(self.process(frame, box).alignment.found)

    def test_projected_rings_use_bullseye_instead_of_outer_ellipse_center(self):
        plane = np.full((640,640,3), 230, np.uint8)
        for radius in (230,180,130,80,30):
            cv2.circle(plane, (320,320), radius, (20,20,20), 3, cv2.LINE_AA)
        transform = np.array([[.955,0,119.4],[.144,.7,-30.08],[.0006,0,.808]])
        frame = cv2.warpPerspective(plane, transform, (640,480), borderValue=(230,230,230))
        box = [dict(xyxy=[170,30,635,450], confidence=.95, class_id=11)]
        result = self.process(frame, box)
        self.assertTrue(result.alignment.found)
        self.assertAlmostEqual(result.alignment.center_x, 425, delta=5)
        self.assertAlmostEqual(result.alignment.center_y, 240, delta=5)
        self.assertEqual(result.alignment.command, 'TURN_RIGHT')

    def test_perspective_colored_target_keeps_bullseye_across_ring_sizes(self):
        plane = np.full((640,640,3), 230, np.uint8)
        colors = ((20,20,20), (200,80,20), (30,30,220), (20,220,230), (15,15,15))
        for radius, color in zip((230,180,130,80,30), colors):
            cv2.circle(plane, (320,320), radius, color, -1, cv2.LINE_AA)
        transform = np.array([[.955,0,119.4],[.144,.7,-30.08],[.0006,0,.808]])
        frame = cv2.warpPerspective(plane, transform, (640,480), borderValue=(230,230,230))
        points = cv2.perspectiveTransform(np.float32([[[90,90],[550,90],[90,550],[550,550]]]), transform)[0]
        bounds = [points[:,0].min()-5, points[:,1].min()-5, points[:,0].max()+5, points[:,1].max()+5]
        result = self.process(frame, [dict(xyxy=bounds, confidence=.95, class_id=11)])
        self.assertTrue(result.alignment.found)
        self.assertAlmostEqual(result.alignment.center_x, 425, delta=5)
        self.assertEqual(result.alignment.command, 'TURN_RIGHT')

    def test_confirmed_center_is_marked_and_input_frame_is_unchanged(self):
        image = target_frame()
        original = image.copy()
        result = self.process(image)
        self.assertTrue(result.alignment.center_verified)
        self.assertTrue(np.array_equal(image, original))
        self.assertFalse(np.array_equal(result.annotated_frame[235, 350], original[235, 350]))

    def test_invalid_camera_frame_clears_verified_state_and_commands_stop(self):
        self.assertTrue(self.process(target_frame()).alignment.center_verified)
        commands = []
        result = self.ai.process_frame(None, control=lambda v,w: commands.append((v,w)))
        self.assertFalse(result.alignment.found)
        self.assertFalse(result.alignment.center_verified)
        self.assertEqual(commands, [(0.0, 0.0)])

    def test_one_circle_is_not_enough_to_confirm_a_target(self):
        frame = np.full((480, 640, 3), 230, np.uint8)
        cv2.circle(frame, (330, 235), 120, (15, 15, 15), 4, cv2.LINE_AA)
        self.assertFalse(self.process(frame).alignment.found)

    def test_rectangles_on_wall_do_not_confirm_a_target(self):
        frame = np.full((480, 640, 3), 230, np.uint8)
        for margin in (0, 35, 70, 100):
            cv2.rectangle(frame, (110+margin, 60+margin), (550-margin, 420-margin), (20, 20, 20), 3)
        self.assertFalse(self.process(frame).alignment.found)

    def test_missing_center_clears_previous_box_immediately(self):
        self.assertTrue(self.process(target_frame()).alignment.found)
        result = self.process(np.full((480, 640, 3), 230, np.uint8))
        self.assertFalse(result.alignment.found)
        self.assertIsNone(result.alignment.display_box_xyxy)
        self.assertEqual(result.alignment.angular_velocity, 0.0)

    def test_false_box_does_not_hide_a_second_verified_target(self):
        boxes = [dict(xyxy=[0, 0, 85, 470], confidence=.99, class_id=11),
                 dict(xyxy=[95, 50, 560, 430], confidence=.9, class_id=11)]
        result = self.process(target_frame(), boxes)
        self.assertTrue(result.alignment.found)
        self.assertAlmostEqual(result.alignment.center_x, 350, delta=5)
        self.assertEqual(len(result.detections), 1)


if __name__ == '__main__':
    unittest.main()
