"""
Line-delimited JSON IPC worker: owns CapCutLikeUi(headless=True) in the process main thread.

Commands (one JSON object per line on stdin):
  {"cmd":"ping"}
  {"cmd":"shutdown"}
  {"cmd":"sync","settings":{...},"scene":{...}}
  {"cmd":"preview","settings":{...},"scene":{...},"t":0.5,"meta":true,"preview_max_w":640}  -> png base64 + hitboxes (координаты всегда 1080×1920; PNG может быть уже)
  {"cmd":"random_politician"} / {"cmd":"random_horoscope"}  — тема + 12 знаков
  {"cmd":"resummarize"}  — снова перемешать знаки в описании
  {"cmd":"generate_headline"}  — случайная тема как заголовок
  {"cmd":"merge_text_style","element":"title","style":{...}}
  {"cmd":"pick_font_file"}  -> {"ok":true,"path":"C:\\...\\font.ttf"} (диалог tk на машине с UI)
  {"cmd":"pick_file","title":"...","filetypes":[["Images","*.png *.jpg"]]}  -> путь к файлу
  {"cmd":"pick_folder","title":"..."}  -> путь к папке
  {"cmd":"save_preset_file","settings":{...}}  -> диалог «Сохранить» с initialdir presets/, {"ok":true,"path":"..."} или {"ok":false,"cancelled":true}

Responses: one JSON object per line on stdout.
"""

from __future__ import annotations

import asyncio
import base64
import copy
import io
import json
import sys
import traceback
from pathlib import Path

