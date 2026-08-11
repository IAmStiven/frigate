"""Provide cached high-resolution frames for secondary image processing."""

from __future__ import annotations

import copy
import logging
import os
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

if TYPE_CHECKING:
    from frigate.config import FrigateConfig

logger = logging.getLogger(__name__)


@dataclass
class HighResolutionFrame:
    """A decoded high-resolution frame and its fetch timestamp."""

    frame: np.ndarray
    width: int
    height: int
    fetched_at: float


class HighResolutionFrameProvider:
    """Fetch high-resolution record-stream frames without blocking detection.

    go2rtc snapshot requests run on a small worker pool. Callers keep using the
    detect frame until the first high-resolution frame is ready, then reuse the
    cached frame while a refresh happens in the background.
    """

    def __init__(
        self,
        config: FrigateConfig,
        refresh_interval: float = 0.75,
        max_age: float = 2.5,
        request_timeout: float = 6.0,
        max_workers: int = 2,
    ) -> None:
        self.config = config
        self.refresh_interval = refresh_interval
        self.max_age = max_age
        self.request_timeout = request_timeout
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="high_resolution_frame",
        )
        self.frames: dict[str, HighResolutionFrame] = {}
        self.pending: dict[str, Future[HighResolutionFrame | None]] = {}
        self.disabled_cameras: set[str] = set()
        self.streams = self._find_record_streams()
        self.time_offsets = self._parse_time_offsets(
            os.environ.get("FRIGATE_HIGHRES_TIME_OFFSETS", "")
        )
        self.lock = threading.Lock()

    def _parse_time_offsets(self, value: str) -> dict[str, float]:
        """Parse comma-separated camera=seconds stream synchronization offsets."""
        offsets: dict[str, float] = {}

        for item in value.split(","):
            item = item.strip()
            if not item:
                continue

            try:
                camera, seconds = item.split("=", 1)
                camera = camera.strip()
                if camera not in self.config.cameras:
                    logger.warning(
                        "Ignoring high-resolution time offset for unknown camera %s",
                        camera,
                    )
                    continue
                offsets[camera] = float(seconds.strip())
            except (TypeError, ValueError):
                logger.warning(
                    "Ignoring invalid FRIGATE_HIGHRES_TIME_OFFSETS item %r", item
                )

        return offsets

    def get_time_offset(self, camera: str) -> float:
        """Return the recording-time correction for a detect-frame timestamp."""
        return self.time_offsets.get(camera, 0.0)

    def _find_record_streams(self) -> dict[str, str]:
        streams: dict[str, str] = {}

        for camera, camera_config in self.config.cameras.items():
            for ffmpeg_input in camera_config.ffmpeg.inputs:
                roles = {
                    role.value if hasattr(role, "value") else str(role)
                    for role in ffmpeg_input.roles
                }
                if "record" not in roles:
                    continue

                parsed = urllib.parse.urlparse(str(ffmpeg_input.path))
                if parsed.hostname not in {"127.0.0.1", "localhost"}:
                    continue

                stream = parsed.path.lstrip("/").split("/", 1)[0]
                if stream:
                    streams[camera] = stream
                break

        return streams

    def _fetch_frame(self, camera: str) -> HighResolutionFrame | None:
        stream = self.streams.get(camera)
        if stream is None:
            return None

        query = urllib.parse.urlencode({"src": stream})
        url = f"http://127.0.0.1:1984/api/frame.jpeg?{query}"

        try:
            with urllib.request.urlopen(url, timeout=self.request_timeout) as response:
                image_bytes = response.read(16 * 1024 * 1024)
        except (OSError, TimeoutError) as err:
            logger.debug(
                "Unable to fetch high-resolution frame for %s: %s", camera, err
            )
            return None

        bgr = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if bgr is None:
            logger.debug("Unable to decode high-resolution frame for %s", camera)
            return None

        height, width = bgr.shape[:2]
        detect = self.config.cameras[camera].detect
        if width <= detect.width and height <= detect.height:
            return HighResolutionFrame(
                frame=np.empty((0, 0), dtype=np.uint8),
                width=width,
                height=height,
                fetched_at=time.monotonic(),
            )

        yuv = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV_I420)
        return HighResolutionFrame(
            frame=yuv,
            width=width,
            height=height,
            fetched_at=time.monotonic(),
        )

    def get_frame(self, camera: str, refresh: bool = True) -> np.ndarray | None:
        """Return a cached frame and optionally schedule a background refresh."""
        if camera not in self.streams or camera in self.disabled_cameras:
            return None

        now = time.monotonic()

        with self.lock:
            pending = self.pending.get(camera)
            if pending is not None and pending.done():
                self.pending.pop(camera, None)
                try:
                    result = pending.result()
                except Exception:
                    logger.exception(
                        "Unexpected high-resolution frame error for %s", camera
                    )
                    result = None

                if result is not None and result.frame.size == 0:
                    self.disabled_cameras.add(camera)
                    self.frames.pop(camera, None)
                    return None

                if result is not None:
                    self.frames[camera] = result

            cached = self.frames.get(camera)
            should_refresh = cached is None or now - cached.fetched_at >= (
                self.refresh_interval
            )

            if refresh and should_refresh and camera not in self.pending:
                self.pending[camera] = self.executor.submit(self._fetch_frame, camera)

            if cached is None or now - cached.fetched_at > self.max_age:
                return None

            return cached.frame

    def scale_object_data(
        self, camera: str, obj_data: dict[str, Any], frame: np.ndarray
    ) -> dict[str, Any]:
        """Scale detect-frame coordinates to a high-resolution YUV frame."""
        detect = self.config.cameras[camera].detect
        frame_height = frame.shape[0] * 2 // 3
        frame_width = frame.shape[1]
        scale_x = frame_width / detect.width
        scale_y = frame_height / detect.height
        scaled = copy.deepcopy(obj_data)

        def scale_box(box: list[int | float] | tuple[int | float, ...]):
            return [
                int(round(box[0] * scale_x)),
                int(round(box[1] * scale_y)),
                int(round(box[2] * scale_x)),
                int(round(box[3] * scale_y)),
            ]

        for key in ("box", "region"):
            box = scaled.get(key)
            if box and len(box) == 4:
                scaled[key] = scale_box(box)

        if "area" in scaled:
            scaled["area"] = int(round(scaled["area"] * scale_x * scale_y))

        for key in ("attributes", "current_attributes"):
            for attribute in scaled.get(key, []):
                box = attribute.get("box")
                if box and len(box) == 4:
                    attribute["box"] = scale_box(box)

        return scaled

    def stop(self) -> None:
        """Stop background frame workers."""
        self.executor.shutdown(wait=False, cancel_futures=True)
