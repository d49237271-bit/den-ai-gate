# Шлюз Ден.AI для Claude Code

Шлюз работает на твоём компьютере и подключает бесплатные нейросети по твоим ключам. Лимит одной
модели кончился — запрос уходит к следующей. Команду установки выдаёт бот канала [Ден.AI](https://t.me/den_ai_dev).

## Что появится

| Команда | Что делает |
|---|---|
| `/free <задача>` в Claude Code | Claude разбивает задачу, отдаёт код бесплатной модели, проверяет результат |
| `claude-free` | Claude Code на бесплатных моделях, когда лимит подписки кончился. Внутри не Claude |
| `neurogate add` | Добавить ключ на локальной странице |
| `neurogate doctor` | Проверить систему и подсказать исправление |
| `neurogate update` | Обновить код и список моделей. Ключи останутся |

## Что нужно знать до установки

- **Данные.** Бесплатные сервисы могут использовать запросы для обучения. Не запускай `/free` на коде
  клиентов и рядом с секретами. `/free` работает только когда ты его вызвал.
- **Качество.** Бесплатные модели слабее Claude. Поэтому проверяет результат Claude, а `claude-free`
  годится для простых задач.
- **Лимиты.** Одна задача агента занимает десятки запросов. На 50 запросах в день OpenRouter далеко
  не уедешь: добавь 2–3 ключа через `neurogate add`.
- **Россия и Беларусь.** Gemini работает только с VPN на весь компьютер, и при получении ключа, и во
  время работы. NVIDIA просит код на телефон, номеров +7 в списке нет.
- **Коммерция.** У части сервисов бесплатный тариф только для личного использования, например у Cohere
  и NVIDIA. Условия смотри на сайте сервиса.

## Границы исполнителя

Бесплатная модель работает через Claude Code с такими ограничениями:

- правит и читает файлы только в текущей папке;
- не запускает команды и не ходит в интернет;
- не читает `.env`, `.pem`, `.key`;
- не видит твои MCP-серверы.

Эти границы проверяет `tests/e2e/test_worker_boundaries.py` на настоящем Claude Code: смотрит, что
появилось на диске и что ушло провайдеру.

`neurogate delegate --shell` разрешает модели запускать команды без подтверждения: тесты, сборку.
Запрет на `curl`, `git push`, `sudo` и чтение `.env` остаётся, но это страховка, а не песочница.
Используй только в своём коде.

## Удаление

macOS:

```bash
launchctl unload ~/Library/LaunchAgents/dev.neurogate.plist
rm -rf ~/Library/LaunchAgents/dev.neurogate.plist ~/neurogate ~/.local/bin/neurogate ~/.local/bin/claude-free ~/.claude/skills/free
```

Linux:

```bash
systemctl --user disable --now neurogate
rm -rf ~/.config/systemd/user/neurogate.service ~/neurogate ~/.local/bin/neurogate ~/.local/bin/claude-free ~/.claude/skills/free
```

Windows (PowerShell):

```powershell
Unregister-ScheduledTask -TaskName neurogate -Confirm:$false -EA 0
Get-NetTCPConnection -LocalPort 8765 -State Listen -EA 0 | % { Stop-Process -Id $_.OwningProcess -Force }
Remove-Item -Recurse -Force $HOME\neurogate, $HOME\.local\bin\neurogate*, $HOME\.local\bin\claude-free*, $HOME\.claude\skills\free
```

## Откуда код

Шлюз, роутер и список моделей: [neurogate](https://github.com/basaltcode/neurogate), автор Мансур,
Basalt Code, лицензия MIT. Установщик и страница ключей: [форк NurTech](https://github.com/NurTechKSA/neurogate).
Этот форк добавил `/free`, `neurogate update`, границы исполнителя и защиту локального сервера от чужих сайтов.
