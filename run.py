#!/usr/bin/env python3
"""
Скрипт для запуска Telegram Music Bot
"""

import sys
import os
from bot import MusicBot

def main():
    """Основная функция запуска"""
    print("🎵 Запуск Telegram Music Bot...")
    print("📁 Рабочая директория:", os.getcwd())
    
    # Проверяем настройку токена
    from config import TELEGRAM_BOT_TOKEN
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Токен бота не настроен!")
        print("📝 Отредактируйте config.py и замените YOUR_BOT_TOKEN_HERE на ваш токен")
        return
    
    try:
        bot = MusicBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
