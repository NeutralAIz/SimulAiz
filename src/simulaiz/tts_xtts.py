from __future__ import annotations

import asyncio
import os
from typing import List

import numpy as np
from scipy.signal import resample_poly  # type: ignore

try:
    import torch  # noqa: F401
    from TTS.tts.configs.xtts_config import XttsConfig  # type: ignore
    from TTS.tts.models.xtts import Xtts  # type: ignore
except Exception as _e:  # pragma: no cover - import-time guard
    Xtts = None  # type: ignore
    XttsConfig = None  # type: ignore


class XTTSStreamer:
    def __init__(self, model_dir: str, out_rate: int = 48000, device: str = "cuda", ref_wav: str | None = None):
        if Xtts is None or XttsConfig is None:
            raise RuntimeError("Coqui TTS (XTTS) is not installed. Please install 'TTS' package.")
        cfg = XttsConfig()
        cfg.load_json(os.path.join(model_dir, "config.json"))
        model = Xtts.init_from_config(cfg)
        model.load_checkpoint(
            cfg,
            checkpoint_path=os.path.join(model_dir, "model.pth"),
            vocab_path=os.path.join(model_dir, "vocab.json"),
            use_deepspeed=False,
        )
        self.model = model.to(device).eval()
        self.device = device
        self.out_rate = out_rate
        self.gpt_cond_latent = None
        self.spk_emb = None
        if ref_wav:
            self.gpt_cond_latent, self.spk_emb = self.model.get_conditioning_latents(ref_wav, ref_wav, device)

    async def speak(self, text: str) -> List[np.ndarray]:
        gen = self.model.inference_stream(
            text=text,
            language="en",
            gpt_cond_latent=self.gpt_cond_latent,
            speaker_embedding=self.spk_emb,
            stream_chunk_size=8,
            enable_text_splitting=True,
        )
        chunks: List[np.ndarray] = []
        for sample in gen:
            wav = sample.audio  # float32 at sample.sr
            if sample.sr != self.out_rate:
                wav = resample_poly(wav, self.out_rate, sample.sr)
            pcm = np.clip(wav * 32768.0, -32768, 32767).astype(np.int16)
            frame = int(self.out_rate * 0.02)
            for i in range(0, len(pcm), frame):
                part = pcm[i : i + frame]
                if len(part):
                    chunks.append(part.copy())
            await asyncio.sleep(0)
        return chunks

