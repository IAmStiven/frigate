import unittest

import numpy as np

from frigate.util.model import post_process_yolo26


class TestPostProcessYolo26(unittest.TestCase):
    def test_post_process_yolo26_xyxy(self):
        predictions = np.array(
            [[[10, 20, 50, 70, 0.9, 1], [0, 0, 0, 0, 0.2, 0]]], dtype=np.float32
        )

        detections = post_process_yolo26([predictions], width=100, height=200)

        assert detections.shape == (20, 6)
        np.testing.assert_allclose(
            detections[0],
            np.array([1, 0.9, 0.1, 0.1, 0.35, 0.5], dtype=np.float32),
        )

    def test_post_process_yolo26_with_batch_index(self):
        predictions = np.array(
            [[[0, 5, 15, 25, 35, 0.8, 3], [0, 0, 0, 0, 0, 0.1, 0]]],
            dtype=np.float32,
        )

        detections = post_process_yolo26([predictions], width=50, height=100)

        assert detections.shape == (20, 6)
        np.testing.assert_allclose(
            detections[0],
            np.array([3, 0.8, 0.15, 0.1, 0.35, 0.5], dtype=np.float32),
        )
