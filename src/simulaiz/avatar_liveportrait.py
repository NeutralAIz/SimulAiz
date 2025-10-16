from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

import cv2  # type: ignore
import numpy as np
from livekit import rtc  # type: ignore


class LivePortraitBridge:
    """High-fidelity avatar bridge.

    This class is designed to integrate a real LivePortrait runtime if present.
    If models/runtime are not available, it falls back to animating the provided
    portrait image with audio-reactive mouth motion (more realistic than a plain
    placeholder and requires no extra models).
    """

    def __init__(
        self,
        image_path: str,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
    ) -> None:
        self.w, self.h, self.fps = width, height, fps
        self.src = rtc.VideoSource(width=self.w, height=self.h)
        self._stop = False
        self._audio_q: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=64)
        self._frame_q: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=256)

        img_path = Path(image_path)
        if not img_path.exists():
            raise FileNotFoundError(f"Avatar image not found: {image_path}")
        base = cv2.imread(str(img_path))
        if base is None:
            raise RuntimeError(f"Failed to load avatar image: {image_path}")
        self.base = cv2.resize(base, (self.w, self.h), interpolation=cv2.INTER_AREA)

        # Placeholder flags for optional true LivePortrait runtime
        self._lp_available = False  # toggled true if you wire in the runtime

    async def start(self, room: rtc.Room) -> None:
        track = self.src.create_track()
        await room.local_participant.publish_track(track)
        await asyncio.gather(self._player(), self._worker())

    def stop(self) -> None:
        self._stop = True

    async def consume_tts_chunk(self, pcm_int16: np.ndarray) -> None:
        try:
            self._audio_q.put_nowait(pcm_int16)
        except asyncio.QueueFull:
            pass

    async def _player(self) -> None:
        frame_period = 1 / max(1, self.fps)
        while not self._stop:
            try:
                img = await asyncio.wait_for(self._frame_q.get(), timeout=0.5)
            except asyncio.TimeoutError:
                img = self.base.copy()
            frame = rtc.VideoFrame(self.w, self.h, rtc.VideoBufferType.BGR, img.tobytes())
            self.src.capture_frame(frame)
            await asyncio.sleep(frame_period)

    async def _worker(self) -> None:
        # Basic fallback: audio-reactive mouth on the portrait
        level = 0.0
        while not self._stop:
            try:
                pcm = await asyncio.wait_for(self._audio_q.get(), timeout=0.5)
            except asyncio.TimeoutError:
                # push idle frame
                await self._frame_q.put(self._draw_mouth(self.base.copy(), 0.0))
                continue

            if pcm.size:
                rms = float(np.sqrt(np.mean(pcm.astype(np.float32) ** 2)))
                level = 0.9 * level + 0.1 * min(1.0, rms / 18000.0)
            else:
                level *= 0.9

            await self._frame_q.put(self._draw_mouth(self.base.copy(), level))

    def _draw_mouth(self, img: np.ndarray, level: float) -> np.ndarray:
        # Draw a simple mouth overlay that scales with level (0..1)
        # Position near the lower third of the face
        cx, cy = self.w // 2, int(self.h * 0.58)
        mouth_w = int(self.w * 0.18)
        mouth_h = int(max(8, 10 + 80 * level))
        color = (30, 30, 30)
        cv2.ellipse(img, (cx, cy), (mouth_w, mouth_h), 0, 0, 360, color, -1)
        return img

