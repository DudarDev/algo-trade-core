#!/usr/bin/env bash
# ==============================================================================
# 🌐 AlgoTrade PRO - Скрипт налаштування безкоштовного статичного домену DuckDNS
# Дозволяє отримати постійну адресу вигляду: https://YOUR-SUBDOMAIN.duckdns.org
# ==============================================================================

set -e

echo "=========================================================="
echo "🚀 Налаштування DuckDNS Static Hostname для AlgoTrade PRO"
echo "=========================================================="

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Використання: ./scripts/setup_duckdns.sh <SUBDOMAIN> <DUCKDNS_TOKEN>"
    echo ""
    echo "Приклад:"
    echo "  ./scripts/setup_duckdns.sh my-algo-bot a1b2c3d4-e5f6-7890-abcd-1234567890ef"
    echo ""
    echo "Як отримати безкоштовно:"
    echo "1. Зайдіть на https://www.duckdns.org (вхід через Google чи GitHub)"
    echo "2. Створіть собі домен (наприклад: 'my-algo-bot')"
    echo "3. Скопіюйте ваш 'Token' з головної сторінки DuckDNS"
    exit 1
fi

SUBDOMAIN="$1"
TOKEN="$2"
DUCK_DIR="$HOME/duckdns"

echo "📦 1. Створення директорії та скрипта оновлення IP..."
mkdir -p "$DUCK_DIR"
cat << EOF > "$DUCK_DIR/duck.sh"
#!/bin/bash
echo url="https://www.duckdns.org/update?domains=${SUBDOMAIN}&token=${TOKEN}&ip=" | curl -k -o "$DUCK_DIR/duck.log" -K -
EOF

chmod 700 "$DUCK_DIR/duck.sh"

echo "🔄 2. Первинний тестовий запуск оновлення IP..."
"$DUCK_DIR/duck.sh"
STATUS=$(cat "$DUCK_DIR/duck.log")
echo "Відповідь DuckDNS: $STATUS"

if [ "$STATUS" != "OK" ]; then
    echo "⚠️ Увага: DuckDNS повернув '$STATUS'. Перевірте правильність субдомену та токену."
fi

echo "⏰ 3. Додавання автооновлення IP у cron (кожні 5 хвилин)..."
(crontab -l 2>/dev/null | grep -v "duck.sh" ; echo "*/5 * * * * $DUCK_DIR/duck.sh >/dev/null 2>&1") | crontab -

echo ""
echo "🎉 Готово! Ваш статичний домен: http://${SUBDOMAIN}.duckdns.org:8000"
echo "Або через Nginx (порт 80): http://${SUBDOMAIN}.duckdns.org"
echo "=========================================================="