from PIL import Image

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def respond(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    from capcut_ui import CapCutLikeUi

    ui = CapCutLikeUi(headless=True)

    for line in sys.stdin:
        line = (line or "").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception as e:
            respond({"ok": False, "error": f"invalid json: {e}"})
            continue

        cmd = msg.get("cmd")
        try:
            if cmd == "ping":
                respond({"ok": True})
            elif cmd == "shutdown":
                respond({"ok": True})
                return 0
            elif cmd == "sync":
                settings = msg.get("settings")
                if isinstance(settings, dict) and settings:
                    ui.apply_settings_dict(settings, refresh=False)
                scene = msg.get("scene")
                if isinstance(scene, dict) and scene:
                    ui.apply_scene_dict(scene, refresh=False)
                respond({"ok": True})
            elif cmd == "preview":
                settings = msg.get("settings")
                if isinstance(settings, dict) and settings:
                    ui.apply_settings_dict(settings, refresh=False)
                scene = msg.get("scene")
                if isinstance(scene, dict) and scene:
                    ui.apply_scene_dict(scene, refresh=False)
                t = float(msg.get("t", ui.current_time))
                ui.current_time = max(0.0, min(t, ui.settings.duration_max))
                frame = ui.compose_preview_frame(ui.current_time)
                max_w = msg.get("preview_max_w")
                if isinstance(max_w, int) and max_w >= 320 and max_w < frame.width:
                    nh = max(1, int(round(frame.height * (max_w / float(frame.width)))))
                    resample = getattr(Image, "Resampling", Image).LANCZOS
                    frame = frame.resize((max_w, nh), resample)
                buf = io.BytesIO()
                frame.save(buf, format="PNG")
                out = {
                    "ok": True,
                    "png": base64.standard_b64encode(buf.getvalue()).decode("ascii"),
                }
                if msg.get("meta"):
                    hb = {}
                    for k, v in getattr(ui, "hitboxes_video", {}).items():
                        if isinstance(v, (tuple, list)) and len(v) == 4:
                            hb[k] = [int(x) for x in v]
                    out["hitboxes"] = hb
                    if getattr(ui, "_bg_snap_dirty", False):
                        try:
                            out["text_styles"] = copy.deepcopy(ui.settings.text_styles)
                        except Exception:
                            out["text_styles"] = dict(ui.settings.text_styles)
                        ui._bg_snap_dirty = False
                respond(out)
            elif cmd in ("random_politician", "random_hero", "random_horoscope"):
                ui.pick_random_horoscope()
                respond(
                    {
                        "ok": True,
                        "scene": {
                            "headline": ui.headline_var.get() if hasattr(ui, "headline_var") else "",
                            "hero": ui.hero_var.get(),
                            "bio": ui.bio_box.get("1.0", "end").strip(),
                            "dates": ui.dates_var.get(),
                            "image_path": ui.current_image_path,
                            "current_time": ui.current_time,
                        },
                    }
                )
            elif cmd == "resummarize":
                ui.resummarize()
                respond(
                    {
                        "ok": True,
                        "bio": ui.bio_box.get("1.0", "end").strip(),
                    }
                )
            elif cmd == "generate_headline":
                ui.generate_headline()
                respond(
                    {
                        "ok": True,
                        "headline": ui.headline_var.get() if hasattr(ui, "headline_var") else "",
                    }
                )
            elif cmd == "merge_text_style":
                element = str(msg.get("element") or "")
                updates = msg.get("style") or {}
                if not element:
                    respond({"ok": False, "error": "missing element"})
                else:
                    ui.merge_text_style(element, updates if isinstance(updates, dict) else {})
                    respond({"ok": True, "text_styles": ui.settings.text_styles})
            elif cmd == "pick_font_file":
                import tkinter as tk
                from tkinter import filedialog

                root = getattr(ui, "root", None)
                if root is None:
                    respond({"ok": False, "error": "no tk root"})
                else:
                    try:
                        root.lift()
                        root.attributes("-topmost", True)
                        root.update_idletasks()
                    except Exception:
                        pass
                    path = filedialog.askopenfilename(
                        parent=root,
                        title="Выберите файл шрифта",
                        filetypes=[("Шрифты", "*.ttf *.otf *.ttc"), ("Все файлы", "*.*")],
                    )
                    try:
                        root.attributes("-topmost", False)
                    except Exception:
                        pass
                    respond({"ok": True, "path": str(path or "").strip()})
            elif cmd in ("pick_file", "pick_folder"):
                from tkinter import filedialog

                root = getattr(ui, "root", None)
                if root is None:
                    respond({"ok": False, "error": "no tk root"})
                else:
                    try:
                        root.lift()
                        root.attributes("-topmost", True)
                        root.update_idletasks()
                    except Exception:
                        pass
                    title = str(msg.get("title") or ("Выберите папку" if cmd == "pick_folder" else "Выберите файл"))
                    try:
                        if cmd == "pick_folder":
                            path = filedialog.askdirectory(parent=root, title=title, mustexist=True)
                        else:
                            fts = msg.get("filetypes")
                            filetypes = [("Все файлы", "*.*")]
                            if isinstance(fts, list) and fts:
                                conv = []
                                for row in fts:
                                    if isinstance(row, (list, tuple)) and len(row) >= 2:
                                        conv.append((str(row[0]), str(row[1])))
                                if conv:
                                    filetypes = conv
                            path = filedialog.askopenfilename(parent=root, title=title, filetypes=filetypes)
                    finally:
                        try:
                            root.attributes("-topmost", False)
                        except Exception:
                            pass
                    respond({"ok": True, "path": str(path or "").strip()})
            elif cmd == "save_preset_file":
                settings = msg.get("settings")
                if not isinstance(settings, dict):
                    respond({"ok": False, "error": "settings dict required"})
                else:
                    from tkinter import filedialog

                    presets_dir = _ROOT / "presets"
                    presets_dir.mkdir(parents=True, exist_ok=True)
                    root = getattr(ui, "root", None)
                    if root is None:
                        respond({"ok": False, "error": "no tk root"})
                    else:
                        try:
                            root.lift()
                            root.attributes("-topmost", True)
                            root.update_idletasks()
                        except Exception:
                            pass
                        path = filedialog.asksaveasfilename(
                            parent=root,
                            title="Сохранить пресет в файл",
                            defaultextension=".json",
                            filetypes=[("JSON пресет", "*.json"), ("Все файлы", "*.*")],
                            initialdir=str(presets_dir),
                            initialfile="horoscope_studio_preset.json",
                        )
                        try:
                            root.attributes("-topmost", False)
                        except Exception:
                            pass
                        if not path:
                            respond({"ok": False, "cancelled": True, "error": "cancelled"})
                        else:
                            try:
                                Path(path).expanduser().write_text(
                                    json.dumps(settings, ensure_ascii=False, indent=2),
                                    encoding="utf-8",
                                )
                                respond({"ok": True, "path": str(path)})
                            except OSError as e:
                                respond({"ok": False, "error": str(e)})
            else:
                respond({"ok": False, "error": f"unknown cmd: {cmd!r}"})
        except Exception:
            respond({"ok": False, "error": traceback.format_exc()})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
