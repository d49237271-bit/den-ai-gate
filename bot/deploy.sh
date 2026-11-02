#!/usr/bin/env bash
# Установка и обновление бота на VPS (Ubuntu). Запускать на сервере:
#   curl -fsSL https://raw.githubusercontent.com/d49237271-bit/den-ai-gate/stable/bot/deploy.sh | bash
# Повторный запуск обновляет код и перезапускает бота. Токен и база остаются.
set -euo pipefail

REPO="${DEN_REPO:-d49237271-bit/den-ai-gate}"
BRANCH="${DEN_BRANCH:-stable}"
DIR="${DEN_DIR:-/opt/den-ai-gate}"
UNIT=den-ai-gate-bot
SUDO=""
[ "$(id -u)" -eq 0 ] || SUDO=sudo

$SUDO apt-get install -y -qq git python3-venv >/dev/null

if [ -d "$DIR/.git" ]; then
  $SUDO git -C "$DIR" pull -q --ff-only
else
  $SUDO git clone -q --depth 1 --branch "$BRANCH" "https://github.com/$REPO.git" "$DIR"
fi

cd "$DIR/bot"
[ -d .venv ] || $SUDO python3 -m venv .venv
$SUDO .venv/bin/pip install -q -r requirements.txt

if ! $SUDO test -f .env; then
  # Токен читаем скрыто и сразу в файл с правами 600: в истории команд его не будет
  read -rsp "Токен бота от @BotFather: " token </dev/tty
  echo
  case "$token" in
    *[!A-Za-z0-9:_-]*|"") echo "Это не похоже на токен бота"; exit 1 ;;
  esac
  sed -e "s|^BOT_TOKEN=.*|BOT_TOKEN=$token|" -e "s|^GITHUB_REPO=.*|GITHUB_REPO=$REPO|" -e "s|^GITHUB_BRANCH=.*|GITHUB_BRANCH=$BRANCH|" .env.example \
    | $SUDO sh -c 'umask 077; cat > .env'
fi

$SUDO cp "$UNIT.service" "/etc/systemd/system/$UNIT.service"
$SUDO systemctl daemon-reload
$SUDO systemctl enable -q "$UNIT"
$SUDO systemctl restart "$UNIT"
sleep 3
$SUDO systemctl is-active "$UNIT"
$SUDO journalctl -u "$UNIT" -n 8 --no-pager
