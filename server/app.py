import asyncio
import base64
import json
import os
import platform
import re
import subprocess
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional
from urllib.parse import unquote

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from server.studio_bridge import bridge

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
SETTINGS_PATH = ROOT / "ui_settings.json"
RENDER_THUMB_PATH = ROOT / ".studio_render_thumb.png"


def _sanitize_videos_subfolder(text: str) -> str:
    t = (text or "").strip()[:120]
    t = re.sub(r'[\\/:*?"<>|]', "_", t)
    t = re.sub(r"\s+", "_", t).strip("._")
    return t or "video"


class RenderJob(BaseModel):
    mode: str  # "current" | "batch"
    count: Optional[int] = None
    output_dir: Optional[str] = None  # если нет вотермарки — каталог сохранения (абсолютный путь)
    save_folder: Optional[str] = None  # абсолютный путь ИЛИ имя подпапки Videos/…
    resolution: Optional[str] = None  # 1080p | 720p | 480p
    video_bitrate_mbps: Optional[int] = None  # 3…10
    video_bitrate_min_mbps: Optional[int] = None  # 1…20
    video_bitrate_max_mbps: Optional[int] = None  # 1…20
    fps: Optional[int] = None  # 15, 24, 30, 50, 60
    duration_min_sec: Optional[float] = None
    duration_max_sec: Optional[float] = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global MAIN_LOOP
    # WebSocket hub и рендер шлют сообщения через этот loop; при только lifespan без on_event
    # старый startup мог не выполниться — MAIN_LOOP оставался None и лог рендера терялся.
    MAIN_LOOP = asyncio.get_running_loop()
    # Не блокировать приём HTTP: импорт studio worker (tk / moviepy) может занять десятки секунд.
    threading.Thread(target=bridge.start, daemon=True, name="horoscope-studio-bridge").start()
    yield
    bridge.stop()


app = FastAPI(title="Politics Studio API", lifespan=lifespan)
MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self.clients.discard(ws)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        async with self._lock:
            clients = list(self.clients)
        for ws in clients:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self.clients.discard(ws)

    def broadcast_threadsafe(self, message: Dict[str, Any]) -> None:
        loop = MAIN_LOOP
        if loop is None:
            return

        async def _run() -> None:
            await self.broadcast(message)

        try:
            asyncio.run_coroutine_threadsafe(_run(), loop)
        except RuntimeError:
            return


hub = Hub()

_render_lock = threading.Lock()
_render_proc: Optional[subprocess.Popen] = None


def _preset_watermark_text() -> str:
    try:
        if SETTINGS_PATH.exists():
            d = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return str(d.get("watermark_text") or "").strip()
    except Exception:
        pass
    return ""


def build_render_cmd(job: RenderJob) -> list[str]:
    capcut = ROOT / "capcut_ui.py"
    if job.mode == "current":
        return [sys.executable, "-u", str(capcut), "--studio-headless-current"]
    cmd = [sys.executable, "-u", str(capcut), "--studio-headless-batch"]
    if job.count is not None:
        cmd.extend(["--count", str(int(job.count))])
    return cmd


def kill_process_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if platform.system() == "Windows":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=30,
            )
        else:
            proc.terminate()
            try:
                proc.wait(timeout=12)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def is_render_running() -> bool:
    with _render_lock:
        p = _render_proc
    return p is not None and p.poll() is None


def _decode_subprocess_line_bytes(raw: bytes) -> str:
    """Windows-консоль часто cp1251; Python может писать UTF-8. Не режем многобайтный UTF-8 по кускам read()."""
    if not raw:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1251", errors="replace")


def iter_subprocess_stdout_lines(raw_stream, bufsize: int = 8192) -> Iterator[str]:
    """Читает stdout потока: tqdm/MoviePy пишут прогресс через \\r без \\n — обычный for line их не отдаёт."""
    pending = b""
    while True:
        block = raw_stream.read(bufsize)
        if not block:
            break
        pending += block
        while True:
            ri = pending.find(b"\r")
            ni = pending.find(b"\n")
            if ri == -1 and ni == -1:
                break
            if ni != -1 and (ri == -1 or ni < ri):
                line_b = pending[:ni].rstrip(b"\r")
                pending = pending[ni + 1 :]
                line = _decode_subprocess_line_bytes(line_b)
                if line.strip():
                    yield line
            else:
                line_b = pending[:ri]
                pending = pending[ri + 1 :]
                line = _decode_subprocess_line_bytes(line_b)
                if line.strip():
                    yield line
    tail = pending.strip()
    if tail:
        yield _decode_subprocess_line_bytes(tail).rstrip("\r\n")


