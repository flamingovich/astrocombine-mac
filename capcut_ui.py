import argparse
import asyncio
import hashlib
import json
import math
import os
import random
import re
import shutil
import sys
import textwrap
import tkinter as tk
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps, ImageTk

# Pillow 10+ убрал Image.ANTIALIAS; MoviePy 1.x в resize() всё ещё к нему обращается.
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.LANCZOS)

import numpy as np
from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    ImageSequenceClip,
    VideoClip,
    VideoFileClip,
    vfx,
)
from proglog.proglog import TqdmProgressBarLogger, troncate_string

from script import HoroscopeStudioCreator

_REPO_ROOT = Path(__file__).resolve().parent
_ZODIAC_SIGN_TO_EMOJI_STEM: dict[str, str] = {
    "ОВЕН": "oven",
    "ТЕЛЕЦ": "telec",
    "БЛИЗНЕЦЫ": "blizneci",
    "РАК": "rak",
    "ЛЕВ": "lev",
    "ДЕВА": "deva",
    "ВЕСЫ": "vesi",
    "СКОРПИОН": "skorpion",
    "СТРЕЛЕЦ": "strelec",
    "КОЗЕРОГ": "kozerog",
    "ВОДОЛЕЙ": "vodoley",
    "РЫБЫ": "ribi",
}

# -----------------------------------------------------------------------------
# Гороскоп-студия — Electron + web/. Этот файл — движок превью/рендера и
# опциональный legacy Tk UI; главный UX в web/.
# -----------------------------------------------------------------------------


class PipeFriendlyBarLogger(TqdmProgressBarLogger):
    """tqdm по умолчанию отключается без TTY; при рендере в pipe/WebSocket прогресс не шёл в UI."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("notebook", False)
        kwargs.setdefault("min_time_interval", 0.2)
        super().__init__(*args, **kwargs)

    def new_tqdm_bar(self, bar):
        if (bar in self.tqdm_bars) and (self.tqdm_bars[bar] is not None):
            self.close_tqdm_bar(bar)
        infos = self.bars[bar]
        self.tqdm_bars[bar] = self.tqdm(
            total=infos["total"],
            desc=infos["title"],
            postfix=dict(now=troncate_string(str(infos["message"]))),
            leave=self.leave_bars,
            file=sys.stdout,
            disable=False,
        )


def default_layer_frame_style():
    """Обводка и тень вокруг слоя (фото героя или карточка текста), как у рамки."""
    return {
        "stroke_enabled": False,
        "stroke_color": "#000000",
        "stroke_width": 3,
        # Внешняя / внутренняя обводка рамки (если stroke_outer_* не заданы — как stroke_enabled + stroke_width).
        "stroke_outer_enabled": None,
        "stroke_outer_width": None,
        "stroke_outer_color": None,
        "stroke_inner_enabled": False,
        "stroke_inner_width": 0,
        "stroke_inner_color": "#000000",
        "corner_radius": 12,
        "shadow_enabled": False,
        "shadow_color": "#000000",
        "shadow_opacity": 110,
        "shadow_blur": 10,
        "shadow_dx": 4,
        "shadow_dy": 4,
    }


def default_text_styles():
    base = {
        "use_gradient": False,
        "gradient_start": "#FFFFFF",
        "gradient_end": "#4AA3FF",
        "stroke_color": "#000000",
        "stroke_width": 2,
        # Внешняя / внутренняя обводка (если *_outer_* не заданы — берутся stroke_width / stroke_color).
        "stroke_outer_enabled": None,
        "stroke_outer_width": None,
        "stroke_outer_color": None,
        "stroke_inner_enabled": False,
        "stroke_inner_width": 0,
        "stroke_inner_color": "#000000",
        "shadow_enabled": False,
        "shadow_color": "#000000",
        "shadow_opacity": 120,
        "shadow_blur": 3,
        "shadow_dx": 2,
        "shadow_dy": 2,
        "bg_enabled": False,
        "bg_color": "#000000",
        "bg_colors": [],
        "bg_opacity": 80,
        "bg_padding_x": 12,
        "bg_padding_y": 8,
        "bg_corner_radius": 12,
        "bg_stroke_color": "#FFFFFF",
        "bg_stroke_width": 0,
        "bg_stroke_inside": True,
        "bg_stroke_outside": False,
        "bg_stroke_outer_enabled": None,
        "bg_stroke_outer_width": None,
        "bg_stroke_outer_color": None,
        "bg_stroke_inner_enabled": None,
        "bg_stroke_inner_width": None,
        "bg_stroke_inner_color": None,
        "bg_use_gradient": False,
        "bg_gradient_start": "#000000",
        "bg_gradient_end": "#333333",
        "bg_image": "",
        "text_fill_mode": "",
        "text_palette_colors": [],
        "text_alternate_pairs": [],
        "text_lighten_bases": [],
        # Подложка фиксированного размера (px внутри, до padding): не сжимается/не растёт при смене размера шрифта.
        "bg_use_fixed_inner_box": False,
        "bg_fixed_width": 0,
        "bg_fixed_height": 0,
        # True = подложка как раньше по bbox текста; False = запомнить размер (bg_snap_inner_*) при первом кадре, шрифт меняется отдельно.
        "bg_resizes_with_font": True,
        "bg_snap_inner_w": 0,
        "bg_snap_inner_h": 0,
    }
    return {
        "title": {**base, "use_gradient": True, "gradient_start": "#FFFFFF", "gradient_end": "#D6E5FF", "stroke_width": 3, "bg_resizes_with_font": False},
        "subtitle": {**base, "stroke_width": 0, "bg_enabled": False, "bg_resizes_with_font": False},
        "dates": {**base, "stroke_width": 0, "bg_enabled": False, "gradient_start": "#FFFFFF", "gradient_end": "#FFFFFF", "bg_resizes_with_font": False},
        "watermark": {**base, "stroke_width": 0, "shadow_enabled": False, "bg_enabled": False, "bg_resizes_with_font": False},
    }


def _bg_cap_corner_radius(rect, r):
    """Радиус скругления подложки, не больше половины меньшей стороны прямоугольника."""
    x0, y0, x1, y1 = rect
    w = max(0, int(x1) - int(x0))
    h = max(0, int(y1) - int(y0))
    if w < 2 or h < 2:
        return 0
    return max(0, min(int(r), w // 2, h // 2))


def default_output_name_parts() -> list:
    """Конструктор имени файла по умолчанию: префикс + заголовок + хештеги."""
    return [
        {"type": "prefix"},
        {"type": "literal", "value": " "},
        {"type": "headline"},
        {"type": "literal", "value": " "},
        {"type": "hashtags"},
    ]


def sanitize_watermark_folder(text: str) -> str:
    """Имя подпапки под `Videos/…` из текста вотермарки (безопасно для ФС)."""
    t = (text or "").strip()[:120]
    t = re.sub(r'[\\/:*?"<>|]', "_", t)
    t = re.sub(r"\s+", "_", t).strip("._")
    return t or "video"


def _ensure_spaces_before_hashtags_in_filename(name: str) -> str:
    """Пробел перед каждым #, если символ слева не пробел и не # (например …Иванович#тег → …Иванович #тег)."""
    return re.sub(r"(?<=[^\s#])#", " #", str(name or ""))


_RENDER_THUMB_PATH = Path(__file__).resolve().parent / ".studio_render_thumb.png"


@dataclass
class UiSettings:
    card_width: int = 1080
    card_height: int = 880
    photo_height: int = 450
    photo_width: int = 1080
    photo_offset_x: int = 0
    photo_offset_y: int = 0
    card_offset_x: int = 0
    card_offset_y: int = 0
    photo_frame: dict = field(default_factory=default_layer_frame_style)
    card_frame: dict = field(default_factory=default_layer_frame_style)
    title_font_size: int = 86
    # Нижняя граница при автоуменьшении заголовка по длине текста (px).
    title_font_size_min: int = 22
    hero_mirror_percent: int = 40  # 0–100: доля роликов с горизонтально зеркальным главным фото (детерминированно от пути и заголовка)
    subtitle_font_size: int = 54
    title_y: int = 90
    subtitle_y: int = 430
    title_x: int = 0
    subtitle_x: int = 0
    # 0 = ширина колонки заголовка как раньше (кадр минус 2×side_padding); иначе макс. ширина текста заголовка, px.
    title_wrap_width: int = 0
    # 0 = как раньше (кадр − 2×side_padding); иначе макс. ширина текста описания, px.
    subtitle_wrap_width: int = 0
    side_padding: int = 90
    title_color: str = "#FFFFFF"
    title_stroke: str = "#000000"
    subtitle_color: str = "#000000"
    card_bg: str = "#FFFFFF"
    # Доп. цвета/градиенты подложки карточки: при непустом списке при рендере выбирается случайная строка (как card_bg).
    card_bg_colors: list[str] = field(default_factory=list)
    card_bg_media: str = ""
    # Скрыть только GIF/видео/картинку под текстом карточки; текст и цвет/градиент card_bg остаются.
    card_bg_media_hidden: bool = False
    # Без цветной подложки и без медиа — только текст на прозрачном слое (виден общий фон кадра).
    card_backdrop_hidden: bool = False
    title_font: str = "fonts/impact.ttf"
    subtitle_font: str = "fonts/tahomabd.ttf"
    dates_font: str = "fonts/tahomabd.ttf"
    watermark_font: str = "fonts/tahomabd.ttf"
    subtitle_line_spacing: int = 10
    subtitle_max_words: int = 200
    # Минимум «слов» в описании для экспорта (12 знаков зодиака — 12 токенов при переносах строк).
    subtitle_min_words: int = 10
    duration_min: float = 6.5
    duration_max: float = 7.5
    photo_zoom_start: float = 1.0
    photo_zoom_end: float = 1.2
    # Ложь: фото без зума по времени (масштаб = photo_zoom_start на всём ролике).
    photo_animation_enabled: bool = True
    # Движение фото: zoom (зум от центра слота), slide_left / slide_right — горизонтальная панорама кропа.
    photo_anim_kind: str = "zoom"
    # При экспорте каждый раз случайный режим из zoom / slide_left / slide_right (поле photo_anim_kind — для превью и когда выкл.).
    photo_anim_random: bool = False
    # Минимальный запас кропа для слайда (px к ширине слота); вместе с zoom_start задаёт масштаб «с запасом».
    photo_slide_range_px: int = 120
    dates_font_size: int = 44
    dates_y: int = 270
    dates_x: int = 0
    dates_color: str = "#303030"
    watermark_text: str = ""
    watermark_font_size: int = 34
    watermark_color: str = "#FFFFFF"
    watermark_opacity: int = 80
    watermark_x: int = 40
    watermark_y: int = 1840
    video_output_dir: str = ""
    # Legacy: оверлей из _masked/effects больше не используется (оставлено для совместимости старых пресетов).
    effect_opacity: float = 0.10
    effect_hidden: bool = True
    # Анимированный блик/засвет (два мягких круга сверху и снизу), самый верхний слой «glow».
    glow_overlay_enabled: bool = True
    glow_overlay_opacity: float = 0.38
    # Пусто = мягкий голубой по умолчанию; несколько строк #RRGGBB — случайный цвет на ролик.
    glow_overlay_colors: list[str] = field(default_factory=list)
    force_caps: bool = False
    # По одной теме на строку; для ролика случайно выбирается одна строка как заголовок карточки.
    headline_topics: str = (
        "Топ знаков зодиака по богатству\n"
        "Кого ждёт удача на этой неделе\n"
        "Самые сильные знаки зодиака\n"
        "Рейтинг знаков по интуиции\n"
        "Кто из знаков блистает в любви"
    )
    # Пул хештегов для имени файла (каждая строка — отдельный тег). Пусто = как hashtags.txt.
    hashtags_pool: str = ""
    text_styles: dict = field(default_factory=default_text_styles)
    # Пользовательские блоки на кадре 9:16 (веб-редактор): {id, kind: text|image, x, y, ...}
    scene_overlays: list = field(default_factory=list)
    title_hidden: bool = False
    subtitle_hidden: bool = False
    dates_hidden: bool = False
    watermark_hidden: bool = False
    photo_hidden: bool = True
    card_hidden: bool = False
    # Имя выходного mp4: конструктор из блоков (output_name_parts) + пулы; output_name_template — запас для старых пресетов
    output_name_parts: list = field(default_factory=default_output_name_parts)
    output_name_template: str = "{prefix} [имя] {hashtags}"
    output_hashtag_count: int = 3
    output_name_emoji_pool: str = ""
    output_name_text_pool: str = ""
    output_name_prefix_pool: str = ""
    # Фон всего кадра 9:16 (за фото и карточкой)
    video_bg_mode: str = "folder"  # folder | flat | photo_blur
    video_bg_folder: str = "bg"
    # Цвет (#RRGGBB) или linear-gradient(180deg|to bottom, #a, #b) — для режима flat
    video_bg_spec: str = "#1a1f2a"
    # Путь к фото для режима «Фото+блюр» (если пусто — как раньше: scene.image_path / current_image_path).
    video_bg_photo_path: str = ""
    video_bg_photo_blur: float = 22.0
    video_bg_photo_brightness: float = 1.0
    # Режим «Папка»: плавный цикл случайного отрезка с кроссфейдом на стыке (только видео).
    video_bg_seamless_loop: bool = False
    video_bg_loop_crossfade_sec: float = 0.75
    # 0 = авто: L ≈ min(14, max(4, duration*0.35), длина_файла − 2*fade).
    video_bg_loop_segment_sec: float = 0.0
    # Слои: { "id", "start", "end", "z" } — id: background|glow|card|title|subtitle|dates|watermark|overlay:…
    timeline_layers: list = field(default_factory=list)


# Такой текст в поле описания не рендерим (пустой контент).
MISSING_BIO_PLACEHOLDER = "Текст описания отсутствует."


def _is_missing_bio_placeholder(text: str) -> bool:
    return (text or "").strip().casefold() == MISSING_BIO_PLACEHOLDER.casefold()


