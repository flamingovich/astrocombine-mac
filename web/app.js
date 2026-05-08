const $ = (id) => document.getElementById(id);

const API = "";

/** Диалог выбора файла: Electron — нативно; иначе IPC worker (tk). */
async function pickFileNative(opts = {}) {
  const pe = window.politicsStudio;
  if (pe && typeof pe.pickFile === "function") {
    const p = await pe.pickFile(opts);
    return typeof p === "string" ? p.trim() : "";
  }
  const filetypes = opts.filetypesForWorker || [
    ["Все файлы", "*.*"],
  ];
  const r = await studio({
    cmd: "pick_file",
    title: opts.title || "Выберите файл",
    filetypes,
  });
  if (r && r.ok && r.path) return String(r.path).trim();
  return "";
}

async function pickFolderNative(opts = {}) {
  const pe = window.politicsStudio;
  if (pe && typeof pe.pickFolder === "function") {
    const p = await pe.pickFolder(opts);
    return typeof p === "string" ? p.trim() : "";
  }
  const r = await studio({
    cmd: "pick_folder",
    title: opts.title || "Выберите папку",
  });
  if (r && r.ok && r.path) return String(r.path).trim();
  return "";
}

function randomHexColor() {
  const n = Math.floor(Math.random() * 0xffffff);
  return `#${n.toString(16).padStart(6, "0").toUpperCase()}`;
}

const TABS = [
  { id: "text", label: "Текст" },
  { id: "topics", label: "Темы" },
  { id: "scene", label: "Сцена" },
  { id: "bgframe", label: "Фон" },
  { id: "motion", label: "Анимация" },
  { id: "mark", label: "Вотермарка" },
  { id: "style", label: "Стиль текста" },
  { id: "render", label: "Рендер" },
];

/** Поля пресета (как вкладки справа в Tk). */
const FIELDS = [
  { tab: "text", key: "title_font_size", label: "Размер заголовка", kind: "int" },
  { tab: "text", key: "title_font_size_min", label: "Мин. размер заголовка (авто по длине)", kind: "int" },
  { tab: "text", key: "title_wrap_width", label: "Ширина колонки заголовка (0 = авто)", kind: "int" },
  { tab: "text", key: "subtitle_font_size", label: "Размер описания", kind: "int" },
  { tab: "text", key: "subtitle_wrap_width", label: "Ширина колонки описания (0 = авто)", kind: "int" },
  { tab: "text", key: "title_y", label: "Y заголовка", kind: "int" },
  { tab: "text", key: "title_x", label: "Сдвиг заголовка X (от центра)", kind: "int" },
  { tab: "text", key: "subtitle_y", label: "Y описания", kind: "int" },
  { tab: "text", key: "subtitle_x", label: "Сдвиг описания X (от центра)", kind: "int" },
  { tab: "text", key: "dates_font_size", label: "Размер дат", kind: "int" },
  { tab: "text", key: "dates_y", label: "Y дат", kind: "int" },
  { tab: "text", key: "dates_x", label: "Сдвиг дат X (от центра)", kind: "int" },
  { tab: "text", key: "side_padding", label: "Боковой отступ", kind: "int" },
  { tab: "text", key: "subtitle_line_spacing", label: "Межстрочный интервал", kind: "int" },
  { tab: "text", key: "subtitle_max_words", label: "Лимит слов описания", kind: "int" },
  { tab: "text", key: "subtitle_min_words", label: "Мин. слов в описании (для экспорта)", kind: "int" },
  { tab: "text", key: "title_font", label: "Шрифт заголовка", kind: "path_font" },
  { tab: "text", key: "subtitle_font", label: "Шрифт описания", kind: "path_font" },
  { tab: "text", key: "dates_font", label: "Шрифт дат", kind: "path_font" },
  { tab: "text", key: "force_caps", label: "Текст только КАПСОМ", kind: "bool" },
  { tab: "text", key: "title_hidden", label: "Скрыть заголовок (не рендерить)", kind: "bool" },
  { tab: "text", key: "subtitle_hidden", label: "Скрыть описание (не рендерить)", kind: "bool" },
  { tab: "text", key: "dates_hidden", label: "Скрыть даты (не рендерить)", kind: "bool" },

  {
    tab: "topics",
    key: "headline_topics",
    label: "Темы для заголовков (по одной на строку; для ролика случайно выбирается целая строка)",
    kind: "textarea",
    rows: 14,
  },

  { tab: "scene", key: "title_color", label: "Цвет заголовка", kind: "color" },
  { tab: "scene", key: "title_stroke", label: "Обводка заголовка", kind: "color" },
  { tab: "scene", key: "subtitle_color", label: "Цвет описания", kind: "color" },
  { tab: "scene", key: "dates_color", label: "Цвет дат", kind: "color" },

  {
    tab: "bgframe",
    key: "video_bg_mode",
    label: "Режим фона кадра",
    kind: "select",
    options: [
      { value: "folder", label: "Папка — случайное видео" },
      { value: "flat", label: "Цвет или градиент" },
      { value: "photo_blur", label: "Фото на весь кадр + блюр (выберите файл ниже)" },
    ],
  },
  { tab: "bgframe", key: "video_bg_folder", label: "Папка с видео-фонами (от корня проекта)", kind: "path_folder" },
  { tab: "bgframe", key: "video_bg_seamless_loop", label: "Бесшовный цикл видео-фона (случайный отрезок + кроссфейд)", kind: "bool" },
  { tab: "bgframe", key: "video_bg_loop_crossfade_sec", label: "Кроссфейд на стыке цикла (сек, 0.2–2.5)", kind: "float" },
  {
    tab: "bgframe",
    key: "video_bg_loop_segment_sec",
    label: "Длина сегмента цикла L (сек, 0 = авто: от длины ролика и файла)",
    kind: "float",
  },
  {
    tab: "bgframe",
    key: "video_bg_photo_path",
    label: "Фото для режима «Фото на весь кадр + блюр»",
    kind: "path_image",
  },
  {
    tab: "bgframe",
    key: "video_bg_spec",
    label: "Цвет (#RRGGBB) или linear-gradient(180deg, #a, #b) — для режима «Цвет или градиент»",
    kind: "str",
  },
  { tab: "bgframe", key: "video_bg_photo_blur", label: "Сила размытия фона (радиус, 0–90)", kind: "float" },
  { tab: "bgframe", key: "video_bg_photo_brightness", label: "Яркость фона при «Фото+блюр» (0.2–2.5, 1 = как есть)", kind: "float" },

  { tab: "motion", key: "duration_min", label: "Длительность ОТ (сек)", kind: "float" },
  { tab: "motion", key: "duration_max", label: "Длительность ДО (сек)", kind: "float" },
  { tab: "motion", key: "glow_overlay_enabled", label: "Включить анимированный блик (верхний слой)", kind: "bool" },
  { tab: "motion", key: "glow_overlay_opacity", label: "Непрозрачность блика (0–1)", kind: "float" },
  {
    tab: "motion",
    key: "glow_overlay_colors",
    label: "Цвета блика",
    kind: "glow_palette",
  },

  { tab: "mark", key: "watermark_font", label: "Шрифт вотермарки", kind: "path_font" },
  { tab: "mark", key: "watermark_text", label: "Текст вотермарки", kind: "str" },
  { tab: "mark", key: "watermark_font_size", label: "Размер вотермарки", kind: "int" },
  { tab: "mark", key: "watermark_color", label: "Цвет вотермарки", kind: "color" },
  { tab: "mark", key: "watermark_opacity", label: "Прозрачность (0–255)", kind: "int" },
  { tab: "mark", key: "watermark_x", label: "X вотермарки", kind: "int" },
  { tab: "mark", key: "watermark_y", label: "Y вотермарки", kind: "int" },
  { tab: "mark", key: "watermark_hidden", label: "Скрыть вотермарку (не рендерить)", kind: "bool" },
  {
    tab: "mark",
    key: "video_output_dir",
    label: "Папка без вотермарки (полный путь)",
    kind: "path_folder",
  },

  {
    tab: "render",
    key: "output_name_builder",
    label: "Имя выходного файла",
    kind: "name_builder",
  },
  {
    tab: "render",
    key: "hashtags_pool",
    label: "Хештеги (каждая строка — отдельный тег; при первом запуске подставляется hashtags.txt)",
    kind: "textarea",
    rows: 10,
  },
  { tab: "render", key: "output_hashtag_count", label: "Сколько хештегов в блоке «Хештеги»", kind: "int" },
  { tab: "render", key: "output_name_emoji_pool", label: "Пул эмодзи (строка = один вариант)", kind: "textarea", rows: 5 },
  { tab: "render", key: "output_name_text_pool", label: "Пул текстов (строка = один вариант)", kind: "textarea", rows: 5 },
  { tab: "render", key: "output_name_prefix_pool", label: "Пул префиксов (пусто = встроенный набор)", kind: "textarea", rows: 4 },
];

let state = { settings: {} };
let activeTab = "text";
let previewTimer = null;
let lastPreviewUrl = null;
/** Отмена устаревшего fetch превью при новом вводе */
let previewFetchAbort = null;
let tabsInitialized = false;

/** Редактирование в превью (координаты 1080×1920 с сервера) */
let previewHitboxes = {};
let previewSelected = "subtitle";
let previewDrag = null;
/** Было реальное перемещение — только тогда в pointerup перезапрашиваем кадр (иначе ломается dblclick) */
let previewDragMutated = false;
/** Смещение выбранного хитбокса в координатах кадра во время drag (пока PNG не перерисован) */
let previewGhostOffset = null;
/** Вертикальная направляющая по центру кадра (x = 540) при магните при перетаскивании */
let previewSnapVertical = false;
let previewWheelTimer = null;

/** Счётчик запросов превью — не гасим оверлей устаревшего ответа */
let previewRequestId = 0;

let elementEditorHit = null;
/** Временный превью одной строки палитры подложки (кнопка «глаз»): { hit, spec } */
let bgPalettePreviewOverride = null;
/** Превью заливки текста по строке (👁): { hit, kind: 'static'|'lighten'|'pair', hex?, pair?: {a,b} } */
let textFillPreviewOverride = null;

const PREVIEW_SCALE_LS = "horoscope_studio_preview_stack_scale";
/** Включена ли визуальная рамка Shorts (только UI, не влияет на экспорт) */
const PREVIEW_SHORTS_LS = "horoscope_studio_preview_shorts_shell";
/** Узкий PNG с сервера в режиме Shorts: быстрее сеть и decode, хитбоксы остаются в 1080×1920 */
const PREVIEW_SHORTS_MAX_W = 640;
/** Один раз за сессию вкладки: полноэкранная заставка превью до первого готового PNG */
const PREVIEW_SPLASH_DONE_KEY = "horoscope_studio_preview_first_png_done";

function shouldShowPreviewSplash() {
  try {
    return sessionStorage.getItem(PREVIEW_SPLASH_DONE_KEY) !== "1";
  } catch (_) {
    return true;
  }
}

function markPreviewSplashDone() {
  try {
    sessionStorage.setItem(PREVIEW_SPLASH_DONE_KEY, "1");
  } catch (_) {
    /* ignore */
  }
}

/** Базовые поля text_styles (схема пресета / Python-рендер; основной UI — Electron `web/`) */
const STYLE_BASE = {
  use_gradient: false,
  gradient_start: "#FFFFFF",
  gradient_end: "#4AA3FF",
  stroke_color: "#000000",
  stroke_width: 2,
  stroke_outer_enabled: null,
  stroke_outer_width: null,
  stroke_outer_color: null,
  stroke_inner_enabled: false,
  stroke_inner_width: 0,
  stroke_inner_color: "#000000",
  shadow_enabled: false,
  shadow_color: "#000000",
  shadow_opacity: 120,
  shadow_blur: 3,
  shadow_dx: 2,
  shadow_dy: 2,
  bg_enabled: false,
  bg_color: "#000000",
  bg_opacity: 80,
  bg_padding_x: 12,
  bg_padding_y: 8,
  bg_corner_radius: 12,
  bg_stroke_color: "#FFFFFF",
  bg_stroke_width: 0,
  bg_stroke_inside: true,
  bg_stroke_outside: false,
  bg_stroke_outer_enabled: null,
  bg_stroke_outer_width: null,
  bg_stroke_outer_color: null,
  bg_stroke_inner_enabled: null,
  bg_stroke_inner_width: null,
  bg_stroke_inner_color: null,
  bg_use_gradient: false,
  bg_gradient_start: "#000000",
  bg_gradient_end: "#333333",
  bg_image: "",
  text_fill_mode: "",
  text_palette_colors: [],
  text_alternate_pairs: [],
  text_lighten_bases: [],
  /** Игнорируется, если подложка включена (подложка не тянется за шрифтом). */
  bg_resizes_with_font: false,
  bg_snap_inner_w: 0,
  bg_snap_inner_h: 0,
  /** Подложка фиксированного размера (px текста bbox до padding); центр = центр текста; шрифт меняется отдельно. */
  bg_use_fixed_inner_box: false,
  bg_fixed_width: 0,
  bg_fixed_height: 0,
  /** Несколько цветов/строк градиента: при непустом списке на каждое новое видео выбирается случайная строка (рендер в Python). */
  bg_colors: [],
};

const STYLE_PRESETS = {
  title: { ...STYLE_BASE, use_gradient: true, gradient_start: "#FFFFFF", gradient_end: "#D6E5FF", stroke_width: 3, bg_resizes_with_font: false },
  subtitle: { ...STYLE_BASE, stroke_width: 0, bg_resizes_with_font: false },
  dates: { ...STYLE_BASE, stroke_width: 0, gradient_start: "#FFFFFF", gradient_end: "#FFFFFF", bg_resizes_with_font: false },
  watermark: { ...STYLE_BASE, stroke_width: 0, shadow_enabled: false, bg_resizes_with_font: false },
};

const DEFAULT_LAYER_FRAME = {
  stroke_enabled: false,
  stroke_color: "#000000",
  stroke_width: 3,
  stroke_outer_enabled: null,
  stroke_outer_width: null,
  stroke_outer_color: null,
  stroke_inner_enabled: false,
  stroke_inner_width: 0,
  stroke_inner_color: "#000000",
  corner_radius: 12,
  shadow_enabled: false,
  shadow_color: "#000000",
  shadow_opacity: 110,
  shadow_blur: 10,
  shadow_dx: 4,
  shadow_dy: 4,
};

function collectLfFromModal(body, which) {
  const o = {};
  if (!body) return o;
  body.querySelectorAll(`[data-lf="${which}"]`).forEach((el) => {
    const key = el.dataset.lfkey;
    if (!key) return;
    if (el.type === "checkbox") o[key] = Boolean(el.checked);
    else if (el.type === "number") {
      const n = parseFloat(el.value);
      o[key] = Number.isFinite(n) ? Math.round(n) : 0;
    } else o[key] = String(el.value ?? "");
  });
  return o;
}

function lfStrokeOuterOn(st) {
  if (st.stroke_outer_enabled === false) return false;
  if (st.stroke_outer_enabled === true) return true;
  return Boolean(st.stroke_enabled) && Number(st.stroke_width || 0) > 0;
}
function lfStrokeOuterWidthVal(st) {
  if (st.stroke_outer_width != null && st.stroke_outer_width !== "") return Number(st.stroke_outer_width);
  return lfStrokeOuterOn(st) ? Number(st.stroke_width || 0) : 0;
}
function lfStrokeOuterColorVal(st) {
  return st.stroke_outer_color || st.stroke_color || "#000000";
}
function lfStrokeInnerOn(st) {
  if (st.stroke_inner_enabled === false) return false;
  if (st.stroke_inner_enabled === true) return true;
  return false;
}
function lfStrokeInnerWidthVal(st) {
  if (st.stroke_inner_width != null && st.stroke_inner_width !== "") return Number(st.stroke_inner_width);
  return lfStrokeInnerOn(st) ? Number(st.stroke_inner_width || st.stroke_width || 0) : 0;
}
function lfStrokeInnerColorVal(st) {
  return st.stroke_inner_color || st.stroke_color || "#000000";
}

function renderLayerFrameFieldsForPrefix(lfPrefix, st, lab) {
  const ow = lfStrokeOuterWidthVal(st);
  const ocol = lfStrokeOuterColorVal(st);
  const iw = lfStrokeInnerWidthVal(st);
  const icol = lfStrokeInnerColorVal(st);
  return `
    <div class="ccElemSection">Обводка (${lab})</div>
    <p class="ccElemField__hint">Внешняя / внутренняя — отдельные цвета и толщины. Старые пресеты без этих полей читаются как одна внешняя обводка.</p>
    <label class="ccElemCheck"><input type="checkbox" data-lf="${lfPrefix}" data-lfkey="stroke_outer_enabled" ${lfStrokeOuterOn(st) ? "checked" : ""} /> Внешняя обводка</label>
    <div class="ccElemRow2">
      ${elemColorFieldLf(lfPrefix, "Цвет снаружи", "stroke_outer_color", ocol)}
      <div class="ccElemField"><label>Толщина снаружи (px)</label><input class="ccInput" type="number" data-lf="${lfPrefix}" data-lfkey="stroke_outer_width" min="0" max="40" step="1" value="${escAttr(ow)}" /></div>
    </div>
    <label class="ccElemCheck"><input type="checkbox" data-lf="${lfPrefix}" data-lfkey="stroke_inner_enabled" ${lfStrokeInnerOn(st) ? "checked" : ""} /> Внутренняя обводка</label>
    <div class="ccElemRow2">
      ${elemColorFieldLf(lfPrefix, "Цвет внутри", "stroke_inner_color", icol)}
      <div class="ccElemField"><label>Толщина внутри (px)</label><input class="ccInput" type="number" data-lf="${lfPrefix}" data-lfkey="stroke_inner_width" min="0" max="40" step="1" value="${escAttr(iw)}" /></div>
    </div>
    <div class="ccElemField"><label>Скругление углов (px)</label><input class="ccInput" type="number" data-lf="${lfPrefix}" data-lfkey="corner_radius" min="0" max="80" step="1" value="${escAttr(st.corner_radius)}" /></div>
    <div class="ccElemSection">Тень (${lab})</div>
    <label class="ccElemCheck"><input type="checkbox" data-lf="${lfPrefix}" data-lfkey="shadow_enabled" ${st.shadow_enabled ? "checked" : ""} /> Включить тень</label>
    <div class="ccElemRow2">
      ${elemColorFieldLf(lfPrefix, "Цвет тени", "shadow_color", st.shadow_color)}
      <div class="ccElemField"><label>Непрозрачность (0–255)</label><input class="ccInput" type="number" data-lf="${lfPrefix}" data-lfkey="shadow_opacity" min="0" max="255" step="1" value="${escAttr(st.shadow_opacity)}" /></div>
    </div>
    <div class="ccElemRow2">
      <div class="ccElemField"><label>Размытие</label><input class="ccInput" type="number" data-lf="${lfPrefix}" data-lfkey="shadow_blur" min="0" max="48" step="1" value="${escAttr(st.shadow_blur)}" /></div>
      <div class="ccElemField"><label>Сдвиг X / Y</label>
        <div class="ccElemRow2" style="margin-top:4px">
          <input class="ccInput" type="number" data-lf="${lfPrefix}" data-lfkey="shadow_dx" step="1" value="${escAttr(st.shadow_dx)}" />
          <input class="ccInput" type="number" data-lf="${lfPrefix}" data-lfkey="shadow_dy" step="1" value="${escAttr(st.shadow_dy)}" />
        </div>
      </div>
    </div>`;
}

function ensureSceneOverlays(s) {
  if (!Array.isArray(s.scene_overlays)) s.scene_overlays = [];
  return s.scene_overlays;
}

function newOverlayId() {
  return "ov_" + Math.random().toString(36).slice(2, 11);
}

function mergeOverlayFrame(ov) {
  return { ...DEFAULT_LAYER_FRAME, ...(ov && ov.frame && typeof ov.frame === "object" ? ov.frame : {}) };
}

function overlayHitKeys() {
  return Object.keys(previewHitboxes)
    .filter((k) => k.startsWith("overlay:"))
    .sort();
}

function collectOverlayScalarsFromModal(body) {
  const o = {};
  if (!body) return o;
  body.querySelectorAll("[data-ov-field]").forEach((el) => {
    const k = el.dataset.ovField;
    if (!k) return;
    if (el.type === "checkbox") o[k] = Boolean(el.checked);
    else if (el.type === "number") {
      const n = el.step && String(el.step).includes(".") ? parseFloat(el.value) : parseInt(el.value, 10);
      o[k] = Number.isFinite(n) ? n : 0;
    } else o[k] = String(el.value ?? "");
  });
  return o;
}

/** Модальное окно «Рендеринг» открыто — дублируем туда поток WS и строки запуска */
let renderLogModalOpen = false;
/** Параметры экспорта (перед стартом рендера) */
let exportSettingsModalOpen = false;
/** Время старта текущего запуска рендера (для строки «сессия … с») */
let renderSessionT0 = null;
let renderHadProgress = false;
/** Номер ролика в серии / всего (для строки «Видео: n/m») */
let renderVideoIndex = 1;
let renderVideoTotal = 1;
/** Пайплайн рендера на сервере запущен — доступна отмена */
let renderProcActive = false;
/** Прогресс кодирования текущего файла (tqdm %), 0–100 */
let renderCurrentClipPct = 0;
/** Последние значения tqdm для текущего ролика */
let renderLastTqdmElapsed = null;
let renderLastTqdmEta = null;
/** Имя файла из строки [OUT] / [DONE] */
let renderLastOutBasename = "—";
/** Один таймер: обновление «Всего прошло» и периодический превью-кадр */
let renderModalTimer = null;
let renderModalTick = 0;
/** objectURL для кадра рендера (/api/render-thumb), не путать с превью редактора */
let renderThumbObjectUrl = null;

function stopRenderModalTimers() {
  if (renderModalTimer) {
    clearInterval(renderModalTimer);
    renderModalTimer = null;
  }
}