_SAFE_STUDIO_ASSET_EXT = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"})


@app.get("/api/studio-asset")
def studio_asset(path: str = "") -> Response:
    """Локальное изображение под корнем проекта — превью на таймлайне (path = абсолютный путь)."""
    raw = (unquote(path or "")).strip().strip('"')
    if not raw:
        return Response(status_code=400)
    try:
        p = Path(raw).expanduser()
        p = p.resolve()
    except Exception:
        return Response(status_code=400)
    try:
        p.relative_to(ROOT.resolve())
    except ValueError:
        return Response(status_code=403)
    if not p.is_file():
        return Response(status_code=404)
    suf = p.suffix.lower()
    if suf not in _SAFE_STUDIO_ASSET_EXT:
        return Response(status_code=400)
    mt = {".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}.get(suf, "image/jpeg")
    return FileResponse(str(p), media_type=mt)


@app.get("/api/render-thumb")
def render_thumb() -> Response:
    """PNG первого кадра текущего/последнего рендера (пишет capcut_ui при старте кодирования)."""
    if not RENDER_THUMB_PATH.is_file():
        return Response(status_code=404)
    return FileResponse(str(RENDER_THUMB_PATH), media_type="image/png")


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "root": str(ROOT),
        "studio_worker": bridge.ready,
        "studio_error": bridge.last_error,
    }


_FONT_EXTS = frozenset({".ttf", ".otf", ".ttc"})


def _font_family_style_from_filename(path: Path) -> tuple[str, str]:
    """
    Эвристика: выделяем family/style из имени файла.
    Пример: "Arial-BoldItalicMT" -> ("Arial", "Bold Italic MT")
    """
    stem = str(path.stem or "").strip()
    if not stem:
        return (path.name, "Regular")
    stem = re.sub(r"\s+", " ", stem)
    # Частый кейс у системных шрифтов: Family-Style
    if "-" in stem:
        family_raw, style_raw = stem.split("-", 1)
    else:
        family_raw, style_raw = stem, ""

    family = re.sub(r"[_]+", " ", family_raw).strip() or family_raw
    style_raw = re.sub(r"[_]+", " ", style_raw).strip()
    if style_raw:
        # Разбиваем CamelCase в style, чтобы "BoldItalic" => "Bold Italic"
        style = re.sub(r"([a-z])([A-Z])", r"\1 \2", style_raw).strip()
    else:
        style = "Regular"
    return (family, style)


@app.get("/api/system-fonts")
def system_fonts() -> Dict[str, Any]:
    """Список шрифтов для выпадающего списка в веб-UI: системные + fonts/ проекта."""
    items: list[Dict[str, str]] = []
    seen: set[str] = set()

    def push(path: Path, source: str, force_rel: bool = False, rel_value: str | None = None) -> None:
        if not path.is_file() or path.suffix.lower() not in _FONT_EXTS:
            return
        try:
            key = str(path.resolve())
        except Exception:
            key = str(path)
        if key.lower() in seen:
            return
        seen.add(key.lower())
        family, style = _font_family_style_from_filename(path)
        val = (str(rel_value or "").replace("\\", "/").strip() if force_rel else key) or key
        items.append({"path": val, "label": f"{family} — {style} [{source}]"})

    def scan_dir(d: Path, source: str, recursive: bool = False, force_rel: bool = False) -> None:
        if not d.is_dir():
            return
        it = d.rglob("*") if recursive else d.iterdir()
        for p in sorted(it, key=lambda x: x.name.lower()):
            if p.is_file() and p.suffix.lower() in _FONT_EXTS:
                push(p, source, force_rel=force_rel)

    custom = (os.environ.get("STUDIO_SYSTEM_FONTS_DIR") or "").strip()
    if custom:
        scan_dir(Path(custom).expanduser(), "Custom", recursive=True)
    else:
        sys_name = platform.system()
        if sys_name == "Darwin":
            scan_dir(Path("/System/Library/Fonts"), "macOS System", recursive=True)
            scan_dir(Path("/Library/Fonts"), "macOS Library", recursive=True)
            scan_dir(Path.home() / "Library" / "Fonts", "macOS User", recursive=True)
        elif sys_name == "Windows":
            win = os.environ.get("WINDIR", r"C:\Windows")
            scan_dir(Path(win) / "Fonts", "Windows", recursive=True)
        else:
            scan_dir(Path("/usr/share/fonts"), "Linux System", recursive=True)
            scan_dir(Path("/usr/local/share/fonts"), "Linux Local", recursive=True)
            scan_dir(Path.home() / ".local" / "share" / "fonts", "Linux User", recursive=True)

    proj_fonts = ROOT / "fonts"
    if proj_fonts.is_dir():
        for p in sorted(proj_fonts.iterdir(), key=lambda x: x.name.lower()):
            if p.is_file() and p.suffix.lower() in _FONT_EXTS:
                rel = Path("fonts") / p.name
                push(ROOT / rel, "Project", force_rel=True, rel_value=str(rel))

    items.sort(key=lambda x: x["label"].lower())
    return {"fonts": items}


