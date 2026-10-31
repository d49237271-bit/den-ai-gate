---
project: neurogate
public: true
type: feature
audience: students
title: Видеоинструкция NeuroGate прямо на сайте
summary: На главной странице можно посмотреть полный показ настройки NeuroGate, развернуть видео и перемотать к нужному месту.
user_impact:
  - Инструкция на 6 минут 47 секунд доступна без скачивания исходного файла.
  - Версия для сайта занимает 43 МБ вместо 440 МБ и сохраняет разрешение 1080p.
screenshots:
  - artifacts/browser-setup/home-desktop.jpg
  - artifacts/browser-setup/home-mobile.jpg
checks:
  - env -u CODEX_SANDBOX_NETWORK_DISABLED PYTHONPATH=src .venv/bin/python -m pytest -q tests/
  - node ../check-browser.cjs
  - ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height work/media/neurogate-tutorial.mp4
deploy_url: https://neurogate.nurtech.dev/#video
---

Notes for editor:
- What changed: Обычный видеоплеер без автозапуска, обложка и ссылка для отдельного открытия MP4. Поддержаны Range-запросы для перемотки. Полный API-ключ, попавший в запись, закрыт в опубликованной версии.
- Where to verify: Главная страница → «Как пользоваться NeuroGate»; начать воспроизведение и перемотать. Видео показывает путь через Telegram; рядом пояснено, что теперь настройка доступна и в браузере.
- Risks: Медиа хранится в постоянном томе бота /data/media, отдельно от Git и образа. При переносе сервиса нужно перенести файлы; подробности в docs/browser-setup.md.
