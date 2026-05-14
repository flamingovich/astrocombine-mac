import json
import os
import random
import re
from pathlib import Path

PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")

_DEFAULT_HEADLINE_TOPICS = (
    "Пока мы платим больше, они обещают меньше\n"
    "Очередной день, когда народ снова платит за чужой комфорт\n"
    "Цены вверх, зарплаты вниз, отчёты снова красивые\n"
    "У людей долги, у системы новые красивые планы\n"
    "Пока мы экономим на еде, нам рассказывают про успехи"
)

_DESCRIPTION_PLACEHOLDERS: tuple[str, ...] = (
    "Народ уже устал тянуть всё на себе: цены растут, зарплаты стоят, а обещания каждый раз как под копирку. "
    "Сверху снова красивые отчёты и разговоры про стабильность. "
    "На деле обычным людям становится только тяжелее.",
    "Платёжки больше, продукты дороже, лекарства недоступнее, а у людей всё меньше запаса прочности. "
    "При этом нам снова рассказывают, что всё под контролем. "
    "Ощущение, будто реальную жизнь никто не хочет замечать.",
    "Пока люди считают каждую покупку, вокруг продолжают говорить о росте и достижениях. "
    "Но в кошельке этот рост почему-то не появляется. "
    "Хочется не новых лозунгов, а нормальной жизни без вечного стресса.",
)


class HoroscopeStudioCreator:
    """Контент для вертикальных политических роликов: заголовок, описание, медиа."""

    def __init__(self) -> None:
        self.video_width = 1080
        self.video_height = 1920
        self.duration = 7
        self.df = None
        self.name_prefixes = [
            "Политика",
            "Без цензуры",
            "Голос людей",
            "Реальность дня",
            "Народный взгляд",
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

    def build_political_description(self) -> str:
        """Временная заглушка описания под политический ролик."""
        return random.choice(_DESCRIPTION_PLACEHOLDERS)

    def load_hashtag_lines(self) -> list[str]:
        if os.path.exists("hashtags.txt"):
            with open("hashtags.txt", "r", encoding="utf-8") as f:
                tags = [ln.strip() for ln in f if ln.strip()]
        else:
            tags = []
        if not tags:
            tags = ["#политика", "#новости", "#мнение", "#общество", "#голоснарода"]
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

    def get_random_politician_media(self) -> str | None:
        """Случайный файл из папки photos (картинка или GIF)."""
        return self.get_random_file("photos", PHOTO_EXTENSIONS)

    def init_match_report(self) -> None:
        self.match_report_path.write_text(
            "=== Match report ===\n"
            "Раньше здесь логировалось сопоставление имён с Excel; сейчас не используется.\n\n",
            encoding="utf-8",
        )

    def ensure_excel_cache(self) -> None:
        """Заглушка обратной совместимости."""
        return None

    def get_politician_bio_from_table(self, hero_name: str):
        return None, None

    def build_complaint_description(self, _name: str) -> str:
        """Совместимость: возвращает заглушку описания."""
        return self.build_political_description()

    def get_random_politician_photo(self):
        """Совместимость API: случайный медиа-файл из photos."""
        media = self.get_random_politician_media()
        if media:
            return media, "ok"
        return None, "Папка photos пуста"


# Обратная совместимость импортов из старых скриптов.
PoliticsStudioCreator = HoroscopeStudioCreator