@app.get("/api/settings")
def get_settings() -> Dict[str, Any]:
    """Полный пресет: дефолты из UiSettings + ui_settings.json; хештеги из hashtags.txt, если в JSON нет ключа."""
    base: Dict[str, Any] = {}
    try:
        from dataclasses import asdict

        from capcut_ui import UiSettings

        base = asdict(UiSettings())
    except Exception:
        pass
    disk_has_hashtags = False
    if SETTINGS_PATH.exists():
        try:
            disk = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(disk, dict):
                disk_has_hashtags = "hashtags_pool" in disk
                base.update(disk)
        except Exception:
            pass
    if not disk_has_hashtags and not (str(base.get("hashtags_pool") or "").strip()):
        hp = ROOT / "hashtags.txt"
        if hp.is_file():
            try:
                base["hashtags_pool"] = hp.read_text(encoding="utf-8")
            except Exception:
                pass
    return base


@app.post("/api/settings")
def save_settings(payload: Dict[str, Any]) -> Dict[str, str]:
    SETTINGS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "saved"}


@app.post("/api/render")
def start_render(job: RenderJob) -> Any:
    if job.mode not in ("current", "batch"):
        return JSONResponse({"status": "error", "error": "invalid mode"}, status_code=400)

    if is_render_running():
        return JSONResponse(
            {"status": "error", "error": "Рендер уже выполняется"},
            status_code=409,
        )

    wm = _preset_watermark_text()
    out_dir = (job.output_dir or "").strip() if job.output_dir else ""
    save_folder = (job.save_folder or "").strip() if job.save_folder else ""
    if not wm and not out_dir and not save_folder:
        return JSONResponse(
            {
                "status": "error",
                "error": "Укажите «Сохранить в папку» (путь или имя подпапки), либо текст вотермарки в пресете.",
            },
            status_code=400,
        )

    def run() -> None:
        global _render_proc
        env = os.environ.copy()
        temp_root = ROOT / "temp"
        temp_root.mkdir(parents=True, exist_ok=True)
        env["PYTHONUNBUFFERED"] = "1"
        # Вывод дочернего Python в UTF-8 + корректный разбор строк на Windows
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.setdefault("PYTHONUTF8", "1")
        env["TMP"] = str(temp_root)
        env["TEMP"] = str(temp_root)
        env["TMPDIR"] = str(temp_root)
        env.pop("STUDIO_OUTPUT_DIR", None)
        env.pop("STUDIO_VIDEOS_SUBFOLDER", None)
        env.pop("STUDIO_DURATION_MIN", None)
        env.pop("STUDIO_DURATION_MAX", None)
        env.pop("STUDIO_VIDEO_BITRATE_MIN_MBPS", None)
        env.pop("STUDIO_VIDEO_BITRATE_MAX_MBPS", None)
        if save_folder:
            p = Path(save_folder)
            if p.is_absolute() or (len(save_folder) > 1 and save_folder[1] == ":"):
                env["STUDIO_OUTPUT_DIR"] = str(p.expanduser().resolve())
            else:
                env["STUDIO_VIDEOS_SUBFOLDER"] = _sanitize_videos_subfolder(save_folder)
        elif not wm and out_dir:
            env["STUDIO_OUTPUT_DIR"] = out_dir

        prof = (job.resolution or "1080p").strip().lower()
        if prof in ("1080p", "720p", "480p"):
            env["STUDIO_EXPORT_PROFILE"] = prof
        if job.fps is not None:
            env["STUDIO_FPS"] = str(int(job.fps))
        if job.video_bitrate_mbps is not None:
            env["STUDIO_VIDEO_BITRATE_MBPS"] = str(max(1, min(20, int(job.video_bitrate_mbps))))
        if job.video_bitrate_min_mbps is not None and job.video_bitrate_max_mbps is not None:
            lo = max(1, min(20, int(job.video_bitrate_min_mbps)))
            hi = max(1, min(20, int(job.video_bitrate_max_mbps)))
            lo, hi = min(lo, hi), max(lo, hi)
            env["STUDIO_VIDEO_BITRATE_MIN_MBPS"] = str(lo)
            env["STUDIO_VIDEO_BITRATE_MAX_MBPS"] = str(hi)
        if job.duration_min_sec is not None and job.duration_max_sec is not None:
            try:
                lo = float(job.duration_min_sec)
                hi = float(job.duration_max_sec)
                lo, hi = min(lo, hi), max(lo, hi)
                lo = max(0.5, lo)
                hi = max(0.5, hi)
                env["STUDIO_DURATION_MIN"] = str(lo)
                env["STUDIO_DURATION_MAX"] = str(hi)
            except Exception:
                pass

        proc = subprocess.Popen(
            build_render_cmd(job),
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            bufsize=0,
            env=env,
        )
        with _render_lock:
            _render_proc = proc
        raw_out = proc.stdout
        assert raw_out is not None
        code = 1
        try:
            for line in iter_subprocess_stdout_lines(raw_out):
                hub.broadcast_threadsafe({"type": "log", "line": line})
            code = proc.wait()
        except Exception as ex:
            hub.broadcast_threadsafe({"type": "log", "line": f"[render] pipe: {ex}"})
            try:
                c = proc.poll()
                code = int(c) if c is not None else int(proc.wait(timeout=8))
            except Exception:
                code = -1
        finally:
            with _render_lock:
                if _render_proc is proc:
                    _render_proc = None
        hub.broadcast_threadsafe({"type": "done", "code": code})

    threading.Thread(target=run, daemon=True, name="horoscope-studio-render").start()
    return {"status": "started"}


