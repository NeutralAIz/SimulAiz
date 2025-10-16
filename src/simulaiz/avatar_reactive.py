from __future__ import annotations

import asyncio
import random
import time

import cv2  # type: ignore
import numpy as np
from livekit import rtc  # type: ignore


class ReactiveAvatar:
    def __init__(self, name: str = "SimulAiz", w: int = 1280, h: int = 720, fps: int = 30):
        self.name, self.w, self.h, self.fps = name, w, h, fps
        self.level = 0.0
        self.src = rtc.VideoSource(width=w, height=h)
        self._stop = False

    def update_level(self, pcm_int16: np.ndarray) -> None:
        if pcm_int16.size:
            rms = float(np.sqrt(np.mean(pcm_int16.astype(np.float32) ** 2)))
            self.level = 0.85 * self.level + 0.15 * (rms / 20000.0)

    async def start(self, room: rtc.Room) -> None:
        track = self.src.create_track()
        await room.local_participant.publish_track(track)
        blink = 0.0
        while not self._stop:
            img = np.full((self.h, self.w, 3), 245, np.uint8)
            cx, cy = self.w // 2, self.h // 2
            # face
            cv2.circle(img, (cx, cy), min(self.w, self.h) // 4, (210, 210, 210), -1)
            # eyes
            if time.time() > blink and random.random() < 0.02:
                blink = time.time() + 0.15
            eh = 18 if time.time() > blink else 3
            cv2.ellipse(img, (cx - 120, cy - 40), (50, eh), 0, 0, 360, (50, 50, 50), -1)
            cv2.ellipse(img, (cx + 120, cy - 40), (50, eh), 0, 0, 360, (50, 50, 50), -1)
            # mouth
            mh = int(20 + 80 * min(1.0, self.level * 2.0))
            cv2.ellipse(img, (cx, cy + 90), (110, mh), 0, 0, 360, (60, 60, 60), -1)
            # nameplate
            cv2.rectangle(img, (40, self.h - 120), (520, self.h - 40), (230, 230, 230), -1)
            cv2.putText(img, self.name, (60, self.h - 70), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (30, 30, 30), 3, cv2.LINE_AA)
            frame = rtc.VideoFrame(self.w, self.h, rtc.VideoBufferType.BGR, img.tobytes())
            self.src.capture_frame(frame)
            await asyncio.sleep(1 / self.fps)

    def stop(self) -> None:
        self._stop = True

