# SimulAiz

SimulAiz is a modular multi-agent simulation toolkit. This repository currently contains the project scaffold, container orchestration assets, and contributor guidelines described in `AGENTS.md`.

## Getting Started

1. Copy `.env.sample` to `.env` and adjust values for your environment.
2. Ensure the external Docker network exists:
   ```bash
   docker network create webhost-network
   ```
3. Set LiveKit credentials in `.env` (URL, API key/secret). The UI is served at `http://simulaiz.test.neutralaiz.com/` when Traefik is active.
4. Build and start the stack (GPU-enabled host with NVIDIA Container Toolkit):
   ```bash
   docker compose build
    docker compose up -d
    ```
5. Exec into the app container for development commands:
   ```bash
    docker compose exec app bash
    ```

If using offline XTTS‑v2, place weights under `./models/xtts/` (config.json, model.pth, vocab.json). This folder is mounted at `/models/xtts` in the container.

### Demo UI
- Open the control panel at `/` and fill in caller details, mood, voice/tts, and avatar fields.
- Click Connect to obtain a LiveKit token from `/api/get-token` and join the room. The background agent (if enabled) also joins.
- In Voice & Avatar, choose avatar mode (LivePortrait, Wav2Lip, or Reactive). Upload a headshot, then click “Apply Avatar Settings” to switch instantly via data channel.

### Environment Variables (subset)
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` – server URL and credentials
- `AGENT_ENABLE`, `AGENT_NAME`, `AGENT_ROOM` – agent behavior
- `TTS_PROVIDER`, `TTS_VOICE`, `STT_PROVIDER`, `LLM_MODEL`, `PRECISION` – quality/performance
- `XTTS_DIR`, `XTTS_REF_WAV` – path to XTTS‑v2 model folder and optional reference WAV for cloning
- `AVATAR_MODE`, `AVATAR_IMAGE`, `AVATAR_FPS`, `AVATAR_WIDTH`, `AVATAR_HEIGHT` – choose `liveportrait` with a headshot for realism, or `reactive` fallback
- `W2L_WEIGHTS` – set path to Wav2Lip weights to enable audio-driven lipsync (`AVATAR_MODE=wav2lip`)
- `W2L_AUTODOWNLOAD`, `W2L_WEIGHTS_URL` – optionally auto-download weights on first run

### Offline engines
- STT: faster‑whisper (Whisper large‑v3) is bundled; set `FasterWhisper` to run on CPU by default. GPU acceleration requires CUDA builds of ctranslate2.
- TTS: Coqui XTTS‑v2 is integrated for streaming; it requires PyTorch. The default image installs CPU wheels. For GPU, rebuild with a CUDA‑enabled base and matching PyTorch.
- Avatar: LivePortrait bridge is scaffolded. Place a portrait image and set `AVATAR_MODE=liveportrait`. For full real‑time LivePortrait, clone the model repo and weights under `/models/liveportrait` and install its runtime; the bridge will fall back to an audio‑reactive portrait if unavailable.

### "WOW" GPU build
- Use the CUDA image for full GPU acceleration (Torch CUDA, xformers):
  ```bash
  DOCKERFILE=Dockerfile.gpu docker compose build
  DOCKERFILE=Dockerfile.gpu docker compose up -d
  ```
- Ensure NVIDIA Container Toolkit is installed and `gpus: all` works on your host.

To enable Wav2Lip lipsync (ultra‑realistic):
- Place the pretrained `wav2lip_gan.pth` at `./models/wav2lip/wav2lip_gan.pth`.
- Set `AVATAR_MODE=wav2lip` and `W2L_WEIGHTS=/models/wav2lip/wav2lip_gan.pth` in `.env`.


Refer to `AGENTS.md` for full contributor guidance.
