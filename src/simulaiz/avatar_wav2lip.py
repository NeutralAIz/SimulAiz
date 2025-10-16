from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

import cv2  # type: ignore
import numpy as np
from livekit import rtc  # type: ignore


class Wav2LipBridge:
    """Audio-driven lipsync using Wav2Lip on a single portrait.

    Requirements (placed inside the container):
      - Wav2Lip repo installed as a module (pip install git+https://github.com/Rudrabha/Wav2Lip.git)
      - Weights at /models/wav2lip/wav2lip_gan.pth

    This implementation batches short audio windows, runs lipsync, and publishes
    frames at ~25 fps. If dependencies are missing, raises at init.
    """

    def __init__(self, image_path: str, weights: str = "/models/wav2lip/wav2lip_gan.pth", fps: int = 25,
                 width: int = 640, height: int = 640) -> None:
        try:
            from wav2lip.inference import load_model, datagen, face_detect
        except Exception as e:  # pragma: no cover
            raise RuntimeError("Wav2Lip not installed. Install git+https://github.com/Rudrabha/Wav2Lip.git") from e
        self._w2l_load_model = load_model  # type: ignore
        self._w2l_face_detect = face_detect  # type: ignore

        if not Path(weights).exists():
            raise FileNotFoundError(f"Wav2Lip weights not found: {weights}")
        self.weights = weights

        img = cv2.imread(image_path)
        if img is None:
            raise RuntimeError(f"Failed to load portrait image: {image_path}")
        self.portrait = cv2.resize(img, (width, height))
        self.h, self.w = self.portrait.shape[:2]
        self.fps = fps
        self.src = rtc.VideoSource(width=self.w, height=self.h)
        self._stop = False
        self._pcm_q: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=64)
        self._frame_q: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=64)

        # Lazy model load
        self._model = None

    async def start(self, room: rtc.Room) -> None:
        track = self.src.create_track()
        await room.local_participant.publish_track(track)
        await asyncio.gather(self._player(), self._worker())

    def stop(self) -> None:
        self._stop = True

    async def consume_tts_chunk(self, pcm_int16: np.ndarray) -> None:
        try:
            self._pcm_q.put_nowait(pcm_int16)
        except asyncio.QueueFull:
            pass

    async def _player(self) -> None:
        period = 1 / max(1, self.fps)
        while not self._stop:
            try:
                img = await asyncio.wait_for(self._frame_q.get(), timeout=0.5)
            except asyncio.TimeoutError:
                img = self.portrait.copy()
            frame = rtc.VideoFrame(self.w, self.h, rtc.VideoBufferType.BGR, img.tobytes())
            self.src.capture_frame(frame)
            await asyncio.sleep(period)

    async def _worker(self) -> None:
        # Minimal streaming approximation: collect ~0.5s audio windows, render a short burst
        sr = 48000
        window = int(0.5 * sr)
        buf = np.zeros(0, dtype=np.int16)
        while not self._stop:
            try:
                chunk = await asyncio.wait_for(self._pcm_q.get(), timeout=0.5)
                buf = np.concatenate([buf, chunk])
            except asyncio.TimeoutError:
                # idle frame
                await self._frame_q.put(self.portrait.copy())
                continue
            if len(buf) < window:
                continue
            audio = buf[:window].copy()
            buf = buf[window:]
            # Render lipsync for this window
            try:
                frames = self._render_window(audio, sr)
                for fr in frames:
                    try:
                        self._frame_q.put_nowait(fr)
                    except asyncio.QueueFull:
                        break
            except Exception:
                # On failure, push portrait
                await self._frame_q.put(self.portrait.copy())

    def _lazy_model(self):
        if self._model is None:
            self._model = self._w2l_load_model(self.weights)
        return self._model

    def _render_window(self, pcm: np.ndarray, sr: int) -> list[np.ndarray]:
        # Adapted from Wav2Lip’s inference loop (simplified for a fixed portrait)
        import torch
        from wav2lip.inference import datagen, face_detect

        mel_step_size = 16
        gen = datagen(self.portrait[:,:,::-1].copy(), pcm, sr, self.fps, pads=[0,10,0,0])
        model = self._lazy_model()
        model.eval()
        out_frames: list[np.ndarray] = []
        with torch.no_grad():
            for (img_batch, mel_batch, frames, coords) in gen:
                img_batch = torch.FloatTensor(np.transpose(img_batch, (0, 3, 1, 2))).to(model.device)
                mel_batch = torch.FloatTensor(np.transpose(mel_batch, (0, 3, 1, 2))).to(model.device)
                pred = model(mel_batch, img_batch)
                pred = pred.cpu().numpy().transpose(0, 2, 3, 1) * 255.0
                for p, f, c in zip(pred, frames, coords):
                    y1, y2, x1, x2 = c
                    f[y1:y2, x1:x2] = p
                    out_frames.append(f[:, :, ::-1].copy())
        return out_frames