async function refreshRenderLiveThumb() {
  if (!renderLogModalOpen) return;
  const rp = $("renderPreviewImg");
  if (!rp) return;
  try {
    const res = await fetch(`${API}/api/render-thumb?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) return;
    const blob = await res.blob();
    if (renderThumbObjectUrl) URL.revokeObjectURL(renderThumbObjectUrl);
    renderThumbObjectUrl = URL.createObjectURL(blob);
    rp.src = renderThumbObjectUrl;
  } catch (_) {
    /* ignore */
  }
}

function startRenderModalTimers() {
  stopRenderModalTimers();
  renderModalTick = 0;
  renderModalTimer = setInterval(() => {
    if (!renderLogModalOpen) return;
    renderModalTick += 1;
    if (renderProcActive) syncRenderModalUi();
    if (renderProcActive && renderModalTick % 3 === 0) {
      refreshRenderLiveThumb().catch(() => {});
    }
  }, 1000);
}

function computeRenderJobPercent() {
  const total = Math.max(1, renderVideoTotal || 1);
  const idx = Math.min(Math.max(1, renderVideoIndex || 1), total);
  const clip = Math.min(100, Math.max(0, renderCurrentClipPct)) / 100;
  return Math.min(100, ((idx - 1 + clip) / total) * 100);
}

function syncRenderModalUi() {
  const title = $("renderLogTitle");
  if (title) title.textContent = `Рендер видео ${Math.max(1, renderVideoIndex || 1)}`;

  const clipFill = $("renderClipProgressFill");
  const clipPct = $("renderClipProgressPct");
  const cp = Math.min(100, Math.max(0, renderCurrentClipPct));
  if (clipFill) clipFill.style.width = `${cp}%`;
  if (clipPct) clipPct.textContent = `${Math.round(cp)}%`;

  const jobFill = $("renderJobProgressFill");
  const jobPctEl = $("renderJobProgressPct");
  const jp = computeRenderJobPercent();
  if (jobFill) jobFill.style.width = `${jp}%`;
  if (jobPctEl) jobPctEl.textContent = `${Math.round(jp)}%`;

  const el = $("renderStatElapsed");
  if (el) {
    el.textContent = `Прошло: ${renderLastTqdmElapsed != null ? formatRenderSeconds(renderLastTqdmElapsed) : "—"}`;
  }
  const et = $("renderStatEta");
  if (et) {
    et.textContent = `Осталось: ${renderLastTqdmEta != null ? `~${formatRenderSeconds(renderLastTqdmEta)}` : "—"}`;
  }
  const t = Math.max(1, renderVideoTotal || 1);
  const i = Math.min(Math.max(1, renderVideoIndex || 1), t);
  const vl = $("renderStatVideosLeft");
  if (vl) {
    if (!renderProcActive && !renderHadProgress) {
      vl.textContent = "Осталось видео: —";
    } else if (!renderProcActive) {
      vl.textContent = "Осталось видео: 0";
    } else {
      vl.textContent = `Осталось видео: ${Math.max(0, t - i + 1)}`;
    }
  }
  const fn = $("renderStatFilename");
  if (fn) fn.textContent = renderLastOutBasename || "—";
  const ss = $("renderStatSession");
  if (ss) {
    ss.textContent = `Всего прошло: ${renderSessionT0 ? formatRenderSeconds((Date.now() - renderSessionT0) / 1000) : "—"}`;
  }
}

function updateRenderCancelButton() {
  const b = $("btnRenderCancel");
  if (b) b.disabled = !renderProcActive;
}

function setRenderLogPanelExpanded(wantOpen) {
  const det = $("renderLogDetails");
  const btn = $("btnShowRenderLogs");
  if (!det) return;
  det.classList.toggle("ccRenderLogDetails--open", Boolean(wantOpen));
  if (btn) {
    btn.setAttribute("aria-expanded", wantOpen ? "true" : "false");
    btn.textContent = wantOpen ? "Скрыть логи" : "Показать логи";
  }
  if (wantOpen) {
    const sc = $("renderLogScroll");
    if (sc) {
      requestAnimationFrame(() => {
        sc.scrollIntoView({ block: "nearest", behavior: "smooth" });
        sc.scrollTop = sc.scrollHeight;
        sc.focus({ preventScroll: true });
      });
    }
  }
}

function toggleRenderLogPanel() {
  const det = $("renderLogDetails");
  if (!det) return;
  setRenderLogPanelExpanded(!det.classList.contains("ccRenderLogDetails--open"));
}

async function copyRenderLogsToClipboard() {
  const r = $("renderLogOut");
  const txt = r ? String(r.textContent || "") : "";
  const btn = $("btnCopyRenderLogs");
  const prev = btn ? btn.textContent : "";
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      await navigator.clipboard.writeText(txt);
    } else {
      const ta = document.createElement("textarea");
      ta.value = txt;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    if (btn) {
      btn.textContent = "Скопировано";
      setTimeout(() => {
        if (btn) btn.textContent = prev || "Копировать логи";
      }, 1800);
    }
  } catch (e) {
    appendLog(`[copy logs] ${e}`);
    if (btn) btn.textContent = prev || "Копировать логи";
  }
}

function appendLog(line) {
  const el = $("log");
  if (el) {
    el.textContent += line + "\n";
    el.scrollTop = el.scrollHeight;
  }
}

function formatRenderSeconds(sec) {
  const n = Math.max(0, Math.floor(Number(sec) || 0));
  const s = n % 60;
  const m = Math.floor(n / 60) % 60;
  const h = Math.floor(n / 3600);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function parseTqdmColonTime(t) {
  const raw = String(t || "").replace(/\?$/, "").trim();
  if (!raw || raw === "?") return null;
  const p = raw.split(":").map((x) => parseInt(x, 10));
  if (p.some((n) => Number.isNaN(n))) return null;
  if (p.length === 1) return p[0];
  if (p.length === 2) return p[0] * 60 + p[1];
  if (p.length === 3) return p[0] * 3600 + p[1] * 60 + p[2];
  return null;
}

function updateRenderProgressFromLine(line) {
  if (!line) return;

  const outM = line.match(/^\[OUT\]\s+(.+)$/);
  if (outM) {
    const full = (outM[1] || "").trim();
    renderLastOutBasename = full.split(/[/\\]/).pop() || full || "—";
    syncRenderModalUi();
    setTimeout(() => refreshRenderLiveThumb().catch(() => {}), 1500);
    return;
  }

  const doneM = line.match(/^\[DONE\]\s+(.+)$/);
  if (doneM) {
    const full = (doneM[1] || "").trim();
    renderLastOutBasename = full.split(/[/\\]/).pop() || full || "—";
    renderCurrentClipPct = 100;
    syncRenderModalUi();
    return;
  }

  const batchM = line.match(/\[BATCH\]\s*(\d+)\s*\/\s*(\d+)/i);
  if (batchM) {
    renderVideoIndex = Math.max(1, parseInt(batchM[1], 10) || 1);
    renderVideoTotal = Math.max(1, parseInt(batchM[2], 10) || 1);
    renderCurrentClipPct = 0;
    renderLastTqdmElapsed = null;
    renderLastTqdmEta = null;
    syncRenderModalUi();
    return;
  }

  let m = line.match(/^\s*(?:[\w.]+\s*:\s*)?(\d+)\s*%\|[^|]*\|\s*(\d+)\s*\/\s*(\d+)\s*\[\s*([\d:.?]+)\s*<\s*([\d:.?]+)/);
  if (m) {
    renderHadProgress = true;
    const pct = Math.min(100, Math.max(0, parseInt(m[1], 10)));
    renderCurrentClipPct = pct;
    renderLastTqdmElapsed = parseTqdmColonTime(m[4]);
    renderLastTqdmEta = parseTqdmColonTime(m[5]);
    syncRenderModalUi();
    return;
  }
  m = line.match(/\|\s*(\d+)\s*\/\s*(\d+)\s*\[\s*([\d:.?]+)\s*<\s*([\d:.?]+)/);
  if (m) {
    renderHadProgress = true;
    const cur = parseInt(m[1], 10);
    const tot = parseInt(m[2], 10);
    const pct = tot > 0 ? Math.min(100, Math.round((100 * cur) / tot)) : 0;
    renderCurrentClipPct = pct;
    renderLastTqdmElapsed = parseTqdmColonTime(m[3]);
    renderLastTqdmEta = parseTqdmColonTime(m[4]);
    syncRenderModalUi();
  }
}

function resetRenderProgressUi() {
  renderHadProgress = false;
  renderCurrentClipPct = 0;
  renderLastTqdmElapsed = null;
  renderLastTqdmEta = null;
  renderLastOutBasename = "—";
  const clipFill = $("renderClipProgressFill");
  const jobFill = $("renderJobProgressFill");
  if (clipFill) clipFill.style.width = "0%";
  if ($("renderClipProgressPct")) $("renderClipProgressPct").textContent = "0%";
  if (jobFill) jobFill.style.width = "0%";
  if ($("renderJobProgressPct")) $("renderJobProgressPct").textContent = "0%";
  const rp = $("renderPreviewImg");
  if (rp) {
    if (renderThumbObjectUrl) {
      URL.revokeObjectURL(renderThumbObjectUrl);
      renderThumbObjectUrl = null;
    }
    rp.src =
      "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
  }
  syncRenderModalUi();
}

function finalizeRenderProgress(exitCode) {
  stopRenderModalTimers();
  renderCurrentClipPct = 100;
  const clipFill = $("renderClipProgressFill");
  const jobFill = $("renderJobProgressFill");
  if (renderHadProgress && clipFill) clipFill.style.width = "100%";
  if ($("renderClipProgressPct")) $("renderClipProgressPct").textContent = "100%";
  if (jobFill) jobFill.style.width = "100%";
  if ($("renderJobProgressPct")) $("renderJobProgressPct").textContent = "100%";
  const wall = renderSessionT0 ? (Date.now() - renderSessionT0) / 1000 : null;
  const ss = $("renderStatSession");
  if (ss) {
    const base = `Всего прошло: ${wall != null ? formatRenderSeconds(wall) : "—"}`;
    ss.textContent = `${base} · код выхода ${exitCode}.`;
  }
}

function appendRenderModalLine(line) {
  const r = $("renderLogOut");
  const sc = $("renderLogScroll");
  if (!r) return;
  r.textContent += line + "\n";
  if (renderLogModalOpen && sc) sc.scrollTop = sc.scrollHeight;
  if (renderLogModalOpen) updateRenderProgressFromLine(line);
}

function openRenderLogModal(clear) {
  const m = $("renderLogModal");
  if (!m) return;
  renderLogModalOpen = true;
  m.classList.add("is-open");
  m.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  if (clear) {
    const r = $("renderLogOut");
    if (r) r.textContent = "";
    setRenderLogPanelExpanded(false);
    resetRenderProgressUi();
    renderSessionT0 = Date.now();
    renderProcActive = false;
    updateRenderCancelButton();
    startRenderModalTimers();
    setTimeout(() => {
      if (renderLogModalOpen) refreshRenderLiveThumb().catch(() => {});
    }, 400);
  } else if (renderProcActive) {
    startRenderModalTimers();
  }
  const det = $("renderLogDetails");
  if (det?.classList.contains("ccRenderLogDetails--open")) {
    $("renderLogScroll")?.focus({ preventScroll: true });
  } else {
    $("btnShowRenderLogs")?.focus({ preventScroll: true });
  }
}

function closeRenderLogModal() {
  const m = $("renderLogModal");
  if (!m) return;
  stopRenderModalTimers();
  if (renderThumbObjectUrl) {
    URL.revokeObjectURL(renderThumbObjectUrl);
    renderThumbObjectUrl = null;
  }
  renderLogModalOpen = false;
  m.classList.remove("is-open");
  m.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
}

function syncExportModalFromState() {
  const wm = (state.settings.watermark_text || "").trim();
  const saved = (state.settings.video_output_dir || "").trim();
  const inp = $("exportSaveFolder");
  if (inp) inp.value = wm || saved || "";
  const dmin = $("exportDurationMin");
  const dmax = $("exportDurationMax");
  const lo = state.settings.duration_min;
  const hi = state.settings.duration_max;
  if (dmin && lo != null && lo !== "") dmin.value = String(lo);
  if (dmax && hi != null && hi !== "") dmax.value = String(hi);
}

function openExportSettingsModal() {
  syncExportModalFromState();
  const m = $("exportSettingsModal");
  if (!m) return;
  exportSettingsModalOpen = true;
  m.classList.add("is-open");
  m.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  $("exportSaveFolder")?.focus();
}

function closeExportSettingsModal() {
  const m = $("exportSettingsModal");
  if (!m) return;
  exportSettingsModalOpen = false;
  m.classList.remove("is-open");
  m.setAttribute("aria-hidden", "true");
  if (!renderLogModalOpen) document.body.style.overflow = "";
}

function setBanner(text) {
  const b = $("studioBanner");
  if (!text) {
    b.classList.remove("show");
    b.textContent = "";
    return;
  }
  b.textContent = text;
  b.classList.add("show");
}

let ws;
function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${location.host}/ws/logs`;
  ws = new WebSocket(url);
  ws.addEventListener("open", () => appendLog(`[ws] ${url}`));
  ws.addEventListener("message", (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "log") {
        const ln = msg.line || "";
        appendLog(ln);
        appendRenderModalLine(ln);
      }
      if (msg.type === "done") {
        renderProcActive = false;
        updateRenderCancelButton();
        const dn = `[ws] render exit code: ${msg.code}`;
        appendLog(dn);
        appendRenderModalLine(dn);
        finalizeRenderProgress(msg.code);
      }
    } catch {
      appendLog(ev.data);
      appendRenderModalLine(ev.data);
    }
  });
}

function fieldId(key) {
  return `fld_${key}`;
}

/** Конструктор имени выходного mp4 (вкладка «Рендер») */
const OUTPUT_NAME_BUILDER_TYPES = [
  { id: "prefix", label: "Случайный префикс" },
  { id: "hero", label: "Метка для файла (короткий текст)" },
  { id: "headline", label: "Заголовок на карточке" },
  { id: "hashtags", label: "Хештеги из файла" },
  { id: "emoji", label: "Случайный эмодзи" },
  { id: "text", label: "Случайный текст" },
  { id: "literal", label: "Свой текст / пробел" },
];

function defaultOutputNameParts() {
  return [
    { type: "prefix" },
    { type: "literal", value: " " },
    { type: "hero" },
    { type: "literal", value: " " },
    { type: "hashtags" },
  ];
}

function normalizeOutputNameParts(raw) {
  const allowed = new Set(["hero", "headline", "hashtags", "emoji", "text", "prefix", "literal"]);
  if (!Array.isArray(raw) || raw.length === 0) return defaultOutputNameParts();
  const out = [];
  for (const p of raw) {
    if (!p || typeof p !== "object") continue;
    const t = String(p.type || "").toLowerCase();
    if (!allowed.has(t)) continue;
    if (t === "literal") out.push({ type: "literal", value: String(p.value ?? "") });
    else out.push({ type: t });
  }
  return out.length ? out : defaultOutputNameParts();
}

function readOutputNamePartsFromDom() {
  const rows = document.querySelector("#outputNameBuilderMount .ccNameBuilderRows");
  if (!rows) return null;
  const out = [];
  rows.querySelectorAll(":scope > .ccNameBuilderRow").forEach((row) => {
    const sel = row.querySelector(".ccNameBuilderType");
    const lit = row.querySelector(".ccNameBuilderLiteral");
    const type = (sel && sel.value) || "hero";
    if (type === "literal") out.push({ type: "literal", value: lit ? lit.value : "" });
    else out.push({ type });
  });
  return out;
}

function labelForNamePartType(t) {
  const m = OUTPUT_NAME_BUILDER_TYPES.find((x) => x.id === t);
  return m ? m.label : t;
}

function updateOutputNameBuilderPreview() {
  const el = $("outputNameBuilderPreview");
  if (!el) return;
  const parts = readOutputNamePartsFromDom();
  if (!parts || parts.length === 0) {
    el.textContent = "";
    return;
  }
  const chunks = parts.map((p) => {
    if (p.type === "literal") return JSON.stringify(p.value ?? "");
    if (p.type === "hero") return "«Метка»";
    if (p.type === "headline") return "«Заголовок»";
    return `«${labelForNamePartType(p.type)}»`;
  });
  el.textContent = "Порядок: " + chunks.join(" → ");
}

function renderOutputNameBuilderRow(part) {
  const row = document.createElement("div");
  row.className = "ccNameBuilderRow";
  const sel = document.createElement("select");
  sel.className = "ccInput ccNameBuilderType";
  for (const opt of OUTPUT_NAME_BUILDER_TYPES) {
    const o = document.createElement("option");
    o.value = opt.id;
    o.textContent = opt.label;
    sel.appendChild(o);
  }
  sel.value = part.type || "hero";
  const lit = document.createElement("input");
  lit.type = "text";
  lit.className = "ccInput ccNameBuilderLiteral";
  lit.placeholder = "Пробел, скобки, дефис…";
  lit.value = part.type === "literal" ? String(part.value ?? "") : "";
  lit.classList.toggle("is-hidden", sel.value !== "literal");
  sel.addEventListener("change", () => {
    const isLit = sel.value === "literal";
    lit.classList.toggle("is-hidden", !isLit);
    if (!isLit) lit.value = "";
    updateOutputNameBuilderPreview();
  });
  lit.addEventListener("input", () => updateOutputNameBuilderPreview());
  const move = (dir) => () => {
    const wrap = document.querySelector("#outputNameBuilderMount .ccNameBuilderRows");
    if (!wrap) return;
    const all = [...wrap.querySelectorAll(":scope > .ccNameBuilderRow")];
    const i = all.indexOf(row);
    if (i < 0) return;
    const j = i + dir;
    const parts = readOutputNamePartsFromDom();
    if (!parts || j < 0 || j >= parts.length) return;
    const a = parts[i];
    parts[i] = parts[j];
    parts[j] = a;
    mountOutputNameBuilder(parts);
  };
  const btnUp = document.createElement("button");
  btnUp.type = "button";
  btnUp.className = "ccBtn ccBtn--ghost ccNameBuilderIconBtn";
  btnUp.title = "Выше";
  btnUp.textContent = "↑";
  btnUp.addEventListener("click", move(-1));
  const btnDn = document.createElement("button");
  btnDn.type = "button";
  btnDn.className = "ccBtn ccBtn--ghost ccNameBuilderIconBtn";
  btnDn.title = "Ниже";
  btnDn.textContent = "↓";
  btnDn.addEventListener("click", move(1));
  const btnDel = document.createElement("button");
  btnDel.type = "button";
  btnDel.className = "ccBtn ccBtn--ghost ccNameBuilderIconBtn";
  btnDel.title = "Удалить блок";
  btnDel.textContent = "✕";
  btnDel.addEventListener("click", () => {
    const wrap = document.querySelector("#outputNameBuilderMount .ccNameBuilderRows");
    if (!wrap) return;
    const all = [...wrap.querySelectorAll(":scope > .ccNameBuilderRow")];
    const idx = all.indexOf(row);
    const parts = readOutputNamePartsFromDom();
    if (!parts || idx < 0 || parts.length <= 1) return;
    parts.splice(idx, 1);
    mountOutputNameBuilder(parts);
  });
  row.appendChild(sel);
  row.appendChild(lit);
  const tools = document.createElement("div");
  tools.className = "ccNameBuilderRowTools";
  tools.appendChild(btnUp);
  tools.appendChild(btnDn);
  tools.appendChild(btnDel);
  row.appendChild(tools);
  return row;
}

function mountOutputNameBuilder(parts) {
  const mount = $("outputNameBuilderMount");
  if (!mount) return;
  const norm = normalizeOutputNameParts(parts);
  const rowsWrap = document.createElement("div");
  rowsWrap.className = "ccNameBuilderRows";
  norm.forEach((p) => rowsWrap.appendChild(renderOutputNameBuilderRow(p)));
  const bar = document.createElement("div");
  bar.className = "ccNameBuilderBar";
  const add = document.createElement("button");
  add.type = "button";
  add.className = "ccBtn ccBtn--teal ccNameBuilderAdd";
  add.textContent = "+ Добавить блок";
  add.addEventListener("click", () => {
    const cur = readOutputNamePartsFromDom() || norm;
    mountOutputNameBuilder([...cur, { type: "literal", value: " " }]);
  });
  bar.appendChild(add);
  mount.replaceChildren(rowsWrap, bar);
  updateOutputNameBuilderPreview();
}

function initOutputNameBuilderPanel(wrap) {
  const mount = document.createElement("div");
  mount.id = "outputNameBuilderMount";
  mount.className = "ccNameBuilderMount";
  const preview = document.createElement("div");
  preview.id = "outputNameBuilderPreview";
  preview.className = "ccNameBuilderPreview";
  wrap.appendChild(mount);
  wrap.appendChild(preview);
  mountOutputNameBuilder(state.settings?.output_name_parts);
}

function escAttr(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;");
}

/** Текст внутри &lt;textarea&gt;…&lt;/textarea&gt; (без кавычек), переносы строк сохраняются */
function escHtmlText(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;");
}

