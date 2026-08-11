import unittest
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np

from frigate.util.highres import HighResolutionFrameProvider


class TestHighResolutionFrameProvider(unittest.TestCase):
    def setUp(self) -> None:
        self.camera = SimpleNamespace(
            detect=SimpleNamespace(width=960, height=576),
            ffmpeg=SimpleNamespace(
                inputs=[
                    SimpleNamespace(
                        roles=["record"],
                        path="rtsp://127.0.0.1:8554/front_main",
                    )
                ]
            ),
        )
        self.config = SimpleNamespace(cameras={"front": self.camera})

    def test_finds_local_record_stream(self) -> None:
        provider = HighResolutionFrameProvider(self.config)
        self.addCleanup(provider.stop)

        self.assertEqual(provider.streams, {"front": "front_main"})

    def test_ignores_direct_camera_stream(self) -> None:
        self.camera.ffmpeg.inputs[0].path = "rtsp://192.168.1.20/main"
        provider = HighResolutionFrameProvider(self.config)
        self.addCleanup(provider.stop)

        self.assertEqual(provider.streams, {})

    def test_scales_object_and_attribute_boxes_without_mutating_input(self) -> None:
        provider = HighResolutionFrameProvider(self.config)
        self.addCleanup(provider.stop)
        high_resolution_yuv = np.zeros((1620, 1920), dtype=np.uint8)
        obj_data = {
            "box": [96, 58, 480, 288],
            "region": [0, 0, 960, 576],
            "area": 88320,
            "attributes": [{"label": "license_plate", "box": [100, 100, 200, 150]}],
        }

        scaled = provider.scale_object_data("front", obj_data, high_resolution_yuv)

        self.assertEqual(scaled["box"], [192, 109, 960, 540])
        self.assertEqual(scaled["region"], [0, 0, 1920, 1080])
        self.assertEqual(scaled["area"], 331200)
        self.assertEqual(scaled["attributes"][0]["box"], [200, 188, 400, 281])
        self.assertEqual(obj_data["box"], [96, 58, 480, 288])

    def test_parses_camera_time_offsets(self) -> None:
        with patch.dict(
            "os.environ",
            {"FRIGATE_HIGHRES_TIME_OFFSETS": "front=-2.0,unknown=1,bad"},
        ):
            provider = HighResolutionFrameProvider(self.config)
            self.addCleanup(provider.stop)

        self.assertEqual(provider.get_time_offset("front"), -2.0)
        self.assertEqual(provider.get_time_offset("unknown"), 0.0)


if __name__ == "__main__":
    unittest.main()
