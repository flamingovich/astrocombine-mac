#!/bin/zsh

set -euo pipefail

DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$DIR"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "[ERROR] ffmpeg не найден."
  echo "Установи его командой: brew install ffmpeg"
  read -r "?Нажми Enter, чтобы закрыть..."
  exit 1
fi

count=0

for f in *.mp4; do
  if [[ ! -e "$f" ]]; then
    echo "[INFO] В папке нет MP4 файлов."
    read -r "?Нажми Enter, чтобы закрыть..."
    exit 0
  fi

  base="${f%.*}"
  out="${base}.gif"
  palette="${base}_palette.png"

  echo "[INFO] Конвертация: $f -> $out"

  ffmpeg -y -i "$f" -vf "fps=12,scale=720:-1:flags=lanczos,palettegen" "$palette"
  ffmpeg -y -i "$f" -i "$palette" -lavfi "fps=12,scale=720:-1:flags=lanczos[x];[x][1:v]paletteuse" "$out"

  rm -f "$palette"
  count=$((count + 1))
done

echo "[DONE] Готово. Сконвертировано файлов: $count"
read -r "?Нажми Enter, чтобы закрыть..."
