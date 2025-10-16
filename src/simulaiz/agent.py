from __future__ import annotations

import asyncio
import json
import os
import threading
from dataclasses import dataclass
from typing import Optional, Any, Dict


@dataclass
class AgentConfig:
    enabled: bool = bool(os.getenv("AGENT_ENABLE", "true").lower() in {"1", "true", "yes"})
    identity: str = os.getenv("AGENT_IDENTITY", "simulaiz-agent")
    display_name: str = os.getenv("AGENT_NAME", "SimulAiz Agent")
    room: str = os.getenv("AGENT_ROOM", "simulaiz-demo")
    lk_url: str = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    api_key: str = os.getenv("LIVEKIT_API_KEY", "")
    api_secret: str = os.getenv("LIVEKIT_API_SECRET", "")


class SimpleBrain:
    def __init__(self) -> None:
        self.s: Dict[str, Any] = {
            "mood": os.getenv("CALLER_MOOD", "normal"),
            "reason": os.getenv("CALL_REASON", "demo"),
            "caller_name": os.getenv("CALLER_NAME", "Jordan"),
        }

    def opening(self) -> str:
        reason = self.s.get("reason") or "a quick test"
        return f"Hi, I’d like to start {reason}."

    def answer(self, heard: str) -> str:
        mood = (self.s.get("mood") or "normal").lower()
        pre = {
            "happy": "Sure!",
            "sad": "I’m not feeling great, but",
            "scared": "I’m a bit worried,",
            "panicked": "Please—",
            "normal": "Okay,",
        }.get(mood, "Okay,")
        return f"{pre} I heard: {heard.strip()}."


