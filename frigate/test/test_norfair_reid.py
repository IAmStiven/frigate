import unittest
from types import SimpleNamespace

import numpy as np
from norfair.tracker import Detection

from frigate.track.norfair_tracker import (
    NorfairTracker,
    appearance_continuity_distance,
    appearance_reid_distance,
)


def make_detection(
    label: str,
    frame_time: float,
    box: list[int],
    embedding: np.ndarray,
) -> Detection:
    return Detection(
        points=np.array([[box[0], box[1]], [box[2], box[3]]]),
        label=label,
        embedding=embedding,
        data={"label": label, "frame_time": frame_time, "box": box},
    )


class TestAppearanceReidDistance(unittest.TestCase):
    def setUp(self) -> None:
        self.dark_vehicle = np.zeros(512, dtype=np.float32)
        self.dark_vehicle[7:14] = 1.0
        self.other_vehicle = np.zeros(512, dtype=np.float32)
        self.other_vehicle[300:307] = 1.0

    def tracker(self, *detections: Detection) -> SimpleNamespace:
        return SimpleNamespace(past_detections=list(detections))

    def test_reconnects_same_vehicle_after_rotation_gap(self) -> None:
        old = self.tracker(
            make_detection("vehicle", 100.0, [500, 180, 700, 400], self.dark_vehicle)
        )
        new = self.tracker(
            make_detection("vehicle", 108.4, [465, 185, 680, 410], self.dark_vehicle)
        )

        self.assertLess(appearance_reid_distance(old, new), 0.42)

    def test_rejects_visually_different_vehicle(self) -> None:
        old = self.tracker(
            make_detection("vehicle", 100.0, [500, 180, 700, 400], self.dark_vehicle)
        )
        new = self.tracker(
            make_detection("vehicle", 108.4, [465, 185, 680, 410], self.other_vehicle)
        )

        self.assertEqual(appearance_reid_distance(old, new), 1.0)

    def test_rejects_same_appearance_at_implausible_position(self) -> None:
        old = self.tracker(
            make_detection("vehicle", 100.0, [500, 180, 700, 400], self.dark_vehicle)
        )
        new = self.tracker(
            make_detection("vehicle", 108.4, [10, 10, 110, 90], self.dark_vehicle)
        )

        self.assertEqual(appearance_reid_distance(old, new), 1.0)

    def test_reconnects_animal_after_overlap_gap(self) -> None:
        old = self.tracker(
            make_detection("animal", 100.0, [500, 180, 600, 300], self.dark_vehicle)
        )
        new = self.tracker(
            make_detection("animal", 120.0, [490, 185, 600, 305], self.dark_vehicle)
        )

        self.assertLess(appearance_reid_distance(old, new), 0.44)

    def test_rejects_animal_beyond_overlap_window(self) -> None:
        old = self.tracker(
            make_detection("animal", 100.0, [500, 180, 600, 300], self.dark_vehicle)
        )
        new = self.tracker(
            make_detection("animal", 126.0, [490, 185, 600, 305], self.dark_vehicle)
        )

        self.assertEqual(appearance_reid_distance(old, new), 1.0)

    def test_dormant_norfair_track_keeps_frigate_identity(self) -> None:
        dormant = SimpleNamespace(
            global_id="track-1",
            reid_hit_counter=12,
            reid_hit_counter_is_positive=True,
        )
        tracker = object.__new__(NorfairTracker)
        tracker.trackers = {
            "vehicle": {"static": SimpleNamespace(tracked_objects=[dormant])}
        }
        tracker.default_tracker = {}

        self.assertTrue(tracker._is_reid_pending("track-1"))
        self.assertFalse(tracker._is_reid_pending("different-track"))

    def test_active_vehicle_uses_last_detection_when_estimate_drifted(self) -> None:
        previous = make_detection(
            "vehicle", 100.0, [500, 180, 700, 400], self.dark_vehicle
        )
        current = make_detection(
            "vehicle", 107.9, [505, 182, 706, 402], self.dark_vehicle
        )
        active_track = SimpleNamespace(last_detection=previous)

        bridged = appearance_continuity_distance(current, active_track, 4.5)

        self.assertLess(bridged, 0.5)

    def test_active_vehicle_rejects_different_appearance(self) -> None:
        previous = make_detection(
            "vehicle", 100.0, [500, 180, 700, 400], self.dark_vehicle
        )
        current = make_detection(
            "vehicle", 107.9, [505, 182, 706, 402], self.other_vehicle
        )
        active_track = SimpleNamespace(last_detection=previous)

        self.assertEqual(
            appearance_continuity_distance(current, active_track, 4.5), 4.5
        )

    def test_active_vehicle_rejects_stale_detection(self) -> None:
        previous = make_detection(
            "vehicle", 100.0, [500, 180, 700, 400], self.dark_vehicle
        )
        current = make_detection(
            "vehicle", 116.0, [505, 182, 706, 402], self.dark_vehicle
        )
        active_track = SimpleNamespace(last_detection=previous)

        self.assertEqual(
            appearance_continuity_distance(current, active_track, 4.5), 4.5
        )

    def test_active_vehicle_rejects_implausible_position(self) -> None:
        previous = make_detection(
            "vehicle", 100.0, [500, 180, 700, 400], self.dark_vehicle
        )
        current = make_detection(
            "vehicle", 107.9, [20, 20, 120, 100], self.dark_vehicle
        )
        active_track = SimpleNamespace(last_detection=previous)

        self.assertEqual(
            appearance_continuity_distance(current, active_track, 4.5), 4.5
        )


if __name__ == "__main__":
    unittest.main()
