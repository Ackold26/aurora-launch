"""
Генерация иконок Tauri-приложения из мастер-логотипа Aurora.

Использование:
    python tools/generate_icons.py [--source PATH] [--out DIR]

Скрипт берёт мастер-логотип (по умолчанию из aurora-meta дизайн-системы)
и генерирует полный набор иконок Tauri в нужных размерах:

- 32x32.png, 128x128.png, 128x128@2x.png, 256x256.png, 512x512.png
- icon.ico (multi-resolution Windows ICO с 16/32/48/64/128/256)
- icon.icns (multi-resolution macOS ICNS с 16..1024)

Мастер-источник — `aurora-deliverable-gold-accent.png` (3543x3542 RGBA)
из общей дизайн-системы Aurora (по пути `--source`). Этап 1.8 ROADMAP_
POST_V0_1_0.md ожидает специфический Launch Planner иконку от Маши
небесной/дизайнера; до её получения используем общий Aurora лого.

Скрипт центрирует master в квадрате (master почти квадрат: 1px разница),
делает downscale через Lanczos (наилучшее качество ребрендинга).

Требует только Pillow (уже в [dev] зависимостях).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# UTF-8 reconfigure для Windows cp1251 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path(
    "D:/Docs/Aurora_Ai/06_Aurora_Design_system/05_Logo/Flat/Deliverable/"
    "aurora-deliverable-gold-accent.png"
)
DEFAULT_OUT = REPO_ROOT / "src-tauri" / "icons"

ICO_SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
ICNS_SIZES = [(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)]


def log(msg: str) -> None:
    print(f"[generate_icons] {msg}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Сгенерировать набор Tauri-иконок из мастер-логотипа Aurora.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Путь к мастер-логотипу (по умолчанию: {DEFAULT_SOURCE}).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Папка для иконок (по умолчанию: {DEFAULT_OUT}).",
    )
    args = parser.parse_args()

    try:
        from PIL import Image
    except ImportError:
        log("ОШИБКА: Pillow не установлен. Установите: pip install Pillow")
        sys.exit(1)

    if not args.source.exists():
        log(f"ОШИБКА: мастер-логотип не найден: {args.source}")
        log(
            "Если запускаете в CI — добавьте шаг копирования мастер-логотипа из "
            "aurora-meta дизайн-системы или временно используйте placeholder."
        )
        sys.exit(2)

    args.out.mkdir(parents=True, exist_ok=True)

    log(f"Источник: {args.source}")
    log(f"Назначение: {args.out}")

    master = Image.open(args.source).convert("RGBA")
    log(f"Мастер размер: {master.size}, режим: {master.mode}")

    # Центрированный square-crop (мастер почти квадрат: 3543x3542)
    side = min(master.size)
    left = (master.width - side) // 2
    top = (master.height - side) // 2
    square = master.crop((left, top, left + side, top + side))
    log(f"После square-crop: {square.size}")

    # PNG иконки
    for sz in [32, 128, 256, 512]:
        out_path = args.out / f"{sz}x{sz}.png"
        resized = square.resize((sz, sz), Image.LANCZOS)
        resized.save(out_path, "PNG", optimize=True)
        log(f"  {out_path.name}: {out_path.stat().st_size:,} байт")

    # 128x128@2x.png — Retina/HiDPI
    retina = args.out / "128x128@2x.png"
    square.resize((256, 256), Image.LANCZOS).save(retina, "PNG", optimize=True)
    log(f"  {retina.name}: {retina.stat().st_size:,} байт")

    # Multi-resolution ICO (Windows)
    ico = args.out / "icon.ico"
    square.save(ico, format="ICO", sizes=ICO_SIZES)
    log(f"  {ico.name}: {ico.stat().st_size:,} байт (multi: {[s[0] for s in ICO_SIZES]})")

    # Multi-resolution ICNS (macOS)
    icns = args.out / "icon.icns"
    square.resize((1024, 1024), Image.LANCZOS).save(icns, format="ICNS", sizes=ICNS_SIZES)
    log(f"  {icns.name}: {icns.stat().st_size:,} байт (multi: {[s[0] for s in ICNS_SIZES]})")

    log("Готово. Запустите `npm run tauri:build` чтобы применить новые иконки.")


if __name__ == "__main__":
    main()
