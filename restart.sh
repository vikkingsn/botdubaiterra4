#!/bin/bash
cd /Users/aspbr/Documents/botdubaiterra4

echo "🛑 Останавливаем бота..."
pkill -f "python3 main.py" 2>/dev/null
sleep 2

echo "🧹 Очищаем кэш Python..."
find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

echo "🚀 Запускаем бота..."
python3 main.py
