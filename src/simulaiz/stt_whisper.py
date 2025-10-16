from __future__ import annotations

import asyncio
import time
from typing import Optional

import numpy as np
import webrtcvad  # type: ignore
from faster_whisper import WhisperModel  # type: ignore


class WhisperStreamingSTT:
    """Streaming STT using faster-whisper + VAD + local-agreement stabilization.

    Provides get_partial() and get_final() async accessors. Input must be 16 kHz mono int16 PCM.
    """

    def __init__(
        self,
        model_name: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
        lang: str = "en",
        sample_rate: int = 16000,
        frame_ms: int = 20,
        window_s: int = 12,
        step_ms: int = 400,
    ) -> None:
        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)
        self.lang = lang
        self.sr = sample_rate
        self.frame = int(sample_rate * frame_ms / 1000)
        self.vad = webrtcvad.Vad(2)
        self.window = int(window_s * sample_rate)
        self.step = int(step_ms / 1000 * sample_rate)
        self.buf = np.zeros(0, dtype=np.int16)
        self.last_confirmed_t = 0.0
        self.last_text = ""
        self._final_q: asyncio.Queue[str] = asyncio.Queue()
        self._partial = ""

    async def start(self) -> None:  # pragma: no cover - interface symmetry
        return

    async def push_pcm(self, pcm: np.ndarray, sample_rate: int, num_channels: int = 1) -> None:
        if num_channels == 2:
            pcm = pcm.reshape((-1, 2)).mean(axis=1).astype(np.int16)
        if sample_rate != self.sr:
            raise ValueError("Provide 16 kHz PCM to WhisperStreamingSTT")
        # append & trim
        self.buf = np.concatenate([self.buf, pcm])[-self.window :]
        # quick VAD to avoid work in long silences
        speechy = False
        for i in range(0, len(pcm) - self.frame, self.frame):
            try:
                if self.vad.is_speech(pcm[i : i + self.frame].tobytes(), self.sr):
                    speechy = True
                    break
            except Exception:
                pass
        if not speechy:
            return

        # sliding decode every ~step_ms
        now = time.time()
        if now - self.last_confirmed_t < (self.step / self.sr):
            return

        # Decode last few seconds
        segs, _ = self.model.transcribe(
            self.buf.astype(np.float32) / 32768.0,
            language=self.lang,
            task="transcribe",
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300),
            word_timestamps=False,
        )
        text = "".join(s.text for s in segs).strip()
        # Local agreement: confirm when stable twice
        if text and text.startswith(self.last_text) and len(text) > len(self.last_text) + 6:
            new_part = text[len(self.last_text) :].strip()
            if new_part:
                await self._final_q.put(new_part)
                self.last_text = text
                self.last_confirmed_t = now
        else:
            self._partial = text

    async def get_partial(self) -> Optional[str]:
        return self._partial or None

    async def get_final(self) -> Optional[str]:
        try:
            return self._final_q.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def stop(self) -> None:  # pragma: no cover - interface symmetry
        return