function normalizeColorHex(s) {
  let t = String(s || "").trim();
  if (!t) return "";
  if (!t.startsWith("#")) t = `#${t}`;
  if (/^#([0-9a-f]{3})$/i.test(t)) {
    const [, a] = t.match(/^#([0-9a-f]{3})$/i);
    return `#${a[0]}${a[0]}${a[1]}${a[1]}${a[2]}${a[2]}`.toUpperCase();
  }
  if (/^#([0-9a-f]{6})$/i.test(t)) return t.toUpperCase();
  return t;
}

function hexToColorInput(hex) {
  const n = normalizeColorHex(hex);
  if (/^#[0-9A-F]{6}$/.test(n)) return n;
  return "#808080";
}

/** Строка «палитра + образец + hex» для полей data-style в редакторе элемента */
function elemColorFieldStyle(label, dataStyleKey, val) {
  const hexVal = escAttr(normalizeColorHex(val) || "#888888");
  const eyeVal = escAttr(hexToColorInput(val));
  return `<div class="ccElemField ccElemColorWrap">
    <label>${escAttr(label)}</label>
    <div class="ccElemColorTools">
      <input type="color" class="ccColorNative ccElemColorEye" value="${eyeVal}" title="Палитра" />
      <div class="ccColorSwatch ccElemColorSwatch" style="background:${hexVal}" aria-hidden="true"></div>
      <input type="text" class="ccInput ccElemColorHex" data-style="${escAttr(dataStyleKey)}" value="${hexVal}" spellcheck="false" />
    </div>
  </div>`;
}

function elemColorFieldLf(which, label, lfKey, val) {
  const hexVal = escAttr(normalizeColorHex(val) || "#888888");
  const eyeVal = escAttr(hexToColorInput(val));
  return `<div class="ccElemField ccElemColorWrap">
    <label>${escAttr(label)}</label>
    <div class="ccElemColorTools">
      <input type="color" class="ccColorNative ccElemColorEye" value="${eyeVal}" title="Палитра" />
      <div class="ccColorSwatch ccElemColorSwatch" style="background:${hexVal}" aria-hidden="true"></div>
      <input type="text" class="ccInput ccElemColorHex" data-lf="${which}" data-lfkey="${escAttr(lfKey)}" value="${hexVal}" spellcheck="false" />
    </div>
  </div>`;
}

function elemColorFieldTop(label, topKey, val) {
  const hexVal = escAttr(normalizeColorHex(val) || "#888888");
  const eyeVal = escAttr(hexToColorInput(val));
  return `<div class="ccElemField ccElemColorWrap">
    <label>${escAttr(label)}</label>
    <div class="ccElemColorTools">
      <input type="color" class="ccColorNative ccElemColorEye" value="${eyeVal}" title="Палитра" />
      <div class="ccColorSwatch ccElemColorSwatch" style="background:${hexVal}" aria-hidden="true"></div>
      <input type="text" class="ccInput ccElemColorHex" data-top="${escAttr(topKey)}" value="${hexVal}" spellcheck="false" />
    </div>
  </div>`;
}

/** Секция редактора элемента: сворачиваемый блок (details/summary) */
function elemDetails(title, innerHtml, open = false) {
  const op = open ? " open" : "";
  return `<details class="ccElemDetails"${op}><summary class="ccElemDetails__summary">${escAttr(title)}</summary><div class="ccElemDetails__body">${innerHtml}</div></details>`;
}

function strokeOuterEnabledFromStyle(st) {
  if (st.stroke_outer_enabled === false) return false;
  if (st.stroke_outer_enabled === true) return true;
  const w = Number(st.stroke_outer_width != null ? st.stroke_outer_width : st.stroke_width ?? 0);
  return w > 0;
}

function strokeOuterWidthVal(st) {
  return Number(st.stroke_outer_width != null ? st.stroke_outer_width : st.stroke_width ?? 0);
}

function strokeOuterColorVal(st) {
  return st.stroke_outer_color || st.stroke_color || "#000000";
}

function bgStrokeOuterEnabledFromStyle(st) {
  if (st.bg_stroke_outer_enabled === false) return false;
  if (st.bg_stroke_outer_enabled === true) return true;
  const sw = Number(st.bg_stroke_width || 0);
  return Boolean(st.bg_stroke_outside) && sw > 0;
}
function bgStrokeInnerEnabledFromStyle(st) {
  if (st.bg_stroke_inner_enabled === false) return false;
  if (st.bg_stroke_inner_enabled === true) return true;
  const sw = Number(st.bg_stroke_width || 0);
  return st.bg_stroke_inside !== false && sw > 0;
}
function bgStrokeOuterWidthDisp(st) {
  if (st.bg_stroke_outer_width != null && st.bg_stroke_outer_width !== "") return Number(st.bg_stroke_outer_width);
  return bgStrokeOuterEnabledFromStyle(st) ? Number(st.bg_stroke_width || 0) : 0;
}
function bgStrokeInnerWidthDisp(st) {
  if (st.bg_stroke_inner_width != null && st.bg_stroke_inner_width !== "") return Number(st.bg_stroke_inner_width);
  return bgStrokeInnerEnabledFromStyle(st) ? Number(st.bg_stroke_width || 0) : 0;
}
function bgStrokeOuterColorDisp(st) {
  return st.bg_stroke_outer_color || st.bg_stroke_color || "#FFFFFF";
}
function bgStrokeInnerColorDisp(st) {
  return st.bg_stroke_inner_color || st.bg_stroke_color || "#FFFFFF";
}

/** Цвет квадрата-превью для строки палитры (#hex или linear-gradient…) */
function swatchForBgSpec(s) {
  const t = String(s || "").trim();
  if (!t) return "#2A3852";
  const m = t.match(/^linear-gradient\s*\(\s*(?:180deg|to\s+bottom)\s*,\s*(#[0-9a-fA-F]{3,8})\s*,/i);
  if (m) return normalizeColorHex(m[1]) || "#2A3852";
  return normalizeColorHex(t) || "#2A3852";
}

/** linear-gradient(180deg|to bottom, #a, #b) → [fullMatch, c1, c2] или null */
function parseLinearGradient180Full(spec) {
  const t = String(spec || "").trim();
  const m = t.match(/^linear-gradient\s*\(\s*(?:180deg|to\s+bottom)\s*,\s*(#[0-9a-fA-F]{3,8})\s*,\s*(#[0-9a-fA-F]{3,8})\s*\)\s*$/i);
  return m || null;
}

/** Клон настроек: для превью подменить подложку так, будто выбрана одна строка палитры (без сохранения). */
function buildSettingsWithBgPaletteLinePreview(settings, hit, spec) {
  const s = JSON.parse(JSON.stringify(settings));
  const specTrim = String(spec || "").trim();
  if (!specTrim) return s;
  const g = parseLinearGradient180Full(specTrim);

  const applyToStyle = (baseStyle) => {
    const cur = { ...STYLE_BASE, ...(baseStyle && typeof baseStyle === "object" ? baseStyle : {}) };
    let out = { ...cur };
    if (g) {
      out.bg_use_gradient = true;
      out.bg_gradient_start = normalizeColorHex(g[1]) || g[1];
      out.bg_gradient_end = normalizeColorHex(g[2]) || g[2];
      out.bg_colors = [];
    } else {
      out.bg_use_gradient = false;
      const hx = normalizeColorHex(specTrim);
      if (hx && /^#[0-9A-F]{6}$/i.test(hx)) out.bg_color = hx;
      out.bg_colors = [];
    }
    out.bg_enabled = true;
    return syncLegacyTextStrokeFields(out);
  };

  if (typeof hit === "string" && hit.startsWith("overlay:")) {
    const id = hit.slice(8);
    const arr = Array.isArray(s.scene_overlays) ? s.scene_overlays : [];
    const idx = arr.findIndex((o) => o && String(o.id) === id);
    if (idx < 0) return s;
    const ov = { ...arr[idx] };
    ov.style = applyToStyle(ov.style || {});
    arr[idx] = ov;
    s.scene_overlays = arr;
    return s;
  }
  if (["title", "subtitle", "dates", "watermark"].includes(hit)) {
    const ts = ensureTextStyles(s);
    const base = getMergedStyle(s, hit);
    ts[hit] = applyToStyle(base);
    return s;
  }
  return s;
}

/** Клон настроек: превью одной строки палитры / пары / базы «к светлому» в кадре (без сохранения). */
function buildSettingsWithTextFillRowPreview(settings, hit, ov) {
  if (!ov || !ov.kind || !hit) return settings;
  const s = JSON.parse(JSON.stringify(settings));
  const patch = (stIn) => {
    const st = { ...STYLE_BASE, ...(stIn && typeof stIn === "object" ? stIn : {}) };
    if (ov.kind === "static") {
      const hx = normalizeColorHex(ov.hex) || String(ov.hex || "").trim();
      if (!hx) return stIn;
      return syncLegacyTextStrokeFields({
        ...st,
        text_fill_mode: "static_palette",
        text_palette_colors: [hx],
        text_alternate_pairs: [],
        text_lighten_bases: [],
        use_gradient: false,
      });
    }
    if (ov.kind === "pair" && ov.pair) {
      const a = String(ov.pair.a || "").trim();
      const b = String(ov.pair.b || "").trim();
      if (!a || !b) return stIn;
      return syncLegacyTextStrokeFields({
        ...st,
        text_fill_mode: "alternate_pairs",
        text_alternate_pairs: [{ a, b }],
        text_palette_colors: [],
        text_lighten_bases: [],
        use_gradient: false,
      });
    }
    if (ov.kind === "lighten") {
      const hx = normalizeColorHex(ov.hex) || String(ov.hex || "").trim();
      if (!hx) return stIn;
      return syncLegacyTextStrokeFields({
        ...st,
        text_fill_mode: "lighten_lines",
        text_lighten_bases: [hx],
        text_palette_colors: [],
        text_alternate_pairs: [],
        use_gradient: false,
      });
    }
    return stIn;
  };
  if (typeof hit === "string" && hit.startsWith("overlay:")) {
    const id = hit.slice(8);
    const arr = Array.isArray(s.scene_overlays) ? [...s.scene_overlays] : [];
    const idx = arr.findIndex((o) => o && String(o.id) === id);
    if (idx < 0) return s;
    const ov0 = { ...arr[idx] };
    if ((ov0.kind || "text") !== "text") return s;
    ov0.style = patch({
      ...STYLE_PRESETS.subtitle,
      ...(ov0.style && typeof ov0.style === "object" ? ov0.style : {}),
    });
    arr[idx] = ov0;
    s.scene_overlays = arr;
    return s;
  }
  if (["title", "subtitle", "dates", "watermark"].includes(hit)) {
    const ts = ensureTextStyles(s);
    const cur = getMergedStyle(s, hit);
    ts[hit] = patch(cur);
    return s;
  }
  return s;
}

/** Одна строка палитры блика (только сплошной #RRGGBB, без градиентов). */
function glowPaletteRowHtml(hex) {
  const n = normalizeColorHex(hex);
  const col = /^#[0-9A-F]{6}$/.test(n) ? n : "#B9E6FF";
  const sw = escAttr(col);
  const eye = escAttr(hexToColorInput(col));
  const hv = escAttr(col);
  return `<div class="ccGlowPaletteRow ccElemColorWrap" style="margin-top:6px;display:flex;align-items:center;gap:8px;width:100%">
    <div class="ccElemColorTools" style="flex:1;min-width:0">
      <input type="color" class="ccColorNative ccElemColorEye" value="${eye}" title="Палитра" />
      <div class="ccColorSwatch ccElemColorSwatch" style="background:${sw}" aria-hidden="true"></div>
      <input type="text" class="ccInput ccElemColorHex ccGlowPaletteHex" value="${hv}" spellcheck="false" />
    </div>
    <button type="button" class="ccBtn ccBtn--ghost ccGlowPaletteDel">Удалить</button>
  </div>`;
}

function bindGlowPaletteRowPreviewSync(row) {
  if (!row) return;
  row.querySelectorAll(".ccElemColorEye, .ccGlowPaletteHex").forEach((el) => {
    el.addEventListener("input", () => schedulePreviewSlow());
  });
}

/** @param {HTMLElement | null} root */
function paintGlowPaletteRoot(root, colors) {
  if (!root) return;
  const arr = Array.isArray(colors) ? colors : [];
  const normalized = arr
    .map((c) => normalizeColorHex(c))
    .filter((n) => /^#[0-9A-F]{6}$/.test(n));
  root.innerHTML = normalized.map((n) => glowPaletteRowHtml(n)).join("");
  root.querySelectorAll(".ccGlowPaletteDel").forEach((del) => {
    del.addEventListener("click", () => {
      del.closest(".ccGlowPaletteRow")?.remove();
      schedulePreviewSlow();
    });
  });
  wireElemEditorColorRows(root);
  root.querySelectorAll(".ccGlowPaletteRow").forEach((row) => bindGlowPaletteRowPreviewSync(row));
}

function wireGlowPaletteField(wrap) {
  const root = wrap && wrap.querySelector(".ccGlowPaletteRoot");
  const addBtn = wrap && wrap.querySelector("[data-glow-palette-add]");
  if (!root || !addBtn) return;
  addBtn.addEventListener("click", () => {
    const frag = document.createElement("div");
    frag.innerHTML = glowPaletteRowHtml("#B9E6FF").trim();
    const el = frag.firstElementChild;
    if (!el) return;
    root.appendChild(el);
    wireElemEditorColorRows(el);
    bindGlowPaletteRowPreviewSync(el);
    el.querySelector(".ccGlowPaletteDel")?.addEventListener("click", () => {
      el.remove();
      schedulePreviewSlow();
    });
    schedulePreviewSlow();
  });
}

function bgPaletteRowOuterHtml(spec) {
  const v = String(spec || "").trim() || "#1A2430";
  const sw = escAttr(swatchForBgSpec(v));
  const eye = escAttr(/^linear-gradient/i.test(v) ? "#808080" : hexToColorInput(v));
  const hv = escAttr(v);
  return `<div class="ccBgPaletteRow ccElemColorWrap" style="margin-top:6px;display:flex;align-items:center;gap:8px;width:100%">
    <div class="ccElemColorTools" style="flex:1;min-width:0">
      <input type="color" class="ccColorNative ccElemColorEye" value="${eye}" title="Палитра" />
      <div class="ccColorSwatch ccElemColorSwatch" style="background:${sw}" aria-hidden="true"></div>
      <input type="text" class="ccInput ccElemColorHex ccBgPaletteHex" value="${hv}" spellcheck="false" />
    </div>
    <button type="button" class="ccBtn ccBtn--ghost ccBgPalettePreview" title="Показать этот вариант в превью (ещё раз — сброс)" aria-label="Превью в кадре">👁</button>
    <button type="button" class="ccBtn ccBtn--ghost ccBgPaletteDel">Удалить</button>
  </div>`;
}

function renderTextStyleBgPalette(st) {
  const raw = st.bg_colors;
  let lines = [];
  if (Array.isArray(raw)) lines = raw.map((x) => String(x).trim()).filter(Boolean);
  else if (typeof raw === "string") lines = raw.split(/[\n,;]+/).map((x) => x.trim()).filter(Boolean);
  const rowsHtml = lines.map(bgPaletteRowOuterHtml).join("");
  return `
    <div class="ccElemField" style="margin-top:10px">
      <label>Случайный цвет подложки (каждое новое видео)</label>
      <p class="ccElemField__hint" style="margin:4px 0 8px 0">Если список не пуст — при рендере выбирается случайная строка. Пустой список = только «Цвет подложки» выше. Можно вписать <code>linear-gradient(180deg, #0a1628, #1e3a4a)</code>. Кнопка 👁 — как будет выглядеть эта строка в превью (без сохранения; повторный щелчок по активной — сброс).</p>
      <div class="ccBgPalette" data-bg-palette-root>${rowsHtml}</div>
      <button type="button" class="ccBtn ccBtn--ghost" data-bg-palette-add style="margin-top:8px">+ Добавить цвет</button>
    </div>`;
}

function renderTextStyleBgSection(st) {
  const bow = bgStrokeOuterWidthDisp(st);
  const boc = bgStrokeOuterColorDisp(st);
  const biw = bgStrokeInnerWidthDisp(st);
  const bic = bgStrokeInnerColorDisp(st);
  const cr = st.bg_corner_radius != null ? st.bg_corner_radius : 12;
  return `
    <label class="ccElemCheck"><input type="checkbox" data-style="bg_enabled" ${st.bg_enabled ? "checked" : ""} data-bg-enabled-toggle /> Включить подложку</label>
    <p class="ccElemField__hint">При включённой подложке размер подложки не следует за шрифтом — меняется только текст. Запомненный размер подложки задаётся при первом превью; «Сброс…» — привязать снова к текущему тексту. Ниже можно задать фиксированный прямоугольник.</p>
    <button type="button" class="ccBtn ccBtn--ghost" data-bg-reset-snap>Сбросить запомненный размер подложки</button>
    <input type="hidden" data-style="bg_snap_inner_w" value="${escAttr(st.bg_snap_inner_w != null ? st.bg_snap_inner_w : 0)}" />
    <input type="hidden" data-style="bg_snap_inner_h" value="${escAttr(st.bg_snap_inner_h != null ? st.bg_snap_inner_h : 0)}" />
    <label class="ccElemCheck"><input type="checkbox" data-style="bg_use_gradient" ${st.bg_use_gradient ? "checked" : ""} /> Градиент подложки</label>
    <div class="ccElemRow2">
      ${elemColorFieldStyle("Цвет подложки", "bg_color", st.bg_color)}
      <div class="ccElemField"><label>Непрозрачность подложки (0–255)</label><input class="ccInput" type="number" data-style="bg_opacity" min="0" max="255" step="1" value="${escAttr(st.bg_opacity)}" /></div>
    </div>
    <div class="ccElemRow2">
      <div class="ccElemField"><label>Отступ X / Y</label>
        <div class="ccElemRow2" style="margin-top:4px">
          <input class="ccInput" type="number" data-style="bg_padding_x" step="1" value="${escAttr(st.bg_padding_x)}" />
          <input class="ccInput" type="number" data-style="bg_padding_y" step="1" value="${escAttr(st.bg_padding_y)}" />
        </div>
      </div>
      <div class="ccElemField"><label>Скругление подложки (px, 0 = без)</label><input class="ccInput" type="number" data-style="bg_corner_radius" min="0" max="80" step="1" value="${escAttr(cr)}" /></div>
    </div>
    <label class="ccElemCheck"><input type="checkbox" data-style="bg_use_fixed_inner_box" ${st.bg_use_fixed_inner_box ? "checked" : ""} /> Фиксированный размер подложки (не от размера шрифта)</label>
    <div class="ccElemRow2">
      <div class="ccElemField"><label>Ширина блока подложки (px, без отступов; 0 = авто)</label><input class="ccInput" type="number" data-style="bg_fixed_width" min="0" max="1080" step="1" value="${escAttr(st.bg_fixed_width != null ? st.bg_fixed_width : 0)}" /></div>
      <div class="ccElemField"><label>Высота блока подложки (px; 0 = авто)</label><input class="ccInput" type="number" data-style="bg_fixed_height" min="0" max="2000" step="1" value="${escAttr(st.bg_fixed_height != null ? st.bg_fixed_height : 0)}" /></div>
    </div>
    <p class="ccElemField__hint">Включите и задайте ширину и высоту: прямоугольник центрируется на тексте; «Размер описания» / колёсико меняют только шрифт. 0×0 или выкл. — подложка по границам текста, как раньше.</p>
    <div class="ccElemSection">Обводка подложки</div>
    <label class="ccElemCheck"><input type="checkbox" data-style="bg_stroke_outer_enabled" ${bgStrokeOuterEnabledFromStyle(st) ? "checked" : ""} /> Внешняя</label>
    <div class="ccElemRow2">
      ${elemColorFieldStyle("Цвет снаружи", "bg_stroke_outer_color", boc)}
      <div class="ccElemField"><label>Толщина снаружи (px)</label><input class="ccInput" type="number" data-style="bg_stroke_outer_width" min="0" max="24" step="1" value="${escAttr(bow)}" /></div>
    </div>
    <label class="ccElemCheck"><input type="checkbox" data-style="bg_stroke_inner_enabled" ${bgStrokeInnerEnabledFromStyle(st) ? "checked" : ""} /> Внутренняя</label>
    <div class="ccElemRow2">
      ${elemColorFieldStyle("Цвет внутри", "bg_stroke_inner_color", bic)}
      <div class="ccElemField"><label>Толщина внутри (px)</label><input class="ccInput" type="number" data-style="bg_stroke_inner_width" min="0" max="24" step="1" value="${escAttr(biw)}" /></div>
    </div>
    <p class="ccElemField__hint">Старые пресеты без отдельных полей используют толщину ниже и галочки «внутри / снаружи».</p>
    <div class="ccElemRow2">
      ${elemColorFieldStyle("Цвет обводки (legacy)", "bg_stroke_color", st.bg_stroke_color)}
      <div class="ccElemField"><label>Толщина (legacy, px)</label><input class="ccInput" type="number" data-style="bg_stroke_width" min="0" max="16" step="1" value="${escAttr(st.bg_stroke_width)}" /></div>
    </div>
    <div class="ccElemRow2 ccElemRow2--checks">
      <label class="ccElemCheck"><input type="checkbox" data-style="bg_stroke_inside" ${st.bg_stroke_inside !== false ? "checked" : ""} /> Внутри (legacy)</label>
      <label class="ccElemCheck"><input type="checkbox" data-style="bg_stroke_outside" ${st.bg_stroke_outside ? "checked" : ""} /> Снаружи (legacy)</label>
    </div>
    <div class="ccElemRow2">
      ${elemColorFieldStyle("Градиент подложки — начало", "bg_gradient_start", st.bg_gradient_start)}
      ${elemColorFieldStyle("Градиент подложки — конец", "bg_gradient_end", st.bg_gradient_end)}
    </div>
    <div class="ccElemField"><label>Картинка подложки</label>
      <div class="ccFontPickRow">
        <input class="ccInput" type="text" readonly data-style="bg_image" value="${escAttr(st.bg_image)}" title="Файл или папка с картинками" spellcheck="false" />
        <button type="button" class="ccBtn ccBtn--ghost" data-pick-bg-image="file">Файл…</button>
        <button type="button" class="ccBtn ccBtn--ghost" data-pick-bg-image="folder">Папка…</button>
        <button type="button" class="ccBtn ccBtn--ghost" data-clear-bg-image title="Очистить">✕</button>
      </div>
      <p class="ccElemField__hint">Папка с несколькими изображениями — при рендере случайный файл из папки.</p>
    </div>
    ${renderTextStyleBgPalette(st)}`;
}

function renderTextPaletteRows(colors) {
  const arr = Array.isArray(colors) ? colors : [];
  const lines = arr.length ? arr : [""];
  return lines
    .map(
      (hv) => `
    <div class="ccBgPaletteRow ccElemColorWrap" style="margin-top:6px;display:flex;align-items:center;gap:8px;width:100%">
      <div class="ccElemColorTools" style="flex:1;min-width:0">
        <input type="color" class="ccColorNative ccElemColorEye" value="${escAttr(hexToColorInput(String(hv || "#FFFFFF")))}" title="Палитра" />
        <div class="ccColorSwatch ccElemColorSwatch" style="background:${escAttr(swatchForBgSpec(String(hv || "#FFFFFF")))}" aria-hidden="true"></div>
        <input type="text" class="ccInput ccElemColorHex ccTextPaletteHex" value="${escAttr(String(hv || ""))}" spellcheck="false" />
      </div>
      <button type="button" class="ccBtn ccBtn--ghost ccTextFillPreviewEye" title="Превью в кадре (ещё раз — сброс)" aria-label="Превью">👁</button>
      <button type="button" class="ccBtn ccBtn--ghost ccTextPaletteDel">Удалить</button>
    </div>`,
    )
    .join("");
}

function renderAlternatePairRows(pairs) {
  const arr = Array.isArray(pairs) ? pairs : [];
  const rows = arr.length ? arr : [{ a: "#FFFFFF", b: "#4AA3FF" }];
  return rows
    .map((p) => {
      const a = String((p && p.a) || (Array.isArray(p) ? p[0] : "") || "#FFFFFF");
      const b = String((p && p.b) || (Array.isArray(p) ? p[1] : "") || "#4AA3FF");
      return `
    <div class="ccAltPairRow" style="margin-top:8px;display:flex;flex-wrap:wrap;align-items:center;gap:8px;width:100%">
      <span class="ccElemField__hint" style="margin:0;width:100%">Пара</span>
      <div class="ccElemColorWrap" style="flex:1;min-width:140px">
        <div class="ccElemColorTools">
          <input type="color" class="ccColorNative ccElemColorEye" value="${escAttr(hexToColorInput(a))}" />
          <div class="ccColorSwatch ccElemColorSwatch" style="background:${escAttr(normalizeColorHex(a) || "#FFFFFF")}" aria-hidden="true"></div>
          <input type="text" class="ccInput ccElemColorHex ccAltPairA" value="${escAttr(a)}" spellcheck="false" />
        </div>
      </div>
      <div class="ccElemColorWrap" style="flex:1;min-width:140px">
        <div class="ccElemColorTools">
          <input type="color" class="ccColorNative ccElemColorEye" value="${escAttr(hexToColorInput(b))}" />
          <div class="ccColorSwatch ccElemColorSwatch" style="background:${escAttr(normalizeColorHex(b) || "#4AA3FF")}" aria-hidden="true"></div>
          <input type="text" class="ccInput ccElemColorHex ccAltPairB" value="${escAttr(b)}" spellcheck="false" />
        </div>
      </div>
      <button type="button" class="ccBtn ccBtn--ghost ccTextFillPreviewPairEye" title="Превью этой пары в кадре (ещё раз — сброс)" aria-label="Превью">👁</button>
      <button type="button" class="ccBtn ccBtn--ghost ccAltPairDel">Удалить пару</button>
    </div>`;
    })
    .join("");
}

function renderTextStyleFillSection(st) {
  const mode = String(st.text_fill_mode || "").trim() || "gradient";
  const pal = Array.isArray(st.text_palette_colors) ? st.text_palette_colors : [];
  const pairs = Array.isArray(st.text_alternate_pairs) ? st.text_alternate_pairs : [];
  const bases = Array.isArray(st.text_lighten_bases) ? st.text_lighten_bases : [];
  const gradOn = Boolean(st.use_gradient);
  return `
    <div class="ccElemSection">Стили текста</div>
    <div class="ccElemField"><label>Режим заливки текста</label>
      <select class="ccInput" data-style="text_fill_mode">
        <option value="gradient" ${mode === "gradient" || !mode ? "selected" : ""}>Градиент (два цвета)</option>
        <option value="solid" ${mode === "solid" ? "selected" : ""}>Один цвет</option>
        <option value="static_palette" ${mode === "static_palette" ? "selected" : ""}>Статичный: случайный из списка</option>
        <option value="alternate_pairs" ${mode === "alternate_pairs" ? "selected" : ""}>Чередование двух цветов по строкам</option>
        <option value="lighten_lines" ${mode === "lighten_lines" ? "selected" : ""}>К светлому: каждая строка светлее</option>
      </select>
    </div>
    <div data-text-fill-panel="gradient" style="display:${mode === "gradient" || !mode ? "block" : "none"}">
      <label class="ccElemCheck"><input type="checkbox" data-style="use_gradient" ${gradOn ? "checked" : ""} /> Градиент текста</label>
      <div class="ccElemRow2">
        ${elemColorFieldStyle("Цвет / начало градиента", "gradient_start", st.gradient_start)}
        ${elemColorFieldStyle("Конец градиента", "gradient_end", st.gradient_end)}
      </div>
    </div>
    <div data-text-fill-panel="solid" style="display:${mode === "solid" ? "block" : "none"}">
      <div class="ccElemColorWrap ccElemField">
        <label>Цвет текста</label>
        <div class="ccElemColorTools" style="margin-top:6px">
          <input type="color" class="ccColorNative ccElemColorEye" value="${escAttr(hexToColorInput(st.gradient_start || "#FFFFFF"))}" />
          <div class="ccColorSwatch ccElemColorSwatch" style="background:${escAttr(normalizeColorHex(st.gradient_start) || "#FFFFFF")}" aria-hidden="true"></div>
          <input type="text" class="ccInput ccElemColorHex" data-text-solid-hex value="${escAttr(st.gradient_start)}" spellcheck="false" />
        </div>
      </div>
    </div>
    <div data-text-fill-panel="static_palette" style="display:${mode === "static_palette" ? "block" : "none"}">
      <p class="ccElemField__hint">Несколько цветов — при рендере выбирается случайный. «Добавить цвет» добавляет случайный оттенок в список.</p>
      <div class="ccTextPalette" data-text-palette-root>${renderTextPaletteRows(pal)}</div>
      <button type="button" class="ccBtn ccBtn--ghost" data-text-palette-add>Добавить цвет</button>
    </div>
    <div data-text-fill-panel="alternate_pairs" style="display:${mode === "alternate_pairs" ? "block" : "none"}">
      <p class="ccElemField__hint">Строка 1 — цвет A, строка 2 — B, снова A… Несколько пар — при рендере случайная пара.</p>
      <div data-text-alt-pairs-root>${renderAlternatePairRows(pairs)}</div>
      <button type="button" class="ccBtn ccBtn--ghost" data-text-alt-pair-add>Добавить цвет (пара)</button>
    </div>
    <div data-text-fill-panel="lighten_lines" style="display:${mode === "lighten_lines" ? "block" : "none"}">
      <p class="ccElemField__hint">Базовый цвет; каждая следующая строка светлее. Несколько баз — при рендере случайная.</p>
      <div class="ccTextLightenRoot" data-text-lighten-root>${renderTextPaletteRows(bases)}</div>
      <button type="button" class="ccBtn ccBtn--ghost" data-text-lighten-add>Добавить цвет</button>
    </div>`;
}

function collectTextFillFromModal(body) {
  const o = {};
  if (!body) return o;
  const modeSel = body.querySelector('[data-style="text_fill_mode"]');
  if (modeSel) o.text_fill_mode = String(modeSel.value || "").trim();
  const palRoot = body.querySelector("[data-text-palette-root]");
  if (palRoot) {
    const cols = [];
    palRoot.querySelectorAll(".ccTextPaletteHex").forEach((inp) => {
      const v = String(inp.value || "").trim();
      if (v) cols.push(v);
    });
    o.text_palette_colors = cols;
  }
  const altRoot = body.querySelector("[data-text-alt-pairs-root]");
  if (altRoot) {
    const pairs = [];
    altRoot.querySelectorAll(".ccAltPairRow").forEach((row) => {
      const a = String(row.querySelector(".ccAltPairA")?.value || "").trim();
      const b = String(row.querySelector(".ccAltPairB")?.value || "").trim();
      if (a && b) pairs.push({ a, b });
    });
    o.text_alternate_pairs = pairs;
  }
  const litRoot = body.querySelector("[data-text-lighten-root]");
  if (litRoot) {
    const bases = [];
    litRoot.querySelectorAll(".ccTextPaletteHex").forEach((inp) => {
      const v = String(inp.value || "").trim();
      if (v) bases.push(v);
    });
    o.text_lighten_bases = bases;
  }
  const ug = body.querySelector('[data-style="use_gradient"]');
  if (ug) o.use_gradient = Boolean(ug.checked);
  const solidHex = body.querySelector("[data-text-solid-hex]");
  const m = String(o.text_fill_mode || "").trim();
  if (solidHex && m === "solid") {
    const v = normalizeColorHex(solidHex.value) || String(solidHex.value || "").trim();
    if (v) o.gradient_start = v;
  }
  if (m === "solid") o.use_gradient = false;
  return o;
}

function wireTextFillMode(body) {
  if (!body) return;
  const sel = body.querySelector('[data-style="text_fill_mode"]');
  if (!sel) return;
  const sync = () => {
    textFillPreviewOverride = null;
    clearTextFillPreviewMarks(body);
    const m = String(sel.value || "").trim() || "gradient";
    body.querySelectorAll("[data-text-fill-panel]").forEach((p) => {
      p.style.display = p.getAttribute("data-text-fill-panel") === m ? "block" : "none";
    });
    if (m === "solid") {
      const ug = body.querySelector('[data-style="use_gradient"]');
      if (ug) ug.checked = false;
    }
    schedulePreviewSlow();
  };
  sel.addEventListener("change", sync);
  sync();
}

function clearTextFillPreviewMarks(body) {
  if (!body || !body.querySelectorAll) return;
  body.querySelectorAll(".is-text-fill-preview").forEach((el) => el.classList.remove("is-text-fill-preview"));
}

function bindTextFillPreviewRowEye(body, row, btn, kind) {
  if (!btn || !row || !body) return;
  btn.addEventListener("click", () => {
    const hit = elementEditorHit;
    if (!hit) return;
    if (kind === "pair") {
      const a = String(row.querySelector(".ccAltPairA")?.value || "").trim();
      const b = String(row.querySelector(".ccAltPairB")?.value || "").trim();
      if (!a || !b) return;
      const same =
        textFillPreviewOverride &&
        textFillPreviewOverride.hit === hit &&
        textFillPreviewOverride.kind === "pair" &&
        textFillPreviewOverride.pair &&
        String(textFillPreviewOverride.pair.a) === a &&
        String(textFillPreviewOverride.pair.b) === b &&
        row.classList.contains("is-text-fill-preview");
      if (same) {
        textFillPreviewOverride = null;
        row.classList.remove("is-text-fill-preview");
        schedulePreviewFast();
        return;
      }
      clearTextFillPreviewMarks(body);
      row.classList.add("is-text-fill-preview");
      textFillPreviewOverride = { hit, kind: "pair", pair: { a, b } };
      schedulePreviewFast();
      return;
    }
    const hexInp = row.querySelector(".ccTextPaletteHex");
    const hex = hexInp ? String(hexInp.value || "").trim() : "";
    if (!hex) return;
    const same =
      textFillPreviewOverride &&
      textFillPreviewOverride.hit === hit &&
      textFillPreviewOverride.kind === kind &&
      String(textFillPreviewOverride.hex || "") === hex &&
      row.classList.contains("is-text-fill-preview");
    if (same) {
      textFillPreviewOverride = null;
      row.classList.remove("is-text-fill-preview");
      schedulePreviewFast();
      return;
    }
    clearTextFillPreviewMarks(body);
    row.classList.add("is-text-fill-preview");
    textFillPreviewOverride = { hit, kind, hex };
    schedulePreviewFast();
  });
}

function wireTextFillPreviewEyes(body) {
  if (!body || !elementEditorHit) return;
  body.querySelectorAll("[data-text-palette-root] .ccTextFillPreviewEye").forEach((btn) => {
    const row = btn.closest(".ccBgPaletteRow");
    bindTextFillPreviewRowEye(body, row, btn, "static");
  });
  body.querySelectorAll("[data-text-lighten-root] .ccTextFillPreviewEye").forEach((btn) => {
    const row = btn.closest(".ccBgPaletteRow");
    bindTextFillPreviewRowEye(body, row, btn, "lighten");
  });
  body.querySelectorAll(".ccTextFillPreviewPairEye").forEach((btn) => {
    const row = btn.closest(".ccAltPairRow");
    bindTextFillPreviewRowEye(body, row, btn, "pair");
  });
}

function wireTextFillPalettes(body) {
  if (!body) return;
  const palAdd = body.querySelector("[data-text-palette-add]");
  const palRoot = body.querySelector("[data-text-palette-root]");
  if (palAdd && palRoot) {
    palAdd.addEventListener("click", () => {
      const wrap = document.createElement("div");
      wrap.innerHTML = renderTextPaletteRows([randomHexColor()]).trim();
      const el = wrap.firstElementChild;
      if (el) {
        palRoot.appendChild(el);
        wireElemEditorColorRows(el);
        const pe = el.querySelector(".ccTextFillPreviewEye");
        if (pe) bindTextFillPreviewRowEye(body, el, pe, "static");
        el.querySelector(".ccTextPaletteDel")?.addEventListener("click", () => {
          el.remove();
          schedulePreviewSlow();
        });
      }
      schedulePreviewSlow();
    });
    palRoot.querySelectorAll(".ccTextPaletteDel").forEach((b) => {
      b.addEventListener("click", () => {
        b.closest(".ccBgPaletteRow")?.remove();
        schedulePreviewSlow();
      });
    });
  }
  const altAdd = body.querySelector("[data-text-alt-pair-add]");
  const altRoot = body.querySelector("[data-text-alt-pairs-root]");
  if (altAdd && altRoot) {
    altAdd.addEventListener("click", () => {
      const wrap = document.createElement("div");
      wrap.innerHTML = renderAlternatePairRows([{ a: randomHexColor(), b: randomHexColor() }]).trim();
      const el = wrap.firstElementChild;
      if (el) {
        altRoot.appendChild(el);
        wireElemEditorColorRows(el);
        const pe = el.querySelector(".ccTextFillPreviewPairEye");
        if (pe) bindTextFillPreviewRowEye(body, el, pe, "pair");
        el.querySelector(".ccAltPairDel")?.addEventListener("click", () => {
          el.remove();
          schedulePreviewSlow();
        });
      }
      schedulePreviewSlow();
    });
    altRoot.querySelectorAll(".ccAltPairDel").forEach((b) => {
      b.addEventListener("click", () => {
        b.closest(".ccAltPairRow")?.remove();
        schedulePreviewSlow();
      });
    });
  }
  const lnAdd = body.querySelector("[data-text-lighten-add]");
  const lnRoot = body.querySelector("[data-text-lighten-root]");
  if (lnAdd && lnRoot) {
    lnAdd.addEventListener("click", () => {
      const wrap = document.createElement("div");
      wrap.innerHTML = renderTextPaletteRows([randomHexColor()]).trim();
      const el = wrap.firstElementChild;
      if (el) {
        lnRoot.appendChild(el);
        wireElemEditorColorRows(el);
        const pe = el.querySelector(".ccTextFillPreviewEye");
        if (pe) bindTextFillPreviewRowEye(body, el, pe, "lighten");
        el.querySelector(".ccTextPaletteDel")?.addEventListener("click", () => {
          el.remove();
          schedulePreviewSlow();
        });
      }
      schedulePreviewSlow();
    });
    lnRoot.querySelectorAll(".ccTextPaletteDel").forEach((b) => {
      b.addEventListener("click", () => {
        b.closest(".ccBgPaletteRow")?.remove();
        schedulePreviewSlow();
      });
    });
  }
  wireTextFillPreviewEyes(body);
}

function wireOverlaySrcPick(body, isGif) {
  const btn = body.querySelector("[data-ov-src-pick]");
  const inp = body.querySelector('[data-ov-field="src"]');
  if (!btn || !inp) return;
  btn.addEventListener("click", async () => {
    const p = await pickFileNative({
      title: isGif ? "Выберите GIF" : "Выберите изображение",
      filters: isGif
        ? [{ name: "GIF", extensions: ["gif"] }]
        : [{ name: "Изображения", extensions: ["png", "jpg", "jpeg", "webp", "bmp", "gif"] }],
      filetypesForWorker: isGif
        ? [["GIF", "*.gif"], ["Все файлы", "*.*"]]
        : [["Изображения", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"], ["Все файлы", "*.*"]],
    });
    if (p) {
      inp.value = p;
      schedulePreviewSlow();
    }
  });
}

function wireBgImagePickers(body) {
  if (!body) return;
  const inp = body.querySelector('[data-style="bg_image"]');
  if (!inp) return;
  body.querySelector("[data-pick-bg-image=\"file\"]")?.addEventListener("click", async () => {
    const p = await pickFileNative({
      title: "Картинка подложки",
      filters: [{ name: "Изображения", extensions: ["png", "jpg", "jpeg", "webp", "bmp", "gif"] }],
      filetypesForWorker: [["Изображения", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"], ["Все файлы", "*.*"]],
    });
    if (p) {
      inp.value = p;
      schedulePreviewSlow();
    }
  });
  body.querySelector("[data-pick-bg-image=\"folder\"]")?.addEventListener("click", async () => {
    const p = await pickFolderNative({ title: "Папка с картинками для подложки" });
    if (p) {
      inp.value = p;
      schedulePreviewSlow();
    }
  });
  body.querySelector("[data-clear-bg-image]")?.addEventListener("click", () => {
    inp.value = "";
    schedulePreviewSlow();
  });
}

/** Синхронизация stroke_width / stroke_color с внешней обводкой для старых полей пресета */
function syncLegacyTextStrokeFields(m) {
  const out = { ...m };
  const ow = out.stroke_outer_width != null ? Number(out.stroke_outer_width) : Number(out.stroke_width || 0);
  out.stroke_outer_width = ow;
  out.stroke_width = ow;
  const oc = out.stroke_outer_color;
  if (oc != null && String(oc).trim() !== "") {
    out.stroke_outer_color = String(oc);
    out.stroke_color = String(oc);
  }
  return out;
}

let _systemFontsCache = null;

async function loadSystemFontsList() {
  if (_systemFontsCache) return _systemFontsCache;
  const res = await fetch(`${API}/api/system-fonts`, { cache: "no-store" });
  if (!res.ok) {
    _systemFontsCache = [];
    return _systemFontsCache;
  }
  const data = await res.json();
  _systemFontsCache = Array.isArray(data.fonts) ? data.fonts : [];
  return _systemFontsCache;
}

function normFontPath(p) {
  return String(p || "")
    .trim()
    .replace(/\\/g, "/");
}

function fillFontSelectOptions(select, fonts, currentPath) {
  if (!select) return;
  const cur = normFontPath(currentPath);
  select.innerHTML = "";
  const z = document.createElement("option");
  z.value = "";
  z.textContent = "— выберите шрифт —";
  select.appendChild(z);
  let found = false;
  for (const f of fonts) {
    const fp = normFontPath(f.path);
    const o = document.createElement("option");
    o.value = f.path;
    o.textContent = f.label || f.path;
    if (!found && cur && fp && (fp === cur || cur.endsWith(fp) || fp.endsWith(cur))) {
      o.selected = true;
      found = true;
    }
    select.appendChild(o);
  }
  if (cur && !found) {
    const o = document.createElement("option");
    o.value = currentPath;
    o.selected = true;
    o.textContent = `Текущий: ${cur.split("/").pop()}`;
    select.appendChild(o);
  }
}

/**
 * @param {HTMLElement} body
 * @param {string} selectSel  CSS-селектор select
 * @param {string} currentPath
 * @param {string} pickSel  CSS-селектор кнопки «Обзор»
 */
async function wireFontPickerInBody(body, selectSel, currentPath, pickSel) {
  const sel = body.querySelector(selectSel);
  if (!sel) return;
  const fonts = await loadSystemFontsList();
  fillFontSelectOptions(sel, fonts, currentPath);
  const btn = body.querySelector(pickSel);
  if (btn) {
    btn.addEventListener("click", async () => {
      try {
        const r = await apiJson("/api/studio", { method: "POST", body: JSON.stringify({ cmd: "pick_font_file" }) });
        if (r && r.ok && r.path) {
          const p = String(r.path);
          let opt = Array.from(sel.options).find((o) => normFontPath(o.value) === normFontPath(p));
          if (!opt) {
            opt = document.createElement("option");
            opt.value = p;
            opt.textContent = p.replace(/\\/g, "/").split("/").pop();
            sel.appendChild(opt);
          }
          sel.value = opt.value;
        }
      } catch (e) {
        console.warn("pick_font_file", e);
      }
    });
  }
}

function wireElemEditorColorRows(root) {
  if (!root) return;
  root.querySelectorAll(".ccElemColorWrap").forEach((wrap) => {
    const eye = wrap.querySelector(".ccElemColorEye");
    const hex = wrap.querySelector(".ccElemColorHex");
    const sw = wrap.querySelector(".ccElemColorSwatch");
    if (!eye || !hex) return;
    const isPal = hex.classList.contains("ccBgPaletteHex") || hex.classList.contains("ccTextPaletteHex");
    const syncSwatch = () => {
      if (isPal) {
        if (sw) sw.style.background = swatchForBgSpec(hex.value);
        if (/^linear-gradient/i.test(String(hex.value || ""))) eye.value = "#808080";
        else eye.value = hexToColorInput(hex.value);
      } else {
        const n = normalizeColorHex(hex.value);
        if (sw) sw.style.background = /^#[0-9A-F]{6}$/i.test(n) ? n : hexToColorInput(hex.value);
      }
    };
    const fromEye = () => {
      hex.value = normalizeColorHex(eye.value) || hex.value;
      syncSwatch();
    };
    const fromHex = () => {
      if (isPal) {
        eye.value = /^linear-gradient/i.test(String(hex.value || "")) ? "#808080" : hexToColorInput(hex.value);
        syncSwatch();
      } else {
        eye.value = hexToColorInput(hex.value);
        syncSwatch();
      }
    };
    eye.addEventListener("input", fromEye);
    hex.addEventListener("input", fromHex);
    fromHex();
  });
}

function collectBgPaletteFromModal(body) {
  const root = body && body.querySelector && body.querySelector("[data-bg-palette-root]");
  if (!root) return undefined;
  const out = [];
  root.querySelectorAll(".ccBgPaletteHex").forEach((inp) => {
    const v = String(inp.value || "").trim();
    if (v) out.push(v);
  });
  return out;
}

function bindBgPalettePreviewEye(eyeBtn, palRoot) {
  if (!eyeBtn || !palRoot || !elementEditorHit) return;
  eyeBtn.addEventListener("click", () => {
    const row = eyeBtn.closest(".ccBgPaletteRow");
    const inp = row?.querySelector(".ccBgPaletteHex");
    if (!inp) return;
    const spec = String(inp.value || "").trim();
    if (!spec) return;
    const isSame =
      bgPalettePreviewOverride &&
      bgPalettePreviewOverride.hit === elementEditorHit &&
      bgPalettePreviewOverride.spec === spec &&
      row.classList.contains("is-previewing");
    if (isSame) {
      bgPalettePreviewOverride = null;
      row.classList.remove("is-previewing");
      schedulePreviewFast();
      return;
    }
    bgPalettePreviewOverride = { hit: elementEditorHit, spec };
    palRoot.querySelectorAll(".ccBgPaletteRow").forEach((r) => r.classList.remove("is-previewing"));
    row.classList.add("is-previewing");
    schedulePreviewFast();
  });
}

function wireBgSnapReset(body) {
  const btn = body?.querySelector("[data-bg-reset-snap]");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const w = body.querySelector('[data-style="bg_snap_inner_w"]');
    const h = body.querySelector('[data-style="bg_snap_inner_h"]');
    if (w) w.value = "0";
    if (h) h.value = "0";
    schedulePreviewSlow();
  });
}

function wireBgPalette(body) {
  const root = body && body.querySelector("[data-bg-palette-root]");
  const addBtn = body && body.querySelector("[data-bg-palette-add]");
  if (!root || !addBtn) return;
  const appendRow = (spec) => {
    const wrap = document.createElement("div");
    wrap.innerHTML = bgPaletteRowOuterHtml(spec).trim();
    const el = wrap.firstElementChild;
    if (!el) return;
    root.appendChild(el);
    wireElemEditorColorRows(el);
    el.querySelector(".ccBgPaletteDel")?.addEventListener("click", () => {
      el.remove();
      schedulePreviewSlow();
    });
    bindBgPalettePreviewEye(el.querySelector(".ccBgPalettePreview"), root);
    schedulePreviewSlow();
  };
  addBtn.addEventListener("click", () => appendRow("#1A2430"));
  root.querySelectorAll(".ccBgPaletteDel").forEach((del) => {
    del.addEventListener("click", () => {
      del.closest(".ccBgPaletteRow")?.remove();
      schedulePreviewSlow();
    });
  });
  root.querySelectorAll(".ccBgPalettePreview").forEach((eyeBtn) => bindBgPalettePreviewEye(eyeBtn, root));
}

/** Подмешать в клон настроек несохранённые поля открытой панели элемента (чтобы 👁 и превью совпадали с формой). */
function mergeOpenElementEditorIntoSettingsClone(settings) {
  const hit = elementEditorHit;
  const edBody = $("elementEditorBody");
  const panel = $("elementEditorPanel");
  if (!hit || !edBody || !panel || panel.hidden) return settings;
  if (["title", "subtitle", "dates", "watermark"].includes(hit)) {
    const palette = collectBgPaletteFromModal(edBody);
    const stylePatch = collectStyleFromModalBody(edBody);
    Object.assign(stylePatch, collectTextFillFromModal(edBody));
    if (palette !== undefined) stylePatch.bg_colors = palette;
    const ts = ensureTextStyles(settings);
    ts[hit] = syncLegacyTextStrokeFields({ ...getMergedStyle(settings, hit), ...stylePatch });
    return settings;
  }
  if (typeof hit === "string" && hit.startsWith("overlay:")) {
    const id = hit.slice(8);
    const arr = ensureSceneOverlays(settings);
    const idx = arr.findIndex((o) => o && String(o.id) === id);
    if (idx < 0) return settings;
    const cur = { ...arr[idx] };
    if ((cur.kind || "text") === "text") {
      const palette = collectBgPaletteFromModal(edBody);
      const stylePatch = collectStyleFromModalBody(edBody);
      Object.assign(stylePatch, collectTextFillFromModal(edBody));
      if (palette !== undefined) stylePatch.bg_colors = palette;
      cur.style = syncLegacyTextStrokeFields({
        ...STYLE_PRESETS.subtitle,
        ...(cur.style && typeof cur.style === "object" ? cur.style : {}),
        ...stylePatch,
      });
      const scal = collectOverlayScalarsFromModal(edBody);
      Object.assign(cur, scal);
      cur.hidden = Boolean(cur.hidden);
      arr[idx] = cur;
    }
    return settings;
  }
  return settings;
}

function ensureTextStyles(s) {
  if (!s.text_styles || typeof s.text_styles !== "object") s.text_styles = {};
  return s.text_styles;
}

function getMergedStyle(s, el) {
  const preset = STYLE_PRESETS[el] || STYLE_PRESETS.subtitle;
  return { ...preset, ...(ensureTextStyles(s)[el] || {}) };
}

function setPreviewLoading(visible) {
  const el = $("previewLoading");
  if (el) el.classList.toggle("is-visible", Boolean(visible));
}

function applyPreviewStackScale(pct) {
  const v = Math.max(60, Math.min(100, Number(pct) || 100));
  const scale = v / 100;
  const stack = $("previewStack");
  if (stack) stack.style.setProperty("--cc-preview-stack-scale", String(scale));
  const lab = $("previewStackScaleVal");
  if (lab) lab.textContent = `${v}%`;
  const rng = $("previewStackScale");
  if (rng && String(rng.value) !== String(v)) rng.value = String(v);
  try {
    localStorage.setItem(PREVIEW_SCALE_LS, String(v));
  } catch (_) {
    /* ignore */
  }
}

function loadPreviewStackScale() {
  let v = 100;
  try {
    const raw = localStorage.getItem(PREVIEW_SCALE_LS);
    if (raw != null) v = Math.max(60, Math.min(100, parseInt(raw, 10) || 100));
  } catch (_) {
    /* ignore */
  }
  applyPreviewStackScale(v);
}

function isPreviewShortsShell() {
  const el = $("previewShortsShell");
  return Boolean(el && el.checked);
}

function syncPreviewShortsShellLayout() {
  const on = isPreviewShortsShell();
  const stack = $("previewStack");
  const chrome = $("previewShortsChrome");
  const svg = $("previewOverlay");
  if (stack) stack.classList.toggle("ccPreviewStack--shorts", on);
  if (chrome) chrome.hidden = !on;
  if (svg) svg.setAttribute("preserveAspectRatio", on ? "xMidYMid slice" : "xMidYMid meet");
}

function applyPreviewShortsShellFromCheckbox() {
  try {
    localStorage.setItem(PREVIEW_SHORTS_LS, isPreviewShortsShell() ? "1" : "0");
  } catch (_) {
    /* ignore */
  }
  syncPreviewShortsShellLayout();
  schedulePreviewFast();
}

function loadPreviewShortsShell() {
  let on = false;
  try {
    on = localStorage.getItem(PREVIEW_SHORTS_LS) === "1";
  } catch (_) {
    /* ignore */
  }
  const chk = $("previewShortsShell");
  if (chk) chk.checked = on;
  syncPreviewShortsShellLayout();
}

function openElementEditorModal() {
  const p = $("elementEditorPanel");
  if (!p) return;
  p.hidden = false;
  try {
    p.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (_) {
    p.scrollIntoView();
  }
}

function closeElementEditorModal() {
  const p = $("elementEditorPanel");
  if (p) p.hidden = true;
  elementEditorHit = null;
  bgPalettePreviewOverride = null;
  textFillPreviewOverride = null;
  const body = $("elementEditorBody");
  if (body) body.innerHTML = "";
}

function collectStyleFromModalBody(body) {
  const o = {};
  if (!body) return o;
  body.querySelectorAll("[data-style]").forEach((el) => {
    const k = el.dataset.style;
    if (!k) return;
    if (el.type === "checkbox") o[k] = Boolean(el.checked);
    else if (el.type === "number") {
      const n = el.step && String(el.step).includes(".") ? parseFloat(el.value) : parseInt(el.value, 10);
      o[k] = Number.isFinite(n) ? n : 0;
    } else o[k] = String(el.value ?? "");
  });
  if (o.bg_enabled) o.bg_resizes_with_font = false;
  return o;
}

function readModalTop(body, key) {
  const el = body.querySelector(`[data-top="${key}"]`);
  if (!el) return undefined;
  if (el.type === "checkbox") return Boolean(el.checked);
  if (el.type === "number") {
    const raw = parseFloat(el.value);
    if (!Number.isFinite(raw)) return 0;
    const st = String(el.step || "");
    if (!st || st === "1") return Math.round(raw);
    return raw;
  }
  if (el.tagName === "SELECT") return String(el.value ?? "");
  return String(el.value ?? "");
}

function renderTextElementEditor(hit, s) {
  const st = getMergedStyle(s, hit);
  const fontKey =
    hit === "title" ? "title_font" : hit === "subtitle" ? "subtitle_font" : hit === "dates" ? "dates_font" : "watermark_font";
  const sizeKey =
    hit === "title" ? "title_font_size" : hit === "subtitle" ? "subtitle_font_size" : hit === "dates" ? "dates_font_size" : "watermark_font_size";
  const yKey = hit === "title" ? "title_y" : hit === "subtitle" ? "subtitle_y" : hit === "dates" ? "dates_y" : null;
  const xKey = hit === "title" ? "title_x" : hit === "subtitle" ? "subtitle_x" : hit === "dates" ? "dates_x" : null;

  let posBlock = "";
  if (hit === "watermark") {
    posBlock = `
      <div class="ccElemRow2">
        <div class="ccElemField"><label>X</label><input class="ccInput" type="number" data-top="watermark_x" value="${escAttr(s.watermark_x)}" /></div>
        <div class="ccElemField"><label>Y</label><input class="ccInput" type="number" data-top="watermark_y" value="${escAttr(s.watermark_y)}" /></div>
      </div>
      <div class="ccElemField"><label>Текст</label><input class="ccInput" type="text" data-top="watermark_text" value="${escAttr(s.watermark_text)}" /></div>
      <div class="ccElemRow2">
        ${elemColorFieldTop("Цвет текста", "watermark_color", s.watermark_color)}
        <div class="ccElemField"><label>Прозрачность (0–255)</label><input class="ccInput" type="number" data-top="watermark_opacity" min="0" max="255" value="${escAttr(s.watermark_opacity)}" /></div>
      </div>`;
  } else if (yKey && xKey) {
    const xv = s[xKey] != null ? s[xKey] : 0;
    posBlock = `<div class="ccElemRow2">
      <div class="ccElemField"><label>Позиция X (от центра, px)</label><input class="ccInput" type="number" data-top="${xKey}" step="1" value="${escAttr(xv)}" /></div>
      <div class="ccElemField"><label>Позиция Y (px)</label><input class="ccInput" type="number" data-top="${yKey}" step="1" value="${escAttr(s[yKey])}" /></div>
    </div>`;
  }

  const strokeScene =
    hit === "title"
      ? `${elemColorFieldTop("Обводка (сцена, дублирует стиль)", "title_stroke", s.title_stroke)}`
      : "";
  const hideKey =
    hit === "title"
      ? "title_hidden"
      : hit === "subtitle"
        ? "subtitle_hidden"
        : hit === "dates"
          ? "dates_hidden"
          : hit === "watermark"
            ? "watermark_hidden"
            : null;
  const hideRow = hideKey
    ? `<label class="ccElemCheck"><input type="checkbox" data-top="${hideKey}" ${s[hideKey] ? "checked" : ""} /> Скрыть элемент</label>`
    : "";

  const ow = strokeOuterWidthVal(st);
  const ocol = strokeOuterColorVal(st);
  const secPos = `${posBlock}${hideRow}${strokeScene}`;
  const sizeExtras =
    hit === "title"
      ? `<div class="ccElemField"><label>Мин. размер при длинном тексте (px)</label><input class="ccInput" type="number" data-top="title_font_size_min" min="10" max="140" step="1" value="${escAttr(s.title_font_size_min != null ? s.title_font_size_min : 22)}" /></div>
         <div class="ccElemField"><label>Ширина колонки заголовка (px, 0 = по кадру и отступам)</label><input class="ccInput" type="number" data-top="title_wrap_width" min="0" max="1080" step="1" value="${escAttr(s.title_wrap_width != null ? s.title_wrap_width : 0)}" /></div>`
      : hit === "subtitle"
        ? `<div class="ccElemField"><label>Ширина колонки описания (px, 0 = по кадру и отступам)</label><input class="ccInput" type="number" data-top="subtitle_wrap_width" min="0" max="1080" step="1" value="${escAttr(s.subtitle_wrap_width != null ? s.subtitle_wrap_width : 0)}" /></div>`
        : "";
  const secFont = `
    <div class="ccElemField">
      <label>Шрифт</label>
      <div class="ccFontPickRow">
        <select class="ccInput ccFontPickSelect" data-top="${fontKey}"></select>
        <button type="button" class="ccBtn ccBtn--ghost" data-font-pick="${fontKey}">Обзор…</button>
      </div>
      <p class="ccElemField__hint">Список из Windows/Fonts и fonts/ проекта. «Обзор» — системный диалог (полный путь на диске).</p>
    </div>
    <div class="ccElemField"><label>Размер (px)</label><input class="ccInput" type="number" data-top="${sizeKey}" min="8" max="200" step="1" value="${escAttr(s[sizeKey])}" /></div>
    ${sizeExtras}`;
  const secFill = renderTextStyleFillSection(st);
  const secStroke = `
    <label class="ccElemCheck"><input type="checkbox" data-style="stroke_outer_enabled" ${strokeOuterEnabledFromStyle(st) ? "checked" : ""} /> Внешняя обводка</label>
    <div class="ccElemRow2">
      ${elemColorFieldStyle("Цвет снаружи", "stroke_outer_color", ocol)}
      <div class="ccElemField"><label>Толщина снаружи (px)</label><input class="ccInput" type="number" data-style="stroke_outer_width" min="0" max="16" step="1" value="${escAttr(ow)}" /></div>
    </div>
    <label class="ccElemCheck"><input type="checkbox" data-style="stroke_inner_enabled" ${st.stroke_inner_enabled ? "checked" : ""} /> Внутренняя обводка</label>
    <div class="ccElemRow2">
      ${elemColorFieldStyle("Цвет внутри", "stroke_inner_color", st.stroke_inner_color || "#000000")}
      <div class="ccElemField"><label>Толщина внутри (px)</label><input class="ccInput" type="number" data-style="stroke_inner_width" min="0" max="16" step="1" value="${escAttr(Number(st.stroke_inner_width || 0))}" /></div>
    </div>
    <p class="ccElemField__hint">При «Применить» поля stroke_width / stroke_color в пресете синхронизируются с внешней обводкой.</p>`;
  const secShadow = `
    <label class="ccElemCheck"><input type="checkbox" data-style="shadow_enabled" ${st.shadow_enabled ? "checked" : ""} /> Включить тень</label>
    <div class="ccElemRow2">
      ${elemColorFieldStyle("Цвет тени", "shadow_color", st.shadow_color)}
      <div class="ccElemField"><label>Непрозрачность тени (0–255)</label><input class="ccInput" type="number" data-style="shadow_opacity" min="0" max="255" step="1" value="${escAttr(st.shadow_opacity)}" /></div>
    </div>
    <div class="ccElemRow2">
      <div class="ccElemField"><label>Размытие</label><input class="ccInput" type="number" data-style="shadow_blur" min="0" max="24" step="1" value="${escAttr(st.shadow_blur)}" /></div>
      <div class="ccElemField"><label>Сдвиг X / Y</label>
        <div class="ccElemRow2" style="margin-top:4px">
          <input class="ccInput" type="number" data-style="shadow_dx" step="1" value="${escAttr(st.shadow_dx)}" />
          <input class="ccInput" type="number" data-style="shadow_dy" step="1" value="${escAttr(st.shadow_dy)}" />
        </div>
      </div>
    </div>`;
  const secBg = renderTextStyleBgSection(st);

  return `
    ${elemDetails("Позиция и видимость", secPos, false)}
    ${elemDetails("Шрифт и размер", secFont, false)}
    ${elemDetails("Стили текста", secFill, false)}
    ${elemDetails("Обводка текста", secStroke, false)}
    ${elemDetails("Тень", secShadow, false)}
    ${elemDetails("Подложка под текстом", secBg, false)}
  `;
}

function renderOverlayTextEditor(ov, s) {
  const st = { ...STYLE_PRESETS.subtitle, ...(ov.style && typeof ov.style === "object" ? ov.style : {}) };
  const ow = strokeOuterWidthVal(st);
  const ocol = strokeOuterColorVal(st);
  const curFont = ov.font || s.subtitle_font;
  const secTxt = `
    <div class="ccElemField">
      <label for="ovTextContent">Содержимое</label>
      <textarea id="ovTextContent" class="ccTextarea ccTextarea--overlay" data-ov-field="text" rows="5" spellcheck="false">${escHtmlText(ov.text)}</textarea>
      <span class="ccElemField__hint">Новая строка: Enter или Shift+Enter</span>
    </div>
    <div class="ccElemRow2">
      <div class="ccElemField"><label>X (центр по горизонтали)</label><input class="ccInput" type="number" data-ov-field="x" step="1" value="${escAttr(ov.x ?? 540)}" /></div>
      <div class="ccElemField"><label>Y</label><input class="ccInput" type="number" data-ov-field="y" step="1" value="${escAttr(ov.y ?? 960)}" /></div>
    </div>
    <div class="ccElemRow2">
      <div class="ccElemField"><label>Макс. ширина текста (px)</label><input class="ccInput" type="number" data-ov-field="max_width" min="80" max="1080" value="${escAttr(ov.max_width ?? 900)}" /></div>
      <div class="ccElemField"><label>Межстрочный интервал</label><input class="ccInput" type="number" data-ov-field="line_spacing" min="0" max="40" value="${escAttr(ov.line_spacing ?? 12)}" /></div>
    </div>
    <label class="ccElemCheck"><input type="checkbox" data-ov-field="hidden" ${ov.hidden ? "checked" : ""} /> Скрыть элемент</label>`;
  const secFont = `
    <div class="ccElemField">
      <label>Шрифт</label>
      <div class="ccFontPickRow">
        <select class="ccInput ccFontPickSelect" data-ov-field="font"></select>
        <button type="button" class="ccBtn ccBtn--ghost" data-ov-font-pick="1">Обзор…</button>
      </div>
      <p class="ccElemField__hint">Тот же выбор, что у текста сцены: Windows/Fonts, fonts/ проекта или диалог.</p>
    </div>
    <div class="ccElemField"><label>Размер (px)</label><input class="ccInput" type="number" data-ov-field="font_size" min="8" max="200" value="${escAttr(ov.font_size ?? 48)}" /></div>`;
  const secFill = renderTextStyleFillSection(st);
  const secStroke = `
    <label class="ccElemCheck"><input type="checkbox" data-style="stroke_outer_enabled" ${strokeOuterEnabledFromStyle(st) ? "checked" : ""} /> Внешняя обводка</label>
    <div class="ccElemRow2">
      ${elemColorFieldStyle("Цвет снаружи", "stroke_outer_color", ocol)}
      <div class="ccElemField"><label>Толщина снаружи (px)</label><input class="ccInput" type="number" data-style="stroke_outer_width" min="0" max="16" step="1" value="${escAttr(ow)}" /></div>
    </div>
    <label class="ccElemCheck"><input type="checkbox" data-style="stroke_inner_enabled" ${st.stroke_inner_enabled ? "checked" : ""} /> Внутренняя обводка</label>
    <div class="ccElemRow2">
      ${elemColorFieldStyle("Цвет внутри", "stroke_inner_color", st.stroke_inner_color || "#000000")}
      <div class="ccElemField"><label>Толщина внутри (px)</label><input class="ccInput" type="number" data-style="stroke_inner_width" min="0" max="16" step="1" value="${escAttr(Number(st.stroke_inner_width || 0))}" /></div>
    </div>`;
  const secShadow = `
    <label class="ccElemCheck"><input type="checkbox" data-style="shadow_enabled" ${st.shadow_enabled ? "checked" : ""} /> Включить тень</label>
    <div class="ccElemRow2">
      ${elemColorFieldStyle("Цвет тени", "shadow_color", st.shadow_color)}
      <div class="ccElemField"><label>Непрозрачность тени (0–255)</label><input class="ccInput" type="number" data-style="shadow_opacity" min="0" max="255" step="1" value="${escAttr(st.shadow_opacity)}" /></div>
    </div>
    <div class="ccElemRow2">
      <div class="ccElemField"><label>Размытие</label><input class="ccInput" type="number" data-style="shadow_blur" min="0" max="24" step="1" value="${escAttr(st.shadow_blur)}" /></div>
      <div class="ccElemField"><label>Сдвиг X / Y</label>
        <div class="ccElemRow2" style="margin-top:4px">
          <input class="ccInput" type="number" data-style="shadow_dx" step="1" value="${escAttr(st.shadow_dx)}" />
          <input class="ccInput" type="number" data-style="shadow_dy" step="1" value="${escAttr(st.shadow_dy)}" />
        </div>
      </div>
    </div>`;
  const secBg = renderTextStyleBgSection(st);
  return `
    ${elemDetails("Текст и позиция", secTxt, false)}
    ${elemDetails("Шрифт и размер", secFont, false)}
    ${elemDetails("Стили текста", secFill, false)}
    ${elemDetails("Обводка текста", secStroke, false)}
    ${elemDetails("Тень", secShadow, false)}
    ${elemDetails("Подложка под текстом", secBg, false)}
  `;
}

function renderOverlayImageEditor(ov, id) {
  const lf = `ovframe_${id}`;
  const st = mergeOverlayFrame(ov);
  const isGif = ov.kind === "gif";
  return `
    <div class="ccElemSection">Файл и позиция</div>
    <div class="ccElemField"><label>${isGif ? "GIF" : "Картинка"}</label>
      <div class="ccFontPickRow">
        <input class="ccInput" type="text" readonly data-ov-field="src" value="${escAttr(ov.src)}" spellcheck="false" title="Выбор файла" />
        <button type="button" class="ccBtn ccBtn--ghost" data-ov-src-pick="1">${isGif ? "Выбрать GIF…" : "Выбрать файл…"}</button>
      </div>
    </div>
    ${
      isGif
        ? `<p class="ccElemField__hint" style="margin:0">В превью и в ролике GIF зацикливается на всю длительность сцены.</p>`
        : ""
    }
    <div class="ccElemRow2">
      <div class="ccElemField"><label>X (левый верх с учётом рамки)</label><input class="ccInput" type="number" data-ov-field="x" step="1" value="${escAttr(ov.x ?? 80)}" /></div>
      <div class="ccElemField"><label>Y</label><input class="ccInput" type="number" data-ov-field="y" step="1" value="${escAttr(ov.y ?? 200)}" /></div>
    </div>
    <div class="ccElemRow2">
      <div class="ccElemField"><label>Ширина (px)</label><input class="ccInput" type="number" data-ov-field="width" min="16" max="1080" value="${escAttr(ov.width ?? 320)}" /></div>
      <div class="ccElemField"><label>Высота (px)</label><input class="ccInput" type="number" data-ov-field="height" min="16" max="1920" value="${escAttr(ov.height ?? 240)}" /></div>
    </div>
    <label class="ccElemCheck"><input type="checkbox" data-ov-field="hidden" ${ov.hidden ? "checked" : ""} /> Скрыть элемент</label>
    ${renderLayerFrameFieldsForPrefix(lf, st, "картинки")}
  `;
}

function fillElementEditorBody(hit, options = {}) {
  const body = $("elementEditorBody");
  if (!body) return;
  const preserveUi = options.preserveUi === true && elementEditorHit === hit;
  if (!preserveUi) {
    bgPalettePreviewOverride = null;
    textFillPreviewOverride = null;
  }
  let prevScrollTop = 0;
  const openDetailIndices = new Set();
  if (preserveUi) {
    prevScrollTop = body.scrollTop;
    body.querySelectorAll("details.ccElemDetails").forEach((d, i) => {
      if (d.open) openDetailIndices.add(i);
    });
  }

  collectSettingsFromForm();
  const s = state.settings;
  const hint = $("elementEditorHint");
  const titles = {
    title: "Заголовок",
    subtitle: "Описание",
    dates: "Даты",
    watermark: "Вотермарка",
  };
  let panelTitle = titles[hit] || hit;
  if (typeof hit === "string" && hit.startsWith("overlay:")) {
    const oid = hit.slice(8);
    const ov = ensureSceneOverlays(s).find((o) => o && String(o.id) === oid);
    panelTitle =
      ov && ov.kind === "image" ? "Картинка на кадре" : ov && ov.kind === "gif" ? "GIF на кадре" : "Текст на кадре";
  }
  $("elementEditorTitle").textContent = panelTitle;
  if (hint) {
    hint.style.display = "";
    if (typeof hit === "string" && hit.startsWith("overlay:")) {
      hint.textContent = "Те же параметры стиля, что у текста сцены. «Применить» не закрывает панель.";
    } else {
      hint.textContent =
        "ПКМ или двойной щелчок по элементу в просмотре, либо ЛКМ по клипу на таймлайне. Здесь — настройки выбранного элемента; превью не перекрывается.";
    }
  }

  if (["title", "subtitle", "dates", "watermark"].includes(hit)) {
    body.innerHTML = renderTextElementEditor(hit, s);
  } else if (typeof hit === "string" && hit.startsWith("overlay:")) {
    const id = hit.slice(8);
    const arr = ensureSceneOverlays(s);
    const ov = arr.find((o) => o && String(o.id) === id);
    if (!ov) {
      body.innerHTML = `<p class="ccElemField" style="color:var(--cc-muted)">Блок удалён или не найден.</p>`;
    } else if (ov.kind === "image" || ov.kind === "gif") {
      body.innerHTML = renderOverlayImageEditor(ov, id);
      wireOverlaySrcPick(body, ov.kind === "gif");
    } else {
      body.innerHTML = renderOverlayTextEditor(ov, s);
    }
  } else {
    body.innerHTML = `<p class="ccElemField" style="color:var(--cc-muted)">Для этого элемента отдельное окно не настроено.</p>`;
  }
  wireElemEditorColorRows(body);
  wireBgPalette(body);
  wireBgSnapReset(body);
  wireBgImagePickers(body);
  wireTextFillMode(body);
  wireTextFillPalettes(body);
  if (["title", "subtitle", "dates", "watermark"].includes(hit)) {
    const fk =
      hit === "title" ? "title_font" : hit === "subtitle" ? "subtitle_font" : hit === "dates" ? "dates_font" : "watermark_font";
    void wireFontPickerInBody(body, `select[data-top="${fk}"]`, String(s[fk] || ""), `[data-font-pick="${fk}"]`);
  } else if (typeof hit === "string" && hit.startsWith("overlay:")) {
    const id = hit.slice(8);
    const ov = ensureSceneOverlays(s).find((o) => o && String(o.id) === id);
    if (ov && (ov.kind || "text") === "text") {
      void wireFontPickerInBody(
        body,
        `select[data-ov-field="font"]`,
        String(ov.font || s.subtitle_font || ""),
        "[data-ov-font-pick]",
      );
    }
  }

  if (preserveUi) {
    requestAnimationFrame(() => {
      body.querySelectorAll("details.ccElemDetails").forEach((d, i) => {
        if (openDetailIndices.has(i)) d.open = true;
      });
      requestAnimationFrame(() => {
        body.scrollTop = prevScrollTop;
      });
    });
  }
}

function applyElementEditorFromModal() {
  const hit = elementEditorHit;
  const body = $("elementEditorBody");
  if (!hit || !body) return;
  bgPalettePreviewOverride = null;
  textFillPreviewOverride = null;
  collectSettingsFromForm();
  const s = state.settings;

  const assignTop = (keys) => {
    for (const k of keys) {
      const v = readModalTop(body, k);
      if (v !== undefined) s[k] = v;
    }
  };

  if (["title", "subtitle", "dates", "watermark"].includes(hit)) {
    const palette = collectBgPaletteFromModal(body);
    const stylePatch = collectStyleFromModalBody(body);
    Object.assign(stylePatch, collectTextFillFromModal(body));
    if (palette !== undefined) stylePatch.bg_colors = palette;
    const ts = ensureTextStyles(s);
    ts[hit] = syncLegacyTextStrokeFields({ ...getMergedStyle(s, hit), ...stylePatch });
    if (hit === "title") {
      assignTop([
        "title_font",
        "title_font_size",
        "title_font_size_min",
        "title_wrap_width",
        "title_y",
        "title_x",
        "title_stroke",
        "title_hidden",
      ]);
    } else if (hit === "subtitle") {
      assignTop(["subtitle_font", "subtitle_font_size", "subtitle_wrap_width", "subtitle_y", "subtitle_x", "subtitle_hidden"]);
    } else if (hit === "dates") {
      assignTop(["dates_font", "dates_font_size", "dates_y", "dates_x", "dates_hidden"]);
    } else if (hit === "watermark") {
      assignTop([
        "watermark_font",
        "watermark_font_size",
        "watermark_x",
        "watermark_y",
        "watermark_text",
        "watermark_color",
        "watermark_opacity",
        "watermark_hidden",
      ]);
    }
  } else if (typeof hit === "string" && hit.startsWith("overlay:")) {
    const id = hit.slice(8);
    const arr = ensureSceneOverlays(s);
    const idx = arr.findIndex((o) => o && String(o.id) === id);
    if (idx < 0) return;
    const cur = { ...arr[idx] };
    const scal = collectOverlayScalarsFromModal(body);
    Object.assign(cur, scal);
    cur.hidden = Boolean(cur.hidden);
    if ((cur.kind || "text") === "text") {
      cur.kind = "text";
      const palette = collectBgPaletteFromModal(body);
      const stylePatch = collectStyleFromModalBody(body);
      Object.assign(stylePatch, collectTextFillFromModal(body));
      if (palette !== undefined) stylePatch.bg_colors = palette;
      cur.style = syncLegacyTextStrokeFields({
        ...STYLE_PRESETS.subtitle,
        ...(cur.style && typeof cur.style === "object" ? cur.style : {}),
        ...stylePatch,
      });
      cur.x = Number.isFinite(Number(cur.x)) ? Math.round(Number(cur.x)) : 540;
      cur.y = Number.isFinite(Number(cur.y)) ? Math.round(Number(cur.y)) : 960;
      cur.font_size = Number.isFinite(Number(cur.font_size)) ? Math.round(Number(cur.font_size)) : 48;
      cur.max_width = Number.isFinite(Number(cur.max_width)) ? Math.round(Number(cur.max_width)) : 900;
      cur.line_spacing = Number.isFinite(Number(cur.line_spacing)) ? Math.round(Number(cur.line_spacing)) : 12;
    } else if (cur.kind === "image" || cur.kind === "gif") {
      const lf = `ovframe_${id}`;
      cur.frame = { ...mergeOverlayFrame(cur), ...collectLfFromModal(body, lf) };
      cur.width = Number.isFinite(Number(cur.width)) ? Math.round(Number(cur.width)) : 320;
      cur.height = Number.isFinite(Number(cur.height)) ? Math.round(Number(cur.height)) : 240;
      cur.x = Number.isFinite(Number(cur.x)) ? Math.round(Number(cur.x)) : 0;
      cur.y = Number.isFinite(Number(cur.y)) ? Math.round(Number(cur.y)) : 0;
    }
    arr[idx] = cur;
    s.scene_overlays = arr;
    renderSceneOverlaysList();
  }

  pushSettingsToForm();
  schedulePreviewSlow();
  fillElementEditorBody(elementEditorHit, { preserveUi: true });
}

function openElementEditor(hit) {
  if (hit === "card" || hit === "photo") return;
  elementEditorHit = hit;
  fillElementEditorBody(hit);
  openElementEditorModal();
}

function defaultOverlayTextBlock(s) {
  return {
    id: newOverlayId(),
    kind: "text",
    hidden: false,
    text: "Новый текст",
    x: 540,
    y: 1100,
    font: s.subtitle_font || "fonts/tahomabd.ttf",
    font_size: 48,
    max_width: 900,
    line_spacing: 12,
    style: { ...STYLE_PRESETS.subtitle },
  };
}

function defaultOverlayImageBlock() {
  return {
    id: newOverlayId(),
    kind: "image",
    hidden: false,
    src: "",
    x: 80,
    y: 200,
    width: 320,
    height: 240,
    frame: { ...DEFAULT_LAYER_FRAME },
  };
}

function defaultOverlayGifBlock() {
  return {
    id: newOverlayId(),
    kind: "gif",
    hidden: false,
    src: "",
    x: 80,
    y: 200,
    width: 320,
    height: 240,
    frame: { ...DEFAULT_LAYER_FRAME },
  };
}

function renderSceneOverlaysList() {
  const root = $("sceneOverlaysList");
  if (!root) return;
  collectSettingsFromForm();
  const list = ensureSceneOverlays(state.settings);
  if (!list.length) {
    root.innerHTML = `<p class="ccDockHint" style="margin:8px 0 0">Пока нет своих блоков — добавьте текст или картинку.</p>`;
    renderTimelineLayersEditor();
    return;
  }
  root.innerHTML = list
    .map((ov) => {
      const id = escAttr(String(ov.id));
      const rawLabel =
        ov.kind === "image"
          ? `Картинка${ov.src ? ` — ${String(ov.src).replace(/\\/g, "/").split("/").pop()}` : ""}`
          : ov.kind === "gif"
            ? `GIF${ov.src ? ` — ${String(ov.src).replace(/\\/g, "/").split("/").pop()}` : ""}`
            : `Текст: ${(ov.text || "").replace(/\s+/g, " ").trim().slice(0, 40) || "…"}`;
      const label = escAttr(rawLabel);
      return `<div class="ccOverlayRow">
        <span class="ccOverlayRow__label" title="${label}">${label}</span>
        <button type="button" class="ccBtn ccBtn--ghost ccOverlayRow__btn" data-overlay-edit="${id}">Править</button>
        <button type="button" class="ccBtn ccBtn--ghost ccOverlayRow__btn" data-overlay-del="${id}">✕</button>
      </div>`;
    })
    .join("");
  renderTimelineLayersEditor();
}

function wireMediaTabs() {
  const tabs = document.querySelectorAll(".ccMediaTab[data-media-tab]");
  const main = $("mediaPaneMain");
  const ovPane = $("mediaPaneOverlays");
  if (!tabs.length || !main || !ovPane) return;
  tabs.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.getAttribute("data-media-tab");
      tabs.forEach((t) => t.classList.toggle("is-active", t === btn));
      const isMain = tab === "main";
      main.hidden = !isMain;
      ovPane.hidden = isMain;
      if (!isMain) renderSceneOverlaysList();
    });
  });
}

function parseCardBgGradientCss(val) {
  const m = String(val || "")
    .trim()
    .match(/linear-gradient\s*\(\s*(?:180deg|to\s+bottom)\s*,\s*(#[0-9a-fA-F]{3,8})\s*,\s*(#[0-9a-fA-F]{3,8})\s*\)/i);
  if (!m) return null;
  return { c1: normalizeColorHex(m[1]) || "#FFFFFF", c2: normalizeColorHex(m[2]) || "#000000" };
}

function rebuildCardBgGradientFromEyes(wrap) {
  const eye = wrap.querySelector(".ccColorNative:not(.ccColorNative--sm)");
  const eye2 = wrap.querySelector(".ccColorNative--sm");
  const hex = wrap.querySelector(".ccColorHex");
  const swatch = wrap.querySelector(".ccColorSwatch");
  if (!eye || !eye2 || !hex) return;
  const a = normalizeColorHex(eye.value) || "#FFFFFF";
  const b = normalizeColorHex(eye2.value) || "#000000";
  hex.value = `linear-gradient(180deg, ${a}, ${b})`;
  if (swatch) swatch.style.background = hex.value;
}

function syncColorFieldFromValue(f, val) {
  const hex = $(fieldId(f.key));
  if (!hex || f.kind !== "color") return;
  const v = val === undefined || val === null ? "" : String(val);
  hex.value = v;
  const wrap = hex.closest(".ccColorFieldWrap");
  if (!wrap) return;
  const eye = wrap.querySelector(".ccColorNative:not(.ccColorNative--sm)");
  const swatch = wrap.querySelector(".ccColorSwatch");
  if (!eye) return;
  if (f.gradient) {
    const gc = $(`${fieldId(f.key)}_grad`);
    const eye2 = $(`${fieldId(f.key)}_g2`);
    const gradRow = wrap.querySelector(".ccGradientRow");
    const g = parseCardBgGradientCss(v);
    if (g && gc && eye2) {
      gc.checked = true;
      if (gradRow) gradRow.style.display = "flex";
      eye.value = hexToColorInput(g.c1);
      eye2.value = hexToColorInput(g.c2);
      if (swatch) swatch.style.background = v;
    } else {
      if (gc) gc.checked = false;
      if (gradRow) gradRow.style.display = "none";
      eye.value = hexToColorInput(v || "#FFFFFF");
      if (eye2) eye2.value = "#000000";
      if (swatch) swatch.style.background = normalizeColorHex(v) || "#333333";
    }
  } else {
    eye.value = hexToColorInput(v || "#FFFFFF");
    if (swatch) swatch.style.background = parseCardBgGradientCss(v) ? v : normalizeColorHex(v) || "#333333";
  }
}

function initColorField(f, panel) {
  const wrap = document.createElement("div");
  wrap.className = "field ccColorFieldWrap";
  const lab = document.createElement("label");
  lab.htmlFor = fieldId(f.key);
  lab.textContent = f.label;
  wrap.appendChild(lab);
  const row = document.createElement("div");
  row.className = "ccColorField";
  const eye = document.createElement("input");
  eye.type = "color";
  eye.className = "ccColorNative";
  eye.title = "Выбор цвета";
  const swatch = document.createElement("div");
  swatch.className = "ccColorSwatch";
  swatch.setAttribute("aria-hidden", "true");
  const hex = document.createElement("input");
  hex.type = "text";
  hex.className = "ccInput ccColorHex";
  hex.id = fieldId(f.key);
  hex.spellcheck = false;
  hex.placeholder = f.gradient ? "#RRGGBB или linear-gradient(...)" : "#RRGGBB";
  row.append(eye, swatch, hex);
  wrap.appendChild(row);

  if (f.gradient) {
    const gradRow = document.createElement("div");
    gradRow.className = "ccGradientRow";
    const gid = `${fieldId(f.key)}_grad`;
    const gc = document.createElement("input");
    gc.type = "checkbox";
    gc.id = gid;
    const glab = document.createElement("label");
    glab.className = "ccGradientLab";
    glab.htmlFor = gid;
    glab.appendChild(gc);
    glab.appendChild(document.createTextNode(" Градиент (вертикаль)"));
    const eye2 = document.createElement("input");
    eye2.type = "color";
    eye2.className = "ccColorNative ccColorNative--sm";
    eye2.title = "Нижний цвет градиента";
    eye2.id = `${fieldId(f.key)}_g2`;
    gradRow.append(glab, eye2);
    wrap.appendChild(gradRow);

    const applyGradientUi = () => {
      gradRow.style.display = gc.checked ? "flex" : "none";
      if (gc.checked) rebuildCardBgGradientFromEyes(wrap);
      else {
        hex.value = normalizeColorHex(eye.value) || "#FFFFFF";
        swatch.style.background = hex.value;
      }
      schedulePreviewSlow();
    };
    gc.addEventListener("change", applyGradientUi);
    eye2.addEventListener("input", () => {
      if (gc.checked) rebuildCardBgGradientFromEyes(wrap);
      schedulePreviewSlow();
    });
  }

  const syncFromEye = () => {
    if (f.gradient && $(`${fieldId(f.key)}_grad`)?.checked) {
      rebuildCardBgGradientFromEyes(wrap);
    } else {
      hex.value = normalizeColorHex(eye.value) || hex.value;
      swatch.style.background = hex.value;
    }
    schedulePreviewSlow();
  };
  eye.addEventListener("input", syncFromEye);
  hex.addEventListener("input", () => {
    const g = f.gradient && parseCardBgGradientCss(hex.value);
    if (g) {
      eye.value = hexToColorInput(g.c1);
      const e2 = $(`${fieldId(f.key)}_g2`);
      if (e2) e2.value = hexToColorInput(g.c2);
      const gc = $(`${fieldId(f.key)}_grad`);
      const gradRow = wrap.querySelector(".ccGradientRow");
      if (gc) gc.checked = true;
      if (gradRow) gradRow.style.display = "flex";
      swatch.style.background = hex.value;
    } else {
      eye.value = hexToColorInput(hex.value);
      swatch.style.background = normalizeColorHex(hex.value) || "#333";
    }
    schedulePreviewSlow();
  });

  panel.appendChild(wrap);
}

function setActiveTab(id) {
  activeTab = id;
  const btns = $("tabButtons").querySelectorAll(".ccTab");
  btns.forEach((b) => {
    b.classList.toggle("is-active", b.dataset.tab === id);
  });
  const panels = $("tabPanels").querySelectorAll(".ccTabPanel");
  panels.forEach((p) => {
    p.classList.toggle("is-active", p.dataset.tab === id);
  });
}

/** Вкладки и поля создаются один раз; переключение вкладки только меняет CSS — иначе лаг и кракозябры из-за потери DOM. */
function initTabsOnce() {
  if (tabsInitialized) return;
  tabsInitialized = true;
  const btns = $("tabButtons");
  const panels = $("tabPanels");
  btns.innerHTML = "";
  panels.innerHTML = "";

  for (const t of TABS) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ccTab";
    b.textContent = t.label;
    b.dataset.tab = t.id;
    b.addEventListener("click", () => setActiveTab(t.id));
    btns.appendChild(b);

    const p = document.createElement("div");
    p.className = "ccTabPanel";
    p.dataset.tab = t.id;
    panels.appendChild(p);
  }

  for (const f of FIELDS) {
    const panel = panels.querySelector(`.ccTabPanel[data-tab="${f.tab}"]`);
    if (!panel) continue;
    if (f.kind === "hint") {
      const div = document.createElement("div");
      div.className = "hint hint--inTab";
      div.textContent = f.text || "";
      panel.appendChild(div);
      continue;
    }
    if (f.kind === "name_builder") {
      const wrap = document.createElement("div");
      wrap.className = "field ccNameBuilderField";
      const lab = document.createElement("label");
      lab.textContent = f.label;
      wrap.appendChild(lab);
      initOutputNameBuilderPanel(wrap);
      panel.appendChild(wrap);
      continue;
    }
    if (f.kind === "lines_list") {
      const wrap = document.createElement("div");
      wrap.className = "field";
      const lab = document.createElement("label");
      lab.htmlFor = fieldId(f.key);
      lab.textContent = f.label;
      wrap.appendChild(lab);
      const el = document.createElement("textarea");
      el.className = "ccTextarea";
      el.id = fieldId(f.key);
      el.rows = f.rows != null ? f.rows : 5;
      if (f.placeholder) el.placeholder = f.placeholder;
      el.spellcheck = false;
      el.addEventListener("input", () => schedulePreviewSlow());
      wrap.appendChild(el);
      panel.appendChild(wrap);
      continue;
    }
    if (f.kind === "glow_palette") {
      const wrap = document.createElement("div");
      wrap.className = "field";
      const lab = document.createElement("label");
      lab.textContent = f.label || "";
      wrap.appendChild(lab);
      if (f.hint) {
        const hint = document.createElement("p");
        hint.className = "hint hint--inTab";
        hint.style.margin = "4px 0 8px 0";
        hint.textContent = f.hint;
        wrap.appendChild(hint);
      }
      const root = document.createElement("div");
      root.className = "ccBgPalette ccGlowPaletteRoot";
      root.id = fieldId(f.key);
      wrap.appendChild(root);
      const addBtn = document.createElement("button");
      addBtn.type = "button";
      addBtn.className = "ccBtn ccBtn--ghost";
      addBtn.style.marginTop = "8px";
      addBtn.textContent = "+ Добавить цвет";
      addBtn.dataset.glowPaletteAdd = "1";
      wrap.appendChild(addBtn);
      panel.appendChild(wrap);
      const cur = state.settings && typeof state.settings === "object" ? state.settings[f.key] : [];
      paintGlowPaletteRoot(root, cur);
      wireGlowPaletteField(wrap);
      continue;
    }
    if (f.kind === "color") {
      initColorField(f, panel);
      continue;
    }
    if (f.kind === "select") {
      const wrap = document.createElement("div");
      wrap.className = "field";
      const lab = document.createElement("label");
      lab.htmlFor = fieldId(f.key);
      lab.textContent = f.label;
      wrap.appendChild(lab);
      const el = document.createElement("select");
      el.id = fieldId(f.key);
      el.className = "ccInput";
      for (const opt of f.options || []) {
        const o = document.createElement("option");
        o.value = opt.value;
        o.textContent = opt.label;
        el.appendChild(o);
      }
      el.addEventListener("change", () => schedulePreviewSlow());
      wrap.appendChild(el);
      panel.appendChild(wrap);
      continue;
    }
    if (f.kind === "path_font" || f.kind === "path_folder" || f.kind === "path_media" || f.kind === "path_image") {
      const wrap = document.createElement("div");
      wrap.className = "field";
      const lab = document.createElement("label");
      lab.htmlFor = fieldId(f.key);
      lab.textContent = f.label;
      wrap.appendChild(lab);
      const row = document.createElement("div");
      row.className = "ccFontPickRow";
      const el = document.createElement("input");
      el.type = "text";
      el.readOnly = true;
      el.id = fieldId(f.key);
      el.className = "ccInput";
      el.title = "Выбирается только через кнопку";
      el.autocomplete = "off";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ccBtn ccBtn--ghost";
      btn.textContent = f.kind === "path_folder" ? "Выбрать папку" : "Выбрать файл";
      btn.addEventListener("click", async () => {
        let p = "";
        if (f.kind === "path_folder") {
          p = await pickFolderNative({ title: f.label, defaultPath: el.value || undefined });
        } else if (f.kind === "path_font") {
          try {
            const r = await apiJson("/api/studio", { method: "POST", body: JSON.stringify({ cmd: "pick_font_file" }) });
            if (r && r.ok && r.path) p = String(r.path);
          } catch (e) {
            console.warn("pick_font_file", e);
          }
        } else if (f.kind === "path_image") {
          p = await pickFileNative({
            title: f.label,
            filters: [{ name: "Изображения", extensions: ["png", "jpg", "jpeg", "webp", "bmp", "gif"] }],
            filetypesForWorker: [["Изображения", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"], ["Все файлы", "*.*"]],
          });
        } else {
          p = await pickFileNative({
            title: f.label,
            filters: [
              { name: "Медиа", extensions: ["mp4", "mov", "avi", "mkv", "webm", "png", "jpg", "jpeg", "webp", "gif"] },
            ],
            filetypesForWorker: [
              ["Видео и картинки", "*.mp4 *.mov *.avi *.mkv *.webm *.png *.jpg *.jpeg *.webp *.gif"],
              ["Все файлы", "*.*"],
            ],
          });
        }
        if (p) {
          el.value = p;
          schedulePreviewSlow();
        }
      });
      row.appendChild(el);
      row.appendChild(btn);
      wrap.appendChild(row);
      panel.appendChild(wrap);
      continue;
    }
    const wrap = document.createElement("div");
    let lab;
    let el;
    const compact = f.kind === "int" || f.kind === "float" || f.kind === "bool";
    if (compact) {
      wrap.className = "paramRow";
      lab = document.createElement("label");
      lab.className = "paramRowLabel";
      lab.htmlFor = fieldId(f.key);
      lab.textContent = f.label;
      wrap.appendChild(lab);
      if (f.kind === "bool") {
        el = document.createElement("input");
        el.type = "checkbox";
        el.id = fieldId(f.key);
        el.className = "paramRowCheck";
      } else {
        el = document.createElement("input");
        el.className = "ccInput ccInput--compact";
        el.id = fieldId(f.key);
        el.type = "number";
        if (f.kind === "float") el.step = "0.01";
        else el.step = "1";
      }
    } else {
      wrap.className = "field";
      lab = document.createElement("label");
      lab.htmlFor = fieldId(f.key);
      lab.textContent = f.label;
      wrap.appendChild(lab);
      if (f.kind === "textarea") {
        el = document.createElement("textarea");
        el.className = "ccTextarea";
        el.id = fieldId(f.key);
        el.rows = f.rows != null ? f.rows : f.key === "headline_topics" ? 12 : 8;
      } else {
        el = document.createElement("input");
        el.className = "ccInput";
        el.id = fieldId(f.key);
        el.type = "text";
      }
    }
    if (f.kind === "bool") {
      el.addEventListener("change", () => schedulePreviewSlow());
    } else {
      el.addEventListener("input", () => schedulePreviewSlow());
    }
    wrap.appendChild(el);
    panel.appendChild(wrap);
  }

  const stylePanel = panels.querySelector('.ccTabPanel[data-tab="style"]');
  if (stylePanel) {
    const wrap = document.createElement("div");
    wrap.className = "field";
    const lab = document.createElement("label");
    lab.htmlFor = "textStylesJson";
    lab.textContent = "text_styles (JSON, как в ui_settings.json)";
    wrap.appendChild(lab);
    const ta = document.createElement("textarea");
    ta.id = "textStylesJson";
    ta.className = "ccTextarea ccTextarea--code";
    ta.rows = 14;
    ta.addEventListener("input", () => schedulePreviewSlow());
    wrap.appendChild(ta);
    stylePanel.appendChild(wrap);

    const row = document.createElement("div");
    row.className = "styleMergeGrid";
    row.innerHTML = `
      <div class="field" style="margin:0">
        <label for="styleElement">Элемент</label>
        <select id="styleElement" class="ccInput">
          <option value="title">title</option>
          <option value="subtitle">subtitle</option>
          <option value="dates">dates</option>
          <option value="watermark">watermark</option>
        </select>
      </div>
      <div class="field" style="margin:0">
        <label>&nbsp;</label>
        <button type="button" class="btn btnPrimary" id="btnMergeStyle" style="width:100%">Слить стиль (patch JSON)</button>
      </div>`;
    stylePanel.appendChild(row);
    const patchWrap = document.createElement("div");
    patchWrap.className = "field";
    patchWrap.innerHTML =
      '<label for="stylePatchJson">Фрагмент стиля (JSON объекта)</label><textarea id="stylePatchJson" class="ccTextarea ccTextarea--code" rows="6" spellcheck="false">{}</textarea>';
    stylePanel.appendChild(patchWrap);
    $("btnMergeStyle").addEventListener("click", onMergeStyle);
  }

  setActiveTab(activeTab);
}

function readFieldValue(f, el) {
  if (f.kind === "bool") return Boolean(el.checked);
  if (f.kind === "select") return String(el.value ?? "");
  if (f.kind === "int") return parseInt(String(el.value || "0"), 10) || 0;
  if (f.kind === "float") return parseFloat(String(el.value || "0")) || 0.0;
  if (f.kind === "lines_list") {
    const raw = String(el.value ?? "");
    return raw
      .split(/\r?\n/)
      .map((x) => x.trim())
      .filter(Boolean);
  }
  return String(el.value ?? "");
}

function writeFieldValue(f, val) {
  if (f.kind === "color") {
    syncColorFieldFromValue(f, val);
    return;
  }
  const el = $(fieldId(f.key));
  if (!el) return;
  if (f.kind === "lines_list") {
    el.value = Array.isArray(val) ? val.join("\n") : String(val ?? "");
    return;
  }
  if (f.kind === "select") {
    const v = val === undefined || val === null ? "" : String(val);
    const opts = f.options || [];
    el.value = opts.some((o) => String(o.value) === v) ? v : opts[0] ? String(opts[0].value) : "";
    return;
  }
  if (f.kind === "bool") {
    el.checked = Boolean(val);
  } else if (val === undefined || val === null) {
    el.value = "";
  } else {
    el.value = String(val);
  }
}

function collectSettingsFromForm() {
  const s = { ...state.settings };
  for (const f of FIELDS) {
    if (f.kind === "hint" || f.kind === "name_builder" || f.kind === "glow_palette") continue;
    const el = $(fieldId(f.key));
    if (!el) continue;
    s[f.key] = readFieldValue(f, el);
  }
  const glowRoot = $("fld_glow_overlay_colors");
  if (glowRoot) {
    const out = [];
    glowRoot.querySelectorAll(".ccGlowPaletteHex").forEach((inp) => {
      const n = normalizeColorHex(inp.value);
      if (/^#[0-9A-F]{6}$/.test(n)) out.push(n);
    });
    s.glow_overlay_colors = out;
  }
  const parts = readOutputNamePartsFromDom();
  if (parts !== null) {
    s.output_name_parts = parts.length > 0 ? parts : defaultOutputNameParts();
  }
  const ts = $("textStylesJson");
  if (ts) {
    try {
      const parsed = JSON.parse(ts.value || "{}");
      if (parsed && typeof parsed === "object") {
        const prev = { ...(s.text_styles || {}) };
        for (const [k, v] of Object.entries(parsed)) {
          if (v && typeof v === "object" && !Array.isArray(v)) {
            prev[k] = { ...(prev[k] || {}), ...v };
          } else {
            prev[k] = v;
          }
        }
        s.text_styles = prev;
      }
    } catch {
      /* оставляем старый text_styles */
    }
  }
  buildTimelineLayersModel(s);
  state.settings = s;
  return s;
}

function pushSettingsToForm() {
  const s = state.settings || {};
  for (const f of FIELDS) {
    if (f.kind === "hint" || f.kind === "name_builder" || f.kind === "glow_palette") continue;
    if (!(f.key in s)) continue;
    writeFieldValue(f, s[f.key]);
  }
  paintGlowPaletteRoot($("fld_glow_overlay_colors"), s.glow_overlay_colors);
  const ts = $("textStylesJson");
  if (ts) {
    try {
      ts.value = JSON.stringify(s.text_styles || {}, null, 2);
    } catch {
      ts.value = "{}";
    }
  }
  $("settingsJsonRaw").value = JSON.stringify(s, null, 2);
  updateTimelineRange();
  buildTimelineLayersModel(s);
  renderTimelineLayersEditor();
  mountOutputNameBuilder(s.output_name_parts);
}

function collectScene() {
  return {
    headline: $("headline").value || "",
    hero: $("hero").value || "",
    bio: $("bio").value || "",
    dates: $("dates").value || "",
    image_path: "",
    current_time: parseFloat($("timeline").value || "0"),
  };
}

function syncTimelineProfessionalPlayhead() {
  const panel = $("timelineLayersPanel");
  if (!panel) return;
  const ph = panel.querySelector(".ccTimelinePro__playhead");
  if (!ph) return;
  const mx = Math.max(0.1, parseFloat(state.settings?.duration_max ?? 10));
  const t = Math.max(0, parseFloat($("timeline")?.value || "0"));
  const pct = Math.min(100, Math.max(0, (t / mx) * 100));
  ph.style.left = `${pct}%`;
}

function updateTimeReadout() {
  const t = parseFloat($("timeline").value || "0");
  const mx = parseFloat(state.settings?.duration_max ?? 10);
  const s = `${t.toFixed(2)} / ${mx.toFixed(2)}`;
  $("timeReadout").textContent = s;
  const ov = $("previewTimeOverlay");
  if (ov) ov.textContent = s;
  syncTimelineProfessionalPlayhead();
}

function updateTimelineRange() {
  const mx = Math.max(0.1, parseFloat(state.settings?.duration_max ?? 10));
  const tl = $("timeline");
  tl.max = String(mx);
  let v = parseFloat(tl.value || "0");
  if (v > mx) {
    v = mx;
    tl.value = String(v);
  }
  updateTimeReadout();
}

const TL_LAYER_SYNC_MS = 400;
let timelineLayersSyncTimer = null;
let timelineProSelectedId = null;
/** @type {{ mode: string, row: any, start0: number, end0: number, mx: number, startX: number, clipEl: HTMLElement, laneTrackEl: HTMLElement } | null} */
let timelineProDrag = null;

/** ЛКМ по клипу: ждём порог движения, иначе открываем панель элемента. */
let timelineClipPick = null;

function timelineProPixelsPerSecond() {
  const z = parseFloat($("timelineZoom")?.value || "3");
  return 48 * Math.max(0.5, Math.min(z, 8));
}

function fmtTimelineClock(sec) {
  const s = Math.max(0, sec);
  const m = Math.floor(s / 60);
  const r = s - m * 60;
  const rs = r < 10 ? `0${r.toFixed(2)}` : r.toFixed(2);
  return `${String(m).padStart(2, "0")}:${rs}`;
}

function isHttpOrDataUrl(src) {
  const t = String(src || "").trim();
  return /^https?:\/\//i.test(t) || /^data:/i.test(t) || /^blob:/i.test(t);
}

function timelineStudioAssetUrl(localPath) {
  const p = String(localPath || "").trim();
  if (!p || isHttpOrDataUrl(p)) return null;
  return `${API}/api/studio-asset?path=${encodeURIComponent(p)}`;
}

function timelineTextStripDataUrl(text, tw = 220, th = 32) {
  const t = String(text || " ").replace(/\s+/g, " ").trim().slice(0, 120) || "…";
  try {
    const c = document.createElement("canvas");
    c.width = tw;
    c.height = th;
    const ctx = c.getContext("2d");
    if (!ctx) return null;
    const g = ctx.createLinearGradient(0, 0, tw, 0);
    g.addColorStop(0, "#121a22");
    g.addColorStop(0.5, "#1a2834");
    g.addColorStop(1, "#121a22");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, tw, th);
    ctx.fillStyle = "#dff8f4";
    ctx.font = "600 11px system-ui,Segoe UI,sans-serif";
    ctx.textBaseline = "middle";
    let s = t;
    while (s.length > 2 && ctx.measureText(s).width > tw - 8) s = `${s.slice(0, -3)}…`;
    ctx.fillText(s, 5, th / 2);
    return c.toDataURL("image/png");
  } catch {
    return null;
  }
}

function getOverlayForLayerId(layerId) {
  if (!String(layerId).startsWith("overlay:")) return null;
  const want = String(layerId).slice("overlay:".length);
  const list = ensureSceneOverlays(state.settings);
  return list.find((o) => sanitizeOverlayTimelineId(o.id) === want) || null;
}

function layerFilmstripBackground(row) {
  const s = state.settings || {};
  const id = row.id;
  if (id === "background") {
    const mode = String(s.video_bg_mode || "folder").toLowerCase();
    if (mode === "photo_blur") {
      return "repeating-linear-gradient(90deg,#2a3040 0 12px,#3a4050 12px 24px)";
    }
    if (mode === "flat") {
      const spec = String(s.video_bg_spec || "#1a1f2a").split(",")[0].trim();
      return `repeating-linear-gradient(90deg, ${spec} 0 20px, rgba(255,255,255,.07) 20px 22px)`;
    }
    return "repeating-linear-gradient(90deg,#1f2838 0 16px,#2a3344 16px 32px)";
  }
  if (id === "glow") {
    return "repeating-linear-gradient(90deg,rgba(255,240,200,.45) 0 6px,rgba(120,180,255,.35) 6px 14px)";
  }
  if (id === "watermark") {
    const wm = timelineTextStripDataUrl(String(s.watermark_text || "WM").trim().slice(0, 60), 240, 32);
    if (wm) return `url("${wm.replace(/"/g, '\\"')}")`;
    return "repeating-linear-gradient(90deg,#3a3a32 0 24px,#4a4a42 24px 48px)";
  }
  if (id === "title") {
    const d = timelineTextStripDataUrl(($("headline") && $("headline").value) || "Заголовок", 260, 32);
    if (d) return `url("${d.replace(/"/g, '\\"')}")`;
    return "repeating-linear-gradient(90deg,#1a3030 0 14px,#244040 14px 28px)";
  }
  if (id === "subtitle") {
    const d = timelineTextStripDataUrl(($("bio") && $("bio").value) || "Описание", 280, 32);
    if (d) return `url("${d.replace(/"/g, '\\"')}")`;
    return "repeating-linear-gradient(90deg,#1a2528 0 14px,#243038 14px 28px)";
  }
  if (id === "dates") {
    const d = timelineTextStripDataUrl(($("dates") && $("dates").value) || "Даты", 200, 32);
    if (d) return `url("${d.replace(/"/g, '\\"')}")`;
    return "repeating-linear-gradient(90deg,#252018 0 14px,#383024 14px 28px)";
  }
  if (String(id).startsWith("overlay:")) {
    const ov = getOverlayForLayerId(id);
    if (!ov) return "repeating-linear-gradient(90deg,#333 0 16px,#444 16px 32px)";
    if (ov.kind === "text") {
      const d = timelineTextStripDataUrl(ov.text || "Текст", 280, 32);
      if (d) return `url("${d.replace(/"/g, '\\"')}")`;
    }
    if ((ov.kind === "image" || ov.kind === "gif") && ov.src) {
      const u = isHttpOrDataUrl(ov.src) ? ov.src : timelineStudioAssetUrl(ov.src);
      if (u) return `url("${String(u).replace(/"/g, '\\"')}")`;
    }
    return "repeating-linear-gradient(90deg,#2d3a44 0 10px,#3d4d5c 10px 20px)";
  }
  return "repeating-linear-gradient(90deg,#333 0 14px,#3a3a3a 14px 28px)";
}

function sanitizeOverlayTimelineId(raw) {
  return String(raw || "")
    .replace(/[^a-zA-Z0-9_-]/g, "")
    .slice(0, 80);
}

function defaultTimelineLayers(mx) {
  const d = Math.max(0.1, mx);
  return [
    { id: "background", start: 0, end: d, z: 0, visible: true },
    { id: "card", start: 0, end: d, z: 20, visible: true },
    { id: "title", start: 0, end: d, z: 21, visible: true },
    { id: "subtitle", start: 0, end: d, z: 22, visible: true },
    { id: "dates", start: 0, end: d, z: 23, visible: true },
    { id: "watermark", start: 0, end: d, z: 100, visible: true },
    { id: "glow", start: 0, end: d, z: 10000, visible: true },
  ];
}

function buildTimelineLayersModel(settingsObj) {
  const s = settingsObj || state.settings || {};
  const mx = Math.max(0.1, parseFloat(s.duration_max ?? 10));
  const defaults = defaultTimelineLayers(mx);
  const byId = Object.fromEntries(defaults.map((r) => [r.id, { ...r }]));
  for (const r of Array.isArray(s.timeline_layers) ? s.timeline_layers : []) {
    if (!r || !r.id) continue;
    const id = String(r.id);
    const prev = byId[id] || { id, start: 0, end: mx, z: 50, visible: true };
    let st = parseFloat(r.start);
    let en = parseFloat(r.end);
    if (Number.isNaN(st)) st = 0;
    if (Number.isNaN(en)) en = mx;
    let visible = prev.visible !== false;
    if (r.visible === false || r.visible === 0 || r.visible === "0" || r.visible === "false") visible = false;
    byId[id] = {
      id,
      start: Math.max(0, Math.min(st, mx)),
      end: Math.max(0, Math.min(en, mx)),
      z: Number.isFinite(Number(r.z)) ? Math.round(Number(r.z)) : prev.z || 0,
      visible,
    };
    if (byId[id].end <= byId[id].start) byId[id].end = Math.min(mx, byId[id].start + 0.2);
  }
  const ovs = ensureSceneOverlays(s);
  for (const ov of ovs) {
    const oid = sanitizeOverlayTimelineId(ov.id);
    if (!oid) continue;
    const lid = `overlay:${oid}`;
    if (!byId[lid]) byId[lid] = { id: lid, start: 0, end: mx, z: 120, visible: true };
  }
  delete byId.photo;
  if (!byId.glow) {
    byId.glow = { id: "glow", start: 0, end: mx, z: 10000, visible: true };
  }
  const rows = Object.values(byId).map((r) => ({
    ...r,
    visible: r.visible !== false,
    start: Math.max(0, Math.min(r.start, mx)),
    end: Math.max(Math.min(r.start + 0.02, mx), Math.min(r.end, mx)),
  }));
  rows.sort((a, b) => (a.z - b.z) || String(a.id).localeCompare(String(b.id)));
  s.timeline_layers = rows;
}

function timelineLayerTitle(id) {
  const m = {
    background: "Фон",
    glow: "Блик / засвет",
    title: "Заголовок",
    subtitle: "Описание",
    dates: "Даты",
    watermark: "Вотермарк",
  };
  if (m[id]) return m[id];
  if (String(id).startsWith("overlay:")) return `Оверлей · ${String(id).slice("overlay:".length)}`;
  return String(id);
}

function scheduleTimelineLayersStudioSync() {
  clearTimeout(timelineLayersSyncTimer);
  timelineLayersSyncTimer = setTimeout(() => {
    timelineLayersSyncTimer = null;
    studioSync().catch((e) => appendLog(String(e)));
  }, TL_LAYER_SYNC_MS);
}

function moveTimelineLayer(id, delta) {
  buildTimelineLayersModel(state.settings);
  const sorted = [...(state.settings.timeline_layers || [])].sort((a, b) => b.z - a.z);
  const idx = sorted.findIndex((r) => r.id === id);
  if (idx < 0) return;
  const ni = idx + delta;
  if (ni < 0 || ni >= sorted.length) return;
  const tmpRow = sorted[idx];
  sorted[idx] = sorted[ni];
  sorted[ni] = tmpRow;
  const n = sorted.length;
  sorted.forEach((r, i) => {
    r.z = (n - 1 - i) * 10;
  });
  state.settings.timeline_layers = [...sorted].sort((a, b) => a.z - b.z || String(a.id).localeCompare(String(b.id)));
  collectSettingsFromForm();
  renderTimelineLayersEditor();
  schedulePreviewSlow();
  scheduleTimelineLayersStudioSync();
}

function timelineProDetachDragListeners() {
  document.removeEventListener("pointermove", timelineProOnPointerMove);
  document.removeEventListener("pointerup", timelineProOnPointerUp);
  document.body.style.userSelect = "";
}

function timelineProOnPointerMove(ev) {
  if (!timelineProDrag) return;
  const d = timelineProDrag;
  const tw = d.laneTrackEl.getBoundingClientRect().width;
  if (tw < 8) return;
  const dsec = ((ev.clientX - d.startX) / tw) * d.mx;
  let st = d.start0;
  let en = d.end0;
  const minL = 0.06;
  if (d.mode === "L") {
    st = d.start0 + dsec;
    st = Math.max(0, Math.min(st, en - minL));
  } else if (d.mode === "R") {
    en = d.end0 + dsec;
    en = Math.min(d.mx, Math.max(en, st + minL));
  } else {
    const len = d.end0 - d.start0;
    st = d.start0 + dsec;
    en = st + len;
    if (st < 0) {
      st = 0;
      en = len;
    }
    if (en > d.mx) {
      en = d.mx;
      st = d.mx - len;
    }
    if (st < 0) st = 0;
    if (en > d.mx) en = d.mx;
    if (en - st < minL) en = st + minL;
  }
  d.row.start = st;
  d.row.end = en;
  d.clipEl.style.left = `${(st / d.mx) * 100}%`;
  d.clipEl.style.width = `${((en - st) / d.mx) * 100}%`;
  const meta = d.clipEl.querySelector(".ccTimelinePro__clipMeta");
  if (meta) meta.textContent = `Δ ${fmtTimelineClock(en - st)}`;
}

function timelineProOnPointerUp() {
  if (!timelineProDrag) return;
  timelineProDrag = null;
  timelineProDetachDragListeners();
  collectSettingsFromForm();
  renderTimelineLayersEditor();
  schedulePreviewSlow();
  scheduleTimelineLayersStudioSync();
}

let timelineCtxMenuEl = null;
let timelineCtxRowRef = null;

function hideTimelineLayerContextMenu() {
  if (timelineCtxMenuEl) {
    timelineCtxMenuEl.hidden = true;
    timelineCtxRowRef = null;
  }
}

function ensureTimelineLayerContextMenu() {
  if (timelineCtxMenuEl) return timelineCtxMenuEl;
  const m = document.createElement("div");
  m.id = "timelineLayerCtxMenu";
  m.className = "ccTimelineCtx";
  m.hidden = true;
  m.innerHTML = `
    <div class="ccTimelineCtx__head">
      <div class="ccTimelineCtx__label">Слой</div>
      <div class="ccTimelineCtx__layerName" data-ctx-layer-name></div>
      <p class="ccTimelineCtx__hint">Порядок — кто перекрывает кого на кадре. «Поверх» значит рисуется поверх остальных слоёв (выше по стеку).</p>
    </div>
    <button type="button" class="ccTimelineCtx__item" data-act="vis">
      <span class="ccTimelineCtx__itemIcon" aria-hidden="true">◎</span>
      <span class="ccTimelineCtx__itemText"><span data-ctx-vis-label>Видимость</span><span class="ccTimelineCtx__itemSub">На превью и в экспорте</span></span>
    </button>
    <div class="ccTimelineCtx__sep"></div>
    <button type="button" class="ccTimelineCtx__item" data-act="up">
      <span class="ccTimelineCtx__itemIcon" aria-hidden="true">↑</span>
      <span class="ccTimelineCtx__itemText">Поверх других<span class="ccTimelineCtx__itemSub">Выше в списке слоёв</span></span>
    </button>
    <button type="button" class="ccTimelineCtx__item" data-act="dn">
      <span class="ccTimelineCtx__itemIcon" aria-hidden="true">↓</span>
      <span class="ccTimelineCtx__itemText">Под другими<span class="ccTimelineCtx__itemSub">Ниже в списке слоёв</span></span>
    </button>
  `;
  m.addEventListener("pointerdown", (e) => e.stopPropagation());
  m.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-act]");
    if (!btn || !timelineCtxRowRef) return;
    const act = btn.getAttribute("data-act");
    const row = timelineCtxRowRef;
    if (act === "vis") row.visible = !(row.visible !== false);
    else if (act === "up") moveTimelineLayer(row.id, -1);
    else if (act === "dn") moveTimelineLayer(row.id, 1);
    hideTimelineLayerContextMenu();
    collectSettingsFromForm();
    renderTimelineLayersEditor();
    schedulePreviewSlow();
    scheduleTimelineLayersStudioSync();
  });
  document.body.appendChild(m);
  timelineCtxMenuEl = m;
  return m;
}

function showTimelineLayerContextMenu(clientX, clientY, row) {
  const m = ensureTimelineLayerContextMenu();
  const nameEl = m.querySelector("[data-ctx-layer-name]");
  if (nameEl) nameEl.textContent = timelineLayerTitle(row.id);
  const visLab = m.querySelector("[data-ctx-vis-label]");
  if (visLab) visLab.textContent = row.visible === false ? "Показать слой" : "Скрыть слой";
  timelineCtxRowRef = row;
  m.hidden = false;
  const pad = 8;
  requestAnimationFrame(() => {
    const w = m.offsetWidth || 160;
    const h = m.offsetHeight || 100;
    m.style.left = `${Math.min(window.innerWidth - w - pad, Math.max(pad, clientX))}px`;
    m.style.top = `${Math.min(window.innerHeight - h - pad, Math.max(pad, clientY))}px`;
  });
}

function timelineProBeginClipDrag(trackEl, clipEl, row, mode, ev) {
  if (ev.button !== 0) return;
  ev.preventDefault();
  ev.stopPropagation();
  const mx = Math.max(0.1, parseFloat(state.settings?.duration_max ?? 10));
  timelineProDrag = {
    mode,
    row,
    start0: row.start,
    end0: row.end,
    mx,
    startX: ev.clientX,
    clipEl,
    laneTrackEl: trackEl,
  };
  document.addEventListener("pointermove", timelineProOnPointerMove);
  document.addEventListener("pointerup", timelineProOnPointerUp);
  document.body.style.userSelect = "none";
}

function timelineClipMetaLine(row) {
  if (String(row.id).startsWith("overlay:")) {
    const ov = getOverlayForLayerId(row.id);
    const sceneTag = ov && ov.hidden ? "скрыт · " : "";
    if (ov && ov.kind === "text") return sceneTag + (String(ov.text || "").replace(/\s+/g, " ").trim().slice(0, 72) || "Текст");
    if (ov && (ov.kind === "image" || ov.kind === "gif") && ov.src)
      return (
        sceneTag +
        String(ov.src)
          .replace(/\\/g, "/")
          .split("/")
          .pop()
      );
  }
  return `Δ ${fmtTimelineClock(row.end - row.start)}`;
}

function renderTimelineLayersEditor() {
  const panel = $("timelineLayersPanel");
  if (!panel) return;
  buildTimelineLayersModel(state.settings);
  const mx = Math.max(0.1, parseFloat(state.settings?.duration_max ?? 10));
  const pps = timelineProPixelsPerSecond();
  const innerW = Math.max(8, mx * pps);
  const rows = [...(state.settings.timeline_layers || [])]
    .filter((r) => r && r.id !== "card")
    .sort((a, b) => b.z - a.z);

  panel.innerHTML = "";
  const root = document.createElement("div");
  root.className = "ccTimelinePro";

  const body = document.createElement("div");
  body.className = "ccTimelinePro__body";

  const scroll = document.createElement("div");
  scroll.className = "ccTimelinePro__scroll";
  const inner = document.createElement("div");
  inner.className = "ccTimelinePro__scrollInner";
  inner.style.width = `${innerW}px`;

  const ruler = document.createElement("div");
  ruler.className = "ccTimelinePro__ruler";
  const secStep = innerW / mx > 90 ? 1 : innerW / mx > 45 ? 2 : 5;
  for (let sec = 0; sec <= mx + 0.0001; sec += secStep) {
    const tick = document.createElement("div");
    tick.className = "ccTimelinePro__rulerTick";
    if (sec % (secStep * 5) < 0.001 || sec === 0) tick.classList.add("ccTimelinePro__rulerTick--major");
    tick.style.left = `${(sec / mx) * 100}%`;
    tick.textContent = fmtTimelineClock(sec);
    ruler.appendChild(tick);
  }
  ruler.addEventListener("pointerdown", (ev) => {
    const rect = inner.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const t = Math.max(0, Math.min(mx, (x / rect.width) * mx));
    const tl = $("timeline");
    if (tl) {
      tl.value = String(t);
      updateTimeReadout();
      schedulePreviewFast();
    }
  });

  const lanes = document.createElement("div");
  lanes.className = "ccTimelinePro__lanes";
  const playhead = document.createElement("div");
  playhead.className = "ccTimelinePro__playhead";

  inner.appendChild(ruler);
  inner.appendChild(lanes);
  inner.appendChild(playhead);
  scroll.appendChild(inner);

  for (const row of rows) {
    const lane = document.createElement("div");
    lane.className = "ccTimelinePro__lane";
    const track = document.createElement("div");
    track.className = "ccTimelinePro__laneTrack";
    const clip = document.createElement("div");
    const ovRow = String(row.id).startsWith("overlay:") ? getOverlayForLayerId(row.id) : null;
    clip.className =
      "ccTimelinePro__clip" +
      (timelineProSelectedId === row.id ? " is-selected" : "") +
      (row.visible === false ? " is-timeline-hidden" : "") +
      (ovRow && ovRow.hidden ? " is-scene-hidden" : "");
    clip.style.left = `${(row.start / mx) * 100}%`;
    clip.style.width = `${((row.end - row.start) / mx) * 100}%`;

    const hdr = document.createElement("div");
    hdr.className = "ccTimelinePro__clipHeader";
    hdr.appendChild(document.createTextNode(timelineLayerTitle(row.id)));
    const sub = document.createElement("div");
    sub.className = "ccTimelinePro__clipMeta";
    sub.textContent = timelineClipMetaLine(row);
    hdr.appendChild(sub);

    const film = document.createElement("div");
    film.className = "ccTimelinePro__clipFilm";
    const filmBg = layerFilmstripBackground(row);
    film.style.backgroundImage = filmBg;
    if (filmBg.startsWith("url(")) film.style.backgroundSize = "auto 100%";

    const hL = document.createElement("div");
    hL.className = "ccTimelinePro__handle ccTimelinePro__handle--L";
    const hR = document.createElement("div");
    hR.className = "ccTimelinePro__handle ccTimelinePro__handle--R";

    clip.appendChild(hdr);
    clip.appendChild(film);
    clip.appendChild(hL);
    clip.appendChild(hR);

    hL.addEventListener("pointerdown", (e) => timelineProBeginClipDrag(track, clip, row, "L", e));
    hR.addEventListener("pointerdown", (e) => timelineProBeginClipDrag(track, clip, row, "R", e));
    clip.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      if (e.target.closest(".ccTimelinePro__handle")) return;
      hideTimelineLayerContextMenu();
      timelineClipPickDetach();
      timelineProSelectedId = row.id;
      panel.querySelectorAll(".ccTimelinePro__clip.is-selected").forEach((el) => el.classList.remove("is-selected"));
      clip.classList.add("is-selected");
      const mx0 = Math.max(0.1, parseFloat(state.settings?.duration_max ?? 10));
      timelineClipPick = {
        row,
        trackEl: track,
        clipEl: clip,
        mx: mx0,
        ox: e.clientX,
        oy: e.clientY,
        dragging: false,
      };
      document.addEventListener("pointermove", timelineClipPickOnMove);
      document.addEventListener("pointerup", timelineClipPickOnUp);
    });
    clip.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      timelineProSelectedId = row.id;
      panel.querySelectorAll(".ccTimelinePro__clip.is-selected").forEach((el) => el.classList.remove("is-selected"));
      clip.classList.add("is-selected");
      showTimelineLayerContextMenu(e.clientX, e.clientY, row);
    });

    track.appendChild(clip);
    lane.appendChild(track);
    lanes.appendChild(lane);
  }

  body.appendChild(scroll);
  root.appendChild(body);
  panel.appendChild(root);

  syncTimelineProfessionalPlayhead();
}

async function apiJson(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    cache: "no-store",
    headers: { "content-type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = { raw: text };
  }
  if (!res.ok) throw new Error(`${path} HTTP ${res.status}: ${text.slice(0, 400)}`);
  return data;
}

async function studio(body) {
  return apiJson("/api/studio", { method: "POST", body: JSON.stringify(body) });
}

async function studioSync() {
  await studio({
    cmd: "sync",
    settings: collectSettingsFromForm(),
    scene: collectScene(),
  });
}

async function runPreview() {
  const myReq = ++previewRequestId;
  if (shouldShowPreviewSplash()) {
    setPreviewLoading(true);
  }
  if (previewFetchAbort) {
    try {
      previewFetchAbort.abort();
    } catch (_) {
      /* ignore */
    }
  }
  previewFetchAbort = new AbortController();
  const signal = previewFetchAbort.signal;
  collectSettingsFromForm();
  let settings = JSON.parse(JSON.stringify(state.settings));
  settings = mergeOpenElementEditorIntoSettingsClone(settings);
  if (bgPalettePreviewOverride && bgPalettePreviewOverride.hit && bgPalettePreviewOverride.spec) {
    settings = buildSettingsWithBgPaletteLinePreview(settings, bgPalettePreviewOverride.hit, bgPalettePreviewOverride.spec);
  }
  if (textFillPreviewOverride && textFillPreviewOverride.hit) {
    settings = buildSettingsWithTextFillRowPreview(settings, textFillPreviewOverride.hit, textFillPreviewOverride);
  }
  const body = {
    settings,
    scene: collectScene(),
    t: parseFloat($("timeline").value || "0"),
    meta: true,
  };
  renderTimelineLayersEditor();
  let res;
  try {
    res = await fetch(`${API}/api/preview`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if (e && e.name === "AbortError") return;
    if (myReq === previewRequestId && shouldShowPreviewSplash()) setPreviewLoading(false);
    throw e;
  }
  if (myReq !== previewRequestId) return;
  if (!res.ok) {
    const t = await res.text();
    appendLog(`[preview] error ${res.status}: ${t.slice(0, 300)}`);
    if (shouldShowPreviewSplash()) setPreviewLoading(false);
    return;
  }
  const data = await res.json();
  if (myReq !== previewRequestId) return;
  if (!data || !data.ok || !data.png) {
    appendLog(`[preview] bad json`);
    if (shouldShowPreviewSplash()) setPreviewLoading(false);
    return;
  }
  if (myReq !== previewRequestId) return;
  previewHitboxes = data.hitboxes && typeof data.hitboxes === "object" ? data.hitboxes : {};
  const isEphemeralStylePreview = Boolean(bgPalettePreviewOverride || textFillPreviewOverride);
  if (!isEphemeralStylePreview && data.text_styles && typeof data.text_styles === "object" && !Array.isArray(data.text_styles)) {
    const prev = { ...(state.settings.text_styles || {}) };
    for (const [k, v] of Object.entries(data.text_styles)) {
      if (v && typeof v === "object" && !Array.isArray(v)) {
        prev[k] = { ...(prev[k] || {}), ...v };
      } else {
        prev[k] = v;
      }
    }
    state.settings.text_styles = prev;
    const tsj = $("textStylesJson");
    if (tsj) {
      try {
        tsj.value = JSON.stringify(state.settings.text_styles || {}, null, 2);
      } catch (_) {
        /* ignore */
      }
    }
    const edBody = $("elementEditorBody");
    const panel = $("elementEditorPanel");
    const hit = elementEditorHit;
    if (edBody && panel && !panel.hidden && hit && data.text_styles[hit]) {
      const pst = data.text_styles[hit];
      const w = edBody.querySelector('[data-style="bg_snap_inner_w"]');
      const h = edBody.querySelector('[data-style="bg_snap_inner_h"]');
      if (w && pst.bg_snap_inner_w != null) w.value = String(pst.bg_snap_inner_w);
      if (h && pst.bg_snap_inner_h != null) h.value = String(pst.bg_snap_inner_h);
    }
  }
  if (lastPreviewUrl) URL.revokeObjectURL(lastPreviewUrl);
  lastPreviewUrl = null;
  const img = $("previewImg");
  const dataUrl = `data:image/png;base64,${data.png}`;
  let settled = false;
  const done = () => {
    if (settled) return;
    settled = true;
    if (myReq === previewRequestId) {
      if (shouldShowPreviewSplash()) markPreviewSplashDone();
      setPreviewLoading(false);
    }
  };
  if (img) {
    img.onload = done;
    img.onerror = done;
    img.src = dataUrl;
    if (img.complete && img.naturalWidth > 0) done();
    else if (typeof img.decode === "function") {
      img.decode().then(done).catch(done);
    }
  } else {
    done();
  }
  redrawPreviewHitboxes();
}

function clientToPreviewVideo(clientX, clientY) {
  const svg = $("previewOverlay");
  if (!svg || !svg.getScreenCTM) return null;
  const pt = svg.createSVGPoint();
  pt.x = clientX;
  pt.y = clientY;
  const inv = svg.getScreenCTM()?.inverse();
  if (!inv) return null;
  const p = pt.matrixTransform(inv);
  if (p.x < 0 || p.y < 0 || p.x > 1080 || p.y > 1920) return null;
  return { vx: p.x, vy: p.y };
}

function pickHitboxAt(vx, vy) {
  // Текст карточки — раньше декоративных overlay, чтобы тянуть/менять ширину описания, а не слой с колесом зодиака.
  const order = ["watermark", "title", "dates", "subtitle", ...overlayHitKeys()];
  for (const key of order) {
    const b = previewHitboxes[key];
    if (!b || b.length !== 4) continue;
    const [x0, y0, x1, y1] = b;
    if (vx >= x0 && vx <= x1 && vy >= y0 && vy <= y1) return key;
  }
  return null;
}

function redrawPreviewHitboxes() {
  const g = $("previewHitboxGroup");
  if (!g) return;
  g.innerHTML = "";
  const order = ["title", "dates", "subtitle", "watermark", ...overlayHitKeys()];
  let gx = 0;
  let gy = 0;
  if (previewGhostOffset && previewSelected) {
    gx = previewGhostOffset.dx;
    gy = previewGhostOffset.dy;
  }
  for (const key of order) {
    const b = previewHitboxes[key];
    if (!b || b.length !== 4) continue;
    let [x0, y0, x1, y1] = b;
    if (previewGhostOffset && key === previewSelected) {
      x0 += gx;
      x1 += gx;
      y0 += gy;
      y1 += gy;
    }
    const r = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    r.setAttribute("x", String(x0));
    r.setAttribute("y", String(y0));
    r.setAttribute("width", String(Math.max(1, x1 - x0)));
    r.setAttribute("height", String(Math.max(1, y1 - y0)));
    r.setAttribute("fill", "rgba(0,0,0,0.02)");
    const sel = key === previewSelected;
    r.setAttribute("stroke", sel ? "#3FA9F5" : "#6D6D6D");
    r.setAttribute("stroke-width", sel ? "3" : "1");
    if (!sel) r.setAttribute("stroke-dasharray", "6 4");
    r.dataset.hit = key;
    g.appendChild(r);
  }
  if (previewSnapVertical) {
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", "540");
    line.setAttribute("x2", "540");
    line.setAttribute("y1", "0");
    line.setAttribute("y2", "1920");
    line.setAttribute("stroke", "#3FA9F5");
    line.setAttribute("stroke-width", "2");
    line.setAttribute("stroke-dasharray", "10 6");
    line.setAttribute("pointer-events", "none");
    g.appendChild(line);
  }
}

function clamp(n, a, b) {
  return Math.max(a, Math.min(b, n));
}

function nudgeLayoutFromPreview(sel, dx, dy) {
  collectSettingsFromForm();
  const s = state.settings;
  if (sel === "title") {
    s.title_y = clamp((s.title_y || 0) + dy, -1200, 2200);
    s.title_x = clamp((s.title_x || 0) + dx, -800, 800);
  } else if (sel === "dates") {
    s.dates_y = clamp((s.dates_y || 0) + dy, -1200, 2200);
    s.dates_x = clamp((s.dates_x || 0) + dx, -800, 800);
  } else if (sel === "subtitle") {
    s.subtitle_y = clamp((s.subtitle_y || 0) + dy, -1200, 2200);
    s.subtitle_x = clamp((s.subtitle_x || 0) + dx, -800, 800);
  } else if (sel === "watermark") {
    s.watermark_x = clamp((s.watermark_x || 0) + dx, -200, 1200);
    s.watermark_y = clamp((s.watermark_y || 0) + dy, -200, 2200);
  } else if (typeof sel === "string" && sel.startsWith("overlay:")) {
    const id = sel.slice(8);
    const arr = ensureSceneOverlays(s);
    const ov = arr.find((o) => o && String(o.id) === id);
    if (!ov) return;
    ov.x = clamp((Number(ov.x) || 0) + dx, -600, 2200);
    ov.y = clamp((Number(ov.y) || 0) + dy, -600, 2600);
    s.scene_overlays = arr;
  } else return;
  pushSettingsToForm();
}

function wheelLayoutFromPreview(sel, delta, shiftKey) {
  collectSettingsFromForm();
  const s = state.settings;
  const d = delta > 0 ? 2 : -2;
  const rwWrapWheel = (x) => clamp(Math.round(x), 0, 1080);
  if (sel === "title") {
    if (shiftKey) {
      const base = Number(s.title_wrap_width);
      const cur = Number.isFinite(base) && base > 0 ? base : 880;
      s.title_wrap_width = rwWrapWheel(cur + d * 14);
    } else {
      s.title_font_size = clamp((s.title_font_size || 40) + d, 34, 140);
      const lo = Number(s.title_font_size_min);
      s.title_font_size_min = Math.min(Number.isFinite(lo) ? lo : 22, s.title_font_size);
    }
  } else if (sel === "dates") s.dates_font_size = clamp((s.dates_font_size || 40) + d, 18, 84);
  else if (sel === "subtitle") {
    if (shiftKey) {
      const base = Number(s.subtitle_wrap_width);
      const cur = Number.isFinite(base) && base > 0 ? base : 880;
      s.subtitle_wrap_width = rwWrapWheel(cur + d * 14);
    } else s.subtitle_font_size = clamp((s.subtitle_font_size || 40) + d, 24, 84);
  }
  else if (sel === "watermark") s.watermark_font_size = clamp((s.watermark_font_size || 24) + d, 12, 120);
  else if (typeof sel === "string" && sel.startsWith("overlay:")) {
    const id = sel.slice(8);
    const arr = ensureSceneOverlays(s);
    const ov = arr.find((o) => o && String(o.id) === id);
    if (!ov) return;
    if (ov.kind === "image" || ov.kind === "gif") {
      if (shiftKey) ov.width = clamp((Number(ov.width) || 320) + d * 6, 32, 1080);
      else ov.height = clamp((Number(ov.height) || 240) + d * 6, 32, 1920);
    } else {
      ov.font_size = clamp((Number(ov.font_size) || 48) + d, 8, 200);
    }
    s.scene_overlays = arr;
  } else return;
  pushSettingsToForm();
}

const PREVIEW_EDGE_PX = 36;

function previewResizeEdgesAt(vx, vy, hb) {
  if (!hb || hb.length !== 4) return null;
  const [x0, y0, x1, y1] = hb;
  if (vx < x0 || vx > x1 || vy < y0 || vy > y1) return null;
  const t = PREVIEW_EDGE_PX;
  const nearL = vx - x0 <= t;
  const nearR = x1 - vx <= t;
  const nearT = vy - y0 <= t;
  const nearB = y1 - vy <= t;
  let h = null;
  if (nearL && nearR) h = vx - x0 < x1 - vx ? "l" : "r";
  else if (nearL) h = "l";
  else if (nearR) h = "r";
  let v = null;
  if (nearT && nearB) v = vy - y0 < y1 - vy ? "t" : "b";
  else if (nearT) v = "t";
  else if (nearB) v = "b";
  if (!h && !v) return null;
  return { h, v };
}

function previewResizeCursor(edges) {
  if (!edges || (!edges.h && !edges.v)) return "";
  const { h, v } = edges;
  if (h && v) return (h === "l" && v === "t") || (h === "r" && v === "b") ? "nwse-resize" : "nesw-resize";
  if (h) return "ew-resize";
  return "ns-resize";
}

function resizeLayoutFromPreview(sel, edges, dx, dy, hitbox) {
  collectSettingsFromForm();
  const s = state.settings;
  const rwWrap = (x) => clamp(Math.round(x), 0, 1080);
  const rOvImgW = (x) => clamp(Math.round(x), 32, 1080);
  const rOvImgH = (x) => clamp(Math.round(x), 32, 1920);
  const rfz = (x, lo, hi) => clamp(Math.round(x), lo, hi);
  const h = edges && edges.h;
  const v = edges && edges.v;
  if (!h && !v) return;

  const wrapFromHitbox = (key) => {
    let base = Number(s[key]) || 0;
    if (!base && hitbox && hitbox.length === 4) base = Math.round(hitbox[2] - hitbox[0]);
    if (!base) base = 880;
    const d = h === "r" ? dx : h === "l" ? -dx : 0;
    s[key] = rwWrap(base + d);
  };

  if (sel === "title") {
    if (h === "r" || h === "l") wrapFromHitbox("title_wrap_width");
    if (v === "b") {
      s.title_font_size = rfz((Number(s.title_font_size) || 40) + Math.round(dy / 5), 22, 140);
      const lo = Number(s.title_font_size_min);
      if (Number.isFinite(lo)) s.title_font_size_min = Math.min(lo, s.title_font_size);
    }
    if (v === "t") {
      s.title_font_size = rfz((Number(s.title_font_size) || 40) - Math.round(dy / 5), 22, 140);
      const lo = Number(s.title_font_size_min);
      if (Number.isFinite(lo)) s.title_font_size_min = Math.min(lo, s.title_font_size);
    }
  } else if (sel === "subtitle") {
    if (h === "r" || h === "l") wrapFromHitbox("subtitle_wrap_width");
    if (v === "b") s.subtitle_font_size = rfz((Number(s.subtitle_font_size) || 40) + Math.round(dy / 5), 24, 84);
    if (v === "t") s.subtitle_font_size = rfz((Number(s.subtitle_font_size) || 40) - Math.round(dy / 5), 24, 84);
  } else if (sel === "dates") {
    if (v === "b") s.dates_font_size = rfz((Number(s.dates_font_size) || 40) + Math.round(dy / 5), 18, 84);
    if (v === "t") s.dates_font_size = rfz((Number(s.dates_font_size) || 40) - Math.round(dy / 5), 18, 84);
    if (h === "r") s.dates_font_size = rfz((Number(s.dates_font_size) || 40) + Math.round(dx / 8), 18, 84);
    if (h === "l") s.dates_font_size = rfz((Number(s.dates_font_size) || 40) - Math.round(dx / 8), 18, 84);
  } else if (sel === "watermark") {
    const d = Math.abs(dx) > Math.abs(dy) ? Math.round(dx / 10) : -Math.round(dy / 10);
    if (h || v) s.watermark_font_size = rfz((Number(s.watermark_font_size) || 24) + d, 12, 120);
  } else if (typeof sel === "string" && sel.startsWith("overlay:")) {
    const id = sel.slice(8);
    const arr = ensureSceneOverlays(s);
    const ov = arr.find((o) => o && String(o.id) === id);
    if (!ov) return;
    if (ov.kind === "image" || ov.kind === "gif") {
      if (h === "r") ov.width = rOvImgW((Number(ov.width) || 320) + dx);
      if (h === "l") ov.width = rOvImgW((Number(ov.width) || 320) - dx);
      if (v === "b") ov.height = rOvImgH((Number(ov.height) || 240) + dy);
      if (v === "t") ov.height = rOvImgH((Number(ov.height) || 240) - dy);
    } else {
      if (h === "r" || h === "l") {
        let base = Number(ov.max_width) || 0;
        if (!base && hitbox && hitbox.length === 4) base = Math.round(hitbox[2] - hitbox[0]);
        if (!base) base = 900;
        ov.max_width = rwWrap(base + (h === "r" ? dx : -dx));
      }
      if (v === "b") ov.font_size = rfz((Number(ov.font_size) || 48) + Math.round(dy / 5), 8, 200);
      if (v === "t") ov.font_size = rfz((Number(ov.font_size) || 48) - Math.round(dy / 5), 8, 200);
    }
    s.scene_overlays = arr;
  } else return;
  pushSettingsToForm();
}

function openElementEditorFromPreviewPoint(clientX, clientY) {
  const p = clientToPreviewVideo(clientX, clientY);
  if (!p) return;
  const hit = pickHitboxAt(p.vx, p.vy);
  if (!hit) return;
  previewSelected = hit;
  redrawPreviewHitboxes();
  openElementEditor(hit);
}

/** Тот же выбор элемента, что по ПКМ в превью: панель слева «Медиа» + подсветка в просмотре. */
function openTimelineLayerInLeftPanel(layerId) {
  hideTimelineLayerContextMenu();
  collectSettingsFromForm();
  const id = String(layerId || "");

  const hitFromCore = (hit) => {
    previewSelected = hit;
    redrawPreviewHitboxes();
    openElementEditor(hit);
  };

  if (["title", "subtitle", "dates", "watermark"].includes(id)) {
    hitFromCore(id);
    document.querySelector('.ccMediaTab[data-media-tab="main"]')?.click();
    return;
  }
  if (id.startsWith("overlay:")) {
    const want = id.slice("overlay:".length);
    const arr = ensureSceneOverlays(state.settings);
    const ov = arr.find((o) => o && sanitizeOverlayTimelineId(o.id) === want);
    if (!ov) return;
    hitFromCore(id);
    document.querySelector('.ccMediaTab[data-media-tab="overlays"]')?.click();
    return;
  }
  if (id === "background") {
    previewSelected = null;
    redrawPreviewHitboxes();
    closeElementEditorModal();
    document.querySelector('.ccMediaTab[data-media-tab="main"]')?.click();
    setActiveTab("bgframe");
    try {
      $(fieldId("video_bg_mode"))?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (_) {
      /* ignore */
    }
    return;
  }
  if (id === "glow") {
    previewSelected = null;
    redrawPreviewHitboxes();
    closeElementEditorModal();
    document.querySelector('.ccMediaTab[data-media-tab="main"]')?.click();
    setActiveTab("motion");
    try {
      $(fieldId("glow_overlay_opacity"))?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (_) {
      /* ignore */
    }
  }
}

function timelineClipPickDetach() {
  if (!timelineClipPick) return;
  document.removeEventListener("pointermove", timelineClipPickOnMove);
  document.removeEventListener("pointerup", timelineClipPickOnUp);
  timelineClipPick = null;
}

function timelineClipPickOnMove(ev) {
  const p = timelineClipPick;
  if (!p || p.dragging) return;
  const dx = ev.clientX - p.ox;
  const dy = ev.clientY - p.oy;
  if (Math.hypot(dx, dy) < 5) return;
  p.dragging = true;
  document.removeEventListener("pointermove", timelineClipPickOnMove);
  document.removeEventListener("pointerup", timelineClipPickOnUp);
  timelineClipPick = null;
  timelineProBeginClipDrag(p.trackEl, p.clipEl, p.row, "M", {
    clientX: p.ox,
    button: 0,
    preventDefault() {},
    stopPropagation() {},
  });
  timelineProOnPointerMove(ev);
}

function timelineClipPickOnUp() {
  const p = timelineClipPick;
  timelineClipPickDetach();
  if (p && !p.dragging) openTimelineLayerInLeftPanel(p.row.id);
}

function wirePreviewEditor() {
  const svg = $("previewOverlay");
  if (!svg) return;

  const stack = $("previewStack");
  if (stack) {
    stack.addEventListener(
      "contextmenu",
      (ev) => {
        ev.preventDefault();
        openElementEditorFromPreviewPoint(ev.clientX, ev.clientY);
      },
      true,
    );
    stack.addEventListener(
      "dblclick",
      (ev) => {
        ev.preventDefault();
        openElementEditorFromPreviewPoint(ev.clientX, ev.clientY);
      },
      true,
    );
  }

  svg.addEventListener("pointerdown", (ev) => {
    if (ev.button !== 0) return;
    const p = clientToPreviewVideo(ev.clientX, ev.clientY);
    if (!p) return;
    const hit = pickHitboxAt(p.vx, p.vy);
    if (hit) {
      previewSelected = hit;
      previewDragMutated = false;
      const hb = previewHitboxes[hit];
      const edges = hb ? previewResizeEdgesAt(p.vx, p.vy, hb) : null;
      if (edges && (edges.h || edges.v)) {
        previewDrag = { vx: p.vx, vy: p.vy, mode: "resize", edges };
        previewGhostOffset = null;
      } else {
        previewDrag = { vx: p.vx, vy: p.vy, mode: "move" };
        previewGhostOffset = { dx: 0, dy: 0 };
      }
      redrawPreviewHitboxes();
    } else {
      previewSelected = null;
      previewDrag = null;
      previewDragMutated = false;
      previewGhostOffset = null;
      redrawPreviewHitboxes();
      return;
    }
    try {
      svg.setPointerCapture(ev.pointerId);
    } catch (_) {
      /* ignore */
    }
  });

  svg.addEventListener("pointermove", (ev) => {
    if (!previewDrag || !previewSelected) return;
    const p = clientToPreviewVideo(ev.clientX, ev.clientY);
    if (!p) return;
    if (previewDrag.mode === "resize") {
      const dx = p.vx - previewDrag.vx;
      const dy = p.vy - previewDrag.vy;
      if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return;
      previewDragMutated = true;
      previewDrag.vx = p.vx;
      previewDrag.vy = p.vy;
      try {
        svg.style.cursor = previewResizeCursor(previewDrag.edges);
      } catch (_) {
        /* ignore */
      }
      resizeLayoutFromPreview(previewSelected, previewDrag.edges, dx, dy, previewHitboxes[previewSelected]);
      redrawPreviewHitboxes();
      return;
    }
    let dx = p.vx - previewDrag.vx;
    let dy = p.vy - previewDrag.vy;
    previewSnapVertical = false;
    const FRAME_CX = 540;
    const SNAP = 14;
    const hb = previewHitboxes[previewSelected];
    if (hb && hb.length === 4) {
      const [x0, y0, x1, y1] = hb;
      const gox = previewGhostOffset ? previewGhostOffset.dx : 0;
      const cx = (x0 + x1) / 2 + gox;
      const nextCx = cx + dx;
      if (Math.abs(nextCx - FRAME_CX) <= SNAP) {
        dx += FRAME_CX - nextCx;
        previewSnapVertical = true;
      }
    }
    if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return;
    previewDragMutated = true;
    previewDrag.vx = p.vx;
    previewDrag.vy = p.vy;
    nudgeLayoutFromPreview(previewSelected, dx, dy);
    if (previewGhostOffset) {
      previewGhostOffset.dx += dx;
      previewGhostOffset.dy += dy;
    }
    redrawPreviewHitboxes();
  });

  svg.addEventListener(
    "pointermove",
    (ev) => {
      if (previewDrag) return;
      const p = clientToPreviewVideo(ev.clientX, ev.clientY);
      if (!p || !previewSelected) {
        try {
          svg.style.cursor = "";
        } catch (_) {
          /* ignore */
        }
        return;
      }
      const hb = previewHitboxes[previewSelected];
      const edges = hb ? previewResizeEdgesAt(p.vx, p.vy, hb) : null;
      try {
        svg.style.cursor = previewResizeCursor(edges);
      } catch (_) {
        /* ignore */
      }
    },
    { passive: true },
  );

  const endDrag = (ev) => {
    const hadPointer = previewDrag != null;
    const mutated = previewDragMutated;
    previewDrag = null;
    previewGhostOffset = null;
    previewDragMutated = false;
    previewSnapVertical = false;
    if (hadPointer) {
      try {
        svg.style.cursor = "";
      } catch (_) {
        /* ignore */
      }
      try {
        svg.releasePointerCapture(ev.pointerId);
      } catch (_) {
        /* ignore */
      }
      redrawPreviewHitboxes();
      if (mutated) {
        clearTimeout(previewTimer);
        previewTimer = null;
        runPreview().catch((e) => appendLog(`[preview] ${e}`));
      }
    }
  };
  svg.addEventListener("pointerup", endDrag);
  svg.addEventListener("pointercancel", endDrag);

  svg.addEventListener(
    "wheel",
    (ev) => {
      if (!previewSelected) return;
      ev.preventDefault();
      wheelLayoutFromPreview(previewSelected, ev.deltaY, ev.shiftKey);
      clearTimeout(previewWheelTimer);
      previewWheelTimer = setTimeout(() => {
        previewWheelTimer = null;
        runPreview().catch((e) => appendLog(`[preview] ${e}`));
      }, 280);
    },
    { passive: false },
  );
}

/** Собрать настройки из вкладок «Свойства», при открытой панели элемента — как «Применить» там; синхронизация с воркером и сразу предпросмотр. */
async function applyAllPropertiesAndPreview() {
  const panel = $("elementEditorPanel");
  if (elementEditorHit && panel && !panel.hidden) {
    applyElementEditorFromModal();
  } else {
    collectSettingsFromForm();
    pushSettingsToForm();
  }
  try {
    await studioSync();
  } catch (e) {
    appendLog(String(e));
  }
  if (previewTimer) {
    clearTimeout(previewTimer);
    previewTimer = null;
  }
  await runPreview().catch((e) => appendLog(`[preview] ${e}`));
}

/** Тяжёлый превью (MoviePy/PIL) — не чаще чем раз в ~0.75 c после правок текста/пресета */
function schedulePreviewSlow() {
  updateTimeReadout();
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => {
    runPreview().catch((e) => appendLog(`[preview] ${e}`));
  }, 750);
}

/** Таймлайн — чуть отзывчивее, но всё равно с отменой предыдущего запроса */
function schedulePreviewFast() {
  updateTimeReadout();
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => {
    runPreview().catch((e) => appendLog(`[preview] ${e}`));
  }, 120);
}

async function loadPresetFromServer() {
  const data = await apiJson("/api/settings");
  state.settings = data && typeof data === "object" ? data : {};
  pushSettingsToForm();
  renderSceneOverlaysList();
}

/** Слияние импорта пресета с текущим state (частичный JSON из файла не затирает всё). */
function applyImportedPresetObject(imported) {
  if (!imported || typeof imported !== "object" || Array.isArray(imported)) {
    throw new Error("Нужен JSON-объект с настройками");
  }
  const cur = state.settings && typeof state.settings === "object" ? state.settings : {};
  const next = { ...cur, ...imported };
  if (imported.text_styles && typeof imported.text_styles === "object" && !Array.isArray(imported.text_styles)) {
    next.text_styles = { ...(cur.text_styles || {}), ...imported.text_styles };
  }
  state.settings = next;
}

async function savePresetToLocalFile() {
  collectSettingsFromForm();
  try {
    const r = await studio({ cmd: "save_preset_file", settings: state.settings });
    if (r && (r.cancelled || r.error === "cancelled")) return;
    if (!r || !r.ok) {
      appendLog(`[ui] сохранить пресет: ${(r && r.error) || "нет ответа"}`);
      return;
    }
    appendLog(`[ui] пресет записан: ${r.path || ""}`);
  } catch (e) {
    appendLog(`[ui] сохранить пресет: ${e}`);
  }
}

async function savePresetToServer() {
  collectSettingsFromForm();
  await apiJson("/api/settings", {
    method: "POST",
    body: JSON.stringify(state.settings),
  });
  appendLog("[ui] пресет сохранён в ui_settings.json");
}

async function checkHealth() {
  const res = await fetch(`${API}/api/health`, { cache: "no-store" });
  const h = await res.json().catch(() => ({}));
  if (!res.ok) {
    setBanner(`API недоступен: HTTP ${res.status}`);
    return h;
  }
  if (!h.studio_worker) {
    setBanner(
      `Процесс предпросмотра не запущен или упал: ${h.studio_error || "нет деталей"}. Проверь консоль uvicorn и лог studio worker (moviepy и т.д.).`,
    );
  } else {
    setBanner("");
  }
  return h;
}

async function randomHoroscope() {
  const r = await studio({ cmd: "random_politician" });
  if (!r.ok) {
    appendLog(`[random_horoscope] ${r.error || JSON.stringify(r)}`);
    return;
  }
  const sc = r.scene || {};
  $("headline").value = sc.headline || "";
  $("hero").value = sc.hero || "";
  $("dates").value = sc.dates || "";
  $("bio").value = sc.bio || "";
  if (sc.current_time != null) $("timeline").value = String(sc.current_time);
  updateTimeReadout();
  await runPreview();
}

async function shuffleZodiac() {
  await studioSync();
  const r = await studio({ cmd: "resummarize" });
  if (!r.ok) {
    appendLog(`[shuffle_zodiac] ${r.error || JSON.stringify(r)}`);
    return;
  }
  $("bio").value = r.bio || "";
  schedulePreviewSlow();
}

async function pickTopicHeadline() {
  await studioSync();
  const r = await studio({ cmd: "generate_headline" });
  if (!r.ok) {
    appendLog(`[pick_topic_headline] ${r.error || JSON.stringify(r)}`);
    return;
  }
  const hl = $("headline");
  if (hl && r.headline != null) hl.value = String(r.headline);
  schedulePreviewSlow();
}

async function onMergeStyle() {
  const element = $("styleElement").value;
  let patch = {};
  try {
    patch = JSON.parse($("stylePatchJson").value || "{}");
  } catch (e) {
    appendLog(`[style] JSON: ${e}`);
    return;
  }
  await studioSync();
  const r = await studio({ cmd: "merge_text_style", element, style: patch });
  if (!r.ok) {
    appendLog(`[merge_text_style] ${r.error || JSON.stringify(r)}`);
    return;
  }
  state.settings.text_styles = r.text_styles || state.settings.text_styles;
  pushSettingsToForm();
  schedulePreviewSlow();
}

async function cancelRender() {
  try {
    const data = await apiJson("/api/render/cancel", { method: "POST", body: "{}" });
    const ln = `[render] отмена → ${JSON.stringify(data)}`;
    appendLog(ln);
    appendRenderModalLine(ln);
  } catch (e) {
    appendLog(`[render] отмена: ${e}`);
    appendRenderModalLine(`[render] отмена: ${e}`);
  }
}

async function startRenderFromModal() {
  collectSettingsFromForm();
  const wm = (state.settings.watermark_text || "").trim();
  const saveFolder = ($("exportSaveFolder")?.value || "").trim();
  if (!wm && !saveFolder) {
    appendLog("[render] Укажите «Сохранить в папку» или задайте вотермарку в пресете.");
    return;
  }
  const resolution = $("exportResolution")?.value || "1080p";
  const fps = Math.max(1, parseInt($("exportFps")?.value || "30", 10));
  const video_bitrate_mbps = Math.max(1, parseInt($("exportBitrate")?.value || "5", 10));
  const count = Math.max(1, parseInt($("exportVideoCount")?.value || "1", 10));
  const mode = count > 1 ? "batch" : "current";

  closeExportSettingsModal();
  renderVideoTotal = count;
  renderVideoIndex = 1;
  openRenderLogModal(true);
  await savePresetToServer();
  await studioSync();
  const payload = { mode, resolution, fps, video_bitrate_mbps };
  if (saveFolder) payload.save_folder = saveFolder;
  if (mode === "batch") payload.count = count;
  const dminStr = ($("exportDurationMin")?.value || "").trim();
  const dmaxStr = ($("exportDurationMax")?.value || "").trim();
  if (dminStr && dmaxStr) {
    const dmin = parseFloat(dminStr);
    const dmax = parseFloat(dmaxStr);
    if (Number.isFinite(dmin) && Number.isFinite(dmax) && dmin > 0 && dmax > 0) {
      payload.duration_min_sec = Math.min(dmin, dmax);
      payload.duration_max_sec = Math.max(dmin, dmax);
    }
  }
  const startLn = `[render] ${JSON.stringify(payload)}`;
  appendLog(startLn);
  appendRenderModalLine(startLn);
  try {
    const data = await apiJson("/api/render", { method: "POST", body: JSON.stringify(payload) });
    const doneLn = `[render] ${JSON.stringify(data)}`;
    appendLog(doneLn);
    appendRenderModalLine(doneLn);
    renderProcActive = true;
    updateRenderCancelButton();
  } catch (e) {
    const errLn = `[render] ошибка старта: ${e}`;
    appendLog(errLn);
    appendRenderModalLine(errLn);
    renderProcActive = false;
    updateRenderCancelButton();
  }
}

function wire() {
  document.addEventListener("click", (ev) => {
    if (!timelineCtxMenuEl || timelineCtxMenuEl.hidden) return;
    const t = ev.target;
    if (t instanceof Node && timelineCtxMenuEl.contains(t)) return;
    hideTimelineLayerContextMenu();
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") hideTimelineLayerContextMenu();
  });

  wirePreviewEditor();
  wireMediaTabs();

  $("btnPropsApplyAll")?.addEventListener("click", () => {
    applyAllPropertiesAndPreview().catch((e) => appendLog(String(e)));
  });

  $("sceneOverlaysList")?.addEventListener("click", async (ev) => {
    const t = ev.target;
    if (!(t instanceof HTMLElement)) return;
    const editEl = t.closest("[data-overlay-edit]");
    const edit = editEl?.getAttribute("data-overlay-edit");
    if (edit) {
      openElementEditor(`overlay:${edit}`);
      return;
    }
    const delEl = t.closest("[data-overlay-del]");
    const del = delEl?.getAttribute("data-overlay-del");
    if (del) {
      collectSettingsFromForm();
      const s = state.settings;
      const arr = ensureSceneOverlays(s).filter((o) => o && String(o.id) !== del);
      s.scene_overlays = arr;
      if (elementEditorHit === `overlay:${del}`) closeElementEditorModal();
      try {
        await savePresetToServer();
        await studioSync();
      } catch (e) {
        appendLog(String(e));
      }
      renderSceneOverlaysList();
      schedulePreviewSlow();
    }
  });

  $("btnAddOverlayText")?.addEventListener("click", async () => {
    collectSettingsFromForm();
    const s = state.settings;
    const ov = defaultOverlayTextBlock(s);
    ensureSceneOverlays(s).push(ov);
    try {
      await savePresetToServer();
      await studioSync();
    } catch (e) {
      appendLog(String(e));
    }
    renderSceneOverlaysList();
    openElementEditor(`overlay:${ov.id}`);
    schedulePreviewSlow();
  });
  $("btnAddOverlayImage")?.addEventListener("click", async () => {
    collectSettingsFromForm();
    const s = state.settings;
    const ov = defaultOverlayImageBlock();
    ensureSceneOverlays(s).push(ov);
    try {
      await savePresetToServer();
      await studioSync();
    } catch (e) {
      appendLog(String(e));
    }
    renderSceneOverlaysList();
    openElementEditor(`overlay:${ov.id}`);
    schedulePreviewSlow();
  });
  $("btnAddOverlayGif")?.addEventListener("click", async () => {
    collectSettingsFromForm();
    const s = state.settings;
    const ov = defaultOverlayGifBlock();
    ensureSceneOverlays(s).push(ov);
    try {
      await savePresetToServer();
      await studioSync();
    } catch (e) {
      appendLog(String(e));
    }
    renderSceneOverlaysList();
    openElementEditor(`overlay:${ov.id}`);
    schedulePreviewSlow();
  });

  loadPreviewStackScale();
  loadPreviewShortsShell();
  $("previewStackScale")?.addEventListener("input", (ev) => {
    applyPreviewStackScale(ev.target.value);
  });
  $("previewShortsShell")?.addEventListener("change", () => applyPreviewShortsShellFromCheckbox());
  $("previewShortsChrome")?.addEventListener("error", () => {
    appendLog(
      "[preview] Не загрузился assets/shorts.png — положите файл в папку web/ (именно web/shorts.png, из корня проекта браузер не отдаёт)."
    );
  });

  $("elementEditorClose")?.addEventListener("click", () => closeElementEditorModal());
  $("elementEditorCancel")?.addEventListener("click", () => closeElementEditorModal());
  $("elementEditorApply")?.addEventListener("click", () => applyElementEditorFromModal());

  $("timeline").addEventListener("input", () => {
    schedulePreviewFast();
  });

  const tlMx = () => parseFloat($("timeline").max || "10");
  $("btnSeekStart")?.addEventListener("click", () => {
    $("timeline").value = "0";
    updateTimeReadout();
    schedulePreviewFast();
  });
  $("btnSeekEnd")?.addEventListener("click", () => {
    $("timeline").value = String(tlMx());
    updateTimeReadout();
    schedulePreviewFast();
  });
  let playTimer = null;
  $("btnPlayToggle")?.addEventListener("click", () => {
    const btn = $("btnPlayToggle");
    if (playTimer) {
      clearInterval(playTimer);
      playTimer = null;
      btn.textContent = "▶";
      return;
    }
    btn.textContent = "❚❚";
    let acc = 0;
    playTimer = setInterval(() => {
      const tl = $("timeline");
      const mx = tlMx();
      let v = parseFloat(tl.value || "0") + 0.06;
      if (v >= mx) {
        v = mx;
        clearInterval(playTimer);
        playTimer = null;
        btn.textContent = "▶";
      }
      tl.value = String(v);
      updateTimeReadout();
      acc += 1;
      if (acc % 2 === 0) schedulePreviewFast();
    }, 90);
  });
  function syncTimelineZoomFromControl() {
    const zEl = $("timelineZoom");
    if (!zEl) return;
    const z = parseFloat(zEl.value || "3");
    document.documentElement.style.setProperty("--cc-tl-zoom", String(z));
  }
  syncTimelineZoomFromControl();
  $("timelineZoom")?.addEventListener("input", () => {
    syncTimelineZoomFromControl();
    renderTimelineLayersEditor();
  });
  $("btnMenuStub")?.addEventListener("click", (e) => e.preventDefault());

  $("headline").addEventListener("input", () => {
    schedulePreviewSlow();
    renderTimelineLayersEditor();
  });
  $("hero").addEventListener("input", schedulePreviewSlow);
  $("dates").addEventListener("input", () => {
    schedulePreviewSlow();
    renderTimelineLayersEditor();
  });
  $("bio").addEventListener("input", () => {
    schedulePreviewSlow();
    renderTimelineLayersEditor();
  });
  $("btnSavePresetFile")?.addEventListener("click", () => {
    savePresetToLocalFile().catch((e) => appendLog(`[ui] сохранить пресет: ${e}`));
  });
  const presetFileInput = $("presetFileInput");
  presetFileInput?.addEventListener("change", async () => {
    const f = presetFileInput.files && presetFileInput.files[0];
    presetFileInput.value = "";
    if (!f) return;
    try {
      const text = await f.text();
      const data = JSON.parse(text);
      applyImportedPresetObject(data);
      pushSettingsToForm();
      renderSceneOverlaysList();
      await studioSync();
      await runPreview();
      appendLog(`[ui] пресет загружен из файла: ${f.name}`);
    } catch (e) {
      appendLog(`[ui] загрузка пресета из файла: ${e}`);
    }
  });
  $("btnLoadPresetFile")?.addEventListener("click", () => {
    presetFileInput?.click();
  });
  $("btnReload").addEventListener("click", async () => {
    await loadPresetFromServer();
    await studioSync();
    await runPreview();
  });
  $("btnSave").addEventListener("click", async () => {
    await savePresetToServer();
    await studioSync();
    await runPreview();
  });
  $("btnApplyParams").addEventListener("click", async () => {
    await savePresetToServer();
    await studioSync();
    await runPreview();
  });
  $("btnRandom").addEventListener("click", () => randomHoroscope().catch((e) => appendLog(String(e))));
  $("btnResum").addEventListener("click", () => shuffleZodiac().catch((e) => appendLog(String(e))));
  const genHl = $("btnGenHeadline");
  if (genHl) genHl.addEventListener("click", () => pickTopicHeadline().catch((e) => appendLog(String(e))));

  $("btnRenderCurrent")?.addEventListener("click", () => openExportSettingsModal());
  $("exportSettingsBackdrop")?.addEventListener("click", () => closeExportSettingsModal());
  $("exportSettingsClose")?.addEventListener("click", () => closeExportSettingsModal());
  $("btnExportStart")?.addEventListener("click", () =>
    startRenderFromModal().catch((e) => {
      appendLog(String(e));
      appendRenderModalLine(String(e));
    }),
  );

  $("btnExportPickFolder")?.addEventListener("click", async () => {
    const inp = $("exportSaveFolder");
    const def = (inp?.value || "").trim() || (state.settings && String(state.settings.video_output_dir || "").trim()) || "";
    let p = "";
    const pe = window.politicsStudio;
    if (pe && typeof pe.pickOutputDirectory === "function") {
      p = await pe.pickOutputDirectory(def || null);
    } else {
      p = await pickFolderNative({ title: "Папка для сохранения видео", defaultPath: def || undefined });
    }
    if (p && inp) inp.value = typeof p === "string" ? p : "";
  });

  $("btnOpenRenderLog")?.addEventListener("click", () => openRenderLogModal(false));
  $("btnShowRenderLogs")?.addEventListener("click", () => toggleRenderLogPanel());
  $("btnCopyRenderLogs")?.addEventListener("click", () => copyRenderLogsToClipboard().catch((e) => appendLog(String(e))));
  $("btnRenderCancel")?.addEventListener("click", () => cancelRender().catch((e) => appendLog(String(e))));
  $("btnRenderLogClose")?.addEventListener("click", () => closeRenderLogModal());
  $("btnRenderLogClose2")?.addEventListener("click", () => closeRenderLogModal());
  $("renderLogBackdrop")?.addEventListener("click", () => closeRenderLogModal());
  $("btnRenderLogClear")?.addEventListener("click", () => {
    const r = $("renderLogOut");
    if (r) r.textContent = "";
    resetRenderProgressUi();
  });

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && exportSettingsModalOpen) {
      ev.preventDefault();
      closeExportSettingsModal();
      return;
    }
    if (ev.key === "Escape" && renderLogModalOpen) closeRenderLogModal();
    const elPanel = $("elementEditorPanel");
    if (ev.key === "Escape" && elPanel && !elPanel.hidden) {
      ev.preventDefault();
      closeElementEditorModal();
    }
  });

  $("btnApplyJson").addEventListener("click", () => {
    try {
      const parsed = JSON.parse($("settingsJsonRaw").value || "{}");
      state.settings = parsed;
      pushSettingsToForm();
      schedulePreviewSlow();
    } catch (e) {
      appendLog(`[json] ${e}`);
    }
  });
}

async function boot() {
  connectWs();
  initTabsOnce();
  wire();
  if (shouldShowPreviewSplash()) setPreviewLoading(true);
  await checkHealth();
  await loadPresetFromServer();
  await randomHoroscope();
}

boot().catch((e) => {
  setBanner(String(e));
  appendLog(`[boot] ${e}`);
});
