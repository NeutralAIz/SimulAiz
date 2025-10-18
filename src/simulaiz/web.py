from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import jwt
from fastapi import FastAPI, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles


def _env(key: str, default: Optional[str] = None) -> str:
    val = os.getenv(key)
    if val is None:
        return default or ""
    return val


def build_livekit_token(
    api_key: str,
    api_secret: str,
    identity: str,
    name: str,
    room: str,
    grants: Optional[Dict[str, Any]] = None,
    ttl_seconds: int = 3600,
) -> str:
    now = int(time.time())
    payload: Dict[str, Any] = {
        "iss": api_key,
        "sub": identity,
        "nbf": now - 10,
        "exp": now + ttl_seconds,
        # LiveKit grants per https://docs.livekit.io
        "video": {
            "room": room,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": True,
        },
    }
    if grants:
        # Attach extra grants under video if needed
        payload["video"].update({k: v for k, v in grants.items() if k != "metadata"})
        # LiveKit expects participant metadata at top-level "metadata" claim
        if "metadata" in grants:
            payload["metadata"] = grants["metadata"]

    token = jwt.encode(payload, api_secret, algorithm="HS256", headers={"kid": api_key})
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def create_app() -> FastAPI:
    app = FastAPI(title="SimulAiz Demo", version="0.1.0")

    static_dir = Path(__file__).parent / "ui"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    assets_dir = (Path.cwd() / "assets").resolve()
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "uploads").mkdir(parents=True, exist_ok=True)
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.on_event("startup")
    async def _startup() -> None:  # pragma: no cover - side-effects only
        # Ensure default avatar image exists; generate one using SDXL-Turbo if possible
        default_path = assets_dir / "uploads" / "default_headshot.png"
        if not default_path.exists():
            # Skip expensive model download in production unless explicitly enabled
            skip_generation = os.getenv("SKIP_DEFAULT_AVATAR_GENERATION", "false").lower() == "true"

            if skip_generation:
                # Create simple placeholder immediately
                try:
                    from PIL import Image, ImageDraw  # type: ignore

                    default_path.parent.mkdir(parents=True, exist_ok=True)
                    im = Image.new("RGB", (512, 512), (18, 24, 40))
                    d = ImageDraw.Draw(im)
                    d.ellipse((156, 96, 356, 296), fill=(220, 220, 220))
                    d.rectangle((176, 320, 336, 420), fill=(220, 220, 220))
                    im.save(default_path)
                except Exception:
                    pass
            else:
                # Try to generate with SDXL
                try:
                    import torch  # type: ignore
                    from diffusers import StableDiffusionXLPipeline  # type: ignore
                    model_id = os.getenv("SDXL_MODEL", "stabilityai/sdxl-turbo")
                    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
                    pipe = StableDiffusionXLPipeline.from_pretrained(model_id, torch_dtype=dtype)
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                    pipe = pipe.to(device)
                    g = torch.Generator(device=device).manual_seed(1234)
                    prompt = os.getenv(
                        "DEFAULT_HEADSHOT_PROMPT",
                        "front-facing studio portrait of a person, neutral expression, plain background, photorealistic, sharp focus",
                    )
                    img = pipe(prompt=prompt, width=512, height=512, generator=g, num_inference_steps=6, guidance_scale=0.0).images[0]
                    default_path.parent.mkdir(parents=True, exist_ok=True)
                    img.save(default_path)
                except Exception:
                    # Fallback: draw a neutral placeholder tile to avoid 404s
                    try:
                        from PIL import Image, ImageDraw  # type: ignore

                        default_path.parent.mkdir(parents=True, exist_ok=True)
                        im = Image.new("RGB", (512, 512), (18, 24, 40))
                        d = ImageDraw.Draw(im)
                        d.ellipse((156, 96, 356, 296), fill=(220, 220, 220))
                        d.rectangle((176, 320, 336, 420), fill=(220, 220, 220))
                        im.save(default_path)
                    except Exception:
                        pass
        # Expose container-internal path for agent default
        if default_path.exists():
            os.environ["DEFAULT_AVATAR_IMAGE_PATH"] = "/app" + str(default_path.resolve())[len(str(Path.cwd().resolve())) :]

    @app.get("/", response_class=HTMLResponse)
    async def index() -> Response:
        index_path = static_dir / "index.html"
        if not index_path.exists():
            return HTMLResponse("<h1>SimulAiz Demo</h1><p>UI missing.</p>", status_code=200)
        return HTMLResponse(index_path.read_text(encoding="utf-8"))

    @app.get("/api/health")
    async def health() -> Dict[str, Any]:
        return {"status": "ok"}

    @app.get("/api/get-token")
    async def get_token(
        roomName: str = Query(...),
        user: Optional[str] = Query(None),
        name: Optional[str] = Query(None),
        userType: Optional[str] = Query(None),
        metadata: Optional[str] = Query(None),
    ) -> JSONResponse:
        api_key = _env("LIVEKIT_API_KEY")
        api_secret = _env("LIVEKIT_API_SECRET")
        lk_url = _env("LIVEKIT_URL")

        if not api_key or not api_secret or not lk_url:
            raise HTTPException(status_code=500, detail="LiveKit configuration missing")

        identity = user or name or f"user-{int(time.time())}"
        display_name = name or user or identity

        grants: Dict[str, Any] = {}
        # Optional: attach metadata as JSON string claim for downstream services
        if metadata:
            try:
                parsed = json.loads(metadata)
                # LiveKit tokens support a top-level metadata string; keep as JSON string
                grants["metadata"] = json.dumps(parsed)
            except Exception:
                grants["metadata"] = metadata

        token = build_livekit_token(
            api_key=api_key,
            api_secret=api_secret,
            identity=identity,
            name=display_name,
            room=roomName,
            grants=grants,
        )

        return JSONResponse({"token": token, "url": lk_url})

    @app.post("/api/upload-avatar")
    async def upload_avatar(file: UploadFile = File(...)) -> JSONResponse:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing filename")
        safe_name = file.filename.replace("..", "_").replace("/", "_")
        out_dir = assets_dir / "uploads"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / safe_name
        contents = await file.read()
        out_path.write_bytes(contents)
        public_url = f"/assets/uploads/{safe_name}"
        internal_path = str(out_path.resolve())
        # Map to container internal path used by agent (/app is WORKDIR)
        if internal_path.startswith(str(Path.cwd().resolve())):
            internal_path = "/app" + internal_path[len(str(Path.cwd().resolve())) :]
        return JSONResponse({"ok": True, "publicUrl": public_url, "internalPath": internal_path})

    @app.post("/api/fetch-w2l-weights")
    async def fetch_w2l_weights(request: Request) -> JSONResponse:
        body = await request.json()
        url = str(body.get("url") or os.getenv("W2L_WEIGHTS_URL") or "").strip()
        path = str(body.get("path") or os.getenv("W2L_WEIGHTS") or "/models/wav2lip/wav2lip_gan.pth").strip()
        if not url:
            raise HTTPException(status_code=400, detail="Provide url or set W2L_WEIGHTS_URL")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            import urllib.request

            urllib.request.urlretrieve(url, path)  # noqa: S310
            ok = os.path.exists(path) and os.path.getsize(path) > 0
            return JSONResponse({"ok": ok, "path": path})
        except Exception as e:  # pragma: no cover
            raise HTTPException(status_code=500, detail=f"download failed: {e}")

    @app.get("/api/w2l-weights-status")
    async def w2l_status(path: str | None = None) -> JSONResponse:
        p = path or os.getenv("W2L_WEIGHTS") or "/models/wav2lip/wav2lip_gan.pth"
        return JSONResponse({"exists": os.path.exists(p), "path": p})

    @app.post("/api/generate-avatar")
    async def generate_avatar(request: Request) -> JSONResponse:
        body = await request.json()
        prompt = str(body.get("prompt") or "portrait photo of a person, neutral expression, studio lighting, plain background, centered, front-facing")
        width = int(body.get("width") or 768)
        height = int(body.get("height") or 768)
        seed = int(body.get("seed") or 42)
        model_id = os.getenv("SDXL_MODEL", "stabilityai/stable-diffusion-xl-base-1.0")
        try:
            import torch  # type: ignore
            from diffusers import StableDiffusionXLPipeline  # type: ignore
            dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            pipe = StableDiffusionXLPipeline.from_pretrained(model_id, torch_dtype=dtype)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            pipe = pipe.to(device)
            g = torch.Generator(device=device).manual_seed(seed)
            image = pipe(prompt=prompt, width=width, height=height, generator=g, num_inference_steps=30, guidance_scale=6.5).images[0]
        except Exception as e:  # pragma: no cover
            raise HTTPException(status_code=500, detail=f"generation failed: {e}")

        # Save to assets/uploads
        name = f"gen_headshot_{int(time.time())}.png"
        out_path = assets_dir / "uploads" / name
        image.save(out_path)
        public_url = f"/assets/uploads/{name}"
        internal_path = str(out_path.resolve())
        if internal_path.startswith(str(Path.cwd().resolve())):
            internal_path = "/app" + internal_path[len(str(Path.cwd().resolve())) :]
        return JSONResponse({"ok": True, "publicUrl": public_url, "internalPath": internal_path})

    return app


app = create_app()
