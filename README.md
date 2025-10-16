# SimulAiz

<div align="center">

**Real-time AI Avatar System with Ultra-Realistic Lipsync**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![CUDA](https://img.shields.io/badge/CUDA-12.1-76B900?logo=nvidia)](https://developer.nvidia.com/cuda-toolkit)

[Features](#features) • [Quick Start](#quick-start) • [Deployment](#deployment) • [Architecture](#architecture) • [Documentation](#documentation)

</div>

---

## Overview

SimulAiz is a real-time interactive AI avatar system that combines state-of-the-art speech processing with photorealistic avatar rendering. Built for production environments with Docker Swarm support, GPU acceleration, and LiveKit WebRTC integration.

### Key Capabilities

- **🎭 Three Avatar Modes**
  - **Wav2Lip**: Ultra-realistic GPU-accelerated lipsync with audio-driven facial animation
  - **LivePortrait**: Fast CPU-based portrait animation with natural expressions
  - **Reactive**: Lightweight WebRTC-based avatar for resource-constrained environments

- **🗣️ Advanced Speech Processing**
  - **Whisper STT**: OpenAI Whisper (large-v3 on GPU, base on CPU) for accurate speech recognition
  - **XTTS TTS**: Coqui XTTS-v2 with voice cloning and streaming audio synthesis

- **🚀 Production-Ready**
  - Docker Swarm orchestration with GPU node support
  - Shared storage via CephFS for model distribution
  - LiveKit WebRTC for real-time communication
  - Horizontal scaling and load balancing

---

## Features

### Avatar Rendering

| Mode | Quality | Performance | Hardware | Use Case |
|------|---------|-------------|----------|----------|
| **Wav2Lip** | Ultra-realistic lipsync | GPU required | CUDA 12.1+ | Production demos, high-fidelity avatars |
| **LivePortrait** | Natural expressions | CPU efficient | Any | General purpose, cost-effective |
| **Reactive** | Basic animation | Lightweight | Browser-only | Development, fallback mode |

### Speech & Audio

- **STT Engine**: faster-whisper with CUDA acceleration
- **TTS Engine**: Coqui XTTS-v2 with voice cloning
- **Audio Processing**: Real-time streaming with <100ms latency
- **Voice Cloning**: One-shot voice replication from reference audio

### Infrastructure

- **WebRTC**: LiveKit integration for real-time media streaming
- **GPU Support**: NVIDIA CUDA 12.1 with PyTorch 2.5.1
- **Container Orchestration**: Docker Swarm with multi-node deployment
- **Shared Storage**: CephFS for model distribution across nodes
- **Monitoring**: Health checks and automatic restart policies

---

## Quick Start

### Prerequisites

- Docker 24.0+ with Docker Compose
- NVIDIA GPU with CUDA 12.1+ (for GPU features)
- NVIDIA Container Toolkit (for GPU support)
- LiveKit server (cloud or self-hosted)

### Local Development (Docker Compose)

1. **Clone the repository**
   ```bash
   git clone https://github.com/NeutralAIz/SimulAiz.git
   cd SimulAiz
   ```

2. **Configure environment**
   ```bash
   cp .env.sample .env
   # Edit .env and set LiveKit credentials:
   # LIVEKIT_URL=wss://your-livekit-server.com
   # LIVEKIT_API_KEY=your-api-key
   # LIVEKIT_API_SECRET=your-api-secret
   ```

3. **Create Docker network**
   ```bash
   docker network create webhost-network
   ```

4. **Choose your build**

   **CPU-only (LivePortrait mode)**
   ```bash
   docker compose build
   docker compose up -d
   ```

   **GPU-enabled (Wav2Lip + CUDA acceleration)**
   ```bash
   DOCKERFILE=Dockerfile.gpu docker compose build
   docker compose up -d
   ```

5. **Access the UI**
   - Open `http://localhost:8000` (or configured domain)
   - Fill in caller details and connect
   - Upload avatar image and select rendering mode

### Model Setup

#### Wav2Lip (Ultra-realistic lipsync - GPU required)

1. Download pretrained weights:
   ```bash
   mkdir -p models/wav2lip
   # Download wav2lip_gan.pth to models/wav2lip/
   wget https://github.com/Rudrabha/Wav2Lip/releases/download/v1.0/wav2lip_gan.pth \
        -O models/wav2lip/wav2lip_gan.pth
   ```

2. Configure in `.env`:
   ```bash
   AVATAR_MODE=wav2lip
   W2L_WEIGHTS=/models/wav2lip/wav2lip_gan.pth
   ```

#### XTTS Voice Cloning (Optional)

1. Place XTTS-v2 model files:
   ```bash
   mkdir -p models/xtts
   # Add: config.json, model.pth, vocab.json
   ```

2. Configure in `.env`:
   ```bash
   XTTS_DIR=/models/xtts
   XTTS_REF_WAV=/path/to/reference/voice.wav  # Optional
   ```

---

## Deployment

### Docker Swarm (Production)

SimulAiz includes full Docker Swarm orchestration with GPU support, shared storage, and automatic scaling.

#### Infrastructure Setup

1. **Configure Swarm Stack**
   ```bash
   # In your infrastructure repository
   cd ~/infrastructure/stacks/simulaiz
   cp .env.example .env
   # Edit .env with LiveKit credentials
   ```

2. **Deploy to Swarm**
   ```bash
   # Automatic deployment (builds, pushes, deploys)
   ~/infrastructure/bin/deploy-simulaiz.sh

   # Or manual deployment
   cd ~/infrastructure/stacks/simulaiz
   ./setup-storage.sh      # Initialize CephFS directories
   ./build-and-push.sh     # Build and push to registry
   ./deploy.sh             # Deploy stack to swarm
   ```

3. **Verify Deployment**
   ```bash
   # Check service status
   docker service ls --filter label=com.docker.stack.namespace=simulaiz

   # View logs
   docker service logs -f simulaiz_simulaiz
   ```

#### Swarm Architecture

- **GPU Nodes**: RTX-3090 with CUDA support for Wav2Lip
- **Shared Storage**: CephFS at `/mnt/cephfs/simulaiz/`
  - Models: `/mnt/cephfs/simulaiz/models/`
  - Assets: `/mnt/cephfs/simulaiz/assets/`
- **Registry**: Shared Docker registry at `registry.shared.neutralaiz.com:5000`
- **Networking**: Traefik reverse proxy with automatic routing
- **Access**: `http://simulaiz.test.neutralaiz.com` (configurable)

#### Scaling

```bash
# Scale GPU instances (if multiple GPU nodes available)
docker service scale simulaiz_simulaiz=2

# Update with zero-downtime
docker service update --image registry.shared.neutralaiz.com:5000/simulaiz:latest \
                      simulaiz_simulaiz
```

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Browser                        │
│                   (WebRTC + Control Panel)                   │
└────────────────────────────┬────────────────────────────────┘
                             │
                    LiveKit WebRTC
                             │
┌────────────────────────────┴────────────────────────────────┐
│                      SimulAiz Agent                          │
├──────────────────────────────────────────────────────────────┤
│  STT (Whisper)  →  LLM  →  TTS (XTTS)  →  Avatar Renderer  │
│                                                               │
│  Avatar Modes:                                               │
│  • Wav2Lip      (GPU - Ultra-realistic lipsync)            │
│  • LivePortrait (CPU - Natural expressions)                │
│  • Reactive     (Browser - Lightweight fallback)           │
└───────────────────────────────────────────────────────────────┘
```

### Technology Stack

- **Runtime**: Python 3.10+ with asyncio
- **Deep Learning**: PyTorch 2.5.1 with CUDA 12.1
- **Speech**: faster-whisper (Whisper large-v3), Coqui XTTS-v2
- **Avatar**: Wav2Lip, LivePortrait, custom reactive renderer
- **WebRTC**: LiveKit Python SDK
- **Containers**: Docker 24.0+, Docker Swarm
- **Storage**: CephFS distributed filesystem
- **Networking**: Traefik reverse proxy

### Data Flow

1. **Audio Input**: Client → LiveKit → Whisper STT
2. **Processing**: Whisper → LLM (optional) → XTTS TTS
3. **Avatar Sync**: Audio → Wav2Lip/LivePortrait → Video frames
4. **Output**: Video frames → LiveKit → Client

---

## Documentation

### Environment Variables

#### LiveKit Configuration
```bash
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
```

#### Agent Settings
```bash
AGENT_ENABLE=true
AGENT_IDENTITY=simulaiz-agent
AGENT_NAME=SimulAiz Agent
AGENT_ROOM=simulaiz-demo
```

#### Speech & TTS
```bash
# STT (Speech-to-Text)
STT_PROVIDER=FasterWhisper
WHISPER_MODEL=large-v3      # or 'base' for CPU
WHISPER_DEVICE=cuda          # or 'cpu'
WHISPER_COMPUTE=float16      # or 'float32' for CPU

# TTS (Text-to-Speech)
TTS_PROVIDER=XTTS
XTTS_DIR=/models/xtts
XTTS_REF_WAV=/path/to/reference.wav  # Optional voice cloning
TTS_DEVICE=cuda              # or 'cpu'
```

#### Avatar Configuration
```bash
AVATAR_MODE=wav2lip          # or 'liveportrait', 'reactive'
AVATAR_IMAGE=/app/assets/avatar.png
AVATAR_FPS=25
AVATAR_WIDTH=512
AVATAR_HEIGHT=512

# Wav2Lip specific
W2L_WEIGHTS=/models/wav2lip/wav2lip_gan.pth
W2L_AUTODOWNLOAD=false
```

### API Endpoints

- `GET /` - Web UI control panel
- `POST /api/get-token` - Generate LiveKit access token
- `WebSocket /ws` - Control channel for avatar switching

### Development

```bash
# Enter development container
docker compose exec app bash

# Run tests
pytest

# Install additional dependencies
pip install -e .

# View logs
docker compose logs -f app
```

### Troubleshooting

**GPU not detected**
```bash
# Check NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# Ensure gpus: all in docker-compose.yml
```

**Model loading fails**
```bash
# Verify model files exist
ls -lh models/wav2lip/wav2lip_gan.pth
ls -lh models/xtts/

# Check permissions
chmod -R 755 models/
```

**LiveKit connection issues**
```bash
# Test LiveKit connectivity
curl -v wss://your-livekit-server.com

# Verify credentials in .env
grep LIVEKIT .env
```

---

## Performance

### GPU Mode (Wav2Lip)
- **Latency**: 80-120ms end-to-end
- **Throughput**: 25 fps @ 512x512 resolution
- **VRAM**: ~4GB (RTX 3090)
- **Quality**: Photorealistic lipsync

### CPU Mode (LivePortrait)
- **Latency**: 150-250ms end-to-end
- **Throughput**: 15-20 fps @ 512x512 resolution
- **RAM**: ~2GB
- **Quality**: Natural expressions, good for general use

---

## Contributing

See [AGENTS.md](AGENTS.md) for contributor guidelines and development workflow.

---

## License

MIT License - see [LICENSE](LICENSE) for details

---

## Acknowledgments

- [Wav2Lip](https://github.com/Rudrabha/Wav2Lip) - Audio-driven lipsync
- [LivePortrait](https://github.com/KwaiVGI/LivePortrait) - Portrait animation
- [Whisper](https://github.com/openai/whisper) - Speech recognition
- [Coqui TTS](https://github.com/coqui-ai/TTS) - Text-to-speech
- [LiveKit](https://livekit.io/) - WebRTC infrastructure

---

<div align="center">

**Built with ❤️ using Python, PyTorch, and Docker**

[Report Bug](https://github.com/NeutralAIz/SimulAiz/issues) • [Request Feature](https://github.com/NeutralAIz/SimulAiz/issues) • [Documentation](https://github.com/NeutralAIz/SimulAiz/wiki)

</div>
