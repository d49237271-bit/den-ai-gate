---
project: neurogate
public: true
type: feature
audience: students
title: NeuroGate можно настроить в браузере без Telegram
summary: Выберите компьютер и сервис на сайте, вставьте бесплатный ключ и скопируйте команду установки. Telegram-бот остаётся альтернативой.
user_impact:
  - Первая настройка проходит по обычной ссылке без переписки с ботом.
  - Ключ и одноразовая команда скрыты; для команды есть кнопка копирования.
screenshots:
  - artifacts/browser-setup/start-desktop.jpg
  - artifacts/browser-setup/start-mobile.jpg
  - artifacts/browser-setup/command-desktop.jpg
checks:
  - env -u CODEX_SANDBOX_NETWORK_DISABLED PYTHONPATH=src .venv/bin/python -m pytest -q tests/
  - node ../check-browser.cjs
  - git diff --check
deploy_url: https://neurogate.nurtech.dev/start
---

Notes for editor:
- What changed: На главной странице основной путь ведёт к браузерной настройке. Ключ проверяется и передаётся установщику в зашифрованном одноразовом пакете со сроком 24 часа. Ошибки формы объясняют следующий шаг; секреты не сохраняются в браузерное хранилище.
- Where to verify: /start, выбрать Mac или Windows, пройти форму и скопировать команду; мобильная ширина 390 px. Автотесты проверяют шифрование и однократное получение пакета, отклонение неверного ключа, ограничения запросов и запрет кэширования.
- Risks: Для установки всё ещё нужно выполнить одну команду на компьютере. Добавление ключей после установки работает через локальную страницу neurogate add. Если провайдер не позволяет проверить ключ, сайт явно предупреждает, что его работоспособность не подтверждена.