async def _run_agent_async(cfg: AgentConfig) -> None:
    try:
        import jwt  # pyjwt
        import time
        from livekit import api as lkapi
        from livekit import rtc as lkrtc
        import numpy as np

        # Offline engines (optional heavy deps)
        try:
            from .stt_whisper import WhisperStreamingSTT
        except Exception as e:
            WhisperStreamingSTT = None  # type: ignore
            print(f"[agent] STT unavailable: {e}")
        try:
            from .tts_xtts import XTTSStreamer
        except Exception as e:
            XTTSStreamer = None  # type: ignore
            print(f"[agent] TTS unavailable: {e}")
        try:
            from .avatar_liveportrait import LivePortraitBridge
        except Exception as e:
            LivePortraitBridge = None  # type: ignore
            print(f"[agent] LivePortrait bridge unavailable: {e}")
        try:
            from .avatar_wav2lip import Wav2LipBridge
        except Exception as e:
            Wav2LipBridge = None  # type: ignore
            print(f"[agent] Wav2Lip bridge unavailable: {e}")
        try:
            from .avatar_reactive import ReactiveAvatar
        except Exception as e:
            ReactiveAvatar = None  # type: ignore
            print(f"[agent] Reactive avatar unavailable: {e}")

        def _ensure_w2l_weights(path: str) -> None:
            try:
                if os.path.exists(path):
                    return
                if os.getenv("W2L_AUTODOWNLOAD", "false").lower() not in {"1", "true", "yes"}:
                    print(f"[agent] Wav2Lip weights missing at {path}; set W2L_AUTODOWNLOAD=true and W2L_WEIGHTS_URL to download.")
                    return
                url = os.getenv("W2L_WEIGHTS_URL", "")
                if not url:
                    print("[agent] W2L_WEIGHTS_URL not set; cannot auto-download.")
                    return
                os.makedirs(os.path.dirname(path), exist_ok=True)
                import urllib.request

                print(f"[agent] Downloading Wav2Lip weights from {url} …")
                urllib.request.urlretrieve(url, path)  # noqa: S310
                print("[agent] Wav2Lip weights downloaded.")
            except Exception as e:
                print(f"[agent] Failed to download Wav2Lip weights: {e}")

        # Build token
        now = int(time.time())
        payload = {
            "iss": cfg.api_key,
            "sub": cfg.identity,
            "nbf": now - 10,
            "exp": now + 3600,
            "video": {
                "room": cfg.room,
                "roomJoin": True,
                "canPublish": True,
                "canSubscribe": True,
                "canPublishData": True,
            },
            # top-level participant metadata
            "metadata": json.dumps({"agent": True, "name": cfg.display_name}),
        }
        token = jwt.encode(payload, cfg.api_secret, algorithm="HS256", headers={"kid": cfg.api_key})
        if isinstance(token, bytes):
            token = token.decode("utf-8")

        room = lkrtc.Room()
        await room.connect(cfg.lk_url, token)

        # Publish audio and video
        audio_src = lkrtc.AudioSource()
        await room.local_participant.publish_track(audio_src.create_track())

        avatar = None
        avatar_task: Optional[asyncio.Task] = None
        avatar_mode = os.getenv("AVATAR_MODE", "reactive").lower()
        if avatar_mode == "wav2lip" and 'Wav2LipBridge' in globals() and Wav2LipBridge:
            img = os.getenv("AVATAR_IMAGE", "")
            if img:
                try:
                    avatar = Wav2LipBridge(
                        image_path=img,
                        weights=os.getenv("W2L_WEIGHTS", "/models/wav2lip/wav2lip_gan.pth"),
                        fps=int(os.getenv("AVATAR_FPS", "25")),
                        width=int(os.getenv("AVATAR_WIDTH", "640")),
                        height=int(os.getenv("AVATAR_HEIGHT", "640")),
                    )
                except Exception as e:
                    print(f"[agent] Wav2Lip init failed: {e}")
        elif avatar_mode == "liveportrait" and 'LivePortraitBridge' in globals() and LivePortraitBridge:
            img = os.getenv("AVATAR_IMAGE", "")
            if img:
                try:
                    avatar = LivePortraitBridge(
                        image_path=img,
                        width=int(os.getenv("AVATAR_WIDTH", "1280")),
                        height=int(os.getenv("AVATAR_HEIGHT", "720")),
                        fps=int(os.getenv("AVATAR_FPS", "30")),
                    )
                except Exception as e:
                    print(f"[agent] LivePortrait init failed, falling back: {e}")
        if avatar is None and 'ReactiveAvatar' in globals() and ReactiveAvatar:
            avatar = ReactiveAvatar(cfg.display_name)
        if avatar is not None:
            avatar_task = asyncio.create_task(avatar.start(room))

        brain = SimpleBrain()

        # Track metadata from remote participant token (sent via UI)
        def _update_state_from_metadata(md: str | None) -> None:
            if not md:
                return
            try:
                data = json.loads(md)
                for k in ("mood", "reason", "caller", "attributes", "voice", "avatar", "quality"):
                    if k in data:
                        brain.s[k] = data[k]
            except Exception:
                pass

        for p in room.remote_participants:
            try:
                md = getattr(p, "metadata", None) or getattr(getattr(p, "info", None), "metadata", None)
                _update_state_from_metadata(md)
            except Exception:
                pass

        async def apply_avatar_settings() -> None:
            nonlocal avatar, avatar_task
            mode = (brain.s.get("avatar_mode") or os.getenv("AVATAR_MODE", "reactive")).lower()
            img = brain.s.get("avatar_image") or os.getenv("AVATAR_IMAGE", "") or os.getenv("DEFAULT_AVATAR_IMAGE_PATH", "")
            fps = int(str(brain.s.get("avatar_fps") or os.getenv("AVATAR_FPS", "30")))
            w = int(str(brain.s.get("avatar_width") or os.getenv("AVATAR_WIDTH", "1280")))
            h = int(str(brain.s.get("avatar_height") or os.getenv("AVATAR_HEIGHT", "720")))
            # Stop previous avatar
            try:
                if avatar is not None:
                    avatar.stop()
                if avatar_task is not None:
                    avatar_task.cancel()
            except Exception:
                pass
            # Attempt to unpublish prior video tracks (best-effort)
            try:
                pubs = getattr(room.local_participant, "get_track_publications", lambda: [])()
                for p in pubs:
                    if getattr(p, "kind", None) == lkrtc.TrackKind.KIND_VIDEO or getattr(getattr(p, "track", None), "kind", None) == lkrtc.TrackKind.KIND_VIDEO:
                        try:
                            room.local_participant.unpublish_track(p.track)
                        except Exception:
                            pass
            except Exception:
                pass
            # (Optional) Ensure Wav2Lip weights
            if mode == "wav2lip":
                _ensure_w2l_weights(os.getenv("W2L_WEIGHTS", "/models/wav2lip/wav2lip_gan.pth"))

            # Build new avatar
            avatar = None
            if mode == "wav2lip" and 'Wav2LipBridge' in globals() and Wav2LipBridge and img:
                try:
                    avatar = Wav2LipBridge(image_path=img, weights=os.getenv("W2L_WEIGHTS", "/models/wav2lip/wav2lip_gan.pth"), fps=fps, width=w, height=h)
                except Exception as e:
                    print(f"[agent] Wav2Lip switch failed: {e}")
            elif mode == "liveportrait" and 'LivePortraitBridge' in globals() and LivePortraitBridge and img:
                try:
                    avatar = LivePortraitBridge(image_path=img, width=w, height=h, fps=fps)
                except Exception as e:
                    print(f"[agent] LivePortrait switch failed: {e}")
            elif 'ReactiveAvatar' in globals() and ReactiveAvatar:
                avatar = ReactiveAvatar(cfg.display_name, w, h, fps)  # type: ignore

            if avatar is not None:
                avatar_task = asyncio.create_task(avatar.start(room))

        @room.on("data_received")
        def _on_data(pkt: lkrtc.DataPacket) -> None:  # type: ignore
            try:
                obj = json.loads(pkt.data.decode("utf-8"))
                if isinstance(obj, dict) and obj.get("type") == "caller.sim":
                    changed = False
                    for k, v in obj.get("set", {}).items():
                        brain.s[k] = v
                        if k.startswith("avatar_"):
                            changed = True
                    if changed:
                        asyncio.create_task(apply_avatar_settings())
            except Exception:
                pass

        # STT + TTS wiring
        stt = None
        if 'WhisperStreamingSTT' in globals() and WhisperStreamingSTT:
            try:
                stt = WhisperStreamingSTT(
                    model_name=os.getenv("WHISPER_MODEL", "large-v3"),
                    device=os.getenv("WHISPER_DEVICE", "cuda"),
                    compute_type=os.getenv("WHISPER_COMPUTE", "float16"),
                    lang=os.getenv("WHISPER_LANG", "en"),
                )
            except Exception as e:
                print(f"[agent] STT init failed: {e}")
        tts = None
        if 'XTTSStreamer' in globals() and XTTSStreamer:
            try:
                tts = XTTSStreamer(
                    model_dir=os.getenv("XTTS_DIR", "/models/xtts"),
                    ref_wav=os.getenv("XTTS_REF_WAV"),
                    device=os.getenv("TTS_DEVICE", "cuda"),
                )
            except Exception as e:
                print(f"[agent] TTS init failed: {e}")

        if stt is None or tts is None:
            print("[agent] STT/TTS not fully available; agent will idle but stay online.")

        # Optional greeting
        async def speak_text(txt: str) -> None:
            if tts is None:
                return
            chunks = await tts.speak(txt)
            for ch in chunks:
                if avatar is not None:
                    # LivePortraitBridge consumes audio to synthesize frames; Reactive updates RMS
                    if hasattr(avatar, "consume_tts_chunk"):
                        await avatar.consume_tts_chunk(ch)  # type: ignore
                    elif hasattr(avatar, "update_level"):
                        avatar.update_level(ch)  # type: ignore
                af = lkrtc.AudioFrame.create(sample_rate=48000, num_channels=1, samples_per_channel=len(ch))
                mv = memoryview(af.data)
                mv[: 2 * len(ch)] = ch.tobytes()
                audio_src.capture_frame(af)
                await asyncio.sleep(len(ch) / 48000.0)

        if tts is not None and os.getenv("AGENT_GREETING", "true").lower() in {"1","true","yes"}:
            asyncio.create_task(speak_text(brain.opening()))

        # Consume remote audio -> STT -> Brain -> TTS -> publish audio
        async def consume_remote_audio(stream: lkrtc.AudioStream) -> None:
            if stt is None:
                return
            await stt.start()
            async for f in stream:
                pcm = np.frombuffer(f.data, dtype=np.int16)
                if f.num_channels == 2:
                    pcm = pcm.reshape((-1, 2)).mean(axis=1).astype(np.int16)
                # downsample 48k -> 16k by decimation (simple but effective)
                if f.sample_rate != 16000:
                    factor = max(1, int(round(f.sample_rate / 16000)))
                    pcm = pcm[::factor]
                await stt.push_pcm(pcm, sample_rate=16000, num_channels=1)
                final = await stt.get_final()
                if final and tts is not None:
                    await speak_text(brain.answer(final))

        @room.on("track_subscribed")
        def _on_sub(track, pub, participant):  # type: ignore
            if getattr(track, "kind", None) == lkrtc.TrackKind.KIND_AUDIO:
                asyncio.create_task(consume_remote_audio(lkrtc.AudioStream(track)))

        # Announce presence
        await room.local_participant.publish_data(
            json.dumps({"type": "agent-online", "name": cfg.display_name}).encode(), reliable=True
        )

        try:
            while True:
                await asyncio.sleep(5)
        finally:
            if avatar is not None:
                avatar.stop()
            await room.disconnect()

    except Exception as e:  # pragma: no cover - best effort background task
        print(f"[agent] failed to start: {e}")


def start_background_agent() -> Optional[threading.Thread]:
    cfg = AgentConfig()
    if not cfg.enabled:
        print("[agent] disabled via AGENT_ENABLE=false")
        return None
    if not (cfg.api_key and cfg.api_secret and cfg.lk_url):
        print("[agent] missing LiveKit configuration; skipping start")
        return None

    def runner() -> None:
        asyncio.run(_run_agent_async(cfg))

    t = threading.Thread(target=runner, name="simulaiz-agent", daemon=True)
    t.start()
    print("[agent] background agent thread started")
    return t
