import json
import os
import random
import re
from pathlib import Path

PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")

# Двенадцать знаков зодиака (фиксированный набор; порядок в ролике — случайный).
ZODIAC_SIGNS_RU: tuple[str, ...] = (
    "Овен",
    "Телец",
    "Близнецы",
    "Рак",
    "Лев",
    "Дева",
    "Весы",
    "Скорпион",
    "Стрелец",
    "Козерог",
    "Водолей",
    "Рыбы",
)

_RANK_LINE_STYLES: tuple[str, ...] = (
    "{rank} МЕСТО - {name}",
    "{rank} РАНГ - {name}",
    "{rank} - {name}",
    "ТОП {rank} - {name}",
)

_DEFAULT_HEADLINE_TOPICS = (
    "Топ знаков зодиака по богатству\n"
    "Кого ждёт удача на этой неделе\n"
    "Самые сильные знаки зодиака\n"
    "Рейтинг знаков по интуиции\n"
    "Кто из знаков блистает в любви"
)


class HoroscopeStudioCreator:
    """Контент для вертикальных роликов про гороскоп: темы заголовков + 12 знаков без нейросетей."""

    def __init__(self) -> None:
        self.video_width = 1080
        self.video_height = 1920
        self.duration = 7
        self.df = None
        self.name_prefixes = [
            "Гороскоп",
            "Звёзды говорят",
            "Зодиак",
            "Астрология",
            "Судьба по знакам",
        ]
        self.match_report_path = Path("match_report.txt")

    @staticmethod
    def parse_topic_lines(text: str) -> list[str]:
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        return lines

    def pick_random_headline(self, headline_topics: str) -> str:
        """Случайная строка из списка тем (каждая строка пресета — отдельный вариант заголовка)."""
        lines = self.parse_topic_lines(headline_topics)
        if not lines:
            lines = self.parse_topic_lines(_DEFAULT_HEADLINE_TOPICS)
        return random.choice(lines)

    def build_zodiac_description(self, separator: str = "\n") -> str:
        """12 знаков в случайном порядке; на ролик выбирается 1 стиль ранга и применяется ко всем строкам."""
        signs = list(ZODIAC_SIGNS_RU)
        random.shuffle(signs)
        line_style = random.choice(_RANK_LINE_STYLES)
        lines = [line_style.format(rank=i, name=name.upper()) for i, name in enumerate(signs, start=1)]
        return separator.join(lines)

    def load_hashtag_lines(self) -> list[str]:
        if os.path.exists("hashtags.txt"):
            with open("hashtags.txt", "r", encoding="utf-8") as f:
                tags = [ln.strip() for ln in f if ln.strip()]
        else:
            tags = []
        if not tags:
            tags = ["#гороскоп", "#зодиак", "#астрология", "#звёзды", "#судьба"]
        return tags

    def sample_hashtags(self, n: int) -> list[str]:
        tags = self.load_hashtag_lines()
        n = max(0, int(n))
        if n == 0 or not tags:
            return []
        if len(tags) >= n:
            return random.sample(tags, n)
        return random.choices(tags, k=n)

    def load_hashtags(self) -> str:
        return " ".join(self.sample_hashtags(3))

    def get_random_file(self, folder: str, exts: tuple[str, ...]) -> str | None:
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
            return None
        files = [f for f in os.listdir(folder) if str(f).lower().endswith(exts)]
        return os.path.join(folder, random.choice(files)) if files else None

    def init_match_report(self) -> None:
        self.match_report_path.write_text(
            "=== Match report ===\n"
            "Раньше здесь логировалось сопоставление имён с Excel; для гороскопов не используется.\n\n",
            encoding="utf-8",
        )

    def ensure_excel_cache(self) -> None:
        """Заглушка: таблица политиков больше не используется."""
        return None

    def get_politician_bio_from_table(self, hero_name: str):
        return None, None

    def build_complaint_description(self, _name: str) -> str:
        """Совместимость: вместо текста «от народа» — знаки зодиака."""
        return self.build_zodiac_description()

    def get_random_politician_photo(self):
        """Совместимость API: фото в гороскопах не используется."""
        return None, "Фото не используется (режим гороскопа)"


# Обратная совместимость импортов из старых скриптов.
PoliticsStudioCreator = HoroscopeStudioCreator
