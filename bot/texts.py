"""Все тексты бота. Хочешь поменять формулировку — правь здесь, логику трогать не нужно.

Разметка — HTML Telegram. Текст внутри <code> копируется нажатием.
"""

from __future__ import annotations

from config import Settings

INTRO = (
    "⚡ <b>Шлюз Ден.AI для Claude Code</b>\n\n"
    "Claude планирует и проверяет, а код пишут бесплатные модели. "
    "Лимит одной кончился — шлюз сам переключается на следующую.\n\n"
    "Кончился лимит Claude — команда <code>claude-free</code> запустит Claude Code на бесплатных моделях.\n\n"
    "Шлюз работает на твоём компьютере, ключи остаются там же."
)

CHOOSE_OS = "Какой у тебя компьютер? Нужен установленный Claude Code."

NOT_SUBSCRIBED = "Подписки пока нет. Подпишись на канал и нажми ещё раз."

UNKNOWN = "Нажми /start, чтобы получить команду установки. Если что-то сломалось — /help."

KEY_NOTE = (
    "<b>Какой ключ взять</b>\n"
    "Мастер начнёт с Gemini: вход через Google, карта не нужна. Из России и Беларуси Gemini "
    "работает только с VPN на весь компьютер, и при получении ключа, и во время работы.\n"
    "Запасной вариант — OpenRouter: 50 запросов в день. Это немного: одна задача агента "
    "может занять десятки запросов.\n\n"
    "Ключ вводится только в твоём терминале и хранится в файле на твоём компьютере. Бот его не видит."
)

_RUN_STEPS = (
    "3. Когда мастер спросит, нажми Enter: откроется сайт с ключом. Скопируй ключ и вставь в окно "
    "терминала. Символы на экране не видны, это нормально.\n"
    "4. Дождись надписи <b>ACCESS GRANTED</b>: обычно 2–3 минуты."
)


def gate(settings: Settings) -> str:
    return f"Шлюз открыт для подписчиков канала {settings.channel}. Подпишись и нажми «Проверить»."


def channel_url(settings: Settings) -> str:
    return f"https://t.me/{settings.channel.lstrip('@')}"


def install_command(os_name: str, settings: Settings) -> str:
    if os_name == "win":
        return f"irm {settings.raw_url}/install.ps1 | iex"
    return f"curl -fsSL {settings.raw_url}/install.sh | bash"


def script_url(os_name: str, settings: Settings) -> str:
    name = "install.ps1" if os_name == "win" else "install.sh"
    return f"{settings.repo_url}/blob/{settings.branch}/{name}"


def install(os_name: str, settings: Settings) -> str:
    command = f"<code>{install_command(os_name, settings)}</code>"
    head, open_terminal = {
        "mac": ("🍏 <b>Установка на Mac</b>", "1. Нажми ⌘ + Пробел, набери «Терминал», нажми Enter."),
        "win": ("🪟 <b>Установка на Windows</b>",
                "1. Нажми Пуск, набери «PowerShell», нажми Enter. Вставка в этом окне — правый клик."),
        "linux": ("🐧 <b>Установка на Linux</b>", "1. Открой терминал."),
    }[os_name]
    return f"{head}\n\n{open_terminal}\n2. Вставь команду и нажми Enter:\n{command}\n{_RUN_STEPS}\n\n{KEY_NOTE}"


USAGE = (
    "✅ <b>Как пользоваться</b>\n\n"
    "1. Открой новое окно терминала и запусти Claude Code в папке проекта.\n"
    "2. Поручи задачу:\n"
    "<code>/free напиши тесты для auth.py</code>\n\n"
    "Claude разобьёт задачу на шаги, отдаст код бесплатной модели и проверит результат. "
    "Бесплатная модель только правит файлы в этой папке: команды она не запускает.\n\n"
    "<b>Кончился лимит Claude</b>\n"
    "<code>claude-free</code>\n"
    "Внутри бесплатные модели, а не Claude. Качество ниже, проверяй результат.\n\n"
    "<b>Другие команды</b>\n"
    "<code>neurogate doctor</code> — проверить систему\n"
    "<code>neurogate add</code> — добавить ключ\n"
    "<code>neurogate update</code> — обновить список моделей\n\n"
    "⚠️ Бесплатные сервисы могут использовать запросы для обучения. "
    "Не запускай /free на коде клиентов и рядом с секретами.\n\n"
    "Шлюз основан на neurogate. Автор: Мансур, Basalt Code, канал @snglrai. "
    "Установщик и страницу ключей сделала команда NurTech."
)

HELP = (
    "🛟 <b>Если не работает</b>\n\n"
    "Сначала выполни:\n"
    "<code>neurogate doctor</code>\n"
    "Команда покажет проблему и как её исправить.\n\n"
    "• <code>neurogate: command not found</code> — открой новое окно терминала.\n"
    "• Ошибка 429 или модели молчат — кончились лимиты. Добавь ключ: <code>neurogate add</code>.\n"
    "• Gemini не отвечает — включи VPN на весь компьютер, а не только в браузере.\n"
    "• <code>/free</code> не появился — перезапусти Claude Code.\n\n"
    "Обновить шлюз: /update. Удалить: /remove.\n"
    "Не помогло — пришли вывод <code>neurogate doctor</code> в чат канала."
)

UPDATE = (
    "🔄 <b>Обновление</b>\n\n"
    "<code>neurogate update</code>\n\n"
    "Команда обновит код и список моделей. Ключи останутся."
)

REMOVE = (
    "🗑 <b>Удаление</b>\n\n"
    "<b>Mac</b>\n"
    "<code>launchctl unload ~/Library/LaunchAgents/dev.neurogate.plist; "
    "rm -rf ~/Library/LaunchAgents/dev.neurogate.plist ~/neurogate ~/.local/bin/neurogate "
    "~/.local/bin/claude-free ~/.claude/skills/free</code>\n\n"
    "<b>Linux</b>\n"
    "<code>systemctl --user disable --now neurogate; "
    "rm -rf ~/.config/systemd/user/neurogate.service ~/neurogate ~/.local/bin/neurogate "
    "~/.local/bin/claude-free ~/.claude/skills/free</code>\n\n"
    "<b>Windows</b>\n"
    "<code>Unregister-ScheduledTask -TaskName neurogate -Confirm:$false -EA 0; "
    "Get-NetTCPConnection -LocalPort 8765 -State Listen -EA 0 | % { Stop-Process -Id $_.OwningProcess -Force }; "
    "Remove-Item -Recurse -Force $HOME\\neurogate, $HOME\\.local\\bin\\neurogate*, "
    "$HOME\\.local\\bin\\claude-free*, $HOME\\.claude\\skills\\free</code>"
)


def stats(s: dict) -> str:
    sources = "\n".join(f"{name}: {count}" for name, count in s["sources"]) or "пока нет"
    os_line = ", ".join(f"{name} {s['os'].get(name, 0)}" for name in ("mac", "win", "linux"))
    return (
        "📊 <b>Воронка</b>\n\n"
        f"Старт: {s['start']}\n"
        f"Подписка: {s['subscribed']}\n"
        f"Команду получили: {s['command']} ({os_line})\n"
        f"Установили: {s['installed']}\n\n"
        f"<b>Источники</b>\n{sources}"
    )
