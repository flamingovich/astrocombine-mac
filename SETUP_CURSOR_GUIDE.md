# Politics Studio — быстрый гайд для нового ПК (и Cursor)

Этот проект — локальная студия на `Electron + FastAPI + Python` для генерации роликов.

## 1) Что установить заранее

- `Node.js` LTS (рекомендуется 20+), вместе с `npm`
- `Python` 3.10+ (на macOS лучше 3.11)
- `ffmpeg` (обязательно для `moviepy`)
- `git`
- (Опционально, но рекомендуется) `Ollama` для AI-описаний

## 2) Клонирование и установка зависимостей

```bash
git clone <URL_ЭТОГО_РЕПО>
cd politics-combine-master
npm install
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-server.txt
pip install pillow numpy proglog
```

Для Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements-server.txt
pip install pillow numpy proglog
```

## 3) Локальная нейронка (Ollama)

В проекте AI-генерация описаний/текстов идет через локальный API `Ollama` (`http://127.0.0.1:11434`), модель по умолчанию: `qwen2.5:14b`.

Установка и запуск:

```bash
ollama pull qwen2.5:14b
ollama serve
```

Проверка:

```bash
ollama list
```

Если Ollama не запущена, проект все равно работает (есть fallback на не-AI описание), но AI-функции будут пустыми.

## 4) Запуск проекта

Самый простой вариант:

- macOS: `./start_studio.command`
- Windows: `start_studio.bat`

Или вручную:

```bash
npm run dev
```

Это поднимает Electron-приложение; backend FastAPI стартует через `server/app.py`.

## 5) Что важно не коммитить

- Папку с локальными видео-артефактами: `Videos/` и `videos/`
- Временные каталоги, кеши, виртуальные окружения (`.venv`, `node_modules`, `__pycache__`)

## 6) Подсказка для Cursor на новом ПК

После открытия проекта в Cursor попросите агента:

1. Проверить, что установлены `Node`, `Python`, `ffmpeg`, `Ollama`.
2. Проверить запуск `npm run dev`.
3. Проверить доступность Ollama на `127.0.0.1:11434` и наличие `qwen2.5:14b`.
4. Не предлагать удалять/коммитить содержимое `Videos/`/`videos/`.
