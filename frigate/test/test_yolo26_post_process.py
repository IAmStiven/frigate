import unittest

import numpy as np

from frigate.util.model import post_process_yolo26


class TestPostProcessYolo26(unittest.TestCase):
    def test_objectness_weighted_scores(self):
        predictions = np.zeros((1, 10, 7), dtype=np.float32)
        predictions[0, 0] = [50, 50, 10, 10, 0.9, 0.1, 0.8]
        predictions[0, 1] = [20, 20, 10, 10, 0.3, 0.9, 0.2]

        detections = post_process_yolo26([predictions], width=100, height=100)

        self.assertEqual(int(detections[0][0]), 1)
        self.assertAlmostEqual(detections[0][1], 0.72, places=2)
        self.assertTrue(np.all(detections[1:] == 0))


if __name__ == "__main__":
    unittest.main()