class CapCutLikeUi:
    def __init__(self, headless: bool = False):
        self.headless = bool(headless)
        self.root = tk.Tk()
        self.root.title("Гороскоп-студия")
        if self.headless:
            self.root.withdraw()
            self.root.overrideredirect(True)
            self.root.geometry("1x1+0+0")
        else:
            self.root.geometry("1760x1020")
            try:
                self.root.state("zoomed")
            except Exception:
                pass
            self.root.minsize(1400, 820)

        self.creator = HoroscopeStudioCreator()
        self.settings = UiSettings()
        self.settings_path = Path("ui_settings.json")
        self.load_settings()

        self.current_hero = ""
        self.current_bio = ""
        self.current_dates = ""
        self.current_image_path = ""
        self.selected_element = "card"  # слоя «фото» больше нет
        self.drag_start = None
        self.tk_preview = None
        self.preview_rect = (0, 0, 405, 720)
        self.hitboxes_video = {}
        self._preview_bg_cached = None  # str path or "" — один случайный bg на сессию, как ощущение «того же» ролика
        self._preview_folder_vc = None  # VideoFileClip для бесшовного превью (закрывается при смене ключа)
        self._preview_folder_vc_key = None
        self._preview_loop_L = 0.0
        self._preview_loop_fade = 0.0
        self._preview_loop_t0 = 0.0
        self._preview_loop_D = 0.001
        self._text_bg_random_pick_cache = {}  # случайный цвет подложки текста: фиксируется на одно видео
        self._text_bg_image_path_cache = {}  # папка подложки → выбранный файл (стабильно для _bg_random_key)
        self._text_style_render_nonce = "init"
        self._glow_color_pick: str | None = None  # цвет блика на ролик при непустой палитре
        self._bg_snap_dirty = False  # после записи bg_snap_* — отдать text_styles в meta превью (веб)
        self.current_time = 0.0
        self.is_playing = False
        self.last_seek_value = 0.0
        self._timeline_internal_update = False
        self.style_editor_window = None
        self._inspector_shown_for = None  # сброс левой панели «свойства элемента» при смене выбора / пресета

        self.icons = {}
        if self.headless:
            self.headless_init()
        else:
            self.init_ui_theme()
            self.init_icons()
            self.build_ui()
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)
            self.pick_random_horoscope()
            self.refresh_preview()

    def headless_init(self):
        # Minimal Tk widgets so methods like apply_controls()/refresh_preview() keep working,
        # while the main window stays hidden (used by Electron/local API wrapper).
        self.controls = {}
        for key in [
            "title_font_size",
            "title_font_size_min",
            "title_wrap_width",
            "subtitle_font_size",
            "subtitle_wrap_width",
            "title_y",
            "subtitle_y",
            "title_x",
            "subtitle_x",
            "dates_font_size",
            "dates_y",
            "dates_x",
            "side_padding",
            "subtitle_line_spacing",
            "subtitle_max_words",
            "subtitle_min_words",
            "duration_min",
            "duration_max",
            "glow_overlay_opacity",
            "watermark_font_size",
            "watermark_opacity",
            "watermark_x",
            "watermark_y",
        ]:
            self.controls[key] = tk.StringVar(value=str(getattr(self.settings, key)))

        self.hero_var = tk.StringVar()
        self.dates_var = tk.StringVar()
        self.force_caps_var = tk.BooleanVar(value=self.settings.force_caps)
        self.glow_overlay_enabled_var = tk.BooleanVar(value=bool(getattr(self.settings, "glow_overlay_enabled", True)))
        self.topics_box = tk.Text(self.root, height=1, width=1)
        self.topics_box.insert("1.0", self.settings.headline_topics)

        self.watermark_text_var = tk.StringVar(value=self.settings.watermark_text)
        self.watermark_color_var = tk.StringVar(value=self.settings.watermark_color)
        self.card_bg_media_var = tk.StringVar(value=self.settings.card_bg_media)
        self.batch_count_var = tk.StringVar(value="10")

        self.bio_box = tk.Text(self.root, height=1, width=1, wrap="word")

        self.canvas = tk.Canvas(self.root, width=405, height=720, bg="#0B0F16", highlightthickness=0)

        self.timeline_var = tk.DoubleVar(value=0.0)
        self.timeline = tk.Scale(self.root, from_=0.0, to=max(0.1, self.settings.duration_max), variable=self.timeline_var)
        self.time_label = tk.Label(self.root, text="")

        self.sync_controls_from_settings()
        self.watermark_text_var.set(self.settings.watermark_text)
        self.watermark_color_var.set(self.settings.watermark_color)
        self.card_bg_media_var.set(self.settings.card_bg_media)
        self.force_caps_var.set(self.settings.force_caps)
        self.glow_overlay_enabled_var.set(bool(getattr(self.settings, "glow_overlay_enabled", True)))
        self.topics_box.delete("1.0", "end")
        self.topics_box.insert("1.0", self.settings.headline_topics)

        self.headline_var = tk.StringVar()
        self.pick_random_horoscope()
        self.refresh_preview()

    def get_text_style(self, element):
        base = default_text_styles().get(element, default_text_styles()["subtitle"]).copy()
        if element not in self.settings.text_styles:
            self.settings.text_styles[element] = base.copy()
        else:
            cur = self.settings.text_styles[element]
            for k, v in base.items():
                if k not in cur:
                    cur[k] = v if not isinstance(v, dict) else v.copy()
        return self.settings.text_styles[element]

    def get_element_font_path(self, element):
        return {
            "title": self.settings.title_font,
            "subtitle": self.settings.subtitle_font,
            "dates": self.settings.dates_font,
            "watermark": self.settings.watermark_font,
        }.get(element, self.settings.subtitle_font)

    def set_element_font_path(self, element, path):
        if element == "title":
            self.settings.title_font = path
        elif element == "subtitle":
            self.settings.subtitle_font = path
        elif element == "dates":
            self.settings.dates_font = path
        elif element == "watermark":
            self.settings.watermark_font = path

    def init_ui_theme(self):
        style = ttk.Style()
        style.theme_use("clam")
        self.root.configure(bg="#0B0F16")
        style.configure("App.TFrame", background="#0B0F16")
        style.configure("Panel.TFrame", background="#121826")
        style.configure("Card.TFrame", background="#0F1523")
        style.configure("PanelTitle.TLabel", background="#121826", foreground="#E8EEF9", font=("Segoe UI Semibold", 10))
        style.configure("Section.TLabel", background="#121826", foreground="#9FB3CC", font=("Segoe UI", 8))
        style.configure("TLabel", background="#121826", foreground="#D5DFED", font=("Segoe UI", 9))
        style.configure("TEntry", fieldbackground="#0D1421", foreground="#E8EEF9", bordercolor="#2A3852", lightcolor="#2A3852", darkcolor="#2A3852", padding=6)
        style.configure("TButton", background="#1D2A44", foreground="#E8EEF9", bordercolor="#1D2A44", lightcolor="#1D2A44", darkcolor="#1D2A44", font=("Segoe UI Semibold", 9), padding=7)
        style.map("TButton", background=[("active", "#27395E"), ("pressed", "#18253C")])
        style.configure("Accent.TButton", background="#2563EB", foreground="#FFFFFF", bordercolor="#2563EB", lightcolor="#2563EB", darkcolor="#2563EB")
        style.map("Accent.TButton", background=[("active", "#1D4ED8"), ("pressed", "#1E40AF")])
        style.configure("TNotebook", background="#121826", borderwidth=0, tabmargins=[0, 0, 0, 0])
        style.configure("TNotebook.Tab", background="#0D1421", foreground="#9FB3CC", padding=(12, 8), font=("Segoe UI Semibold", 9))
        style.map("TNotebook.Tab", background=[("selected", "#1D2A44"), ("active", "#162237")], foreground=[("selected", "#F3F7FF"), ("active", "#DCE7F8")])
        style.configure("Horizontal.TScale", background="#121826", troughcolor="#0D1421")

    def make_icon(self, name, bg, fg="#FFFFFF"):
        img = Image.new("RGBA", (18, 18), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((1, 1, 17, 17), radius=4, fill=bg)
        if name == "random":
            d.line((4, 6, 14, 12), fill=fg, width=2)
            d.line((10, 6, 14, 6), fill=fg, width=2)
            d.line((14, 6, 14, 10), fill=fg, width=2)
        elif name == "text":
            d.line((4, 5, 14, 5), fill=fg, width=2)
            d.line((9, 5, 9, 13), fill=fg, width=2)
        elif name == "refresh":
            d.arc((4, 4, 14, 14), 30, 330, fill=fg, width=2)
            d.polygon((13, 4, 15, 8, 11, 8), fill=fg)
        elif name == "play":
            d.polygon((7, 5, 7, 13, 14, 9), fill=fg)
        elif name == "pause":
            d.rectangle((6, 5, 8, 13), fill=fg)
            d.rectangle((11, 5, 13, 13), fill=fg)
        elif name == "home":
            d.polygon((4, 9, 9, 4, 14, 9), outline=fg, fill=None, width=2)
            d.rectangle((6, 9, 12, 14), outline=fg, width=2)
        elif name == "render":
            d.rectangle((4, 4, 14, 14), outline=fg, width=2)
            d.polygon((8, 7, 8, 11, 12, 9), fill=fg)
        elif name == "batch":
            d.rectangle((3, 5, 9, 11), outline=fg, width=2)
            d.rectangle((9, 7, 15, 13), outline=fg, width=2)
        elif name == "save":
            d.rectangle((4, 4, 14, 14), outline=fg, width=2)
            d.rectangle((6, 5, 12, 8), fill=fg)
        elif name == "load":
            d.rectangle((4, 4, 14, 14), outline=fg, width=2)
            d.polygon((9, 6, 13, 10, 11, 10, 11, 13, 7, 13, 7, 10, 5, 10), fill=fg)
        return ImageTk.PhotoImage(img)

    def init_icons(self):
        self.icons = {
            "random": self.make_icon("random", "#2E7D32"),
            "text": self.make_icon("text", "#1565C0"),
            "refresh": self.make_icon("refresh", "#6A1B9A"),
            "play": self.make_icon("play", "#00897B"),
            "pause": self.make_icon("pause", "#00897B"),
            "home": self.make_icon("home", "#455A64"),
            "render": self.make_icon("render", "#EF6C00"),
            "batch": self.make_icon("batch", "#3949AB"),
            "save": self.make_icon("save", "#546E7A"),
            "load": self.make_icon("load", "#546E7A"),
        }

    def build_ui(self):
        topbar = ttk.Frame(self.root, style="Panel.TFrame", padding=(12, 8))
        topbar.pack(fill="x")
        ttk.Label(topbar, text="Гороскоп-студия", style="PanelTitle.TLabel").pack(side="left")
        ttk.Label(topbar, text="ПРОЕКТНЫЙ МОНТАЖ / VERTICAL 9:16", style="Section.TLabel").pack(side="left", padx=12)
        top_right = ttk.Frame(topbar, style="Panel.TFrame")
        top_right.pack(side="right")
        ttk.Button(
            top_right,
            text="Сохранить пресет",
            image=self.icons["save"],
            compound="left",
            command=self.save_preset_to_file,
        ).pack(side="right", padx=(10, 0))
        ttk.Button(
            top_right,
            text="Загрузить пресет",
            image=self.icons["load"],
            compound="left",
            command=self.load_preset_from_file,
        ).pack(side="right", padx=(10, 0))
        main = ttk.Frame(self.root, padding=10, style="App.TFrame")
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main, width=430, style="Panel.TFrame")
        left.pack(side="left", fill="y")

        center = ttk.Frame(main, style="App.TFrame")
        center.pack(side="left", fill="both", expand=True, padx=8)

        right_outer = ttk.Frame(main, width=360, style="Panel.TFrame")
        right_outer.pack(side="left", fill="y")
        right_outer.pack_propagate(False)

        right = ttk.Frame(right_outer, style="Panel.TFrame", padding=10)
        right.pack(fill="both", expand=True)

        ttk.Label(left, text="Сцена и контент", style="PanelTitle.TLabel").pack(anchor="w", pady=(6, 4), padx=10)
        ttk.Label(left, text="ЗАГОЛОВОК / ЗНАКИ ЗОДИАКА", style="Section.TLabel").pack(anchor="w", padx=10, pady=(0, 8))
        self.headline_var = tk.StringVar()
        self.hero_var = tk.StringVar()
        self.dates_var = tk.StringVar()
        self.bio_var = tk.StringVar()
        form = ttk.Frame(left, style="Card.TFrame", padding=10)
        form.pack(fill="x", padx=8)
        ttk.Label(form, text="Заголовок на карточке").pack(anchor="w")
        ttk.Entry(form, textvariable=self.headline_var, width=55).pack(fill="x", pady=(0, 6))
        ttk.Label(form, text="Метка (для файла, опционально)").pack(anchor="w")
        ttk.Entry(form, textvariable=self.hero_var, width=55).pack(fill="x", pady=(0, 6))
        ttk.Label(form, text="12 знаков в случайном порядке (описание)").pack(anchor="w")
        self.bio_box = tk.Text(
            left,
            height=10,
            wrap="word",
            bg="#0D1421",
            fg="#E8EEF9",
            insertbackground="#E8EEF9",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2A3852",
            highlightcolor="#3B82F6",
            padx=8,
            pady=8,
        )
        self.bio_box.pack(fill="x", padx=8, pady=(6, 0))

        btns = ttk.Frame(left, style="Panel.TFrame")
        btns.pack(fill="x", pady=10, padx=8)
        ttk.Button(btns, text="Случайный", image=self.icons["random"], compound="left", style="Accent.TButton", command=self.pick_random_horoscope).pack(side="left")
        ttk.Button(btns, text="Перемешать знаки", image=self.icons["text"], compound="left", command=self.shuffle_zodiac_description).pack(side="left", padx=6)
        ttk.Button(btns, text="Тема заголовка", image=self.icons["text"], compound="left", command=self.pick_topic_headline).pack(side="left", padx=0)
        ttk.Button(btns, text="Обновить", image=self.icons["refresh"], compound="left", command=self.refresh_preview).pack(side="left", padx=6)

        self.inspector_outer = ttk.LabelFrame(
            left, text="Свойства выбранного элемента", padding=(8, 6), style="Card.TFrame"
        )
        self.inspector_outer.pack(fill="x", padx=8, pady=(2, 6))
        self.inspector_container = ttk.Frame(self.inspector_outer, style="Panel.TFrame")
        self.inspector_container.pack(fill="x")

        self.canvas = tk.Canvas(center, width=700, height=780, bg="#0B0F16", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.on_click_canvas)
        self.canvas.bind("<Double-Button-1>", self.on_double_click_canvas)
        self.canvas.bind("<B1-Motion>", self.on_drag_canvas)
        self.canvas.bind("<MouseWheel>", self.on_wheel)
        self.canvas.bind("<Configure>", lambda _e: self.refresh_preview())

        timeline = ttk.Frame(center, style="Panel.TFrame", padding=8)
        timeline.pack(fill="x", pady=(8, 0))
        self.play_btn = ttk.Button(timeline, text="Пуск", image=self.icons["play"], compound="left", command=self.toggle_play)
        self.play_btn.pack(side="left")
        ttk.Button(timeline, text="В начало", image=self.icons["home"], compound="left", command=self.seek_start).pack(side="left", padx=6)
        self.time_label = ttk.Label(timeline, text=f"0.00 / {self.settings.duration_max:.2f} c")
        self.time_label.pack(side="right")
        self.timeline_var = tk.DoubleVar(value=0.0)
        self.timeline = ttk.Scale(
            timeline,
            from_=0.0,
            to=max(0.1, self.settings.duration_max),
            variable=self.timeline_var,
            command=self.on_timeline_change,
        )
        self.timeline.pack(side="left", fill="x", expand=True, padx=8)

        ttk.Label(right, text="Параметры проекта", style="PanelTitle.TLabel").pack(anchor="w", pady=(2, 2))
        ttk.Label(right, text="НАСТРОЙКИ ПО ВКЛАДКАМ", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        self.controls = {}
        notebook = ttk.Notebook(right)
        notebook.pack(fill="both", expand=True)

        tab_text = ttk.Frame(notebook, padding=10, style="Panel.TFrame")
        tab_prompts = ttk.Frame(notebook, padding=10, style="Panel.TFrame")
        tab_scene = ttk.Frame(notebook, padding=10, style="Panel.TFrame")
        tab_motion = ttk.Frame(notebook, padding=10, style="Panel.TFrame")
        tab_mark = ttk.Frame(notebook, padding=10, style="Panel.TFrame")
        tab_render = ttk.Frame(notebook, padding=10, style="Panel.TFrame")
        notebook.add(tab_text, text="Текст")
        notebook.add(tab_prompts, text="Темы")
        notebook.add(tab_scene, text="Сцена")
        notebook.add(tab_motion, text="Анимация")
        notebook.add(tab_mark, text="Вотермарка")
        notebook.add(tab_render, text="Рендер")

        for key, label, parent in [
            ("title_font_size", "Размер заголовка", tab_text),
            ("title_font_size_min", "Мин. размер заголовка (авто по длине)", tab_text),
            ("title_wrap_width", "Ширина колонки заголовка (0=авто)", tab_text),
            ("subtitle_font_size", "Размер описания", tab_text),
            ("subtitle_wrap_width", "Ширина колонки описания (0=авто)", tab_text),
            ("title_y", "Y заголовка", tab_text),
            ("title_x", "Сдвиг заголовка X (от центра)", tab_text),
            ("subtitle_y", "Y описания", tab_text),
            ("subtitle_x", "Сдвиг описания X (от центра)", tab_text),
            ("dates_font_size", "Размер дат", tab_text),
            ("dates_y", "Y дат", tab_text),
            ("dates_x", "Сдвиг дат X (от центра)", tab_text),
            ("side_padding", "Боковой отступ", tab_text),
            ("subtitle_line_spacing", "Межстрочный интервал", tab_text),
            ("subtitle_max_words", "Лимит слов описания", tab_text),
            ("subtitle_min_words", "Мин. слов в описании (для экспорта)", tab_text),
            ("duration_min", "Длительность ОТ (сек)", tab_motion),
            ("duration_max", "Длительность ДО (сек)", tab_motion),
            ("glow_overlay_opacity", "Непрозрачность блика / засвета (0–1)", tab_motion),
            ("watermark_font_size", "Размер вотермарки", tab_mark),
            ("watermark_opacity", "Прозрачность вотермарки (0-255)", tab_mark),
            ("watermark_x", "X вотермарки", tab_mark),
            ("watermark_y", "Y вотермарки", tab_mark),
        ]:
            ttk.Label(parent, text=label).pack(anchor="w")
            var = tk.StringVar(value=str(getattr(self.settings, key)))
            ttk.Entry(parent, textvariable=var, width=24).pack(anchor="w", pady=(0, 6), fill="x")
            self.controls[key] = var

        self.glow_overlay_enabled_var = tk.BooleanVar(value=bool(getattr(self.settings, "glow_overlay_enabled", True)))
        ttk.Checkbutton(
            tab_motion,
            text="Включить анимированный блик (сверху и снизу, самый верхний слой)",
            variable=self.glow_overlay_enabled_var,
        ).pack(anchor="w", pady=(4, 2))
        ttk.Label(
            tab_motion,
            text="Цвета блика (#RRGGBB, по строке; пусто = мягкий голубой; несколько — случайный цвет на ролик)",
        ).pack(anchor="w", pady=(8, 0))
        self.glow_colors_box = tk.Text(
            tab_motion, height=5, width=44, wrap="none", bg="#0D1421", fg="#E8EEF9", insertbackground="#E8EEF9", relief="flat"
        )
        self.glow_colors_box.pack(anchor="w", fill="x", pady=(2, 6))
        _gc = getattr(self.settings, "glow_overlay_colors", None) or []
        if isinstance(_gc, list) and _gc:
            self.glow_colors_box.insert("1.0", "\n".join(str(x).strip() for x in _gc if str(x).strip()))

        ttk.Button(tab_text, text="Шрифт заголовка", command=self.pick_title_font).pack(fill="x", pady=2)
        ttk.Button(tab_text, text="Шрифт описания", command=self.pick_subtitle_font).pack(fill="x", pady=2)
        self.force_caps_var = tk.BooleanVar(value=self.settings.force_caps)
        ttk.Checkbutton(tab_text, text="Текст только КАПСОМ", variable=self.force_caps_var).pack(anchor="w", pady=(6, 4))
        ttk.Label(
            tab_prompts,
            text="Темы для заголовков — по одной на строку; для ролика случайно берётся одна строка целиком.",
        ).pack(anchor="w", pady=(6, 0))
        self.topics_box = tk.Text(
            tab_prompts, height=14, wrap="word", bg="#0D1421", fg="#E8EEF9", insertbackground="#E8EEF9", relief="flat"
        )
        self.topics_box.pack(fill="both", expand=True, pady=(4, 6))
        self.topics_box.insert("1.0", self.settings.headline_topics)
        ttk.Label(tab_mark, text="Текст вотермарки").pack(anchor="w", pady=(6, 0))
        self.watermark_text_var = tk.StringVar(value=self.settings.watermark_text)
        ttk.Entry(tab_mark, textvariable=self.watermark_text_var, width=25).pack(anchor="w", pady=(0, 6), fill="x")
        ttk.Label(tab_mark, text="HEX цвет вотермарки (например #FFFFFF)").pack(anchor="w")
        self.watermark_color_var = tk.StringVar(value=self.settings.watermark_color)
        ttk.Entry(tab_mark, textvariable=self.watermark_color_var, width=25).pack(anchor="w", pady=(0, 6), fill="x")

        ttk.Label(tab_scene, text="Фон карточки (вместо белой подложки)", style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 6))
        self.card_bg_media_var = tk.StringVar(value=self.settings.card_bg_media)
        row_bg = ttk.Frame(tab_scene, style="Panel.TFrame")
        row_bg.pack(fill="x", pady=(0, 8))
        ttk.Entry(row_bg, textvariable=self.card_bg_media_var).pack(side="left", fill="x", expand=True)
        ttk.Button(
            row_bg,
            text="Файл",
            command=lambda: self.card_bg_media_var.set(
                filedialog.askopenfilename(
                    filetypes=[
                        ("Медиа", "*.mp4 *.mov *.avi *.mkv *.webm *.gif *.png *.jpg *.jpeg *.webp"),
                    ]
                )
                or self.card_bg_media_var.get()
            ),
        ).pack(side="right", padx=6)
        ttk.Button(row_bg, text="Очистить", command=lambda: self.card_bg_media_var.set("")).pack(side="right")

        ttk.Button(tab_render, text="Применить параметры", image=self.icons["refresh"], compound="left", style="Accent.TButton", command=self.apply_controls).pack(fill="x", pady=8)

        ttk.Separator(tab_render, orient="horizontal").pack(fill="x", pady=8)
        ttk.Label(tab_render, text="Генерация", style="PanelTitle.TLabel").pack(anchor="w")
        self.batch_count_var = tk.StringVar(value="10")
        ttk.Label(tab_render, text="Сколько видео").pack(anchor="w")
        ttk.Entry(tab_render, textvariable=self.batch_count_var, width=16).pack(anchor="w", pady=(0, 6))
        ttk.Button(tab_render, text="Текущее видео", image=self.icons["render"], compound="left", command=self.generate_current).pack(fill="x", pady=2)
        ttk.Button(tab_render, text="Массовая генерация", image=self.icons["batch"], compound="left", command=self.generate_batch).pack(fill="x", pady=2)

        ttk.Separator(tab_render, orient="horizontal").pack(fill="x", pady=8)
        ttk.Button(tab_render, text="Сохранить пресет", image=self.icons["save"], compound="left", command=self.save_settings).pack(fill="x", pady=2)
        ttk.Button(tab_render, text="Загрузить пресет", image=self.icons["load"], compound="left", command=self.load_settings_and_refresh).pack(fill="x", pady=2)

        help_text = (
            "Как редактировать:\n"
            "1) Кликни элемент в превью: карточка / заголовок / описание.\n"
            "2) Перетаскивай мышью.\n"
            "3) Колёсико мыши меняет размер выбранного элемента.\n"
            "4) Двойной клик по тексту открывает полный стиль.\n"
            "5) Палитра подложки и случайный фон карточки — в блоке «Свойства выбранного элемента» слева.\n"
            "6) Для точной настройки чисел используй поля справа."
        )
        ttk.Label(left, text=help_text, foreground="#8EA3BE", background="#121826").pack(anchor="w", pady=(10, 0), padx=10)

    def apply_controls(self):
        try:
            self.settings.title_font_size = int(self.controls["title_font_size"].get())
            self.settings.title_font_size_min = max(10, int(self.controls["title_font_size_min"].get()))
            self.settings.title_font_size_min = min(self.settings.title_font_size, self.settings.title_font_size_min)
            self.settings.title_wrap_width = max(0, int(self.controls["title_wrap_width"].get()))
            self.settings.subtitle_font_size = int(self.controls["subtitle_font_size"].get())
            self.settings.subtitle_wrap_width = max(0, int(self.controls["subtitle_wrap_width"].get()))
            self.settings.title_y = int(self.controls["title_y"].get())
            self.settings.title_x = int(self.controls["title_x"].get())
            self.settings.subtitle_y = int(self.controls["subtitle_y"].get())
            self.settings.subtitle_x = int(self.controls["subtitle_x"].get())
            self.settings.dates_font_size = int(self.controls["dates_font_size"].get())
            self.settings.dates_y = int(self.controls["dates_y"].get())
            self.settings.dates_x = int(self.controls["dates_x"].get())
            self.settings.side_padding = int(self.controls["side_padding"].get())
            self.settings.subtitle_line_spacing = int(self.controls["subtitle_line_spacing"].get())
            self.settings.subtitle_max_words = int(self.controls["subtitle_max_words"].get())
            if "subtitle_min_words" in self.controls:
                self.settings.subtitle_min_words = max(1, int(self.controls["subtitle_min_words"].get()))
            self.settings.duration_min = float(self.controls["duration_min"].get())
            self.settings.duration_max = float(self.controls["duration_max"].get())
            self.settings.watermark_font_size = int(self.controls["watermark_font_size"].get())
            self.settings.watermark_opacity = int(self.controls["watermark_opacity"].get())
            self.settings.watermark_x = int(self.controls["watermark_x"].get())
            self.settings.watermark_y = int(self.controls["watermark_y"].get())
            self.settings.glow_overlay_opacity = float(self.controls["glow_overlay_opacity"].get())
        except ValueError:
            if self.headless:
                print("[ERROR] Проверь числовые поля (ui_settings.json).")
            else:
                messagebox.showerror("Ошибка", "Проверь числовые поля справа.")
            return
        if self.settings.duration_max < self.settings.duration_min:
            self.settings.duration_max = self.settings.duration_min
        self.settings.watermark_text = self.watermark_text_var.get().strip()
        self.settings.watermark_color = self.watermark_color_var.get().strip() or "#FFFFFF"
        self.settings.watermark_opacity = max(0, min(255, self.settings.watermark_opacity))
        self.settings.glow_overlay_opacity = max(0.0, min(1.0, self.settings.glow_overlay_opacity))
        self.settings.glow_overlay_enabled = bool(self.glow_overlay_enabled_var.get())
        self.settings.card_bg_media = self.card_bg_media_var.get().strip()
        self.settings.force_caps = bool(self.force_caps_var.get())
        if hasattr(self, "topics_box"):
            tp = self.topics_box.get("1.0", "end").strip()
            self.settings.headline_topics = tp or UiSettings.__dataclass_fields__["headline_topics"].default
        if hasattr(self, "glow_colors_box"):
            graw = self.glow_colors_box.get("1.0", "end")
            self.settings.glow_overlay_colors = [ln.strip() for ln in graw.splitlines() if ln.strip()]
        self.timeline.configure(to=max(0.1, self.settings.duration_max))
        self.current_time = min(self.current_time, self.settings.duration_max)
        self._invalidate_element_inspector()
        self.refresh_preview()
        self.save_settings(show_message=False, apply_first=False)

    def pick_title_font(self):
        path = filedialog.askopenfilename(filetypes=[("Fonts", "*.ttf *.otf")])
        if path:
            self.settings.title_font = path
            self.refresh_preview()

    def pick_subtitle_font(self):
        path = filedialog.askopenfilename(filetypes=[("Fonts", "*.ttf *.otf")])
        if path:
            self.settings.subtitle_font = path
            self.refresh_preview()

    def pick_random_horoscope(self):
        self.apply_controls()
        hl = self.creator.pick_random_headline(self.settings.headline_topics)
        if not hl:
            msg = "Добавьте темы заголовков (вкладка «Темы»): по одной строке на тему."
            if self.headless:
                print(f"[ERROR] {msg}")
            else:
                messagebox.showerror("Ошибка", msg)
            return
        signs_txt = self.creator.build_zodiac_description()
        self.current_hero = "Гороскоп"
        self.current_bio = signs_txt
        self.current_dates = ""
        self.current_image_path = ""
        self.headline_var.set(self.transform_text_case(hl))
        self.hero_var.set(self.current_hero)
        self.dates_var.set(self.current_dates)
        self.bio_box.delete("1.0", "end")
        self.bio_box.insert("1.0", signs_txt)
        self.refresh_preview()

    def pick_random_politician(self):
        """Совместимость со старыми вызовами IPC/UI."""
        self.pick_random_horoscope()

    def extract_life_dates(self, hero_name, bio_text):
        self.creator.ensure_excel_cache()
        if getattr(self.creator, "df", None) is None:
            return ""
        dates = ""
        if self.creator.df is not None:
            row = self.creator.df[(self.creator.names_norm == self.creator.normalize_name(hero_name))]
            if row.empty:
                row = self.creator.df[(self.creator.names_norm == self.creator.format_lastname_first(hero_name))]
            if not row.empty:
                item = row.iloc[0]
                for c in self.creator.df.columns:
                    col = str(c).lower()
                    if "рожд" in col:
                        born = str(item[c]).strip()
                        if born and born != "nan":
                            dates = born
                    if "смерт" in col or "умер" in col:
                        died = str(item[c]).strip()
                        if died and died != "nan":
                            dates = f"{dates} - {died}" if dates else died
        if dates:
            return dates
        text = f"{bio_text}"
        years = re.findall(r"(?:19|20)\d{2}", text)
        if len(years) >= 2:
            return f"{years[0]} - {years[1]}"
        return ""

    def shuffle_zodiac_description(self):
        """Снова перемешать все 12 знаков в поле описания."""
        signs_txt = self.creator.build_zodiac_description()
        self.current_bio = signs_txt
        self.bio_box.delete("1.0", "end")
        self.bio_box.insert("1.0", signs_txt)
        self.refresh_preview()

    def resummarize(self):
        """Совместимость IPC: то же, что перемешать знаки."""
        self.shuffle_zodiac_description()

    def _count_subtitle_words(self, text):
        t = " ".join(str(text or "").split())
        if not t:
            return 0
        return len(t.split())

    def _subtitle_word_bounds(self):
        """Минимум/максимум слов в описании для экспорта (счёт по пробелам и переносам)."""
        lim = max(1, int(self.settings.subtitle_max_words))
        cfg_lo = int(getattr(self.settings, "subtitle_min_words", 10) or 10)
        lo = max(1, min(max(1, cfg_lo), lim))
        return lo, lim

    def normalize_subtitle(self, text):
        raw = str(text or "")
        pieces = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        line_chunks = [" ".join(piece.split()) for piece in pieces]
        while line_chunks and not line_chunks[0]:
            line_chunks.pop(0)
        while line_chunks and not line_chunks[-1]:
            line_chunks.pop()
        text = "\n".join(line_chunks)
        if not text:
            return ""
        words_flat = text.replace("\n", " ").split()
        lim = max(1, int(self.settings.subtitle_max_words))
        if len(words_flat) > lim:
            used = 0
            out_lines: list[str] = []
            for ln in line_chunks:
                wds = ln.split()
                if not wds:
                    continue
                if used + len(wds) <= lim:
                    out_lines.append(ln)
                    used += len(wds)
                    continue
                # Не добавляем обломок строки: иначе остаётся «12» и к точке превращается в «12.»
                break
            text = "\n".join(out_lines)
        if text and not re.search(r"[.!?]$", text):
            text = text.rstrip(",;:") + "."
        return text

    def transform_text_case(self, text):
        return text.upper() if self.settings.force_caps else text

    def pick_topic_headline(self):
        """Случайная тема из списка — как новый заголовок карточки."""
        self.apply_controls()
        line = self.creator.pick_random_headline(self.settings.headline_topics)
        if hasattr(self, "headline_var"):
            self.headline_var.set(self.transform_text_case(line) if line else "")
        self.refresh_preview()

    def generate_headline(self):
        """Совместимость IPC: случайная тема заголовка."""
        self.pick_topic_headline()

    def gradient_image(self, size, c1, c2):
        w, h = max(1, size[0]), max(1, size[1])
        img = Image.new("RGBA", (w, h))
        d = ImageDraw.Draw(img)
        try:
            r1, g1, b1 = ImageColor.getrgb(c1)
            r2, g2, b2 = ImageColor.getrgb(c2)
        except Exception:
            r1, g1, b1 = (255, 255, 255)
            r2, g2, b2 = (160, 200, 255)
        for y in range(h):
            t = y / max(1, h - 1)
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            d.line((0, y, w, y), fill=(r, g, b, 255))
        return img

    def _measure_text_line_width(self, text, font):
        """Ширина одной строки в пикселях (без переносов)."""
        if not text:
            return 0.0
        tmp = Image.new("L", (8, 8))
        dr = ImageDraw.Draw(tmp)
        try:
            return float(dr.textlength(text, font=font))
        except Exception:
            bb = dr.textbbox((0, 0), text, font=font)
            return float(bb[2] - bb[0])

    def _split_oversized_word(self, word: str, font, max_w: float) -> list[str]:
        """Разбивает одно слово на части, каждая не шире max_w."""
        if not word:
            return []
        if self._measure_text_line_width(word, font) <= max_w:
            return [word]
        out: list[str] = []
        buf = ""
        for ch in word:
            trial = buf + ch
            if self._measure_text_line_width(trial, font) <= max_w:
                buf = trial
            else:
                if buf:
                    out.append(buf)
                if self._measure_text_line_width(ch, font) <= max_w:
                    buf = ch
                else:
                    out.append(ch)
                    buf = ""
        if buf:
            out.append(buf)
        return out if out else [word[:1]]

    def _word_wrap_title_lines(self, text: str, font, max_w: float) -> list[str]:
        """Перенос по словам с измерением ширины; длинные слова режутся по символам."""
        words = text.split()
        if not words:
            return []
        lines: list[str] = []
        cur = ""
        for word in words:
            trial = word if not cur else f"{cur} {word}"
            if self._measure_text_line_width(trial, font) <= max_w:
                cur = trial
                continue
            if cur:
                lines.append(cur)
            if self._measure_text_line_width(word, font) <= max_w:
                cur = word
            else:
                parts = self._split_oversized_word(word, font, max_w)
                for p in parts[:-1]:
                    lines.append(p)
                cur = parts[-1] if parts else ""
        if cur:
            lines.append(cur)
        return lines

    def _split_single_string_two_lines(self, s: str, font, max_w: float) -> tuple[str, str] | None:
        """Две непустые строки из одного блока текста; обе не шире max_w. Ищем разрез с наименьшим дисбалансом ширин."""
        if not s:
            return None
        if len(s) == 1:
            return (s, "\u200b")
        best: tuple[str, str] | None = None
        best_key: tuple | None = None
        for i in range(1, len(s)):
            a = s[:i].rstrip()
            b = s[i:].lstrip()
            if not a or not b:
                continue
            wa = self._measure_text_line_width(a, font)
            wb = self._measure_text_line_width(b, font)
            if wa <= max_w and wb <= max_w:
                key = (abs(wa - wb), max(wa, wb))
                if best is None or key < best_key:
                    best = (a, b)
                    best_key = key
        return best

    def _split_title_into_two_lines_word_safe(self, s: str, font, max_w: float) -> tuple[str, str] | None:
        """Две строки без разрыва слова между строками: перенос по словам; при >2 строках — первая + остаток, если влезает."""
        s = " ".join((s or "").replace("\n", " ").replace("\r", " ").split())
        if not s:
            return (" ", " ")
        lines = self._word_wrap_title_lines(s, font, max_w)
        if not lines:
            return (" ", " ")
        if len(lines) == 1:
            return (lines[0], "\u200b")
        if len(lines) == 2:
            return (lines[0], lines[1])
        rest = " ".join(lines[1:])
        if self._measure_text_line_width(rest, font) <= max_w:
            return (lines[0], rest)
        return None

    def _split_title_exactly_two_lines(self, text: str, font, max_w: float) -> tuple[str, str] | None:
        """Ровно две строки заголовка: сначала по границам слов, иначе перенос по словам (без разреза слова посередине)."""
        s = " ".join((text or "").replace("\n", " ").replace("\r", " ").split())
        if not s:
            return (" ", " ")
        words = s.split()
        if len(words) >= 2:
            candidates: list[tuple[float, float, str, str]] = []
            for k in range(1, len(words)):
                a = " ".join(words[:k])
                b = " ".join(words[k:])
                wa = self._measure_text_line_width(a, font)
                wb = self._measure_text_line_width(b, font)
                if wa <= max_w and wb <= max_w:
                    candidates.append((abs(wa - wb), max(wa, wb), a, b))
            if candidates:
                candidates.sort(key=lambda t: (t[0], t[1]))
                return (candidates[0][2], candidates[0][3])
        return self._split_title_into_two_lines_word_safe(s, font, max_w)

    def _hero_photo_mirror_horizontal(self, image_path: str, headline: str) -> bool:
        """Горизонтальное зеркало главного фото: стабильно от пути и заголовка (~40% «да»)."""
        try:
            key = f"{Path(str(image_path)).resolve()}\n{(headline or '').strip()}".encode("utf-8", errors="replace")
        except Exception:
            key = f"{image_path}\n{(headline or '').strip()}".encode("utf-8", errors="replace")
        v = int.from_bytes(hashlib.sha256(key).digest()[:4], "big") % 100
        chance = int(getattr(self.settings, "hero_mirror_percent", 40) or 40)
        chance = max(0, min(100, chance))
        return v < chance

    def _hero_cover_random_crop_rgba(self, img: Image.Image, pw: int, ph: int, rng: random.Random) -> Image.Image:
        """Масштаб «cover» + случайное окно pw×ph в центральной полосе (лёгкий кроп, без сильного сдвига)."""
        img = img.convert("RGBA")
        iw, ih = img.size
        if iw < 2 or ih < 2:
            return img.resize((max(1, pw), max(1, ph)), Image.LANCZOS)
        base = max(pw / float(iw), ph / float(ih))
        extra = rng.uniform(0.02, 0.055)
        scale = base * (1.0 + extra)
        nw = max(pw, int(round(iw * scale)))
        nh = max(ph, int(round(ih * scale)))
        resized = img.resize((nw, nh), Image.LANCZOS)
        ml, mt = nw - pw, nh - ph
        if ml <= 0 and mt <= 0:
            return resized.resize((pw, ph), Image.LANCZOS)
        lo_x, hi_x = (int(ml * 0.22), int(ml * 0.78)) if ml > 0 else (0, 0)
        lo_y, hi_y = (int(mt * 0.22), int(mt * 0.78)) if mt > 0 else (0, 0)
        if ml > 0 and lo_x >= hi_x:
            lo_x, hi_x = 0, ml
        if mt > 0 and lo_y >= hi_y:
            lo_y, hi_y = 0, mt
        lx = rng.randint(lo_x, hi_x) if ml > 0 else 0
        ty = rng.randint(lo_y, hi_y) if mt > 0 else 0
        return resized.crop((lx, ty, lx + pw, ty + ph))

    def _photo_anim_kind_norm(self) -> str:
        ov = getattr(self, "_photo_anim_kind_override", None)
        if isinstance(ov, str) and ov.strip():
            kk = ov.strip().lower()
            if kk in ("zoom", "slide_left", "slide_right"):
                return kk
        k = str(getattr(self.settings, "photo_anim_kind", "zoom") or "zoom").strip().lower()
        if k in ("zoom", "slide_left", "slide_right"):
            return k
        return "zoom"

    def _compose_hero_slot_cropped_rgba(
        self,
        hero_src: Image.Image,
        pw: int,
        ph: int,
        t: float,
        dur: float,
        title_line: str,
        image_path: str,
        *,
        anim_time0: float = 0.0,
    ) -> Image.Image:
        """Масштаб слота + кроп ровно pw×ph: зум от центра или горизонтальный слайд (кроп движется по увеличенному кадру)."""
        _ = image_path  # зарезервировано для будущей детерминированной логики
        kind = self._photo_anim_kind_norm()
        dur_eff = max(0.001, float(dur))
        progress = max(0.0, min(1.0, (float(anim_time0) + float(t)) / dur_eff))
        zoom_start = max(1.0, float(getattr(self.settings, "photo_zoom_start", 1.0) or 1.0))
        zoom_end = max(zoom_start, float(getattr(self.settings, "photo_zoom_end", 1.2) or 1.2))
        rng_px = max(0, int(getattr(self.settings, "photo_slide_range_px", 120) or 120))
        anim_on = bool(getattr(self.settings, "photo_animation_enabled", True))

        if anim_on and kind in ("slide_left", "slide_right"):
            need = (float(pw) + float(rng_px)) / float(max(1, pw))
            zoom = max(zoom_start, need)
        elif anim_on and kind == "zoom":
            zoom = zoom_start + (zoom_end - zoom_start) * progress
        else:
            zoom = zoom_start

        zoom = max(1.0, float(zoom))
        scaled_w = max(pw, int(round(pw * zoom)))
        scaled_h = max(ph, int(round(ph * zoom)))
        im = hero_src.convert("RGBA").resize((scaled_w, scaled_h), Image.LANCZOS)
        ml = max(0, scaled_w - pw)
        mt = max(0, scaled_h - ph)

        if anim_on and kind in ("slide_left", "slide_right"):
            pan = int(round(progress * ml)) if ml else 0
            left = (ml - pan) if kind == "slide_left" else pan
            top = mt // 2
        else:
            left, top = ml // 2, mt // 2

        return im.crop((left, top, left + pw, top + ph))

    def _title_multiline_height(
        self, text: str, font, anchor_x: int, anchor_y: int, spacing: int = 5
    ) -> int:
        """Высота блока многострочного заголовка в тех же условиях, что draw_styled_text (anchor ma)."""
        if not (text or "").strip():
            return 0
        wimg = max(1200, anchor_x + 600, 1080)
        himg = max(1600, anchor_y + 900, 1920)
        tmp = Image.new("RGBA", (wimg, himg), (0, 0, 0, 0))
        dr = ImageDraw.Draw(tmp)
        bbox = dr.multiline_textbbox((anchor_x, anchor_y), text, font=font, anchor="ma", align="center", spacing=spacing)
        return max(0, int(bbox[3] - bbox[1] + 1))

    def _layout_card_photo_vertical(self, vh, ph, ch):
        """Вертикаль карточки не привязана к живой высоте фото; фото поджимается под карточку."""
        REF_PH = 450
        gap = 8
        card_y = int((vh + REF_PH - ch) // 2 + self.settings.card_offset_y)
        card_y = max(0, min(vh - ch - 20, card_y))
        ph_slot = max(int(self.settings.photo_height), ph)
        start_y_photo = (vh - (ph_slot + ch)) // 2
        py_pref = int(start_y_photo + self.settings.photo_offset_y)
        py_max = int(card_y - gap - ph)
        if py_max >= 0:
            py = max(0, min(py_pref, py_max))
        else:
            py = max(0, min(py_pref, vh - ph - 40))
        return card_y, py

    def _layout_card_center_vertical(self, vh: int, ch: int) -> int:
        """Карточка по центру кадра 9:16 (без слота фото)."""
        card_y = int((vh - ch) / 2 + self.settings.card_offset_y)
        return max(0, min(vh - ch - 20, card_y))

    @staticmethod
    def _alpha_composite_text_stroke_ring(canvas_img, fill_mask, width_px, rgb, outer=True):
        """Кольцо обводки по маске заливки: outer = dilate−fill, inner = fill−erode (без multiline_text stroke_width)."""
        if width_px <= 0:
            return
        fb = fill_mask.getbbox()
        if not fb:
            return
        rx0, ry0, rx1, ry1 = fb
        pad = int(width_px) + 10
        cw_i, ch_i = canvas_img.size
        cx0 = max(0, rx0 - pad)
        cy0 = max(0, ry0 - pad)
        cx1 = min(cw_i, rx1 + pad)
        cy1 = min(ch_i, ry1 + pad)
        sub_w, sub_h = cx1 - cx0, cy1 - cy0
        if sub_w <= 0 or sub_h <= 0:
            return
        sub_fill = fill_mask.crop((cx0, cy0, cx1, cy1))
        k = min(max(3, 2 * int(width_px) + 1), 101)
        if k % 2 == 0:
            k += 1
        if outer:
            morphed = sub_fill.filter(ImageFilter.MaxFilter(size=k))
            ring_sub = ImageChops.subtract(morphed, sub_fill)
        else:
            morphed = sub_fill.filter(ImageFilter.MinFilter(size=k))
            ring_sub = ImageChops.subtract(sub_fill, morphed)
        stroke_rgba = Image.new("RGBA", (cw_i, ch_i), (0, 0, 0, 0))
        patch = Image.new("RGBA", (sub_w, sub_h), (0, 0, 0, 0))
        solid_st = Image.new("RGBA", (sub_w, sub_h), (rgb[0], rgb[1], rgb[2], 255))
        patch.paste(solid_st, (0, 0), ring_sub)
        stroke_rgba.paste(patch, (cx0, cy0))
        canvas_img.alpha_composite(stroke_rgba)

    def _persist_bg_snap_inner(self, sw: int, sh: int, element: str | None, overlay_item: dict | None) -> None:
        sw = max(1, int(sw))
        sh = max(1, int(sh))
        if element and element in ("title", "subtitle", "dates", "watermark"):
            self.get_text_style(element)
            self.settings.text_styles[element]["bg_snap_inner_w"] = sw
            self.settings.text_styles[element]["bg_snap_inner_h"] = sh
        elif isinstance(overlay_item, dict):
            st = overlay_item.setdefault("style", {})
            if not isinstance(st, dict):
                st = {}
                overlay_item["style"] = st
            st["bg_snap_inner_w"] = sw
            st["bg_snap_inner_h"] = sh
        self._bg_snap_dirty = True

    def draw_styled_text(
        self,
        canvas_img,
        text,
        x,
        y,
        font,
        style,
        align="center",
        anchor="ma",
        spacing=6,
        *,
        persist_style_element: str | None = None,
        persist_overlay_item: dict | None = None,
    ):
        draw = ImageDraw.Draw(canvas_img)
        try:
            bbox = draw.multiline_textbbox((x, y), text, font=font, anchor=anchor, align=align, spacing=spacing)
        except AttributeError:
            tw, th = draw.multiline_textsize(text, font=font, spacing=spacing)
            bbox = (x - tw // 2, y, x + tw // 2, y + th)

        tx0, ty0, tx1, ty1 = [int(v) for v in bbox]
        bbox = (tx0, ty0, tx1, ty1)
        # Background (внутренний прямоугольник bx* — не обязан совпадать с bbox текста, если подложка «отвязана» от шрифта)
        if style.get("bg_enabled"):
            pad_x = int(style.get("bg_padding_x", 12))
            pad_y = int(style.get("bg_padding_y", 8))
            # Подложка включена — размер подложки не следует за шрифтом (только текст меняется).
            resizes = False
            bg_img_path = self._resolve_style_bg_image_file(style)
            use_manual = bool(style.get("bg_use_fixed_inner_box")) and int(style.get("bg_fixed_width") or 0) > 0 and int(style.get("bg_fixed_height") or 0) > 0
            if use_manual:
                fw = int(style["bg_fixed_width"])
                fh = int(style["bg_fixed_height"])
                cx = (tx0 + tx1) * 0.5
                cy = (ty0 + ty1) * 0.5
                bx0 = int(round(cx - fw / 2.0))
                bx1 = int(round(cx + fw / 2.0))
                by0 = int(round(cy - fh / 2.0))
                by1 = int(round(cy + fh / 2.0))
                pad_top = pad_y
                pad_bot = pad_y
            elif not resizes:
                tw = max(1, tx1 - tx0)
                th = max(1, ty1 - ty0)
                # Цвет / градиент / картинка: внутренний размер из bg_snap_* (после первого кадра не тянется за шрифтом). Snap уходит в meta превью — server/app.py.
                sw = int(style.get("bg_snap_inner_w") or 0)
                sh = int(style.get("bg_snap_inner_h") or 0)
                if sw <= 0 or sh <= 0:
                    sw, sh = tw, th
                    self._persist_bg_snap_inner(sw, sh, persist_style_element, persist_overlay_item)
                cx = (tx0 + tx1) * 0.5
                cy = (ty0 + ty1) * 0.5
                bx0 = int(round(cx - sw / 2.0))
                bx1 = int(round(cx + sw / 2.0))
                by0 = int(round(cy - sh / 2.0))
                by1 = int(round(cy + sh / 2.0))
                pad_top = pad_y
                pad_bot = pad_y
            else:
                bx0, by0, bx1, by1 = tx0, ty0, tx1, ty1
                nlines_bg = max(1, len(text.splitlines())) if (text or "").strip() else 1
                sp_i = max(0, int(spacing))
                inter_extra = max(0, nlines_bg - 1) * sp_i // 2
                pad_top = pad_y + inter_extra // 2
                pad_bot = pad_y + (inter_extra - inter_extra // 2)
            bg_rect = (bx0 - pad_x, by0 - pad_top, bx1 + pad_x, by1 + pad_bot)
            bg_layer = Image.new("RGBA", canvas_img.size, (0, 0, 0, 0))
            bg_draw = ImageDraw.Draw(bg_layer)
            bg_cr = max(0, int(style.get("bg_corner_radius", 12) or 0))
            r_in = _bg_cap_corner_radius(bg_rect, bg_cr)

            bg_new = (
                style.get("bg_stroke_outer_enabled") is not None
                or style.get("bg_stroke_outer_width") is not None
                or style.get("bg_stroke_outer_color") is not None
                or style.get("bg_stroke_inner_enabled") is not None
                or style.get("bg_stroke_inner_width") is not None
                or style.get("bg_stroke_inner_color") is not None
            )
            if not bg_new:
                bg_sw = int(style.get("bg_stroke_width", 0))
                ins = bool(style.get("bg_stroke_inside", True))
                out = bool(style.get("bg_stroke_outside", False))
                if bg_sw > 0 and not ins and not out:
                    ins = True
                s_rgb = None
                if bg_sw > 0:
                    try:
                        s_rgb = ImageColor.getrgb(style.get("bg_stroke_color", "#FFFFFF"))
                    except Exception:
                        s_rgb = (255, 255, 255)
                out_on = bg_sw > 0 and out and s_rgb
                in_on = bg_sw > 0 and ins and s_rgb
                out_rgb = in_rgb = s_rgb
                out_px = max(0, int(bg_sw)) if out_on else 0
                in_px = max(0, int(bg_sw)) if in_on else 0
            else:
                ow_raw = style.get("bg_stroke_outer_width")
                if ow_raw is None:
                    ow = max(0, int(style.get("bg_stroke_width", 0) or 0)) if bool(style.get("bg_stroke_outside", False)) else 0
                else:
                    ow = max(0, int(ow_raw))
                o_en = style.get("bg_stroke_outer_enabled")
                if o_en is None:
                    out_on = ow > 0 and bool(style.get("bg_stroke_outside", False))
                else:
                    out_on = bool(o_en) and ow > 0
                try:
                    out_rgb = ImageColor.getrgb(style.get("bg_stroke_outer_color") or style.get("bg_stroke_color", "#FFFFFF"))
                except Exception:
                    out_rgb = (255, 255, 255)

                iw_raw = style.get("bg_stroke_inner_width")
                if iw_raw is None:
                    iw = max(0, int(style.get("bg_stroke_width", 0) or 0)) if bool(style.get("bg_stroke_inside", True)) else 0
                else:
                    iw = max(0, int(iw_raw))
                i_en = style.get("bg_stroke_inner_enabled")
                if i_en is None:
                    in_on = iw > 0 and bool(style.get("bg_stroke_inside", True))
                else:
                    in_on = bool(i_en) and iw > 0
                try:
                    in_rgb = ImageColor.getrgb(style.get("bg_stroke_inner_color") or style.get("bg_stroke_color", "#FFFFFF"))
                except Exception:
                    in_rgb = (255, 255, 255)
                out_px = max(0, int(ow)) if out_on else 0
                in_px = max(0, int(iw)) if in_on else 0

            # Файл/папка подложки — главное только изображение; не смешивать с цветом/градиентом/обводками подложки.
            if bg_img_path:
                out_on = False
                in_on = False
                out_px = 0
                in_px = 0

            if out_on and out_rgb is not None and out_px > 0:
                bx0, by0, bx1, by1 = bg_rect
                big = (bx0 - out_px, by0 - out_px, bx1 + out_px, by1 + out_px)
                r_big = _bg_cap_corner_radius(big, bg_cr + out_px)
                bg_draw.rounded_rectangle(big, radius=r_big, fill=(out_rgb[0], out_rgb[1], out_rgb[2], 255))

            if bg_img_path:
                bw = max(1, int(bg_rect[2]) - int(bg_rect[0]))
                bh = max(1, int(bg_rect[3]) - int(bg_rect[1]))
                _rs = getattr(Image, "Resampling", Image).LANCZOS
                try:
                    with Image.open(bg_img_path) as im0:
                        if getattr(im0, "n_frames", 1) > 1:
                            try:
                                im0.seek(0)
                            except Exception:
                                pass
                        tex = im0.convert("RGBA").resize((bw, bh), _rs)
                    mask = Image.new("L", tex.size, 0)
                    rr_m = max(0, int(r_in))
                    ImageDraw.Draw(mask).rounded_rectangle((0, 0, tex.size[0], tex.size[1]), radius=rr_m, fill=255)
                    bg_layer.paste(tex, (int(bg_rect[0]), int(bg_rect[1])), mask)
                except Exception:
                    alpha = max(0, min(255, int(style.get("bg_opacity", 80))))
                    try:
                        bg_rgb = ImageColor.getrgb(self._resolve_text_bg_color(style))
                    except Exception:
                        bg_rgb = (32, 36, 44)
                    bg_draw.rounded_rectangle(bg_rect, radius=max(0, int(r_in)), fill=(bg_rgb[0], bg_rgb[1], bg_rgb[2], alpha))
            else:
                alpha = max(0, min(255, int(style.get("bg_opacity", 80))))
                if style.get("bg_use_gradient"):
                    grad = self.gradient_image((bg_rect[2] - bg_rect[0], bg_rect[3] - bg_rect[1]), style.get("bg_gradient_start", "#000000"), style.get("bg_gradient_end", "#333333"))
                    alpha_mask = Image.new("L", grad.size, 0)
                    ImageDraw.Draw(alpha_mask).rounded_rectangle((0, 0, grad.size[0], grad.size[1]), radius=max(0, int(r_in)), fill=alpha)
                    bg_layer.paste(grad, (bg_rect[0], bg_rect[1]), alpha_mask)
                else:
                    try:
                        bg_rgb = ImageColor.getrgb(self._resolve_text_bg_color(style))
                    except Exception:
                        bg_rgb = (0, 0, 0)
                    bg_draw.rounded_rectangle(bg_rect, radius=max(0, int(r_in)), fill=(bg_rgb[0], bg_rgb[1], bg_rgb[2], alpha))

            if in_on and in_rgb is not None and in_px > 0:
                bg_draw.rounded_rectangle(bg_rect, radius=max(0, int(r_in)), outline=(in_rgb[0], in_rgb[1], in_rgb[2], 255), width=in_px)
            canvas_img.alpha_composite(bg_layer)
            # Превью/хитбоксы используют возвращаемый bbox — включить подложку (и внешнюю обводку), иначе
            # клики по картинке при фиксированном блоке попадают мимо и блок нельзя тащить/ресайзить.
            hx0, hy0, hx1, hy1 = int(bg_rect[0]), int(bg_rect[1]), int(bg_rect[2]), int(bg_rect[3])
            if out_on and out_rgb is not None and out_px > 0:
                hx0 = int(bg_rect[0] - out_px)
                hy0 = int(bg_rect[1] - out_px)
                hx1 = int(bg_rect[2] + out_px)
                hy1 = int(bg_rect[3] + out_px)
            bbox = (min(bbox[0], hx0), min(bbox[1], hy0), max(bbox[2], hx1), max(bbox[3], hy1))

        # Shadow
        if style.get("shadow_enabled"):
            shadow_layer = Image.new("RGBA", canvas_img.size, (0, 0, 0, 0))
            sd = ImageDraw.Draw(shadow_layer)
            try:
                s_rgb = ImageColor.getrgb(style.get("shadow_color", "#000000"))
            except Exception:
                s_rgb = (0, 0, 0)
            sd.multiline_text(
                (x + int(style.get("shadow_dx", 2)), y + int(style.get("shadow_dy", 2))),
                text,
                font=font,
                anchor=anchor,
                align=align,
                spacing=spacing,
                fill=(s_rgb[0], s_rgb[1], s_rgb[2], max(0, min(255, int(style.get("shadow_opacity", 120))))),
            )
            blur = int(style.get("shadow_blur", 3))
            if blur > 0:
                shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=blur))
            canvas_img.alpha_composite(shadow_layer)

        ow = style.get("stroke_outer_width")
        if ow is None:
            ow = max(0, int(style.get("stroke_width", 0)))
        else:
            ow = max(0, int(ow))
        outer_color = style.get("stroke_outer_color") or style.get("stroke_color") or "#000000"
        oe = style.get("stroke_outer_enabled")
        if oe is None:
            outer_on = ow > 0
        else:
            outer_on = bool(oe) and ow > 0
        try:
            out_rgb = ImageColor.getrgb(outer_color)
        except Exception:
            out_rgb = (0, 0, 0)

        inner_on = bool(style.get("stroke_inner_enabled", False))
        iw = max(0, int(style.get("stroke_inner_width", 0)))
        inner_color = style.get("stroke_inner_color", "#000000")
        try:
            in_rgb = ImageColor.getrgb(inner_color)
        except Exception:
            in_rgb = (0, 0, 0)

        # Заливка и обводка только через маски + Max/MinFilter: multiline_text(..., stroke_width=...)
        # увеличивает межстрочный интервал в Pillow — не используем.
        fill_mask = Image.new("L", canvas_img.size, 0)
        md = ImageDraw.Draw(fill_mask)
        md.multiline_text((x, y), text, font=font, anchor=anchor, align=align, spacing=spacing, fill=255)

        if outer_on:
            self._alpha_composite_text_stroke_ring(canvas_img, fill_mask, ow, out_rgb, outer=True)

        fb_fill = fill_mask.getbbox()
        if not fb_fill:
            return bbox
        gx0, gy0, gx1, gy1 = fb_fill

        tfm = (style.get("text_fill_mode") or "").strip().lower()
        use_grad = bool(style.get("use_gradient"))
        if tfm in ("static_palette", "alternate_pairs", "lighten_lines"):
            self._draw_per_line_text_fills(canvas_img, x, y, text, font, style, align, spacing, anchor)
        elif tfm == "gradient" or (not tfm and use_grad):
            grad = self.gradient_image((gx1 - gx0 + 2, gy1 - gy0 + 2), style.get("gradient_start", "#FFFFFF"), style.get("gradient_end", "#4AA3FF"))
            temp = Image.new("RGBA", canvas_img.size, (0, 0, 0, 0))
            temp.paste(grad, (gx0, gy0))
            fill_layer = Image.new("RGBA", canvas_img.size, (0, 0, 0, 0))
            fill_layer = Image.composite(temp, fill_layer, fill_mask)
            canvas_img.alpha_composite(fill_layer)
        else:
            try:
                rgb = ImageColor.getrgb(style.get("gradient_start", "#FFFFFF"))
            except Exception:
                rgb = (255, 255, 255)
            color_layer = Image.new("RGBA", canvas_img.size, (rgb[0], rgb[1], rgb[2], 255))
            fill_out = Image.new("RGBA", canvas_img.size, (0, 0, 0, 0))
            fill_out = Image.composite(color_layer, fill_out, fill_mask)
            canvas_img.alpha_composite(fill_out)

        if inner_on and iw > 0:
            self._alpha_composite_text_stroke_ring(canvas_img, fill_mask, iw, in_rgb, outer=False)
        return bbox

    def load_media_frame_rgba(self, path, size, t=0.0, dur=0.0):
        p = Path(path)
        if not p.exists():
            return None
        suf = p.suffix.lower()
        try:
            if suf in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
                img = Image.open(p)
                if hasattr(img, "n_frames") and img.n_frames > 1:
                    if dur and dur > 0:
                        idx = int((max(0.0, t) / dur) * img.n_frames) % img.n_frames
                    else:
                        idx = 0
                    img.seek(idx)
                return img.convert("RGBA").resize(size, Image.LANCZOS)
            if suf in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
                clip = VideoFileClip(str(p))
                tt = max(0.0, min(t, max(0.0, clip.duration - 0.05))) if clip.duration else 0.0
                arr = clip.get_frame(tt)
                clip.close()
                return Image.fromarray(arr).convert("RGBA").resize(size, Image.LANCZOS)
        except Exception:
            return None
        return None

    def _compute_seamless_bg_loop_params_from_d(self, D: float, dur: float, fade_user: float, seg_user: float, seed_str: str) -> tuple[float, float, float]:
        """Период цикла L, длина кроссфейда fade, случайный старт t0 в [0, D−L]. Детерминированно от seed_str."""
        D = max(float(D or 0.0), 0.001)
        dur = max(float(dur or 0.0), 0.1)
        fade = max(0.05, min(2.5, float(fade_user or 0.75)))
        min_L = 2.0 * fade + 0.2
        if D < min_L + 0.08:
            fade = max(0.04, (D - 0.12) / 2.2)
            min_L = 2.0 * fade + 0.12
        seg_u = float(seg_user or 0.0)
        if seg_u > 0.5:
            L = min(seg_u, D - 2.0 * fade - 0.06)
        else:
            L = max(4.0, min(14.0, dur * 0.35, D - 2.0 * fade - 0.06))
        L = max(min_L, min(L, D - 0.05))
        fade = min(fade, max(0.04, (L - 0.15) / 2.0))
        h = int(hashlib.md5(str(seed_str).encode("utf-8")).hexdigest()[:8], 16)
        t0_max = max(0.0, D - L)
        t0 = (h / float(0xFFFFFFFF)) * t0_max if t0_max > 1e-6 else 0.0
        return L, fade, t0

    def _seamless_loop_frame_rgb(self, vc: VideoFileClip, t: float, L: float, fade: float, t0: float, D: float) -> np.ndarray:
        """Один кадр RGB uint8 (H,W,3): в начале периода кроссфейд между хвостом и головой сегмента."""
        eps = 1e-3
        D = max(float(D), eps)
        L = max(float(L), eps)
        fade = max(0.0, min(float(fade), L * 0.45))
        p = (float(t) % L) if L > 0 else 0.0

        def _to_hw3(arr: np.ndarray) -> np.ndarray:
            a = np.asarray(arr, dtype=np.float32)
            if a.ndim == 2:
                a = np.stack([a, a, a], axis=-1)
            elif a.ndim == 3 and a.shape[2] >= 4:
                a = a[:, :, :3]
            return a

        if fade > 1e-5 and p < fade - 1e-6:
            w = max(0.0, min(1.0, p / fade))
            t1 = max(0.0, min(D - eps, t0 + L - fade + p))
            t2 = max(0.0, min(D - eps, t0 + p))
            f1 = _to_hw3(vc.get_frame(t1))
            f2 = _to_hw3(vc.get_frame(t2))
            out = f1 * (1.0 - w) + f2 * w
            return np.clip(out, 0, 255).astype(np.uint8)
        tt = max(0.0, min(D - eps, t0 + p))
        return np.clip(_to_hw3(vc.get_frame(tt)), 0, 255).astype(np.uint8)

    def _gif_frame_durations_ms(self, img: Image.Image) -> tuple[list[int], int]:
        """Длительности кадров GIF в мс и сумма (для зацикливания по времени сцены)."""
        n = max(1, int(getattr(img, "n_frames", 1)))
        durs: list[int] = []
        for i in range(n):
            try:
                img.seek(i)
            except Exception:
                break
            durs.append(max(1, int(img.info.get("duration", 100) or 100)))
        total = sum(durs) if durs else 1
        return durs, max(1, total)

    def _seek_gif_to_clock_time(self, img: Image.Image, t: float) -> None:
        """Позиция на шкале времени t (сек), GIF зациклен по собственной длительности."""
        if not hasattr(img, "n_frames") or int(getattr(img, "n_frames", 1) or 1) <= 1:
            img.seek(0)
            return
        durs, total_ms = self._gif_frame_durations_ms(img)
        if not durs:
            img.seek(0)
            return
        t_ms = (max(0.0, t) * 1000.0) % float(total_ms)
        acc = 0.0
        for i, d in enumerate(durs):
            if acc + d > t_ms:
                img.seek(i)
                return
            acc += d
        img.seek(len(durs) - 1)

    def _overlay_item_is_animated_gif(self, item: dict, p: Path) -> bool:
        kind = str(item.get("kind") or "text").strip().lower()
        if kind == "gif":
            return p.suffix.lower() == ".gif" and p.is_file()
        if kind == "image" and p.suffix.lower() == ".gif" and p.is_file():
            try:
                with Image.open(str(p)) as probe:
                    return int(getattr(probe, "n_frames", 1) or 1) > 1
            except Exception:
                return False
        return False

    def _make_overlay_gif_clip(self, src: str, item: dict, dur: float, frame_w: int, frame_h: int):
        """Клип MoviePy для GIF-оверлея: ресайз, позиция, зацикливание на длительность ролика."""
        p = Path(src).expanduser()
        if not p.is_file() or p.suffix.lower() != ".gif":
            return None
        try:
            tw = max(16, min(frame_w, int(item.get("width", 320))))
            th = max(16, min(frame_h, int(item.get("height", 240))))
        except Exception:
            tw, th = 320, 240
        try:
            x = int(item.get("x", 0))
            y = int(item.get("y", 0))
        except Exception:
            x, y = 0, 0
        frame_d = item.get("frame") if isinstance(item.get("frame"), dict) else None
        frames_np: list[np.ndarray] = []
        durs: list[int] = []
        px = py = 0
        gif = None
        try:
            gif = Image.open(str(p))
            n = max(1, int(getattr(gif, "n_frames", 1)))
            for i in range(n):
                gif.seek(i)
                im = gif.convert("RGBA").resize((tw, th), Image.LANCZOS)
                dec, px, py = self.decorate_layer_rgba_dict(im, frame_d)
                frames_np.append(np.asarray(dec.convert("RGBA"), dtype=np.uint8))
                durs.append(max(20, int(gif.info.get("duration", 100) or 100)))
        except Exception:
            return None
        finally:
            if gif:
                try:
                    gif.close()
                except Exception:
                    pass
        if not frames_np:
            return None
        total_ms = max(1, sum(durs))
        fps = max(1, min(60, int(len(frames_np) / (total_ms / 1000.0))))
        clip = ImageSequenceClip(frames_np, fps=fps)
        if clip.duration < dur:
            clip = clip.fx(vfx.loop, duration=dur)
        clip = clip.subclip(0, dur)
        return clip.set_position((x - px, y - py))

    def parse_card_bg_linear_gradient(self, spec: str):
        """CSS linear-gradient(180deg|to bottom, #a, #b) → (#a, #b) или None."""
        spec = (spec or "").strip()
        m = re.match(
            r"linear-gradient\s*\(\s*(?:180deg|to\s+bottom)\s*,\s*(#[0-9a-fA-F]{3,8})\s*,\s*(#[0-9a-fA-F]{3,8})\s*\)\s*$",
            spec,
            re.I,
        )
        if m:
            return m.group(1).strip(), m.group(2).strip()
        return None

    def card_bg_media_layer_active(self) -> bool:
        """Отдельный слой GIF/видео под текстом карточки (если выключено — остаётся цвет/градиент card_bg)."""
        if bool(getattr(self.settings, "card_backdrop_hidden", False)):
            return False
        m = (self.settings.card_bg_media or "").strip()
        if not m:
            return False
        return not bool(getattr(self.settings, "card_bg_media_hidden", False))

    def _normalize_card_bg_palette(self) -> list[str]:
        raw = getattr(self.settings, "card_bg_colors", None)
        if not raw:
            return []
        if isinstance(raw, str):
            parts = re.split(r"[\n,;]+", raw)
            return [p.strip() for p in parts if p and str(p).strip()]
        if isinstance(raw, (list, tuple)):
            return [str(x).strip() for x in raw if str(x).strip()]
        return []

    def _normalize_text_bg_palette(self, raw) -> list[str]:
        if not raw:
            return []
        if isinstance(raw, str):
            return [p.strip() for p in re.split(r"[\n,;]+", raw) if p and str(p).strip()]
        if isinstance(raw, (list, tuple)):
            return [str(x).strip() for x in raw if str(x).strip()]
        return []

    def _reset_text_bg_random_picks(self) -> None:
        self._text_bg_random_pick_cache = {}
        self._text_bg_image_path_cache = {}
        self._glow_color_pick = None
        # Новый nonce = новый детерминированный выбор палитр/пар для следующего рендера.
        self._text_style_render_nonce = f"{random.getrandbits(64):016x}"

    def _normalize_glow_colors(self, raw) -> list[str]:
        if not raw:
            return []
        if isinstance(raw, str):
            return [p.strip() for p in re.split(r"[\n,;]+", raw) if p and str(p).strip()]
        if isinstance(raw, (list, tuple)):
            return [str(x).strip() for x in raw if str(x).strip()]
        return []

    def _resolved_glow_rgb(self) -> tuple[int, int, int]:
        pal = self._normalize_glow_colors(getattr(self.settings, "glow_overlay_colors", None))
        if not pal:
            return (186, 228, 255)
        pick = getattr(self, "_glow_color_pick", None)
        if pick is None or str(pick).strip() not in pal:
            self._glow_color_pick = random.choice(pal)
            pick = self._glow_color_pick
        try:
            return ImageColor.getrgb(str(pick).strip())
        except Exception:
            return (186, 228, 255)

    def _render_glow_overlay_rgba(self, w: int, h: int, t: float, dur: float) -> Image.Image:
        """Два мягких круга (верх/низ), лёгкая анимация дрейфа и «дыхание» яркости."""
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if not bool(getattr(self.settings, "glow_overlay_enabled", True)):
            return out
        op = max(0.0, min(1.0, float(getattr(self.settings, "glow_overlay_opacity", 0.38) or 0.0)))
        if op <= 1e-6:
            return out
        dur_eff = max(0.001, float(dur))
        r0, g0, b0 = self._resolved_glow_rgb()
        spd = 2.0 * math.pi / max(2.8, dur_eff * 0.55)
        ph1 = float(t) * spd
        ph2 = float(t) * spd * 1.13 + 1.7
        flick = 0.82 + 0.18 * math.sin(ph1 * 2.4)
        peak = int(round(255.0 * op * 0.72 * flick))
        peak = max(0, min(255, peak))
        if peak <= 2:
            return out
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx1 = w * 0.5 + (w * 0.24) * math.sin(ph1)
        cy1 = h * (-0.04) + (h * 0.06) * math.cos(ph1 * 0.62) + 95.0
        cx2 = w * 0.5 + (w * 0.2) * math.sin(ph2 + 0.9)
        cy2 = h * 1.04 - (h * 0.055) * math.cos(ph2 * 0.58)
        rad1 = float(max(w, h)) * 0.58
        rad2 = float(max(w, h)) * 0.52
        d1 = np.sqrt((xx - cx1) ** 2 + (yy - cy1) ** 2)
        d2 = np.sqrt((xx - cx2) ** 2 + (yy - cy2) ** 2)
        a1 = np.clip(1.0 - d1 / rad1, 0.0, 1.0) ** 2.35
        a2 = np.clip(1.0 - d2 / rad2, 0.0, 1.0) ** 2.35
        a = np.clip((a1 + a2) * float(peak), 0.0, 255.0).astype(np.uint8)
        arr = np.zeros((h, w, 4), dtype=np.uint8)
        arr[:, :, 0] = r0
        arr[:, :, 1] = g0
        arr[:, :, 2] = b0
        arr[:, :, 3] = a
        return Image.fromarray(arr, mode="RGBA")

    def _resolve_text_bg_color(self, style: dict) -> str:
        pal = self._normalize_text_bg_palette(style.get("bg_colors"))
        fallback = str(style.get("bg_color") or "#000000").strip() or "#000000"
        if not pal:
            return fallback
        key = str(style.get("_bg_random_key") or "").strip()
        if not key:
            return random.choice(pal)
        pick = self._text_bg_random_pick_cache.get(key)
        if pick is None or str(pick).strip() not in pal:
            pick = random.choice(pal)
            self._text_bg_random_pick_cache[key] = pick
        return str(pick).strip()

    def _resolve_style_bg_image_file(self, style: dict) -> str:
        """Файл картинки подложки: путь к файлу или случайный файл из папки (несколько изображений)."""
        raw = (style.get("bg_image") or "").strip()
        if not raw:
            return ""
        p = Path(os.path.expandvars(os.path.expanduser(str(raw).replace("/", os.sep))))
        if not p.exists():
            p2 = (_REPO_ROOT / str(raw).strip().lstrip("\\/")).resolve()
            if p2.exists():
                p = p2
            else:
                return ""
        img_ext = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
        if p.is_file():
            return str(p) if p.suffix.lower() in img_ext else ""
        if not p.is_dir():
            return ""
        files = sorted([x for x in p.iterdir() if x.is_file() and x.suffix.lower() in img_ext])
        if not files:
            return ""
        if len(files) == 1:
            return str(files[0])
        key = f"bgimg|{str(style.get('_bg_random_key') or 'default')}|{p.resolve()}"
        cand = {str(x) for x in files}
        pick = self._text_bg_image_path_cache.get(key)
        if pick is None or str(pick) not in cand:
            pick = str(random.choice(files))
            self._text_bg_image_path_cache[key] = pick
        return str(pick)

    def _style_fill_rng(self, style: dict, salt: str) -> random.Random:
        nonce = str(getattr(self, "_text_style_render_nonce", "") or "")
        k = f"{style.get('_bg_random_key') or ''}|{salt}|{nonce}"
        h = hashlib.sha256(k.encode("utf-8", errors="replace")).digest()
        seed = int.from_bytes(h[:8], "big", signed=False) or 1
        return random.Random(seed)

    def _hex_to_rgb_safe(self, h) -> tuple[int, int, int]:
        try:
            return ImageColor.getrgb(str(h or "#FFFFFF"))
        except Exception:
            return (255, 255, 255)

    def _lighten_rgb_towards_white(self, rgb: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
        a = max(0.0, min(1.0, float(amount)))
        r, g, b = rgb[0], rgb[1], rgb[2]
        return (
            int(round(r + (255 - r) * a)),
            int(round(g + (255 - g) * a)),
            int(round(b + (255 - b) * a)),
        )

    def _per_line_glyph_masks(
        self,
        canvas_wh: tuple[int, int],
        xy: tuple[float, float],
        text: str,
        font,
        anchor: str,
        align: str,
        spacing: int,
    ) -> list[Image.Image]:
        """L-маски пикселей каждой строки — те же, что даёт multiline_text (для стыковки с обводкой)."""
        cw, ch = int(canvas_wh[0]), int(canvas_wh[1])
        x, y = xy
        lines = (text or "").split("\n")
        if not lines:
            return []
        masks: list[Image.Image] = []
        prev = np.zeros((ch, cw), dtype=np.uint8)
        for i in range(len(lines)):
            chunk = "\n".join(lines[: i + 1])
            cur_img = Image.new("L", (cw, ch), 0)
            ImageDraw.Draw(cur_img).multiline_text(
                (x, y), chunk, font=font, anchor=anchor, align=align, spacing=spacing, fill=255
            )
            cur = np.asarray(cur_img, dtype=np.uint8)
            line_arr = ((cur > 0) & (prev == 0)).astype(np.uint8) * 255
            masks.append(Image.fromarray(line_arr, mode="L"))
            prev = cur
        return masks

    def _normalize_alternate_pairs(self, raw) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        if not raw:
            return out
        if isinstance(raw, list):
            for p in raw:
                if isinstance(p, (list, tuple)) and len(p) >= 2:
                    a, b = str(p[0]).strip(), str(p[1]).strip()
                    if a and b:
                        out.append((a, b))
                elif isinstance(p, dict):
                    a = str(p.get("a") or p.get("0") or "").strip()
                    b = str(p.get("b") or p.get("1") or "").strip()
                    if a and b:
                        out.append((a, b))
        return out

    def _emoji_png_path_for_sign(self, sign_upper: str) -> Path | None:
        stem = _ZODIAC_SIGN_TO_EMOJI_STEM.get(str(sign_upper or "").strip().upper())
        if not stem:
            return None
        base = _REPO_ROOT / "emojis"
        for ext in (".png", ".webp", ".jpg", ".jpeg", ".gif", ".bmp"):
            p = base / f"{stem}{ext}"
            if p.is_file():
                return p
        return None

    def _extract_sign_from_rank_line(self, line: str) -> str | None:
        t = str(line or "").strip().upper()
        if not t:
            return None
        m = re.match(r"^(?:ТОП\s+)?\d+\s*(?:МЕСТО|РАНГ)?\s*-\s*([А-ЯЁA-Z]+)[\.\,\!\?\:\;…]*\s*$", t)
        if not m:
            return None
        sign = str(m.group(1) or "").strip().upper()
        return sign if sign in _ZODIAC_SIGN_TO_EMOJI_STEM else None

    def _draw_rank_line_emoji_pngs(
        self,
        canvas_img: Image.Image,
        text: str,
        x: float,
        y: float,
        font,
        spacing: int,
        *,
        anchor: str = "ma",
        align: str = "center",
    ) -> tuple[int, int, int, int] | None:
        if anchor != "ma" or align != "center":
            return None
        lines = str(text or "").splitlines()
        if not lines:
            return None
        # Берём реальные bbox каждой строки из масок glyph-пикселей; это даёт точное совпадение с фактически
        # нарисованным multiline_text (без "пляски" по Y из-за разницы метрик шрифта/межстрочки).
        line_masks = self._per_line_glyph_masks(canvas_img.size, (x, y), text, font, anchor, align, spacing)
        if not line_masks:
            return None
        d = ImageDraw.Draw(canvas_img)
        union: tuple[int, int, int, int] | None = None
        rs = getattr(Image, "Resampling", Image).LANCZOS
        gap_px = max(6, int((getattr(font, "size", 36) or 36) * 0.18))
        # Единый размер эмодзи для всех строк этого блока (без "пляски" от длины/высоты конкретной строки).
        base_fs = max(12, int(getattr(font, "size", 36) or 36))
        fixed_ih = max(14, int(base_fs * 0.82))
        for i, ln in enumerate(lines):
            raw = str(ln or "")
            clean = raw.strip()
            if i >= len(line_masks):
                continue
            lb = line_masks[i].getbbox()
            if lb is None:
                continue
            lx0, ly0, lx1, ly1 = [int(v) for v in lb]
            lh = max(1, ly1 - ly0)
            sign = self._extract_sign_from_rank_line(clean)
            if sign:
                ep = self._emoji_png_path_for_sign(sign)
                if ep is not None:
                    try:
                        with Image.open(ep) as im0:
                            icon = im0.convert("RGBA")
                        ih = fixed_ih
                        iw = max(12, int(round(icon.width * (ih / max(1, icon.height)))))
                        icon = icon.resize((iw, ih), rs)
                        iy = int(round(ly0 + (lh - ih) / 2.0))
                        ex_left = int(lx0 - gap_px - iw)
                        ex_right = int(lx1 + gap_px)
                        canvas_img.alpha_composite(icon, (ex_left, iy))
                        canvas_img.alpha_composite(icon, (ex_right, iy))
                        bx0 = min(ex_left, ex_right)
                        by0 = iy
                        bx1 = max(ex_left + iw, ex_right + iw)
                        by1 = iy + ih
                        if union is None:
                            union = (bx0, by0, bx1, by1)
                        else:
                            union = (min(union[0], bx0), min(union[1], by0), max(union[2], bx1), max(union[3], by1))
                    except Exception:
                        pass
        return union

    def _draw_per_line_text_fills(
        self,
        canvas_img: Image.Image,
        x: float,
        y: float,
        text: str,
        font,
        style: dict,
        align: str,
        spacing: int,
        anchor: str,
    ) -> None:
        lines = (text or "").split("\n")
        line_masks = self._per_line_glyph_masks(canvas_img.size, (x, y), text, font, anchor, align, spacing)
        if len(line_masks) < len(lines):
            return
        tfm = (style.get("text_fill_mode") or "").strip().lower()
        rng = self._style_fill_rng(style, "linefill")
        rgbs: list[tuple[int, int, int]] = []

        if tfm == "static_palette":
            cols = [str(c).strip() for c in (style.get("text_palette_colors") or []) if str(c).strip()]
            pick = rng.choice(cols) if len(cols) > 1 else (cols[0] if cols else None)
            base = self._hex_to_rgb_safe(pick or style.get("gradient_start", "#FFFFFF"))
            for _ in lines:
                rgbs.append(base)
        elif tfm == "alternate_pairs":
            pairs = self._normalize_alternate_pairs(style.get("text_alternate_pairs"))
            if not pairs:
                c1 = self._hex_to_rgb_safe(style.get("gradient_start", "#FFFFFF"))
                c2 = self._hex_to_rgb_safe(style.get("gradient_end", "#4AA3FF"))
                pair = (c1, c2)
            else:
                ch = rng.choice(pairs)
                pair = (self._hex_to_rgb_safe(ch[0]), self._hex_to_rgb_safe(ch[1]))
            for i in range(len(lines)):
                rgbs.append(pair[i % 2])
        elif tfm == "lighten_lines":
            bases = [str(c).strip() for c in (style.get("text_lighten_bases") or []) if str(c).strip()]
            pick = rng.choice(bases) if len(bases) > 1 else (bases[0] if bases else None)
            base_rgb = self._hex_to_rgb_safe(pick or style.get("gradient_start", "#FFFFFF"))
            step = 0.07
            for i in range(len(lines)):
                rgbs.append(self._lighten_rgb_towards_white(base_rgb, min(0.92, step * i)))
        else:
            return

        for i, line in enumerate(lines):
            if i >= len(rgbs) or i >= len(line_masks):
                break
            if not (line or "").strip():
                continue
            lm = line_masks[i]
            if lm.getbbox() is None:
                continue
            rgb = rgbs[i]
            color_layer = Image.new("RGBA", canvas_img.size, (rgb[0], rgb[1], rgb[2], 255))
            fill_out = Image.new("RGBA", canvas_img.size, (0, 0, 0, 0))
            fill_out = Image.composite(color_layer, fill_out, lm)
            canvas_img.alpha_composite(fill_out)

    def _invalidate_card_bg_random_pick(self) -> None:
        self._card_bg_random_pick = None

    def resolved_card_bg_spec(self) -> str:
        pal = self._normalize_card_bg_palette()
        if len(pal) >= 1:
            pick = getattr(self, "_card_bg_random_pick", None)
            if pick is None or str(pick).strip() not in pal:
                self._card_bg_random_pick = random.choice(pal)
            return str(self._card_bg_random_pick).strip()
        self._card_bg_random_pick = None
        s = (self.settings.card_bg or "").strip()
        return s or "#FFFFFF"

    def ensure_timeline_layers(self) -> None:
        """Слои таймлайна: старт/конец/z; подмешивает overlay:* из scene_overlays."""
        dur = max(0.1, float(self.settings.duration_max))
        defaults = [
            {"id": "background", "start": 0.0, "end": dur, "z": 0, "visible": True},
            {"id": "card", "start": 0.0, "end": dur, "z": 20, "visible": True},
            {"id": "title", "start": 0.0, "end": dur, "z": 21, "visible": True},
            {"id": "subtitle", "start": 0.0, "end": dur, "z": 22, "visible": True},
            {"id": "dates", "start": 0.0, "end": dur, "z": 23, "visible": True},
            {"id": "watermark", "start": 0.0, "end": dur, "z": 100, "visible": True},
            {"id": "glow", "start": 0.0, "end": dur, "z": 10000, "visible": True},
        ]
        rows = getattr(self.settings, "timeline_layers", None)
        if not isinstance(rows, list):
            rows = []
        by_id: dict[str, dict] = {}
        for r in rows:
            if not isinstance(r, dict) or not str(r.get("id") or "").strip():
                continue
            iid = str(r["id"]).strip()
            try:
                z = int(r.get("z", 0))
            except Exception:
                z = 0
            vis = r.get("visible", True)
            if isinstance(vis, str):
                vis = vis.strip().lower() not in ("0", "false", "no", "off", "")
            by_id[iid] = {
                "id": iid,
                "start": float(r.get("start", 0.0)),
                "end": float(r.get("end", dur)),
                "z": z,
                "visible": bool(vis),
            }
        for d in defaults:
            if d["id"] not in by_id:
                by_id[d["id"]] = {"id": d["id"], "start": 0.0, "end": dur, "z": d["z"], "visible": True}
        overlays = getattr(self.settings, "scene_overlays", None)
        if isinstance(overlays, list):
            for item in overlays:
                if not isinstance(item, dict):
                    continue
                oid_raw = str(item.get("id") or "").strip()
                oid = re.sub(r"[^a-zA-Z0-9_\-]", "", oid_raw)[:80]
                if not oid:
                    continue
                lid = f"overlay:{oid}"
                if lid not in by_id:
                    by_id[lid] = {"id": lid, "start": 0.0, "end": dur, "z": 200, "visible": True}
        for lid in list(by_id.keys()):
            r = by_id[lid]
            st = max(0.0, min(float(r.get("start", 0.0)), dur))
            en = max(st, min(float(r.get("end", dur)), dur))
            r["start"], r["end"] = st, en
            if "visible" not in r:
                r["visible"] = True
        # Слой «фото героя» больше не используется — убираем из старых пресетов.
        by_id.pop("photo", None)
        self.settings.timeline_layers = sorted(by_id.values(), key=lambda x: (int(x.get("z", 0)), str(x.get("id", ""))))

    def _timeline_row(self, layer_id: str) -> dict | None:
        self.ensure_timeline_layers()
        want = str(layer_id or "").strip()
        for r in self.settings.timeline_layers or []:
            if isinstance(r, dict) and str(r.get("id") or "").strip() == want:
                return r
        return None

    def _timeline_z(self, layer_id: str) -> int:
        rw = self._timeline_row(layer_id)
        if not rw:
            return 0
        try:
            return int(rw.get("z", 0))
        except Exception:
            return 0

    def _timeline_visible(self, layer_id: str, t: float, clip_dur: float | None = None) -> bool:
        cap = max(0.001, float(clip_dur if clip_dur is not None else self.settings.duration_max))
        rw = self._timeline_row(layer_id)
        if not rw:
            return True
        if rw.get("visible", True) is False:
            return False
        st = float(rw.get("start", 0.0))
        en = float(rw.get("end", cap))
        st_eff = max(0.0, min(st, cap))
        en_eff = max(st_eff, min(en, cap))
        if st_eff >= en_eff:
            return False
        return st_eff <= t < en_eff

    def _timeline_segment_clamped(self, layer_id: str, cap_dur: float) -> tuple[float, float] | None:
        """Отрезок появления слоя в пределах длительности ролика; None если пусто."""
        cap = max(0.04, float(cap_dur))
        self.ensure_timeline_layers()
        rw = self._timeline_row(layer_id)
        if not rw:
            return (0.0, cap)
        if rw.get("visible", True) is False:
            return None
        st = max(0.0, float(rw.get("start", 0.0)))
        en = float(rw.get("end", cap))
        en = min(en, cap)
        if st >= en:
            return None
        st = min(st, cap)
        return (st, en)

    def _time_window_clip(self, clip, layer_id: str, cap_dur: float):
        """Обрезка клипа к окну слоя на глобальной шкале + set_start."""
        seg = self._timeline_segment_clamped(layer_id, cap_dur)
        if seg is None:
            return None
        st, en = seg
        try:
            cdur = float(clip.duration)
        except Exception:
            cdur = cap_dur
        a = max(0.0, min(st, max(cdur - 1e-6, 0.0)))
        b = max(a, min(en, cdur))
        if b - a < 0.03:
            return None
        try:
            out = clip.subclip(a, b)
        except Exception:
            return None
        return out.set_start(st)

    def _preview_layer_drawable(self, layer_id: str, t: float, clip_dur: float | None = None) -> bool:
        if not self._timeline_visible(layer_id, t, clip_dur):
            return False
        if layer_id == "photo":
            return False
        if layer_id == "card" and bool(getattr(self.settings, "card_hidden", False)):
            return False
        if layer_id == "title" and bool(getattr(self.settings, "title_hidden", False)):
            return False
        if layer_id == "subtitle" and bool(getattr(self.settings, "subtitle_hidden", False)):
            return False
        if layer_id == "dates" and bool(getattr(self.settings, "dates_hidden", False)):
            return False
        if layer_id == "watermark" and bool(getattr(self.settings, "watermark_hidden", False)):
            return False
        if layer_id == "watermark" and not (self.settings.watermark_text or "").strip():
            return False
        if layer_id == "effect":
            return False
        if layer_id == "glow" and not bool(getattr(self.settings, "glow_overlay_enabled", True)):
            return False
        return True

    def draw_card_background(self, card_img, t=0.0, dur=0.0):
        w, h = card_img.size
        media = self.settings.card_bg_media.strip()
        if media and self.card_bg_media_layer_active():
            bg = self.load_media_frame_rgba(media, (w, h), t=t, dur=dur)
            if bg:
                card_img.paste(bg, (0, 0))
                return
        spec = self.resolved_card_bg_spec()
        grad = self.parse_card_bg_linear_gradient(spec)
        if grad:
            c1, c2 = grad
            gimg = self.gradient_image((w, h), c1, c2).convert("RGBA")
            card_img.paste(gimg, (0, 0), gimg)
            return
        try:
            rgb = ImageColor.getrgb(spec)
        except Exception:
            rgb = (255, 255, 255)
        ImageDraw.Draw(card_img).rectangle((0, 0, w, h), fill=(rgb[0], rgb[1], rgb[2], 255))

    def render_card_decomposed(
        self,
        title: str,
        subtitle: str,
        dates_text: str = "",
        include_background: bool = True,
        t: float = 0.0,
        dur: float = 0.0,
        *,
        text_frame_wh: tuple[int, int] | None = None,
        card_rect: tuple[int, int, int, int] | None = None,
    ) -> tuple[dict[str, Image.Image], dict]:
        """Слои карточки: backdrop cw×ch; title/subtitle/dates — на отдельном полотне кадра (если заданы text_frame_wh и card_rect).

        Подложка (backdrop) не обрезает текст: перенос и bbox считаются по ширине кадра, координаты текста — от угла карточки на кадре."""
        w = self.settings.card_width
        h = self.settings.card_height
        use_frame_text = (
            text_frame_wh is not None
            and card_rect is not None
            and int(text_frame_wh[0]) > 0
            and int(text_frame_wh[1]) > 0
        )
        tw_img, th_img = (int(text_frame_wh[0]), int(text_frame_wh[1])) if use_frame_text else (w, h)
        cx = cy = cw0 = ch0 = 0
        if use_frame_text:
            cx, cy, cw0, ch0 = (int(card_rect[0]), int(card_rect[1]), int(card_rect[2]), int(card_rect[3]))
        coords_key = "viewport" if use_frame_text else "card"
        empty_meta = {
            "title": (0, 0, 0, 0),
            "subtitle": (0, 0, 0, 0),
            "dates": (0, 0, 0, 0),
            "card": (0, 0, w, h),
            "_coords": coords_key,
        }
        blank_bd = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        blank_txt = Image.new("RGBA", (tw_img, th_img), (0, 0, 0, 0))
        if bool(getattr(self.settings, "card_hidden", False)):
            return {
                "backdrop": blank_bd.copy(),
                "title": blank_txt.copy(),
                "subtitle": blank_txt.copy(),
                "dates": blank_txt.copy(),
            }, empty_meta

        backdrop = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        if include_background and not self.card_bg_media_layer_active():
            if not bool(getattr(self.settings, "card_backdrop_hidden", False)):
                self.draw_card_background(backdrop, t=t, dur=dur)

        subtitle_font = ImageFont.truetype(self.settings.subtitle_font, self.settings.subtitle_font_size)
        dates_font = ImageFont.truetype(self.settings.dates_font, self.settings.dates_font_size)
        default_text_w = float(max(40, tw_img - int(self.settings.side_padding) * 2))
        tw_user = int(getattr(self.settings, "title_wrap_width", 0) or 0)
        if tw_user > 0:
            title_box_w = float(max(40, min(tw_user, tw_img - 20)))
        else:
            title_box_w = default_text_w
        sw_user = int(getattr(self.settings, "subtitle_wrap_width", 0) or 0)
        if sw_user > 0:
            subtitle_box_w = float(max(40, min(sw_user, tw_img - 20)))
        else:
            subtitle_box_w = default_text_w
        box_w = default_text_w

        title_img = Image.new("RGBA", (tw_img, th_img), (0, 0, 0, 0))
        title_t = self.transform_text_case(title).replace("\n", " ").replace("\r", " ").strip()
        title_font = ImageFont.truetype(self.settings.title_font, self.settings.title_font_size)
        title_wrapped = title_t
        if not bool(getattr(self.settings, "title_hidden", False)) and title_t:
            base_sz = max(8, int(self.settings.title_font_size))
            min_sz = max(12, min(base_sz, int(getattr(self.settings, "title_font_size_min", 22))))
            min_sz = min(min_sz, base_sz)
            title_ty_eval = (cy + int(self.settings.title_y)) if use_frame_text else int(self.settings.title_y)
            sub_ty_eval = (cy + int(self.settings.subtitle_y)) if use_frame_text else int(self.settings.subtitle_y)
            gap_m = 14
            if sub_ty_eval > title_ty_eval + gap_m:
                max_title_h = max(64, sub_ty_eval - title_ty_eval - gap_m)
            else:
                max_title_h = max(120, th_img - title_ty_eval - 32)
            tx_eval = (cx + cw0 // 2 + int(self.settings.title_x)) if use_frame_text else (w // 2 + int(self.settings.title_x))
            title_path = self.settings.title_font
            picked = False
            low_floor = max(8, min(min_sz, base_sz))
            for sz in range(base_sz, low_floor - 1, -1):
                try:
                    f_try = ImageFont.truetype(title_path, sz)
                except Exception:
                    continue
                pair_try = self._split_title_exactly_two_lines(title_t, f_try, title_box_w)
                if pair_try is None:
                    continue
                wrapped_try = f"{pair_try[0]}\n{pair_try[1]}"
                h_try = self._title_multiline_height(wrapped_try, f_try, tx_eval, title_ty_eval, spacing=5)
                if h_try <= max_title_h:
                    title_font = f_try
                    title_wrapped = wrapped_try
                    picked = True
                    break
            if not picked:
                for sz in range(low_floor - 1, 7, -1):
                    try:
                        f_try = ImageFont.truetype(title_path, sz)
                    except Exception:
                        continue
                    pair_try = self._split_title_exactly_two_lines(title_t, f_try, title_box_w)
                    if pair_try is None:
                        continue
                    wrapped_try = f"{pair_try[0]}\n{pair_try[1]}"
                    h_try = self._title_multiline_height(wrapped_try, f_try, tx_eval, title_ty_eval, spacing=5)
                    if h_try <= max_title_h:
                        title_font = f_try
                        title_wrapped = wrapped_try
                        picked = True
                        break
            if not picked:
                try:
                    title_font = ImageFont.truetype(title_path, min_sz)
                except Exception:
                    pass
                pair_fb = self._split_title_exactly_two_lines(title_t, title_font, title_box_w)
                if pair_fb is None:
                    title_wrapped = title_t
                else:
                    title_wrapped = f"{pair_fb[0]}\n{pair_fb[1]}"
        if bool(getattr(self.settings, "title_hidden", False)):
            title_bbox = (0, 0, 0, 0)
        else:
            tx = (cx + cw0 // 2 + int(self.settings.title_x)) if use_frame_text else (w // 2 + int(self.settings.title_x))
            ty = (cy + int(self.settings.title_y)) if use_frame_text else int(self.settings.title_y)
            title_bbox = self.draw_styled_text(
                title_img,
                title_wrapped,
                tx,
                ty,
                title_font,
                {**self.get_text_style("title"), "_bg_random_key": "title"},
                align="center",
                anchor="ma",
                spacing=5,
                persist_style_element="title",
            )

        subtitle_img = Image.new("RGBA", (tw_img, th_img), (0, 0, 0, 0))
        subtitle_t = self.transform_text_case(self.normalize_subtitle(subtitle))
        wrapped_segments: list[str] = []
        for block in subtitle_t.split("\n"):
            blk = block.strip()
            if not blk:
                continue
            wrapped_segments.extend(self._word_wrap_title_lines(blk, subtitle_font, subtitle_box_w))
        subtitle_wrapped = "\n".join(wrapped_segments)
        if bool(getattr(self.settings, "subtitle_hidden", False)):
            subtitle_bbox = (0, 0, 0, 0)
        else:
            sx = (cx + cw0 // 2 + int(self.settings.subtitle_x)) if use_frame_text else (w // 2 + int(self.settings.subtitle_x))
            sy = (cy + int(self.settings.subtitle_y)) if use_frame_text else int(self.settings.subtitle_y)
            subtitle_bbox = self.draw_styled_text(
                subtitle_img,
                subtitle_wrapped,
                sx,
                sy,
                subtitle_font,
                {**self.get_text_style("subtitle"), "_bg_random_key": "subtitle"},
                align="center",
                anchor="ma",
                spacing=self.settings.subtitle_line_spacing,
                persist_style_element="subtitle",
            )
            emj_bbox = self._draw_rank_line_emoji_pngs(
                subtitle_img,
                subtitle_wrapped,
                sx,
                sy,
                subtitle_font,
                self.settings.subtitle_line_spacing,
                anchor="ma",
                align="center",
            )
            if emj_bbox is not None:
                subtitle_bbox = (
                    min(int(subtitle_bbox[0]), int(emj_bbox[0])),
                    min(int(subtitle_bbox[1]), int(emj_bbox[1])),
                    max(int(subtitle_bbox[2]), int(emj_bbox[2])),
                    max(int(subtitle_bbox[3]), int(emj_bbox[3])),
                )

        dates_img = Image.new("RGBA", (tw_img, th_img), (0, 0, 0, 0))
        dates_bbox = (0, 0, 0, 0)
        if dates_text.strip() and not bool(getattr(self.settings, "dates_hidden", False)):
            dx = (cx + cw0 // 2 + int(self.settings.dates_x)) if use_frame_text else (w // 2 + int(self.settings.dates_x))
            dy = (cy + int(self.settings.dates_y)) if use_frame_text else int(self.settings.dates_y)
            dates_bbox = self.draw_styled_text(
                dates_img,
                self.transform_text_case(dates_text.strip()),
                dx,
                dy,
                dates_font,
                {**self.get_text_style("dates"), "_bg_random_key": "dates"},
                align="center",
                anchor="ma",
                spacing=4,
                persist_style_element="dates",
            )

        meta = {
            "title": title_bbox,
            "subtitle": subtitle_bbox,
            "dates": dates_bbox,
            "card": (0, 0, w, h),
            "_coords": coords_key,
        }
        return {"backdrop": backdrop, "title": title_img, "subtitle": subtitle_img, "dates": dates_img}, meta

    def render_card_image(self, title, subtitle, dates_text="", include_background=True, t=0.0, dur=0.0):
        parts, meta = self.render_card_decomposed(title, subtitle, dates_text, include_background, t, dur)
        w = self.settings.card_width
        h = self.settings.card_height
        card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        for k in ("backdrop", "title", "subtitle", "dates"):
            card.alpha_composite(parts[k], (0, 0))
        return card, meta

    def merge_layer_frame(self, which: str) -> dict:
        base = default_layer_frame_style()
        src = getattr(self.settings, f"{which}_frame", None) if which in ("photo", "card") else None
        if isinstance(src, dict):
            base.update(src)
        return base

    def merge_layer_frame_dict(self, frame: dict | None) -> dict:
        base = default_layer_frame_style()
        if isinstance(frame, dict):
            base.update(frame)
        return base

    def decorate_layer_rgba(self, img: Image.Image, which: str) -> tuple[Image.Image, int, int]:
        """Рамка + тень вокруг RGBA-слоя. Возвращает (изображение, pad_left, pad_top) для смещения при композите."""
        return self._decorate_layer_rgba_with_style(img, self.merge_layer_frame(which))

    def decorate_layer_rgba_dict(self, img: Image.Image, frame: dict | None) -> tuple[Image.Image, int, int]:
        return self._decorate_layer_rgba_with_style(img, self.merge_layer_frame_dict(frame))

    def _resolve_layer_frame_strokes(self, style: dict) -> tuple[bool, int, tuple[int, int, int], bool, int, tuple[int, int, int]]:
        """Внешняя/внутренняя обводка рамки слоя; при отсутствии новых ключей — legacy stroke_enabled + stroke_width."""
        new_any = (
            style.get("stroke_outer_enabled") is not None
            or style.get("stroke_outer_width") is not None
            or style.get("stroke_outer_color") is not None
            or bool(style.get("stroke_inner_enabled"))
            or int(style.get("stroke_inner_width", 0) or 0) > 0
        )

        def _rgb(s: str) -> tuple[int, int, int]:
            try:
                return ImageColor.getrgb(s)
            except Exception:
                return (0, 0, 0)

        if not new_any:
            leg = bool(style.get("stroke_enabled")) and max(0, int(style.get("stroke_width", 0) or 0)) > 0
            lw = max(0, int(style.get("stroke_width", 0) or 0))
            return leg, lw, _rgb(str(style.get("stroke_color", "#000000"))), False, 0, (0, 0, 0)

        ow_raw = style.get("stroke_outer_width")
        if ow_raw is None:
            ow = max(0, int(style.get("stroke_width", 0) or 0))
        else:
            ow = max(0, int(ow_raw))
        oe = style.get("stroke_outer_enabled")
        if oe is None:
            o_on = bool(style.get("stroke_enabled")) and ow > 0
        else:
            o_on = bool(oe) and ow > 0
        o_rgb = _rgb(str(style.get("stroke_outer_color") or style.get("stroke_color") or "#000000"))
        iw = max(0, int(style.get("stroke_inner_width", 0) or 0))
        i_on = bool(style.get("stroke_inner_enabled")) and iw > 0
        i_rgb = _rgb(str(style.get("stroke_inner_color") or "#000000"))
        return o_on, ow, o_rgb, i_on, iw, i_rgb

    def _layer_frame_rounded_mask(self, cw: int, ch: int, pl: int, pt: int, w: int, h: int, r_rad: int) -> Image.Image:
        """L-маска скруглённого прямоугольника слоя на полотне cw×ch."""
        m = Image.new("L", (max(1, cw), max(1, ch)), 0)
        ww = max(1, w)
        hh = max(1, h)
        rr = max(0, min(int(r_rad), ww // 2, hh // 2))
        sub = Image.new("L", (ww, hh), 0)
        ImageDraw.Draw(sub).rounded_rectangle((0, 0, ww - 1, hh - 1), radius=rr, fill=255)
        m.paste(sub, (int(pl), int(pt)))
        return m

    def _decorate_layer_rgba_with_style(self, img: Image.Image, style: dict) -> tuple[Image.Image, int, int]:
        """Рамка + тень вокруг RGBA-слоя по готовому словарю стиля."""
        img = img.convert("RGBA")
        w, h = img.size
        if w < 1 or h < 1:
            return img, 0, 0
        outer_on, out_w, out_rgb, inner_on, in_w, in_rgb = self._resolve_layer_frame_strokes(style)
        sh_en = bool(style.get("shadow_enabled"))
        blur = max(0, int(style.get("shadow_blur", 0) or 0)) if sh_en else 0
        dx = int(style.get("shadow_dx", 0) or 0) if sh_en else 0
        dy = int(style.get("shadow_dy", 0) or 0) if sh_en else 0
        so = max(0, min(255, int(style.get("shadow_opacity", 0) or 0))) if sh_en else 0
        need_shadow = sh_en and so > 0

        if not outer_on and not inner_on and not need_shadow:
            return img, 0, 0

        out_pad = out_w if outer_on else 0
        pl = pr = pt = pb = out_pad
        if need_shadow:
            pl = max(pl, out_pad + blur + max(0, -dx))
            pr = max(pr, out_pad + blur + max(0, dx))
            pt = max(pt, out_pad + blur + max(0, -dy))
            pb = max(pb, out_pad + blur + max(0, dy))
        cw, ch = w + pl + pr, h + pt + pb
        out = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))

        if need_shadow:
            try:
                sr, sg, sb = ImageColor.getrgb(style.get("shadow_color", "#000000"))
            except Exception:
                sr, sg, sb = (0, 0, 0)
            alpha = img.split()[3]
            sh_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            sh_layer.paste((sr, sg, sb, so), (0, 0), alpha)
            if blur > 0:
                sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(radius=blur))
            out.alpha_composite(sh_layer, (pl + dx, pt + dy))

        r_rad = max(0, int(style.get("corner_radius", 10) or 0))
        if outer_on and out_w > 0:
            fill_m = self._layer_frame_rounded_mask(cw, ch, pl, pt, w, h, r_rad)
            self._alpha_composite_text_stroke_ring(out, fill_m, out_w, out_rgb, outer=True)

        out.alpha_composite(img, (pl, pt))

        if inner_on and in_w > 0:
            fill_m2 = self._layer_frame_rounded_mask(cw, ch, pl, pt, w, h, r_rad)
            self._alpha_composite_text_stroke_ring(out, fill_m2, in_w, in_rgb, outer=False)

        return out, pl, pt

    def render_scene_overlays_rgba(
        self,
        size_wh: tuple[int, int],
        t: float,
        dur: float,
        hitboxes_out: dict | None,
        only_hkey: str | None = None,
    ) -> Image.Image:
        """Пользовательские текст/картинка на прозрачном слое; опционально заполняет hitboxes_out."""
        w, h = size_wh
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        overlays = getattr(self.settings, "scene_overlays", None)
        if not isinstance(overlays, list):
            return layer
        sub_base = default_text_styles().get("subtitle", {}).copy()
        for item in overlays:
            if not isinstance(item, dict):
                continue
            if item.get("hidden"):
                continue
            oid_raw = str(item.get("id") or "").strip()
            oid = re.sub(r"[^a-zA-Z0-9_\-]", "", oid_raw)[:80]
            if not oid:
                continue
            hkey = f"overlay:{oid}"
            if only_hkey is not None and hkey != only_hkey:
                continue
            kind = str(item.get("kind") or "text").strip().lower()
            try:
                x = int(item.get("x", 0))
                y = int(item.get("y", 0))
            except Exception:
                x, y = 0, 0
            if kind in ("image", "gif"):
                src = str(item.get("src") or "").strip()
                if not src:
                    continue
                p = Path(src).expanduser()
                if not p.is_file():
                    continue
                try:
                    tw = max(16, min(w, int(item.get("width", 320))))
                    th = max(16, min(h, int(item.get("height", 240))))
                except Exception:
                    tw, th = 320, 240
                frame_d = item.get("frame") if isinstance(item.get("frame"), dict) else None
                raw = None
                try:
                    if self._overlay_item_is_animated_gif(item, p):
                        raw = Image.open(str(p))
                        self._seek_gif_to_clock_time(raw, t)
                        img0 = raw.convert("RGBA").resize((tw, th), Image.LANCZOS)
                    else:
                        raw = Image.open(str(p))
                        img0 = raw.convert("RGBA").resize((tw, th), Image.LANCZOS)
                except Exception:
                    continue
                finally:
                    if raw:
                        try:
                            raw.close()
                        except Exception:
                            pass
                dec, px, py = self.decorate_layer_rgba_dict(img0, frame_d)
                ox = x - px
                oy = y - py
                layer.alpha_composite(dec, (ox, oy))
                if hitboxes_out is not None:
                    hitboxes_out[hkey] = (ox, oy, ox + dec.width, oy + dec.height)
                continue
            text0 = str(item.get("text") or "")
            if not text0.strip():
                text0 = "Текст"
            text_use = self.transform_text_case(text0)
            fp = str(item.get("font") or self.settings.subtitle_font)
            try:
                fs = max(8, min(200, int(item.get("font_size", 48))))
            except Exception:
                fs = 48
            try:
                mw = max(80, min(w, int(item.get("max_width", 900))))
            except Exception:
                mw = 900
            try:
                lsp = max(0, int(item.get("line_spacing", 12)))
            except Exception:
                lsp = 12
            st_in = item.get("style") if isinstance(item.get("style"), dict) else {}
            style = {**sub_base, **st_in}
            style["_bg_random_key"] = f"overlay:{hkey}"
            try:
                font = ImageFont.truetype(fp, fs)
            except Exception:
                font = ImageFont.load_default()
            wrap_w = max(12, mw // max(1, int(fs * 0.52)))
            parts = []
            for raw_line in text_use.splitlines():
                if not raw_line.strip():
                    parts.append("")
                    continue
                chunk = textwrap.wrap(raw_line.strip(), width=wrap_w)
                parts.append("\n".join(chunk) if chunk else raw_line.strip())
            wrapped = "\n".join(parts) if parts else text_use
            _snap_kw: dict = {}
            if not self.headless:
                _snap_kw["persist_overlay_item"] = item
            bbox = self.draw_styled_text(
                layer, wrapped, x, y, font, style, align="center", anchor="ma", spacing=lsp, **_snap_kw
            )
            if hitboxes_out is not None:
                x0, y0, x1, y1 = [int(v) for v in bbox]
                hitboxes_out[hkey] = (x0, y0, x1, y1)
        return layer

    def build_scene_overlay_moviepy_clips(self, dur: float, vw: int, vh: int) -> list:
        """Клипы оверлеев в порядке списка: статичные куски (PIL) + зацикленные GIF отдельными ImageSequenceClip."""
        overlays = getattr(self.settings, "scene_overlays", None)
        if not isinstance(overlays, list) or not overlays:
            return []
        clips: list = []
        accum = Image.new("RGBA", (vw, vh), (0, 0, 0, 0))
        has_accum = False
        sub_base = default_text_styles().get("subtitle", {}).copy()

        def flush_accum():
            nonlocal accum, has_accum
            if not has_accum:
                return
            arr = np.asarray(accum)
            try:
                c = ImageClip(arr, transparent=True).set_duration(dur).set_position((0, 0))
            except TypeError:
                c = ImageClip(arr).set_duration(dur).set_position((0, 0))
            clips.append(c)
            accum = Image.new("RGBA", (vw, vh), (0, 0, 0, 0))
            has_accum = False

        for item in overlays:
            if not isinstance(item, dict):
                continue
            if item.get("hidden"):
                continue
            kind = str(item.get("kind") or "text").strip().lower()
            try:
                x = int(item.get("x", 0))
                y = int(item.get("y", 0))
            except Exception:
                x, y = 0, 0
            if kind in ("image", "gif"):
                src = str(item.get("src") or "").strip()
                if not src:
                    continue
                p = Path(src).expanduser()
                if not p.is_file():
                    continue
                if self._overlay_item_is_animated_gif(item, p):
                    flush_accum()
                    gc = self._make_overlay_gif_clip(src, item, dur, vw, vh)
                    if gc:
                        clips.append(gc)
                    continue
                try:
                    tw = max(16, min(vw, int(item.get("width", 320))))
                    th = max(16, min(vh, int(item.get("height", 240))))
                except Exception:
                    tw, th = 320, 240
                try:
                    with Image.open(str(p)) as raw:
                        img0 = raw.convert("RGBA").resize((tw, th), Image.LANCZOS)
                except Exception:
                    continue
                frame_d = item.get("frame") if isinstance(item.get("frame"), dict) else None
                dec, px, py = self.decorate_layer_rgba_dict(img0, frame_d)
                ox = x - px
                oy = y - py
                accum.alpha_composite(dec, (ox, oy))
                has_accum = True
                continue
            text0 = str(item.get("text") or "")
            if not text0.strip():
                text0 = "Текст"
            text_use = self.transform_text_case(text0)
            fp = str(item.get("font") or self.settings.subtitle_font)
            try:
                fs = max(8, min(200, int(item.get("font_size", 48))))
            except Exception:
                fs = 48
            try:
                mw = max(80, min(vw, int(item.get("max_width", 900))))
            except Exception:
                mw = 900
            try:
                lsp = max(0, int(item.get("line_spacing", 12)))
            except Exception:
                lsp = 12
            st_in = item.get("style") if isinstance(item.get("style"), dict) else {}
            style = {**sub_base, **st_in}
            style["_bg_random_key"] = f"overlay:{item.get('id') or id(item)}"
            try:
                font = ImageFont.truetype(fp, fs)
            except Exception:
                font = ImageFont.load_default()
            wrap_w = max(12, mw // max(1, int(fs * 0.52)))
            parts = []
            for raw_line in text_use.splitlines():
                if not raw_line.strip():
                    parts.append("")
                    continue
                chunk = textwrap.wrap(raw_line.strip(), width=wrap_w)
                parts.append("\n".join(chunk) if chunk else raw_line.strip())
            wrapped = "\n".join(parts) if parts else text_use
            _snap_kw2: dict = {}
            if not self.headless:
                _snap_kw2["persist_overlay_item"] = item
            self.draw_styled_text(accum, wrapped, x, y, font, style, align="center", anchor="ma", spacing=lsp, **_snap_kw2)
            has_accum = True
        flush_accum()
        return clips

    def _make_photo_blur_fullframe(self, vw: int, vh: int, image_path: str) -> Image.Image:
        p = (image_path or "").strip()
        if not p or not Path(p).is_file():
            return Image.new("RGB", (vw, vh), (28, 30, 36))
        im = Image.open(p)
        try:
            im = ImageOps.exif_transpose(im)
        except Exception:
            pass
        im = im.convert("RGB")
        ir, ic = im.size
        if ir < 2 or ic < 2:
            return Image.new("RGB", (vw, vh), (28, 30, 36))
        # Равномерное увеличение (cover): одна шкала по большей стороне, без растягивания по осям.
        scale = max(vw / float(ic), vh / float(ir))
        new_w = max(1, int(math.ceil(ic * scale)))
        new_h = max(1, int(math.ceil(ir * scale)))
        resample = getattr(Image, "Resampling", Image).LANCZOS
        im = im.resize((new_w, new_h), resample)
        left = max(0, (new_w - vw) // 2)
        top = max(0, (new_h - vh) // 2)
        im = im.crop((left, top, left + vw, top + vh))
        blur = float(getattr(self.settings, "video_bg_photo_blur", 18.0) or 0.0)
        blur = max(0.0, min(90.0, blur))
        if blur > 0.05:
            im = im.filter(ImageFilter.GaussianBlur(radius=blur))
        br = float(getattr(self.settings, "video_bg_photo_brightness", 1.0) or 1.0)
        br = max(0.15, min(2.5, br))
        if abs(br - 1.0) > 0.02:
            im = ImageEnhance.Brightness(im).enhance(br)
        return im

    def _compose_base_frame_rgb(self, vw: int, vh: int, t: float, dur: float, photo_path: str | None = None) -> Image.Image:
        """Фон 9:16: папка с видео / цвет+градиент / размытое фото политика."""
        mode = (getattr(self.settings, "video_bg_mode", "folder") or "folder").strip().lower()
        path_saved = (getattr(self.settings, "video_bg_photo_path", "") or "").strip()
        path_for_blur = path_saved or (photo_path or "").strip() or (self.current_image_path or "").strip()

        if mode == "photo_blur":
            return self._make_photo_blur_fullframe(vw, vh, path_for_blur)

        if mode == "flat":
            spec = (getattr(self.settings, "video_bg_spec", "") or "#1a1f2a").strip()
            grad = self.parse_card_bg_linear_gradient(spec)
            if grad:
                c1, c2 = grad
                return self.gradient_image((vw, vh), c1, c2).convert("RGB")
            try:
                rgb = ImageColor.getrgb(spec)
            except Exception:
                rgb = (26, 31, 42)
            return Image.new("RGB", (vw, vh), rgb)

        folder = (getattr(self.settings, "video_bg_folder", "") or "bg").strip() or "bg"
        seamless = bool(getattr(self.settings, "video_bg_seamless_loop", False))
        fade_s = float(getattr(self.settings, "video_bg_loop_crossfade_sec", 0.75) or 0.75)
        seg_s = float(getattr(self.settings, "video_bg_loop_segment_sec", 0) or 0)
        cache_key = ("vbg", mode, folder, seamless, round(fade_s, 2), round(seg_s, 2), round(float(dur), 2))
        if getattr(self, "_preview_video_bg_key", None) != cache_key:
            self._preview_video_bg_key = cache_key
            if getattr(self, "_preview_folder_vc", None):
                try:
                    self._preview_folder_vc.close()
                except Exception:
                    pass
                self._preview_folder_vc = None
            picked = self.creator.get_random_file(folder, (".mp4", ".mov", ".avi", ".mkv", ".webm"))
            self._preview_bg_cached = picked or ""
            if self._preview_bg_cached and seamless:
                try:
                    pth = Path(self._preview_bg_cached).expanduser()
                    _vc = VideoFileClip(str(pth)).resize((vw, vh))
                    try:
                        self._preview_folder_vc = _vc.without_audio()
                    except Exception:
                        self._preview_folder_vc = _vc
                    self._preview_loop_D = float(self._preview_folder_vc.duration or 0) or 0.001
                    seed = f"{self._preview_bg_cached}|{dur:.4f}"
                    self._preview_loop_L, self._preview_loop_fade, self._preview_loop_t0 = self._compute_seamless_bg_loop_params_from_d(
                        self._preview_loop_D, dur, fade_s, seg_s, seed
                    )
                except Exception:
                    if getattr(self, "_preview_folder_vc", None):
                        try:
                            self._preview_folder_vc.close()
                        except Exception:
                            pass
                        self._preview_folder_vc = None
        if self._preview_bg_cached:
            if seamless and getattr(self, "_preview_folder_vc", None) is not None:
                try:
                    arr = self._seamless_loop_frame_rgb(
                        self._preview_folder_vc,
                        float(t),
                        self._preview_loop_L,
                        self._preview_loop_fade,
                        self._preview_loop_t0,
                        self._preview_loop_D,
                    )
                    return Image.fromarray(arr, mode="RGB")
                except Exception:
                    pass
            fr = self.load_media_frame_rgba(self._preview_bg_cached, (vw, vh), t=t, dur=dur)
            if fr:
                return fr.convert("RGB")
        return Image.new("RGB", (vw, vh), (40, 40, 40))

    def compose_preview_frame(self, t=0.0):
        vw, vh = 1080, 1920
        dur = max(0.001, float(self.settings.duration_max))
        self.ensure_timeline_layers()
        cap = dur

        title_line = (self.headline_var.get().strip() if hasattr(self, "headline_var") else "") or ""

        dates_line = self.dates_var.get().strip()

        cw = int(self.settings.card_width)
        ch = int(self.settings.card_height)
        card_x = int((vw - cw) / 2 + self.settings.card_offset_x)
        card_x = max(-cw + 60, min(vw - 60, card_x))
        card_y = self._layout_card_center_vertical(vh, ch)
        card_parts, card_meta = self.render_card_decomposed(
            title_line,
            self.bio_box.get("1.0", "end").strip(),
            dates_line,
            include_background=not self.card_bg_media_layer_active(),
            t=t,
            dur=self.settings.duration_max,
            text_frame_wh=(vw, vh),
            card_rect=(card_x, card_y, cw, ch),
        )
        media_card = self.settings.card_bg_media.strip()
        card_dec, cpx, cpy = self.decorate_layer_rgba(card_parts["backdrop"].convert("RGBA"), "card")
        cx0, cy0 = card_x - cpx, card_y - cpy

        layers_img: dict[str, Image.Image] = {}
        layers_img["background"] = self._compose_base_frame_rgb(vw, vh, t, dur, photo_path=None).convert("RGBA")
        layers_img["glow"] = (
            self._render_glow_overlay_rgba(vw, vh, t, dur)
            if self._preview_layer_drawable("glow", t, cap)
            else Image.new("RGBA", (vw, vh), (0, 0, 0, 0))
        )

        card_rgba_full = Image.new("RGBA", (vw, vh), (0, 0, 0, 0))
        if self._preview_layer_drawable("card", t, cap):
            if self.card_bg_media_layer_active() and media_card:
                cbg = self.load_media_frame_rgba(media_card, (cw, ch), t=t, dur=dur)
                if cbg:
                    card_rgba_full.alpha_composite(cbg.convert("RGBA"), (card_x, card_y))
            card_rgba_full.alpha_composite(card_dec, (cx0, cy0))
        layers_img["card"] = card_rgba_full

        text_hits_viewport = card_meta.get("_coords") == "viewport"
        for lid, pkey in (("title", "title"), ("subtitle", "subtitle"), ("dates", "dates")):
            lyr = Image.new("RGBA", (vw, vh), (0, 0, 0, 0))
            if self._preview_layer_drawable(lid, t, cap):
                raw = card_parts[pkey].convert("RGBA")
                dec, px2, py2 = self.decorate_layer_rgba(raw, "card")
                if text_hits_viewport:
                    lyr.alpha_composite(dec, (-int(px2), -int(py2)))
                else:
                    lyr.alpha_composite(dec, (card_x - px2, card_y - py2))
            layers_img[lid] = lyr

        wm_rgba, _wm_bb = self.draw_watermark_rgba_layer(vw, vh)
        if wm_rgba is None or not self._preview_layer_drawable("watermark", t, cap):
            layers_img["watermark"] = Image.new("RGBA", (vw, vh), (0, 0, 0, 0))
        else:
            layers_img["watermark"] = wm_rgba

        for row in self.settings.timeline_layers or []:
            if not isinstance(row, dict):
                continue
            lid = str(row.get("id") or "")
            if not lid.startswith("overlay:"):
                continue
            if self._timeline_visible(lid, t, cap):
                hb_one: dict = {}
                layers_img[lid] = self.render_scene_overlays_rgba((vw, vh), t, dur, hb_one, only_hkey=lid)
            else:
                layers_img[lid] = Image.new("RGBA", (vw, vh), (0, 0, 0, 0))

        def _tl_sort_z(r) -> int:
            if not isinstance(r, dict):
                return 0
            try:
                return int(float(r.get("z", 0)))
            except (TypeError, ValueError):
                return 0

        ordered = sorted(
            self.settings.timeline_layers or [],
            key=lambda r: (_tl_sort_z(r), str((r or {}).get("id", "") or "")),
        )
        base = Image.new("RGBA", (vw, vh), (26, 26, 26, 255))
        for row in ordered:
            if not isinstance(row, dict):
                continue
            lid = str(row.get("id") or "").strip()
            if not lid:
                continue
            if not self._timeline_visible(lid, t, cap):
                continue
            if lid == "glow" and not self._preview_layer_drawable("glow", t, cap):
                continue
            im = layers_img.get(lid)
            if im is None:
                continue
            base = Image.alpha_composite(base, im)

        frame = base.convert("RGB")
        self.hitboxes_video = {}
        if self._preview_layer_drawable("card", t, cap):
            self.hitboxes_video["card"] = (cx0, cy0, cx0 + card_dec.width, cy0 + card_dec.height)
        if self._preview_layer_drawable("title", t, cap) and card_meta.get("title"):
            tb = card_meta["title"]
            if text_hits_viewport:
                self.hitboxes_video["title"] = (int(tb[0]), int(tb[1]), int(tb[2]), int(tb[3]))
            else:
                self.hitboxes_video["title"] = (int(tb[0] + card_x), int(tb[1] + card_y), int(tb[2] + card_x), int(tb[3] + card_y))
        if self._preview_layer_drawable("subtitle", t, cap) and card_meta.get("subtitle"):
            sb = card_meta["subtitle"]
            if text_hits_viewport:
                self.hitboxes_video["subtitle"] = (int(sb[0]), int(sb[1]), int(sb[2]), int(sb[3]))
            else:
                self.hitboxes_video["subtitle"] = (int(sb[0] + card_x), int(sb[1] + card_y), int(sb[2] + card_x), int(sb[3] + card_y))
        if self._preview_layer_drawable("dates", t, cap) and card_meta.get("dates") and dates_line.strip():
            db = card_meta["dates"]
            if text_hits_viewport:
                self.hitboxes_video["dates"] = (int(db[0]), int(db[1]), int(db[2]), int(db[3]))
            else:
                self.hitboxes_video["dates"] = (int(db[0] + card_x), int(db[1] + card_y), int(db[2] + card_x), int(db[3] + card_y))
        if self._preview_layer_drawable("watermark", t, cap):
            _, wm_bbox = self.draw_watermark_rgba_layer(vw, vh)
            if wm_bbox:
                self.hitboxes_video["watermark"] = wm_bbox
        hb_ov: dict = {}
        for row in self.settings.timeline_layers or []:
            if not isinstance(row, dict):
                continue
            lid = str(row.get("id") or "")
            if not lid.startswith("overlay:"):
                continue
            if not self._timeline_visible(lid, t, cap):
                continue
            self.render_scene_overlays_rgba((vw, vh), t, dur, hb_ov, only_hkey=lid)
        if hb_ov:
            self.hitboxes_video.update(hb_ov)
        return frame

    def refresh_preview(self):
        frame = self.compose_preview_frame(self.current_time)
        canvas_w = max(1, self.canvas.winfo_width())
        canvas_h = max(1, self.canvas.winfo_height())
        scale = min(canvas_w / 1080, canvas_h / 1920)
        preview_w = max(1, int(1080 * scale))
        preview_h = max(1, int(1920 * scale))
        x = (canvas_w - preview_w) // 2
        y = (canvas_h - preview_h) // 2
        self.preview_rect = (x, y, preview_w, preview_h)
        preview = frame.resize((preview_w, preview_h))
        self.tk_preview = ImageTk.PhotoImage(preview)
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, canvas_w, canvas_h, fill="#1F1F1F", outline="")
        self.canvas.create_image(x, y, anchor="nw", image=self.tk_preview)
        self.canvas.create_rectangle(x, y, x + preview_w, y + preview_h, outline="#E5E5E5", width=2)
        self.draw_selection_overlay()
        self.update_time_label()
        self._sync_inspector_to_selection()

    def draw_selection_overlay(self):
        if self.selected_element not in self.hitboxes_video:
            return
        x0, y0, x1, y1 = self.video_to_canvas_rect(self.hitboxes_video[self.selected_element])
        self.canvas.create_rectangle(x0, y0, x1, y1, outline="#3FA9F5", width=2)
        for key in ("card", "title", "dates", "subtitle", "watermark"):
            if key not in self.hitboxes_video or key == self.selected_element:
                continue
            rx0, ry0, rx1, ry1 = self.video_to_canvas_rect(self.hitboxes_video[key])
            self.canvas.create_rectangle(rx0, ry0, rx1, ry1, outline="#6D6D6D", width=1, dash=(4, 3))

    def video_to_canvas_rect(self, rect):
        vx0, vy0, vx1, vy1 = rect
        px, py, pw, ph = self.preview_rect
        sx = pw / 1080
        sy = ph / 1920
        return (
            int(px + vx0 * sx),
            int(py + vy0 * sy),
            int(px + vx1 * sx),
            int(py + vy1 * sy),
        )

    def canvas_to_video_point(self, x, y):
        px, py, pw, ph = self.preview_rect
        if x < px or y < py or x > px + pw or y > py + ph:
            return None
        vx = int((x - px) * 1080 / pw)
        vy = int((y - py) * 1920 / ph)
        return vx, vy

    def on_click_canvas(self, event):
        self.drag_start = (event.x, event.y)
        point = self.canvas_to_video_point(event.x, event.y)
        if not point:
            return
        vx, vy = point
        for key in ("watermark", "title", "dates", "subtitle", "card"):
            if key not in self.hitboxes_video:
                continue
            x0, y0, x1, y1 = self.hitboxes_video[key]
            if x0 <= vx <= x1 and y0 <= vy <= y1:
                self.selected_element = key
                break
        self.refresh_preview()

    def on_double_click_canvas(self, event):
        self.on_click_canvas(event)
        if self.selected_element in ("title", "subtitle", "dates", "watermark"):
            self.open_text_style_editor(self.selected_element)

    def on_drag_canvas(self, event):
        if not self.drag_start:
            return
        sx, sy = self.drag_start
        dx = event.x - sx
        dy = event.y - sy
        _, _, pw, ph = self.preview_rect
        scale_x = 1080 / max(1, pw)
        scale_y = 1920 / max(1, ph)
        dx_real = int(dx * scale_x)
        dy_real = int(dy * scale_y)
        if self.selected_element == "title":
            self.settings.title_y += dy_real
            self.settings.title_x += dx_real
        elif self.selected_element == "dates":
            self.settings.dates_y += dy_real
            self.settings.dates_x += dx_real
        elif self.selected_element == "subtitle":
            self.settings.subtitle_y += dy_real
            self.settings.subtitle_x += dx_real
        elif self.selected_element == "watermark":
            self.settings.watermark_x += dx_real
            self.settings.watermark_y += dy_real
        elif self.selected_element == "card":
            self.settings.card_offset_x += dx_real
            self.settings.card_offset_y += dy_real
        self.drag_start = (event.x, event.y)
        self.sync_controls_from_settings()
        self.refresh_preview()

    def on_wheel(self, event):
        delta = 2 if event.delta > 0 else -2
        shift = bool(event.state & 0x0001)
        if self.selected_element == "title":
            self.settings.title_font_size = max(34, min(140, self.settings.title_font_size + delta))
        elif self.selected_element == "dates":
            self.settings.dates_font_size = max(18, min(84, self.settings.dates_font_size + delta))
        elif self.selected_element == "subtitle":
            self.settings.subtitle_font_size = max(24, min(84, self.settings.subtitle_font_size + delta))
        elif self.selected_element == "watermark":
            self.settings.watermark_font_size = max(12, min(120, self.settings.watermark_font_size + delta))
        self.sync_controls_from_settings()
        self.refresh_preview()

    def update_time_label(self):
        self.time_label.configure(text=f"{self.current_time:.2f} / {self.settings.duration_max:.2f} c")
        self._timeline_internal_update = True
        self.timeline_var.set(self.current_time)
        self._timeline_internal_update = False

    def toggle_play(self):
        self.is_playing = not self.is_playing
        self.play_btn.configure(
            text="Пауза" if self.is_playing else "Пуск",
            image=self.icons["pause"] if self.is_playing else self.icons["play"],
        )
        if self.is_playing:
            self.play_tick()

    def play_tick(self):
        if not self.is_playing:
            return
        self.current_time += 1 / 30
        if self.current_time >= self.settings.duration_max:
            self.current_time = self.settings.duration_max
            self.is_playing = False
            self.play_btn.configure(text="Пуск", image=self.icons["play"])
        self.refresh_preview()
        if self.is_playing:
            self.root.after(33, self.play_tick)

    def seek_start(self):
        self.current_time = 0.0
        self.refresh_preview()

    def on_timeline_change(self, _value):
        if self._timeline_internal_update:
            return
        val = float(self.timeline_var.get())
        if abs(val - self.last_seek_value) < 0.0001:
            return
        self.last_seek_value = val
        self.current_time = max(0.0, min(self.settings.duration_max, val))
        self.refresh_preview()

    def pick_color_to_var(self, var):
        chosen = colorchooser.askcolor(color=var.get() or "#FFFFFF", title="Выбор цвета")
        if chosen and chosen[1]:
            var.set(chosen[1])

    def _invalidate_element_inspector(self) -> None:
        self._inspector_shown_for = None

    def _coerce_hex_display(self, c: str) -> str:
        t = (c or "").strip()
        if not t:
            return "#2A3852"
        if not t.startswith("#"):
            t = f"#{t}"
        try:
            ImageColor.getrgb(t)
            return t
        except Exception:
            return "#2A3852"

    def _swatch_hex_for_spec(self, spec: str) -> str:
        s = (spec or "").strip()
        if not s:
            return "#2A3852"
        g = self.parse_card_bg_linear_gradient(s)
        if g:
            return self._coerce_hex_display(g[0])
        return self._coerce_hex_display(s)

    def _inspector_update_swatch(self, label: tk.Label, spec: str) -> None:
        try:
            if label.winfo_exists():
                label.configure(bg=self._swatch_hex_for_spec(spec))
        except tk.TclError:
            pass

    def _sync_inspector_to_selection(self) -> None:
        if not hasattr(self, "inspector_container"):
            return
        elt = getattr(self, "selected_element", "card")
        if elt == getattr(self, "_inspector_shown_for", None):
            return
        self._inspector_shown_for = elt
        self._rebuild_element_inspector()

    def _rebuild_element_inspector(self) -> None:
        if not hasattr(self, "inspector_container"):
            return
        for w in self.inspector_container.winfo_children():
            w.destroy()
        elt = getattr(self, "selected_element", "card")
        if elt in ("title", "subtitle", "dates", "watermark"):
            self._inspector_build_text_backdrop(elt)
        elif elt == "card":
            self._inspector_build_card_backdrop()
        else:
            ttk.Label(
                self.inspector_container,
                text=(
                    "Кликните по элементу в превью.\n"
                    "Для подложки текста — заголовок, описание, даты или вотермарка.\n"
                    "Для фона карточки — область карточки."
                ),
                foreground="#8EA3BE",
                background="#121826",
                wraplength=360,
            ).pack(anchor="w")

    def _inspector_build_text_backdrop(self, element: str) -> None:
        titles = {"title": "Заголовок", "subtitle": "Описание", "dates": "Даты", "watermark": "Вотермарка"}
        ttk.Label(
            self.inspector_container,
            text=f"{titles.get(element, element)} — подложка текста",
            style="PanelTitle.TLabel",
        ).pack(anchor="w", pady=(0, 6))

        style = self.get_text_style(element)
        bg_en = tk.BooleanVar(value=bool(style.get("bg_enabled", False)))
        bg_grad = tk.BooleanVar(value=bool(style.get("bg_use_gradient", False)))
        bg_color_var = tk.StringVar(value=str(style.get("bg_color") or "#000000"))
        self._inspector_palette_vars = []

        pal_frame = ttk.Frame(self.inspector_container, style="Panel.TFrame")
        pal_frame.pack(fill="x", pady=(4, 0))

        def push():
            colors = self._normalize_text_bg_palette([x.get().strip() for x in self._inspector_palette_vars])
            st = dict(self.get_text_style(element))
            st["bg_enabled"] = bool(bg_en.get())
            st["bg_use_gradient"] = bool(bg_grad.get())
            st["bg_color"] = (bg_color_var.get() or "").strip() or "#000000"
            st["bg_colors"] = colors
            self.settings.text_styles[element] = st
            self._reset_text_bg_random_picks()
            self.refresh_preview()
            self.save_settings(show_message=False, apply_first=False)

        ttk.Checkbutton(self.inspector_container, text="Включить подложку", variable=bg_en, command=push).pack(anchor="w")
        ttk.Checkbutton(self.inspector_container, text="Градиент подложки (два цвета — в полном стиле)", variable=bg_grad, command=push).pack(anchor="w", pady=(0, 4))

        row_base = ttk.Frame(self.inspector_container, style="Panel.TFrame")
        row_base.pack(fill="x", pady=2)
        ttk.Label(row_base, text="Цвет подложки (если палитра пуста):").pack(side="left")
        sw_b = tk.Label(row_base, width=3, relief="solid", bd=1, bg=self._swatch_hex_for_spec(bg_color_var.get()))
        sw_b.pack(side="right", padx=(4, 0))
        ttk.Button(
            row_base,
            text="…",
            width=3,
            command=lambda: (self.pick_color_to_var(bg_color_var), self._inspector_update_swatch(sw_b, bg_color_var.get()), push()),
        ).pack(side="right", padx=2)
        ent_base = ttk.Entry(row_base, textvariable=bg_color_var, width=14)
        ent_base.pack(side="right")
        ent_base.bind("<FocusOut>", lambda _e: push())

        def trace_base(*_):
            self._inspector_update_swatch(sw_b, bg_color_var.get())

        bg_color_var.trace_add("write", lambda *_: trace_base())

        ttk.Label(
            self.inspector_container,
            text="Случайный цвет подложки при каждом новом видео (если список не пуст):",
            foreground="#9FB3CC",
            background="#121826",
            wraplength=380,
        ).pack(anchor="w", pady=(8, 2))

        def mk_row(parent, initial: str):
            v = tk.StringVar(value=initial)
            self._inspector_palette_vars.append(v)
            row = ttk.Frame(parent, style="Panel.TFrame")
            row.pack(fill="x", pady=2)
            sw = tk.Label(row, width=3, relief="solid", bd=1, bg=self._swatch_hex_for_spec(initial))
            sw.pack(side="left", padx=(0, 4))
            ent = ttk.Entry(row, textvariable=v, width=34)
            ent.pack(side="left", fill="x", expand=True)
            ent.bind("<FocusOut>", lambda _e: push())

            def upd(*_):
                self._inspector_update_swatch(sw, v.get())

            v.trace_add("write", upd)

            def pick_one():
                self.pick_color_to_var(v)
                self._inspector_update_swatch(sw, v.get())
                push()

            def remove():
                try:
                    self._inspector_palette_vars.remove(v)
                except ValueError:
                    pass
                row.destroy()
                push()

            ttk.Button(row, text="…", width=3, command=pick_one).pack(side="left", padx=2)
            ttk.Button(row, text="Удалить", command=remove).pack(side="left", padx=(4, 0))

        init_colors = self._normalize_text_bg_palette(style.get("bg_colors"))
        for c in init_colors:
            mk_row(pal_frame, c)

        def add_solid():
            mk_row(pal_frame, "#1A2430")
            push()

        ttk.Button(pal_frame, text="+ Добавить цвет", command=add_solid).pack(anchor="w", pady=(6, 2))

        ttk.Separator(self.inspector_container, orient="horizontal").pack(fill="x", pady=8)
        ttk.Button(
            self.inspector_container,
            text="Полный стиль текста…",
            command=lambda: self.open_text_style_editor(element),
        ).pack(fill="x")

    def _inspector_build_card_backdrop(self) -> None:
        ttk.Label(
            self.inspector_container,
            text="Карточка — цвет / палитра фона",
            style="PanelTitle.TLabel",
        ).pack(anchor="w", pady=(0, 6))
        ttk.Label(
            self.inspector_container,
            text="Если список не пуст, при каждом новом ролике выбирается случайная строка (цвет или linear-gradient…).",
            foreground="#9FB3CC",
            background="#121826",
            wraplength=380,
        ).pack(anchor="w", pady=(0, 6))

        base_var = tk.StringVar(value=str(self.settings.card_bg or "#FFFFFF").strip())
        self._inspector_card_palette_vars: list[tk.StringVar] = []
        pal_frame = ttk.Frame(self.inspector_container, style="Panel.TFrame")
        pal_frame.pack(fill="x", pady=(4, 0))

        def push():
            self.settings.card_bg = (base_var.get() or "").strip() or "#FFFFFF"
            self.settings.card_bg_colors = self._normalize_card_bg_palette([x.get().strip() for x in self._inspector_card_palette_vars])
            self._invalidate_card_bg_random_pick()
            self.refresh_preview()
            self.save_settings(show_message=False, apply_first=False)

        row_base = ttk.Frame(self.inspector_container, style="Panel.TFrame")
        row_base.pack(fill="x", pady=2)
        ttk.Label(row_base, text="Основной цвет (если палитра пуста):").pack(side="left")
        sw_b = tk.Label(row_base, width=3, relief="solid", bd=1, bg=self._swatch_hex_for_spec(base_var.get()))
        sw_b.pack(side="right", padx=(4, 0))
        ttk.Button(
            row_base,
            text="…",
            width=3,
            command=lambda: (self.pick_color_to_var(base_var), self._inspector_update_swatch(sw_b, base_var.get()), push()),
        ).pack(side="right", padx=2)
        ent_card_base = ttk.Entry(row_base, textvariable=base_var, width=14)
        ent_card_base.pack(side="right")
        ent_card_base.bind("<FocusOut>", lambda _e: push())
        base_var.trace_add("write", lambda *_: self._inspector_update_swatch(sw_b, base_var.get()))

        def mk_row(initial: str):
            v = tk.StringVar(value=initial)
            self._inspector_card_palette_vars.append(v)
            row = ttk.Frame(pal_frame, style="Panel.TFrame")
            row.pack(fill="x", pady=2)
            sw = tk.Label(row, width=3, relief="solid", bd=1, bg=self._swatch_hex_for_spec(initial))
            sw.pack(side="left", padx=(0, 4))
            ent = ttk.Entry(row, textvariable=v, width=34)
            ent.pack(side="left", fill="x", expand=True)
            ent.bind("<FocusOut>", lambda _e: push())

            def upd(*_):
                self._inspector_update_swatch(sw, v.get())

            v.trace_add("write", upd)

            def pick_one():
                self.pick_color_to_var(v)
                self._inspector_update_swatch(sw, v.get())
                push()

            def remove():
                try:
                    self._inspector_card_palette_vars.remove(v)
                except ValueError:
                    pass
                row.destroy()
                push()

            ttk.Button(row, text="…", width=3, command=pick_one).pack(side="left", padx=2)
            ttk.Button(row, text="Удалить", command=remove).pack(side="left", padx=(4, 0))

        for c in self._normalize_card_bg_palette(self.settings.card_bg_colors):
            mk_row(c)

        def add_line():
            mk_row("#1A2430")
            push()

        ttk.Button(pal_frame, text="+ Добавить строку (цвет или градиент)", command=add_line).pack(anchor="w", pady=(6, 0))

    def open_text_style_editor(self, element):
        style = self.get_text_style(element)
        if self.style_editor_window and self.style_editor_window.winfo_exists():
            self.style_editor_window.destroy()
        win = tk.Toplevel(self.root)
        self.style_editor_window = win
        win.title(f"Стиль текста: {element}")
        win.geometry("520x700")
        win.configure(bg="#101722")

        shell = ttk.Frame(win, style="Panel.TFrame")
        shell.pack(fill="both", expand=True)
        scroll = tk.Canvas(shell, bg="#101722", highlightthickness=0)
        sb = ttk.Scrollbar(shell, orient="vertical", command=scroll.yview)
        scroll.configure(yscrollcommand=sb.set)
        scroll.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        body = ttk.Frame(scroll, padding=10, style="Panel.TFrame")
        body_window = scroll.create_window((0, 0), window=body, anchor="nw")

        def _sync_scroll(_event=None):
            scroll.configure(scrollregion=scroll.bbox("all"))
            scroll.itemconfigure(body_window, width=scroll.winfo_width())

        body.bind("<Configure>", _sync_scroll)
        scroll.bind("<Configure>", _sync_scroll)
        win.bind("<MouseWheel>", lambda e: scroll.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        _manual_style_keys = {
            "stroke_outer_width",
            "stroke_outer_enabled",
            "stroke_outer_color",
            "stroke_inner_enabled",
            "stroke_inner_width",
            "stroke_inner_color",
        }
        vars_map = {}
        for key, value in style.items():
            if key in _manual_style_keys:
                continue
            if str(key).startswith("_"):
                continue
            if key == "bg_colors":
                continue
            if isinstance(value, bool):
                vars_map[key] = tk.BooleanVar(value=value)
            elif isinstance(value, int):
                vars_map[key] = tk.IntVar(value=value)
            elif isinstance(value, float):
                vars_map[key] = tk.DoubleVar(value=value)
            else:
                vars_map[key] = tk.StringVar(value=str(value))

        def _outer_w_default() -> int:
            v = style.get("stroke_outer_width")
            if v is None:
                v = style.get("stroke_width", 0)
            return max(0, int(v or 0))

        _oe = style.get("stroke_outer_enabled")
        vars_map["stroke_outer_enabled"] = tk.BooleanVar(
            value=bool(_oe) if isinstance(_oe, bool) else (_outer_w_default() > 0)
        )
        vars_map["stroke_outer_width"] = tk.IntVar(value=_outer_w_default())
        _oc = style.get("stroke_outer_color") or style.get("stroke_color") or "#000000"
        vars_map["stroke_outer_color"] = tk.StringVar(value=str(_oc))
        vars_map["stroke_inner_enabled"] = tk.BooleanVar(value=bool(style.get("stroke_inner_enabled", False)))
        vars_map["stroke_inner_width"] = tk.IntVar(value=max(0, int(style.get("stroke_inner_width", 0) or 0)))
        vars_map["stroke_inner_color"] = tk.StringVar(value=str(style.get("stroke_inner_color") or "#000000"))

        def add_row(label, key, picker=False, parent=None):
            par = parent if parent is not None else body
            row = ttk.Frame(par, style="Panel.TFrame")
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label).pack(side="left")
            entry = ttk.Entry(row, textvariable=vars_map[key], width=20)
            entry.pack(side="right")
            if picker:
                swatch = tk.Label(row, width=2, bg=vars_map[key].get() or "#FFFFFF", relief="solid", bd=1)
                swatch.pack(side="right", padx=4)

                def update_swatch(*_):
                    try:
                        swatch.configure(bg=vars_map[key].get() or "#FFFFFF")
                    except Exception:
                        pass

                vars_map[key].trace_add("write", update_swatch)
                ttk.Button(row, text="Палитра", command=lambda k=key: self.pick_color_to_var(vars_map[k])).pack(side="right", padx=2)

        lf_grad = ttk.LabelFrame(body, text="Цвет и градиент", padding=8)
        lf_grad.pack(fill="x", pady=(0, 6))
        ttk.Checkbutton(lf_grad, text="Использовать градиент текста", variable=vars_map["use_gradient"]).pack(anchor="w")
        row_gs = ttk.Frame(lf_grad, style="Panel.TFrame")
        row_gs.pack(fill="x", pady=2)
        ttk.Label(row_gs, text="Начало / solid:").pack(side="left")
        ttk.Entry(row_gs, textvariable=vars_map["gradient_start"], width=14).pack(side="right")
        ttk.Button(row_gs, text="…", width=3, command=lambda: self.pick_color_to_var(vars_map["gradient_start"])).pack(side="right", padx=2)
        row_ge = ttk.Frame(lf_grad, style="Panel.TFrame")
        row_ge.pack(fill="x", pady=2)
        ttk.Label(row_ge, text="Конец градиента:").pack(side="left")
        ttk.Entry(row_ge, textvariable=vars_map["gradient_end"], width=14).pack(side="right")
        ttk.Button(row_ge, text="…", width=3, command=lambda: self.pick_color_to_var(vars_map["gradient_end"])).pack(side="right", padx=2)

        lf_out = ttk.LabelFrame(body, text="Внешняя обводка текста", padding=8)
        lf_out.pack(fill="x", pady=4)
        ttk.Checkbutton(lf_out, text="Включить внешнюю обводку", variable=vars_map["stroke_outer_enabled"]).pack(anchor="w")
        row_ow = ttk.Frame(lf_out, style="Panel.TFrame")
        row_ow.pack(fill="x", pady=2)
        ttk.Label(row_ow, text="Толщина (px):").pack(side="left")
        ttk.Entry(row_ow, textvariable=vars_map["stroke_outer_width"], width=8).pack(side="right")
        row_oc = ttk.Frame(lf_out, style="Panel.TFrame")
        row_oc.pack(fill="x", pady=2)
        ttk.Label(row_oc, text="Цвет:").pack(side="left")
        ttk.Entry(row_oc, textvariable=vars_map["stroke_outer_color"], width=14).pack(side="right")
        ttk.Button(row_oc, text="…", width=3, command=lambda: self.pick_color_to_var(vars_map["stroke_outer_color"])).pack(side="right", padx=2)

        lf_in = ttk.LabelFrame(body, text="Внутренняя обводка текста", padding=8)
        lf_in.pack(fill="x", pady=4)
        ttk.Checkbutton(lf_in, text="Включить внутреннюю обводку", variable=vars_map["stroke_inner_enabled"]).pack(anchor="w")
        row_iw = ttk.Frame(lf_in, style="Panel.TFrame")
        row_iw.pack(fill="x", pady=2)
        ttk.Label(row_iw, text="Толщина (px):").pack(side="left")
        ttk.Entry(row_iw, textvariable=vars_map["stroke_inner_width"], width=8).pack(side="right")
        row_ic = ttk.Frame(lf_in, style="Panel.TFrame")
        row_ic.pack(fill="x", pady=2)
        ttk.Label(row_ic, text="Цвет:").pack(side="left")
        ttk.Entry(row_ic, textvariable=vars_map["stroke_inner_color"], width=14).pack(side="right")
        ttk.Button(row_ic, text="…", width=3, command=lambda: self.pick_color_to_var(vars_map["stroke_inner_color"])).pack(side="right", padx=2)

        lf_sh = ttk.LabelFrame(body, text="Тень", padding=8)
        lf_sh.pack(fill="x", pady=4)
        ttk.Checkbutton(lf_sh, text="Включить тень", variable=vars_map["shadow_enabled"]).pack(anchor="w")
        add_row("Цвет тени:", "shadow_color", picker=True, parent=lf_sh)
        add_row("Прозрачность тени (0-255):", "shadow_opacity", parent=lf_sh)
        add_row("Размытие тени:", "shadow_blur", parent=lf_sh)
        add_row("Сдвиг X:", "shadow_dx", parent=lf_sh)
        add_row("Сдвиг Y:", "shadow_dy", parent=lf_sh)

        lf_bg = ttk.LabelFrame(body, text="Подложка под текстом", padding=8)
        lf_bg.pack(fill="x", pady=4)
        ttk.Checkbutton(lf_bg, text="Включить подложку", variable=vars_map["bg_enabled"]).pack(anchor="w")
        ttk.Checkbutton(
            lf_bg,
            text="Подложка по размеру текста (растёт и сжимается вместе со шрифтом)",
            variable=vars_map["bg_resizes_with_font"],
        ).pack(anchor="w", pady=(4, 0))
        ttk.Label(
            lf_bg,
            text="Если выключено — при первом превью запоминается размер подложки; «Размер (px)» меняет только шрифт.",
            foreground="#8EA3BE",
            background="#121826",
            wraplength=460,
        ).pack(anchor="w", pady=(0, 4))
        ttk.Checkbutton(lf_bg, text="Градиент подложки", variable=vars_map["bg_use_gradient"]).pack(anchor="w")
        add_row("Цвет подложки:", "bg_color", picker=True, parent=lf_bg)
        ttk.Label(
            lf_bg,
            text="Список цветов для случайной подложки настраивается слева в «Свойства выбранного элемента».",
            foreground="#8EA3BE",
            background="#121826",
            wraplength=460,
        ).pack(anchor="w", pady=(0, 6))
        add_row("Начало градиента:", "bg_gradient_start", picker=True, parent=lf_bg)
        add_row("Конец градиента:", "bg_gradient_end", picker=True, parent=lf_bg)
        add_row("Прозрачность подложки:", "bg_opacity", parent=lf_bg)
        add_row("Padding X:", "bg_padding_x", parent=lf_bg)
        add_row("Padding Y:", "bg_padding_y", parent=lf_bg)
        ttk.Checkbutton(
            lf_bg,
            text="Фиксированный размер подложки (не от размера шрифта)",
            variable=vars_map["bg_use_fixed_inner_box"],
        ).pack(anchor="w", pady=(4, 0))
        add_row("Ширина блока подложки (0 = авто):", "bg_fixed_width", parent=lf_bg)
        add_row("Высота блока подложки (0 = авто):", "bg_fixed_height", parent=lf_bg)
        ttk.Label(
            lf_bg,
            text="При включении задайте ширину и высоту (px) внутреннего прямоугольника; он центрируется на тексте. Отступы padding добавляются снаружи.",
            foreground="#8EA3BE",
            background="#121826",
            wraplength=460,
        ).pack(anchor="w", pady=(0, 4))
        add_row("Обводка подложки:", "bg_stroke_color", picker=True, parent=lf_bg)
        add_row("Толщина обводки подложки:", "bg_stroke_width", parent=lf_bg)
        row_bs = ttk.Frame(lf_bg, style="Panel.TFrame")
        row_bs.pack(fill="x", pady=3)
        ttk.Label(row_bs, text="Контур подложки:").pack(side="left")
        ttk.Checkbutton(row_bs, text="Внутри", variable=vars_map["bg_stroke_inside"]).pack(side="right", padx=(8, 0))
        ttk.Checkbutton(row_bs, text="Снаружи", variable=vars_map["bg_stroke_outside"]).pack(side="right", padx=(8, 0))

        row_img = ttk.Frame(lf_bg, style="Panel.TFrame")
        row_img.pack(fill="x", pady=3)
        ttk.Label(row_img, text="Картинка подложки").pack(side="left")
        ttk.Entry(row_img, textvariable=vars_map["bg_image"], width=18).pack(side="right")
        ttk.Button(
            row_img,
            text="Файл",
            command=lambda: vars_map["bg_image"].set(filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")]) or vars_map["bg_image"].get()),
        ).pack(side="right", padx=6)

        lf_font = ttk.LabelFrame(body, text="Шрифт", padding=8)
        lf_font.pack(fill="x", pady=(6, 4))
        row_font = ttk.Frame(lf_font, style="Panel.TFrame")
        row_font.pack(fill="x")
        font_lab = ttk.Label(row_font, text=f"Файл: {Path(self.get_element_font_path(element)).name}")
        font_lab.pack(side="left")

        def choose_font():
            p = filedialog.askopenfilename(filetypes=[("Fonts", "*.ttf *.otf *.ttc"), ("All", "*.*")])
            if p:
                self.set_element_font_path(element, p)
                font_lab.configure(text=f"Файл: {Path(p).name}")

        ttk.Button(row_font, text="Выбрать файл…", command=choose_font).pack(side="right")

        def apply_style():
            prev_colors = self._normalize_text_bg_palette(self.get_text_style(element).get("bg_colors"))
            new_style = {}
            for key, var in vars_map.items():
                val = var.get()
                if isinstance(var, tk.IntVar):
                    new_style[key] = int(val)
                elif isinstance(var, tk.DoubleVar):
                    new_style[key] = float(val)
                elif isinstance(var, tk.BooleanVar):
                    new_style[key] = bool(val)
                else:
                    new_style[key] = str(val)
            new_style["bg_colors"] = prev_colors
            new_style["stroke_width"] = int(new_style.get("stroke_outer_width", 0))
            new_style["stroke_color"] = str(new_style.get("stroke_outer_color") or "#000000")
            self.settings.text_styles[element] = new_style
            self._reset_text_bg_random_picks()
            self._invalidate_element_inspector()
            self.refresh_preview()
            self.save_settings(show_message=False, apply_first=False)

        btns = ttk.Frame(body, style="Panel.TFrame")
        btns.pack(fill="x", pady=(12, 0))
        def reset_bg_snap_then_apply():
            vars_map["bg_snap_inner_w"].set(0)
            vars_map["bg_snap_inner_h"].set(0)
            apply_style()

        ttk.Button(btns, text="Сброс запомненной подложки", command=reset_bg_snap_then_apply).pack(side="left")
        ttk.Button(btns, text="Закрыть", command=win.destroy).pack(side="right")
        ttk.Button(btns, text="Применить", style="Accent.TButton", command=apply_style).pack(side="right", padx=6)

    def draw_watermark_rgba_layer(self, vw: int, vh: int):
        """Полноэкранный RGBA-слой вотермарки; (None, None) если выключено."""
        if bool(getattr(self.settings, "watermark_hidden", False)):
            return None, None
        text = self.settings.watermark_text.strip()
        if not text:
            return None, None
        overlay = Image.new("RGBA", (vw, vh), (0, 0, 0, 0))
        try:
            font = ImageFont.truetype(self.settings.watermark_font, self.settings.watermark_font_size)
        except Exception:
            font = ImageFont.load_default()
        x, y = self.settings.watermark_x, self.settings.watermark_y
        style = self.get_text_style("watermark")
        style = {**style}
        style["_bg_random_key"] = "watermark"
        style["gradient_start"] = self.settings.watermark_color
        style["shadow_opacity"] = self.settings.watermark_opacity
        bbox = self.draw_styled_text(
            overlay,
            self.transform_text_case(text),
            x,
            y,
            font,
            style,
            align="left",
            anchor="la",
            spacing=2,
            persist_style_element="watermark",
        )
        return overlay, bbox

    def draw_watermark_on_frame(self, frame):
        wm, bbox = self.draw_watermark_rgba_layer(frame.size[0], frame.size[1])
        if wm is None:
            return None
        base = frame.convert("RGBA")
        base = Image.alpha_composite(base, wm)
        frame.paste(base.convert("RGB"))
        return bbox

    def sync_controls_from_settings(self):
        for key in self.controls:
            self.controls[key].set(str(getattr(self.settings, key)))

    def _hashtag_lines_for_output(self) -> list[str]:
        raw = (getattr(self.settings, "hashtags_pool", None) or "").strip()
        if raw:
            lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            if lines:
                return lines
        return self.creator.load_hashtag_lines()

    def sample_output_hashtags(self, n: int) -> list[str]:
        tags = self._hashtag_lines_for_output()
        n = max(0, int(n))
        if n == 0 or not tags:
            return []
        if len(tags) >= n:
            return random.sample(tags, n)
        return random.choices(tags, k=n)

    def _output_name_pool_lines(self, pool: str):
        return [x.strip() for x in (pool or "").splitlines() if x.strip()]

    def _output_name_pick_prefix(self) -> str:
        lines = self._output_name_pool_lines(getattr(self.settings, "output_name_prefix_pool", "") or "")
        if lines:
            return random.choice(lines)
        return random.choice(self.creator.name_prefixes)

    def _output_name_pick_emoji(self) -> str:
        lines = self._output_name_pool_lines(getattr(self.settings, "output_name_emoji_pool", "") or "")
        return random.choice(lines) if lines else ""

    def _output_name_pick_text(self) -> str:
        lines = self._output_name_pool_lines(getattr(self.settings, "output_name_text_pool", "") or "")
        return random.choice(lines) if lines else ""

    def _normalize_output_name_parts(self, raw) -> list:
        allowed = {"hero", "headline", "hashtags", "emoji", "text", "prefix", "literal"}
        if not isinstance(raw, list) or len(raw) == 0:
            return default_output_name_parts()
        out = []
        for p in raw:
            if not isinstance(p, dict):
                continue
            t = str(p.get("type") or "").strip().lower()
            if t not in allowed:
                continue
            if t == "literal":
                out.append({"type": "literal", "value": str(p.get("value", ""))})
            else:
                out.append({"type": t})
        return out if out else default_output_name_parts()

    def _headline_for_output_name(self, headline: str | None) -> str:
        if headline is not None:
            hl = str(headline).strip()
        elif hasattr(self, "headline_var"):
            hl = str(self.headline_var.get() or "").strip()
        else:
            hl = ""
        hl = re.sub(r'[\\/:*?"<>|]', "", hl)
        hl = re.sub(r"\s+", " ", hl).strip()
        return hl[:160]

    def _make_output_name_from_parts(self, hero: str, parts: list, headline: str | None = None) -> str:
        hero_safe = re.sub(r'[\\/:*?"<>|]', "", str(hero).strip())
        n_tags = int(getattr(self.settings, "output_hashtag_count", 3) or 0)
        chunks = []
        for p in parts:
            if not isinstance(p, dict):
                continue
            t = str(p.get("type") or "").strip().lower()
            if t == "hero":
                # Чтобы префикс и имя не слипались: пробел перед именем
                if chunks and chunks[-1] and not str(chunks[-1])[-1].isspace():
                    chunks.append(" ")
                chunks.append(hero_safe)
            elif t == "headline":
                hl_safe = self._headline_for_output_name(headline)
                if hl_safe:
                    if chunks and chunks[-1] and not str(chunks[-1])[-1].isspace():
                        chunks.append(" ")
                    chunks.append(hl_safe)
            elif t == "hashtags":
                tags_list = self.sample_output_hashtags(n_tags)
                ht = " ".join(str(x).strip() for x in tags_list if str(x).strip()).strip()
                if chunks and chunks[-1] and ht and not str(chunks[-1])[-1].isspace():
                    chunks.append(" ")
                chunks.append(ht)
            elif t == "emoji":
                chunks.append(self._output_name_pick_emoji())
            elif t == "text":
                chunks.append(self._output_name_pick_text())
            elif t == "prefix":
                chunks.append(self._output_name_pick_prefix())
            elif t == "literal":
                v = str(p.get("value", ""))
                chunks.append(v)
                # Чтобы свой текст и имя не слипались: один пробел после своего текста, если его не поставили вручную
                if v and (not v[-1].isspace()):
                    chunks.append(" ")
        name = "".join(chunks)
        name = re.sub(r"\s+", " ", name).strip()
        name = _ensure_spaces_before_hashtags_in_filename(name)
        name = re.sub(r'[\\/:*?"<>|]', "", name)
        if not name.lower().endswith(".mp4"):
            name = (name.rstrip(". ") + ".mp4") if name else hero_safe + ".mp4"
        base = name[:-4] if name.lower().endswith(".mp4") else name
        if not base.strip():
            name = hero_safe + ".mp4"
        else:
            name = base + ".mp4"
        return re.sub(r'[\\/:*?"<>|]', "", name)

    def make_output_name(self, hero, headline: str | None = None):
        hero_safe = re.sub(r'[\\/:*?"<>|]', "", str(hero).strip())
        parts = getattr(self.settings, "output_name_parts", None)
        if isinstance(parts, list) and len(parts) > 0:
            norm = self._normalize_output_name_parts(parts)
            return self._make_output_name_from_parts(hero, norm, headline=headline)

        tpl = (getattr(self.settings, "output_name_template", None) or "").strip()
        if not tpl:
            tpl = "{prefix} [имя] {hashtags}"

        n_tags = int(getattr(self.settings, "output_hashtag_count", 3) or 0)
        tags_list = self.sample_output_hashtags(n_tags)
        hashtags_str = " ".join(tags_list).strip()

        def lines_from_pool(pool: str):
            return [x.strip() for x in (pool or "").splitlines() if x.strip()]

        def pick_prefix() -> str:
            lines = lines_from_pool(getattr(self.settings, "output_name_prefix_pool", "") or "")
            if lines:
                return random.choice(lines)
            return random.choice(self.creator.name_prefixes)

        def pick_emoji() -> str:
            lines = lines_from_pool(getattr(self.settings, "output_name_emoji_pool", "") or "")
            return random.choice(lines) if lines else ""

        def pick_text() -> str:
            lines = lines_from_pool(getattr(self.settings, "output_name_text_pool", "") or "")
            return random.choice(lines) if lines else ""

        out = tpl
        out = out.replace("[имя]", hero_safe)
        out = out.replace("[ФИО героя]", hero_safe)
        out = out.replace("{hero}", hero_safe)
        out = out.replace("{hashtags}", hashtags_str)
        while "{prefix}" in out:
            out = out.replace("{prefix}", pick_prefix(), 1)
        while "{emoji}" in out:
            out = out.replace("{emoji}", pick_emoji(), 1)
        while "{text}" in out:
            out = out.replace("{text}", pick_text(), 1)

        name = re.sub(r"\s+", " ", out).strip()
        name = _ensure_spaces_before_hashtags_in_filename(name)
        name = re.sub(r'[\\/:*?"<>|]', "", name)
        if not name.lower().endswith(".mp4"):
            name = (name.rstrip(". ") + ".mp4") if name else hero_safe + ".mp4"
        base = name[:-4] if name.lower().endswith(".mp4") else name
        if not base.strip():
            name = hero_safe + ".mp4"
        else:
            name = base + ".mp4"
        return re.sub(r'[\\/:*?"<>|]', "", name)

    def resolve_video_output_dir(self) -> Path:
        """Каталог вывода: STUDIO_OUTPUT_DIR, иначе Videos/<STUDIO_VIDEOS_SUBFOLDER>, иначе Videos/<вотермарка>, иначе video_output_dir, иначе videos/."""
        env = os.environ.get("STUDIO_OUTPUT_DIR", "").strip()
        if env:
            return Path(env).expanduser().resolve()
        sub = os.environ.get("STUDIO_VIDEOS_SUBFOLDER", "").strip()
        if sub:
            safe = sanitize_watermark_folder(sub)
            return (Path.cwd() / "Videos" / safe).resolve()
        wm = (self.settings.watermark_text or "").strip()
        if wm:
            safe = sanitize_watermark_folder(wm)
            return (Path.cwd() / "Videos" / safe).resolve()
        extra = (self.settings.video_output_dir or "").strip()
        if extra:
            return Path(extra).expanduser().resolve()
        return (Path.cwd() / "videos").resolve()

    def make_card_background_clip(self, media_path, dur, card_x, card_y):
        p = Path(media_path).expanduser()
        if not p.is_file():
            raise FileNotFoundError(f"card_bg_media not found: {p}")
        suf = p.suffix.lower()
        cw, ch = int(self.settings.card_width), int(self.settings.card_height)
        pos = (int(card_x), int(card_y))
        if suf in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
            return VideoFileClip(str(p)).subclip(0, dur).resize((cw, ch)).set_position(pos)
        if suf == ".gif":
            # GIF через кадры PIL; MoviePy ImageSequenceClip ждёт numpy (H,W,3), не PIL.Image.
            gif = Image.open(str(p))
            try:
                frames_np = []
                durations = []
                n = max(1, int(getattr(gif, "n_frames", 1)))
                for i in range(n):
                    gif.seek(i)
                    im = gif.convert("RGB").resize((cw, ch), Image.LANCZOS)
                    frames_np.append(np.asarray(im, dtype=np.uint8))
                    durations.append(max(20, int(gif.info.get("duration", 100))))
            finally:
                try:
                    gif.close()
                except Exception:
                    pass
            total_ms = max(1, sum(durations))
            fps = max(1, min(60, int(len(frames_np) / (total_ms / 1000))))
            clip = ImageSequenceClip(frames_np, fps=fps)
            if clip.duration < dur:
                clip = clip.fx(vfx.loop, duration=dur)
            return clip.subclip(0, dur).set_position(pos)
        return ImageClip(str(p)).set_duration(dur).resize((cw, ch)).set_position(pos)

    def build_main_bg_clip(self, dur: float, photo_path: str):
        """Фон 1080×1920 для экспорта: папка с видео / цвет+градиент / размытое фото политика."""
        vw, vh = 1080, 1920
        mode = (getattr(self.settings, "video_bg_mode", "folder") or "folder").strip().lower()
        if mode == "photo_blur":
            pfb = (getattr(self.settings, "video_bg_photo_path", "") or "").strip() or (photo_path or "").strip()
            if not pfb:
                pfb = (self.current_image_path or "").strip()
            img = self._make_photo_blur_fullframe(vw, vh, pfb)
            arr = np.asarray(img, dtype=np.uint8)
            return ImageClip(arr).set_duration(dur)
        if mode == "flat":
            spec = (getattr(self.settings, "video_bg_spec", "") or "#1a1f2a").strip()
            grad = self.parse_card_bg_linear_gradient(spec)
            if grad:
                c1, c2 = grad
                gimg = self.gradient_image((vw, vh), c1, c2).convert("RGB")
            else:
                try:
                    rgb = ImageColor.getrgb(spec)
                except Exception:
                    rgb = (26, 31, 42)
                gimg = Image.new("RGB", (vw, vh), rgb)
            arr = np.asarray(gimg, dtype=np.uint8)
            return ImageClip(arr).set_duration(dur)
        folder = (getattr(self.settings, "video_bg_folder", "") or "bg").strip() or "bg"
        bg = self.creator.get_random_file(folder, (".mp4", ".mov", ".avi", ".mkv", ".webm"))
        if not bg:
            return ColorClip((vw, vh), (40, 40, 40)).set_duration(dur)
        pth = str(Path(bg).expanduser())
        seamless = bool(getattr(self.settings, "video_bg_seamless_loop", False))
        vc = None
        if seamless:
            try:
                _raw = VideoFileClip(pth).resize((vw, vh))
                try:
                    vc = _raw.without_audio()
                except Exception:
                    vc = _raw
                D = float(vc.duration or 0) or 0.001
                fade_s = float(getattr(self.settings, "video_bg_loop_crossfade_sec", 0.75) or 0.75)
                seg_s = float(getattr(self.settings, "video_bg_loop_segment_sec", 0) or 0)
                seed = f"{pth}|{float(dur):.4f}"
                L, fade, t0 = self._compute_seamless_bg_loop_params_from_d(D, float(dur), fade_s, seg_s, seed)
                if fade < 0.02 or L < 2.0 * fade + 0.05:
                    vc.close()
                    vc = None
                    return VideoFileClip(pth).subclip(0, min(float(dur), max(0.05, D))).resize((vw, vh))
                fps = float(vc.fps or 30) or 30.0

                def make_frame(tt):
                    return self._seamless_loop_frame_rgb(vc, float(tt), L, fade, t0, D)

                out = VideoClip(make_frame=make_frame, duration=float(dur))
                out = out.set_fps(fps)
                out._seamless_vc_keepalive = vc  # удерживаем reader до конца композита
                return out
            except Exception as ex:
                print(f"[BG_LOOP] {ex!r}", flush=True)
                if vc is not None:
                    try:
                        vc.close()
                    except Exception:
                        pass
        v0 = VideoFileClip(pth)
        dmax = min(float(dur), max(0.1, float(v0.duration or dur)))
        return v0.subclip(0, dmax).resize((vw, vh))

    def _save_render_progress_thumb(self, final_clip) -> None:
        """Кадр для веб-модалки «Рендер»: пишется в корень проекта, отдаётся GET /api/render-thumb."""
        try:
            arr = np.asarray(final_clip.get_frame(0))
            if arr.ndim == 2:
                im = Image.fromarray(arr, mode="L").convert("RGB")
            elif arr.ndim == 3 and arr.shape[2] >= 3:
                im = Image.fromarray(arr[:, :, :3], mode="RGB")
            else:
                return
            w, h = im.size
            max_edge = 540
            if max(w, h) > max_edge:
                sc = max_edge / float(max(w, h))
                im = im.resize((max(1, int(w * sc)), max(1, int(h * sc))), Image.LANCZOS)
            _RENDER_THUMB_PATH.parent.mkdir(parents=True, exist_ok=True)
            im.save(_RENDER_THUMB_PATH, format="PNG", optimize=True)
        except Exception as ex:
            print(f"[THUMB] {ex!r}", flush=True)

    def generate_video_for(self, hero, image_path, summary_text, dates_text="", render_duration=None, card_title=None):
        self._reset_text_bg_random_picks()
        self._photo_anim_kind_override = None
        if _is_missing_bio_placeholder(summary_text):
            print(
                "[SKIP] Рендер отменён: нет текста описания. Вставьте текст или нажмите «Случайный».",
                flush=True,
            )
            return None
        lo, lim = self._subtitle_word_bounds()
        sw = self._count_subtitle_words(summary_text)
        if sw < lo:
            print(
                f"[SKIP] Рендер отменён: в описании {sw} слов, нужно не меньше {lo} (максимум {lim}).",
                flush=True,
            )
            return None
        title_line = (card_title or "").strip()
        if not title_line and hasattr(self, "headline_var"):
            title_line = self.headline_var.get().strip()
        if not title_line:
            title_line = self.creator.pick_random_headline(self.settings.headline_topics)
        out_dir = self.resolve_video_output_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        output_name = self.make_output_name(hero, headline=title_line)
        output = str(out_dir / output_name)
        if render_duration is not None:
            dur = float(render_duration)
        else:
            ev_min = (os.environ.get("STUDIO_DURATION_MIN", "") or "").strip()
            ev_max = (os.environ.get("STUDIO_DURATION_MAX", "") or "").strip()
            if ev_min and ev_max:
                try:
                    lo = float(ev_min)
                    hi = float(ev_max)
                    lo, hi = min(lo, hi), max(lo, hi)
                    dur = random.uniform(lo, hi)
                except Exception:
                    dur = random.uniform(self.settings.duration_min, self.settings.duration_max)
            else:
                dur = random.uniform(self.settings.duration_min, self.settings.duration_max)
        dur = max(0.5, dur)
        print("\n" + "=" * 72)
        print(f"[START] {hero}")
        print(f"[OUT]   {output}")
        print(f"[TIME]  {dur:.2f}s")

        music = None
        while True:
            m = self.creator.get_random_file("music", (".mp3", ".wav", ".m4a"))
            if not m:
                break
            try:
                clip = AudioFileClip(m)
                if clip.duration >= dur:
                    music = m
                    clip.close()
                    break
                clip.close()
            except Exception:
                continue

        try:
            out_fps = int(float(os.environ.get("STUDIO_FPS", "30") or 30))
        except Exception:
            out_fps = 30
        out_fps = max(1, min(120, out_fps))

        self.ensure_timeline_layers()

        cw = int(self.settings.card_width)
        ch = int(self.settings.card_height)
        card_x = int((1080 - cw) / 2 + self.settings.card_offset_x)
        card_x = max(-cw + 60, min(1080 - 60, card_x))
        card_y = self._layout_card_center_vertical(1920, ch)

        dates_for_card = (dates_text or "").strip()
        card_parts, _card_decomp_meta = self.render_card_decomposed(
            title_line,
            summary_text,
            dates_for_card,
            include_background=not self.card_bg_media_layer_active(),
            t=0.0,
            dur=dur,
            text_frame_wh=(1080, 1920),
            card_rect=(card_x, card_y, cw, ch),
        )
        temp_root = (_REPO_ROOT / "temp")
        temp_root.mkdir(parents=True, exist_ok=True)
        render_tmp_dir = temp_root / f"render_{os.getpid()}_{random.getrandbits(32):08x}"
        render_tmp_dir.mkdir(parents=True, exist_ok=True)
        card_part_paths: dict[str, tuple[str, int, int]] = {}
        for key, fname in (
            ("backdrop", "card_part_backdrop.png"),
            ("title", "card_part_title.png"),
            ("subtitle", "card_part_subtitle.png"),
            ("dates", "card_part_dates.png"),
        ):
            raw = card_parts[key].convert("RGBA")
            dec, ax, ay = self.decorate_layer_rgba(raw, "card")
            if dec.getbbox() is not None:
                part_file = render_tmp_dir / fname
                dec.save(part_file)
                card_part_paths[key] = (str(part_file), ax, ay)

        seq = 0
        clips_meta: list[tuple[int, int, object]] = []

        def push_timed(layer_id: str, clip) -> None:
            nonlocal seq
            if clip is None:
                return
            z = self._timeline_z(layer_id)
            tc = self._time_window_clip(clip, layer_id, dur)
            if tc is None:
                return
            clips_meta.append((z, seq, tc))
            seq += 1

        clips_meta.append((-100000, seq, ColorClip((1080, 1920), color=(0, 0, 0)).set_duration(dur)))
        seq += 1

        bg_clip = self.build_main_bg_clip(dur, image_path)
        push_timed("background", bg_clip)

        glow_seg = self._timeline_segment_clamped("glow", dur)
        if bool(getattr(self.settings, "glow_overlay_enabled", True)) and glow_seg is not None:
            vw0, vh0 = 1080, 1920
            # MoviePy ожидает RGB (H,W,3); PIL даёт RGBA — иначе «could not broadcast … (…,4) into (…,3)».
            _glow_cache = [None, None]  # [t, rgba ndarray]

            def _glow_rgba(tt: float) -> np.ndarray:
                tt = float(tt)
                if _glow_cache[0] != tt:
                    pil_img = self._render_glow_overlay_rgba(vw0, vh0, tt, dur)
                    _glow_cache[0] = tt
                    _glow_cache[1] = np.asarray(pil_img, dtype=np.uint8)
                return _glow_cache[1]

            def make_glow_frame(tt):
                arr = _glow_rgba(float(tt))
                return np.ascontiguousarray(arr[:, :, :3])

            def make_glow_mask(tt):
                arr = _glow_rgba(float(tt))
                return np.ascontiguousarray(arr[:, :, 3].astype(np.float32) / 255.0)

            try:
                mclip = VideoClip(make_frame=make_glow_mask, ismask=True, duration=float(dur)).set_fps(float(out_fps))
                gclip = VideoClip(make_frame=make_glow_frame, duration=float(dur)).set_fps(float(out_fps)).set_mask(mclip)
                push_timed("glow", gclip)
            except Exception as ex:
                print(f"[GLOW] {ex!r}", flush=True)

        card_bg_media = self.settings.card_bg_media.strip()
        card_vis = not bool(getattr(self.settings, "card_hidden", False))
        card_seg_ok = self._timeline_segment_clamped("card", dur) is not None
        if card_vis and card_seg_ok and self.card_bg_media_layer_active() and card_bg_media:
            try:
                card_bg_clip = self.make_card_background_clip(card_bg_media, dur, card_x, card_y)
                push_timed("card", card_bg_clip)
                print(f"[CARD_BG] ok {card_bg_media}", flush=True)
            except Exception as ex:
                import traceback

                print(f"[CARD_BG] error: {ex!r}", flush=True)
                traceback.print_exc()
                if not bool(getattr(self.settings, "card_backdrop_hidden", False)):
                    cw, ch = self.settings.card_width, self.settings.card_height
                    cspec = self.resolved_card_bg_spec()
                    grad = self.parse_card_bg_linear_gradient(cspec)
                    if grad:
                        c1, c2 = grad
                        gimg = self.gradient_image((cw, ch), c1, c2).convert("RGB")
                        push_timed("card", ImageClip(np.asarray(gimg, dtype=np.uint8)).set_duration(dur).set_position((card_x, card_y)))
                    else:
                        try:
                            rgb = ImageColor.getrgb(cspec)
                        except Exception:
                            rgb = (40, 40, 40)
                        push_timed("card", ColorClip((cw, ch), color=rgb).set_duration(dur).set_position((card_x, card_y)))
                    print("[CARD_BG] fallback: градиент или цвет карточки из пресета", flush=True)
        elif card_vis and card_seg_ok and not bool(getattr(self.settings, "card_backdrop_hidden", False)):
            bd_slot = card_part_paths.get("backdrop")
            if bd_slot:
                fn, ax, ay = bd_slot
                try:
                    bd_clip = ImageClip(fn, transparent=True).set_duration(dur).set_position((card_x - ax, card_y - ay))
                except TypeError:
                    bd_clip = ImageClip(fn).set_duration(dur).set_position((card_x - ax, card_y - ay))
                push_timed("card", bd_clip)
            else:
                cw, ch = self.settings.card_width, self.settings.card_height
                cspec = self.resolved_card_bg_spec()
                grad = self.parse_card_bg_linear_gradient(cspec)
                if grad:
                    c1, c2 = grad
                    gimg = self.gradient_image((cw, ch), c1, c2).convert("RGB")
                    arr = np.asarray(gimg)
                    push_timed("card", ImageClip(arr).set_duration(dur).set_position((card_x, card_y)))
                else:
                    try:
                        rgb = ImageColor.getrgb(cspec)
                    except Exception:
                        rgb = (255, 255, 255)
                    push_timed("card", ColorClip((cw, ch), color=rgb).set_duration(dur).set_position((card_x, card_y)))

        text_clips_frame = (_card_decomp_meta.get("_coords") == "viewport")
        for tid, pkey in (("title", "title"), ("subtitle", "subtitle"), ("dates", "dates")):
            if pkey == "dates" and not dates_for_card.strip():
                continue
            slot = card_part_paths.get(pkey)
            if not slot:
                continue
            if self._timeline_segment_clamped(tid, dur) is None:
                continue
            fn, ax, ay = slot
            pos = (-int(ax), -int(ay)) if text_clips_frame else (card_x - ax, card_y - ay)
            try:
                tclip = ImageClip(fn, transparent=True).set_duration(dur).set_position(pos)
            except TypeError:
                tclip = ImageClip(fn).set_duration(dur).set_position(pos)
            push_timed(tid, tclip)

        wm_clip = None
        if self.settings.watermark_text.strip() and not bool(getattr(self.settings, "watermark_hidden", False)):
            wm_rgba, _bb = self.draw_watermark_rgba_layer(1080, 1920)
            if wm_rgba is not None:
                wm_path = render_tmp_dir / "watermark.png"
                wm_rgba.save(wm_path)
                try:
                    wm_clip = ImageClip(str(wm_path), transparent=True).set_duration(dur).set_position((0, 0))
                except TypeError:
                    wm_clip = ImageClip(str(wm_path)).set_duration(dur).set_position((0, 0))
                push_timed("watermark", wm_clip)

        ov_list = getattr(self.settings, "scene_overlays", None)
        if isinstance(ov_list, list) and ov_list:
            for item in ov_list:
                if not isinstance(item, dict) or item.get("hidden"):
                    continue
                oid_raw = str(item.get("id") or "").strip()
                oid = re.sub(r"[^a-zA-Z0-9_\-]", "", oid_raw)[:80]
                if not oid:
                    continue
                lid = f"overlay:{oid}"
                seg_ov = self._timeline_segment_clamped(lid, dur)
                if seg_ov is None:
                    continue
                st_ov, en_ov = seg_ov
                seg_len = max(0.04, en_ov - st_ov)
                kind = str(item.get("kind") or "text").strip().lower()
                z_ov = self._timeline_z(lid)
                if kind in ("image", "gif"):
                    src = str(item.get("src") or "").strip()
                    p = Path(src).expanduser()
                    if not src or not p.is_file():
                        continue
                    if self._overlay_item_is_animated_gif(item, p):
                        gc = self._make_overlay_gif_clip(src, item, seg_len, 1080, 1920)
                        if gc:
                            try:
                                oc = gc.set_start(st_ov)
                            except Exception:
                                oc = gc
                            clips_meta.append((z_ov, seq, oc))
                            seq += 1
                        continue
                ov_rgba = self.render_scene_overlays_rgba((1080, 1920), 0.0, dur, None, only_hkey=lid)
                arr = np.asarray(ov_rgba.convert("RGBA"), dtype=np.uint8)
                try:
                    oc = ImageClip(arr, transparent=True).set_duration(seg_len).set_position((0, 0)).set_start(st_ov)
                except TypeError:
                    oc = ImageClip(arr).set_duration(seg_len).set_position((0, 0)).set_start(st_ov)
                clips_meta.append((z_ov, seq, oc))
                seq += 1

        clips_meta.sort(key=lambda x: (x[0], x[1]))
        clips = [c for _z, _s, c in clips_meta]
        final = CompositeVideoClip(clips, size=(1080, 1920)).set_duration(dur).subclip(0, dur)
        if music:
            audio_clip = AudioFileClip(music).subclip(0, dur).volumex(0.35).audio_fadeout(1.2)
            final = final.set_audio(audio_clip)

        prof = (os.environ.get("STUDIO_EXPORT_PROFILE", "") or "1080p").strip().lower()
        size_map = {"1080p": (1080, 1920), "720p": (720, 1280), "480p": (480, 854)}
        tw, th = size_map.get(prof, (1080, 1920))
        if (tw, th) != (1080, 1920):
            final = final.resize((tw, th))
        self._save_render_progress_thumb(final)
        try:
            br_mbps = int(os.environ.get("STUDIO_VIDEO_BITRATE_MBPS", "0") or 0)
        except Exception:
            br_mbps = 0
        br_mbps = max(0, min(20, br_mbps))
        write_kw = dict(
            fps=out_fps,
            codec="libx264",
            audio_codec="aac",
            logger=PipeFriendlyBarLogger(),
            verbose=True,
        )
        write_kw["temp_audiofile"] = str(render_tmp_dir / "temp_audio.m4a")
        write_kw["remove_temp"] = True
        if br_mbps > 0:
            write_kw["ffmpeg_params"] = ["-b:v", f"{br_mbps}M"]

        print(
            f"[FX] glow enabled={bool(getattr(self.settings, 'glow_overlay_enabled', True))} "
            f"opacity={float(getattr(self.settings, 'glow_overlay_opacity', 0.38) or 0):.2f}",
            flush=True,
        )
        print(f"[RENDER] profile={prof or '1080p'} fps={out_fps} bitrate_mbps={br_mbps or 'default'}", flush=True)
        print("[RENDER] MoviePy progress below:", flush=True)
        try:
            final.write_videofile(output, **write_kw)
            final.close()
            print(f"[DONE] {output}")
            self._photo_anim_kind_override = None
            return output
        finally:
            try:
                shutil.rmtree(render_tmp_dir, ignore_errors=True)
            except Exception:
                pass

    def generate_current(self):
        self.apply_controls()
        hero = self.hero_var.get().strip() or self.current_hero or "Гороскоп"
        bio = self.bio_box.get("1.0", "end").strip()
        dates = self.dates_var.get().strip()
        if not bio.strip():
            if self.headless:
                print("[ERROR] Нет описания (12 знаков). Нажмите «Случайный» или введите текст.")
            else:
                messagebox.showerror("Ошибка", "Нет описания. Нажмите «Случайный» или введите текст знаков.")
            return
        print("[render] UI закрыт, запускаю генерацию текущего видео...")
        if not self.headless:
            self.root.destroy()
        try:
            hl = self.headline_var.get().strip() if hasattr(self, "headline_var") else ""
            path = self.generate_video_for(hero, "", bio, dates_text=dates, card_title=hl)
            if path:
                print(f"[render] готово: {path}")
        except Exception as e:
            print(f"[render] ошибка: {e}")

    def generate_batch(self):
        self.apply_controls()
        try:
            count = int(self.batch_count_var.get())
        except ValueError:
            if self.headless:
                print("[ERROR] Количество видео должно быть числом.")
            else:
                messagebox.showerror("Ошибка", "Количество видео должно быть числом.")
            return
        if count <= 0:
            return

        print("[BATCH] UI закрыт, запускаю массовую генерацию...")
        if not self.headless:
            self.root.destroy()
        print(f"[BATCH] План: {count} видео")
        ok = 0
        for i in range(count):
            print("\n" + "-" * 72)
            print(f"[BATCH] {i+1}/{count}")
            self.pick_random_horoscope()
            hero = self.hero_var.get().strip() or self.current_hero or "Гороскоп"
            summary = self.bio_box.get("1.0", "end").strip()
            dates = self.dates_var.get().strip()
            hl = self.headline_var.get().strip() if hasattr(self, "headline_var") else ""
            try:
                path = self.generate_video_for(hero, "", summary, dates_text=dates, card_title=hl)
                if path:
                    ok += 1
            except Exception as e:
                import traceback

                print(f"[ERROR] failed batch item {i+1}: {e!r}", flush=True)
                traceback.print_exc()
                continue
        print("\n" + "=" * 72)
        print(f"[BATCH DONE] Готово: {ok}/{count} видео")

    def studio_headless_render_current(self) -> int:
        self.apply_controls()
        hero = self.hero_var.get().strip() or self.current_hero or "Гороскоп"
        bio = self.bio_box.get("1.0", "end").strip()
        dates = self.dates_var.get().strip()
        if not bio.strip():
            print("[ERROR] Нет описания (12 знаков). Заполните сцену или вызовите random_horoscope.")
            return 2
        try:
            hl = self.headline_var.get().strip() if hasattr(self, "headline_var") else ""
            path = self.generate_video_for(hero, "", bio, dates_text=dates, card_title=hl)
            if not path:
                return 3
            print(f"[render] готово: {path}")
            return 0
        except Exception as e:
            print(f"[render] ошибка: {e}")
            return 1

    def studio_headless_render_batch(self, count: int) -> int:
        self.batch_count_var.set(str(int(count)))
        self.apply_controls()
        if count <= 0:
            print("[ERROR] count must be > 0")
            return 2

        print(f"[BATCH] План: {count} видео")
        ok = 0
        for i in range(count):
            print("\n" + "-" * 72)
            print(f"[BATCH] {i+1}/{count}")
            self.pick_random_horoscope()
            hero = self.hero_var.get().strip() or self.current_hero or "Гороскоп"
            summary = self.bio_box.get("1.0", "end").strip()
            dates = self.dates_var.get().strip()
            hl = self.headline_var.get().strip() if hasattr(self, "headline_var") else ""
            try:
                path = self.generate_video_for(hero, "", summary, dates_text=dates, card_title=hl)
                if path:
                    ok += 1
            except Exception as e:
                import traceback

                print(f"[ERROR] failed batch item {i+1}: {e!r}", flush=True)
                traceback.print_exc()
                continue
        print("\n" + "=" * 72)
        print(f"[BATCH DONE] Готово: {ok}/{count} видео")
        return 0 if ok > 0 else 1

    def save_settings(self, show_message=True, apply_first=True):
        if apply_first:
            self.apply_controls()
        self.settings_path.write_text(json.dumps(asdict(self.settings), ensure_ascii=False, indent=2), encoding="utf-8")
        if show_message:
            messagebox.showinfo("Сохранено", f"Пресет сохранён: {self.settings_path}")

    def save_preset_to_file(self):
        """Сохранить текущие настройки в JSON по пути, который выберет пользователь (не только ui_settings.json)."""
        self.apply_controls()
        presets_dir = Path(__file__).resolve().parent / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(
            title="Сохранить пресет в файл",
            defaultextension=".json",
            filetypes=[("JSON пресет", "*.json"), ("Все файлы", "*.*")],
            initialdir=str(presets_dir),
            initialfile="horoscope_studio_preset.json",
        )
        if not path:
            return
        try:
            Path(path).expanduser().write_text(
                json.dumps(asdict(self.settings), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            messagebox.showinfo("Сохранено", f"Пресет записан в файл:\n{path}")
        except OSError as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")

    def load_preset_from_file(self):
        """Загрузить пресет из выбранного JSON (как ui_settings.json)."""
        presets_dir = Path(__file__).resolve().parent / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        path = filedialog.askopenfilename(
            title="Загрузить пресет из файла",
            filetypes=[("JSON пресет", "*.json"), ("Все файлы", "*.*")],
            initialdir=str(presets_dir),
        )
        if not path:
            return
        try:
            raw = Path(path).expanduser().read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, UnicodeDecodeError) as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать файл:\n{e}")
            return
        except json.JSONDecodeError as e:
            messagebox.showerror("Ошибка", f"Некорректный JSON:\n{e}")
            return
        if not isinstance(data, dict):
            messagebox.showerror("Ошибка", "В файле должен быть JSON-объект с полями пресета.")
            return
        if not self.apply_settings_dict(data, refresh=True):
            messagebox.showerror("Ошибка", "Не удалось применить пресет (проверьте формат или версию приложения).")
            return
        self._seed_hashtags_pool_from_file_if_empty()
        messagebox.showinfo("Загружено", f"Пресет применён из файла:\n{path}")

    def _seed_hashtags_pool_from_file_if_empty(self) -> None:
        if (getattr(self.settings, "hashtags_pool", None) or "").strip():
            return
        p = Path(__file__).resolve().parent / "hashtags.txt"
        if not p.is_file():
            return
        try:
            self.settings.hashtags_pool = p.read_text(encoding="utf-8")
        except Exception:
            pass

    def load_settings(self):
        if not self.settings_path.exists():
            self._seed_hashtags_pool_from_file_if_empty()
            return
        try:
            raw = self.settings_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            disk_has_hashtags = isinstance(data, dict) and "hashtags_pool" in data
            self.apply_settings_dict(data, refresh=False)
            if not disk_has_hashtags:
                self._seed_hashtags_pool_from_file_if_empty()
        except Exception:
            pass

    def apply_settings_dict(self, data: dict, refresh: bool = False) -> bool:
        """Apply preset fields from a dict (API / Electron). Optional Tk refresh. Returns False on failure."""
        if not isinstance(data, dict):
            return False
        try:
            d = dict(data)
            if "card_bg_colors" in d:
                v = d.get("card_bg_colors")
                if isinstance(v, str):
                    d["card_bg_colors"] = [ln.strip() for ln in re.split(r"[\n,;]+", v) if ln and str(ln).strip()]
                elif isinstance(v, list):
                    d["card_bg_colors"] = [str(x).strip() for x in v if str(x).strip()]
                else:
                    d["card_bg_colors"] = []
            if "glow_overlay_colors" in d:
                v = d.get("glow_overlay_colors")
                if isinstance(v, str):
                    d["glow_overlay_colors"] = [ln.strip() for ln in re.split(r"[\n,;]+", v) if ln and str(ln).strip()]
                elif isinstance(v, list):
                    d["glow_overlay_colors"] = [str(x).strip() for x in v if str(x).strip()]
                else:
                    d["glow_overlay_colors"] = []
            ts = d.get("text_styles")
            if isinstance(ts, dict):
                # Не затирать стиль целиком частичным объектом с веба (иначе пропадают bg_enabled и подложка).
                raw_old = getattr(self.settings, "text_styles", None) or {}
                if not isinstance(raw_old, dict):
                    raw_old = {}
                base_defs = default_text_styles()
                merged_ts: dict[str, dict] = {}
                names = set(base_defs.keys()) | set(raw_old.keys()) | set(ts.keys())
                for name in sorted(names):
                    o = dict(raw_old[name]) if isinstance(raw_old.get(name), dict) else {}
                    n = dict(ts[name]) if isinstance(ts.get(name), dict) else {}
                    if name in base_defs:
                        merged_el = {**dict(base_defs[name]), **o, **n}
                        if "bg_colors" in merged_el:
                            merged_el["bg_colors"] = self._normalize_text_bg_palette(merged_el.get("bg_colors"))
                        merged_ts[name] = merged_el
                    else:
                        merged_ts[name] = {**o, **n}
                d["text_styles"] = merged_ts
            old_bg_sig = (tuple(self._normalize_card_bg_palette()), (self.settings.card_bg or "").strip())
            if "duration" in d:
                dur = float(d.get("duration", 7.0))
                d["duration_min"] = d.get("duration_min", dur)
                d["duration_max"] = d.get("duration_max", dur)
                d.pop("duration", None)
            valid_keys = set(UiSettings.__dataclass_fields__.keys())
            cleaned = {k: v for k, v in d.items() if k in valid_keys}
            self.settings = UiSettings(**cleaned)
            new_bg_sig = (tuple(self._normalize_card_bg_palette()), (self.settings.card_bg or "").strip())
            if old_bg_sig != new_bg_sig:
                self._invalidate_card_bg_random_pick()
            self._reset_text_bg_random_picks()
            self._invalidate_element_inspector()
        except Exception as ex:
            print(f"[apply_settings_dict] {ex}")
            return False
        if getattr(self, "controls", None):
            self.sync_controls_from_settings()
        if hasattr(self, "watermark_text_var"):
            self.watermark_text_var.set(self.settings.watermark_text)
            self.watermark_color_var.set(self.settings.watermark_color)
        if hasattr(self, "card_bg_media_var"):
            self.card_bg_media_var.set(self.settings.card_bg_media)
        if hasattr(self, "force_caps_var"):
            self.force_caps_var.set(self.settings.force_caps)
        if hasattr(self, "glow_overlay_enabled_var"):
            self.glow_overlay_enabled_var.set(bool(getattr(self.settings, "glow_overlay_enabled", True)))
        if hasattr(self, "glow_colors_box"):
            gc = getattr(self.settings, "glow_overlay_colors", None) or []
            self.glow_colors_box.delete("1.0", "end")
            if isinstance(gc, list) and gc:
                self.glow_colors_box.insert("1.0", "\n".join(str(x).strip() for x in gc if str(x).strip()))
        if hasattr(self, "topics_box"):
            self.topics_box.delete("1.0", "end")
            self.topics_box.insert("1.0", self.settings.headline_topics)
        if hasattr(self, "timeline"):
            self.timeline.configure(to=max(0.1, self.settings.duration_max))
        self.current_time = min(self.current_time, self.settings.duration_max)
        if refresh and hasattr(self, "canvas"):
            self.refresh_preview()
        return True

    def apply_scene_dict(self, scene: dict, refresh: bool = False) -> None:
        """Update headline / hero / bio / photo path / playhead from a dict."""
        if not scene:
            return
        if "headline" in scene and hasattr(self, "headline_var"):
            self.headline_var.set(str(scene.get("headline") or ""))
        if "hero" in scene and hasattr(self, "hero_var"):
            self.hero_var.set(str(scene.get("hero") or ""))
            self.current_hero = str(scene.get("hero") or "")
        if "bio" in scene and hasattr(self, "bio_box"):
            self.bio_box.delete("1.0", "end")
            self.bio_box.insert("1.0", str(scene.get("bio") or ""))
        if "dates" in scene and hasattr(self, "dates_var"):
            self.dates_var.set(str(scene.get("dates") or ""))
        if "image_path" in scene and scene.get("image_path") is not None:
            self.current_image_path = str(scene.get("image_path") or "")
        if "current_time" in scene and scene.get("current_time") is not None:
            t = float(scene.get("current_time") or 0.0)
            self.current_time = max(0.0, min(t, self.settings.duration_max))
            if hasattr(self, "timeline_var"):
                self._timeline_internal_update = True
                self.timeline_var.set(self.current_time)
                self._timeline_internal_update = False
        if refresh and hasattr(self, "canvas"):
            self.refresh_preview()

    def merge_text_style(self, element: str, updates: dict) -> None:
        if not isinstance(updates, dict):
            return
        style = self.get_text_style(element)
        style.update(updates)
        self.settings.text_styles[element] = style
        self._invalidate_element_inspector()

    def load_settings_and_refresh(self):
        self.load_settings()
        self.sync_controls_from_settings()
        self.watermark_text_var.set(self.settings.watermark_text)
        self.watermark_color_var.set(self.settings.watermark_color)
        self.card_bg_media_var.set(self.settings.card_bg_media)
        if hasattr(self, "force_caps_var"):
            self.force_caps_var.set(self.settings.force_caps)
        if hasattr(self, "glow_overlay_enabled_var"):
            self.glow_overlay_enabled_var.set(bool(getattr(self.settings, "glow_overlay_enabled", True)))
        if hasattr(self, "glow_colors_box"):
            gc = getattr(self.settings, "glow_overlay_colors", None) or []
            self.glow_colors_box.delete("1.0", "end")
            if isinstance(gc, list) and gc:
                self.glow_colors_box.insert("1.0", "\n".join(str(x).strip() for x in gc if str(x).strip()))
        if hasattr(self, "topics_box"):
            self.topics_box.delete("1.0", "end")
            self.topics_box.insert("1.0", self.settings.headline_topics)
        self.timeline.configure(to=max(0.1, self.settings.duration_max))
        self._invalidate_element_inspector()
        self.refresh_preview()

    def on_close(self):
        try:
            self.save_settings(show_message=False, apply_first=True)
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    # На Windows иногда нужен selector loop для subprocess/async с Tk; на macOS/Linux атрибута нет.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--studio-headless-current", action="store_true")
    parser.add_argument("--studio-headless-batch", action="store_true")
    parser.add_argument("--count", type=int, default=10)
    args, unknown = parser.parse_known_args()

    if args.studio_headless_current or args.studio_headless_batch:
        app = CapCutLikeUi(headless=True)
        if args.studio_headless_current:
            raise SystemExit(app.studio_headless_render_current())
        raise SystemExit(app.studio_headless_render_batch(args.count))

    # Default: interactive Tk UI (ignore unknown args for compatibility)
    app = CapCutLikeUi(headless=False)
    app.run()