@app.post("/api/render/cancel")
def cancel_render() -> Dict[str, Any]:
    with _render_lock:
        proc = _render_proc
    if proc is None or proc.poll() is not None:
        return {"status": "idle"}
    kill_process_tree(proc)
    return {"status": "cancelled"}


@app.post("/api/studio")
def studio_command(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    return bridge.request(dict(payload))


@app.post("/api/preview")
def preview_frame(payload: Dict[str, Any] = Body(...)) -> Response:
    body = dict(payload)
    body["cmd"] = "preview"
    want_meta = bool(body.pop("meta", False))
    body["meta"] = want_meta
    r = bridge.request(body)
    if not r.get("ok"):
        body = json.dumps(r, ensure_ascii=False).encode("utf-8")
        return Response(content=body, media_type="application/json", status_code=500)
    png_b64 = r.get("png")
    if not isinstance(png_b64, str):
        return Response(
            content=json.dumps({"ok": False, "error": "no png in worker response"}).encode("utf-8"),
            media_type="application/json",
            status_code=500,
        )
    if want_meta:
        out = {
            "ok": True,
            "png": png_b64,
            "hitboxes": r.get("hitboxes") or {},
        }
        # Воркер кладёт text_styles при _bg_snap_dirty (запомненный размер подложки) — без этого веб не получает bg_snap_* и подложка каждый раз пересчитывается по bbox текста.
        if r.get("text_styles") is not None:
            out["text_styles"] = r["text_styles"]
        return JSONResponse(out)
    raw = base64.standard_b64decode(png_b64.encode("ascii"))
    return Response(content=raw, media_type="image/png")


@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket) -> None:
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(ws)


@app.get("/", response_class=HTMLResponse)
def index_page() -> HTMLResponse:
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


app.mount("/assets", StaticFiles(directory=str(WEB_DIR)), name="assets")


def main() -> None:
    import uvicorn

    port = int(os.environ.get("STUDIO_PORT", "8787"))
    uvicorn.run("server.app:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    main()
