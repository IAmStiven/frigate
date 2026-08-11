import unittest

from frigate.util.object import reduce_detections


def detection(score: float, box: tuple[int, int, int, int]) -> tuple:
    width = box[2] - box[0]
    height = box[3] - box[1]
    return (
        "animal",
        score,
        box,
        width * height,
        width / height,
        (0, 0, 1000, 1000),
    )


class TestAnimalOverlapReduction(unittest.TestCase):
    def test_keeps_two_overlapping_animals(self) -> None:
        detections = [
            detection(0.91, (100, 100, 300, 300)),
            detection(0.88, (170, 100, 370, 300)),
        ]

        reduced = reduce_detections((1000, 1000), detections)

        self.assertEqual(len(reduced), 2)

    def test_still_suppresses_duplicate_animal_boxes(self) -> None:
        detections = [
            detection(0.91, (100, 100, 300, 300)),
            detection(0.88, (110, 105, 310, 305)),
        ]

        reduced = reduce_detections((1000, 1000), detections)

        self.assertEqual(len(reduced), 1)


if __name__ == "__main__":
    unittest.main()
