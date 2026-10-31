---
project: neurogate
public: true
type: fix
audience: users
title: Ключи в браузере скрыты, показать можно глазиком
summary: На странице neurogate add API-ключи и дополнительные данные больше не видны открытым текстом. Каждое поле можно показать и снова скрыть кнопкой с глазом.
user_impact:
  - Удобнее добавлять ключи при демонстрации экрана.
  - При переходе на другую вкладку открытые значения снова скрываются.
screenshots:
  - artifacts/browser-setup/keys-desktop.jpg
  - artifacts/browser-setup/keys-mobile.jpg
checks:
  - env -u CODEX_SANDBOX_NETWORK_DISABLED PYTHONPATH=src .venv/bin/python -m pytest -q tests/
  - node ../check-browser.cjs
  - git diff --check
deploy_url: https://neurogate.nurtech.dev
---

Notes for editor:
- What changed: Маскировка по умолчанию, отдельные подписи полей и доступные с клавиатуры переключатели. Глазик не отправляет ключ; кнопка «Подключить» сохраняет и дополнительные поля.
- Where to verify: После обновления локального NeuroGate открыть neurogate add, вставить ключ, показать/скрыть, сменить вкладку. Браузерный тест выполнен с вымышленными данными и проверил отправку дополнительных полей.
- Risks: Существующим установкам нужно обновить NeuroGate, чтобы получить новую локальную страницу. Глазик раскрывает значение по явному нажатию.
