import os
import py_compile
import sys
import re

def scan_project():
    print("🩺 ЗАПУСК РОЗШИРЕНОЇ ДІАГНОСТИКИ ПРОЕКТУ...\n" + "="*50)
    error_count = 0
    scanned_files = 0

    print("1️⃣ ПЕРЕВІРКА СИНТАКСИСУ (Python Files)...")
    for root, dirs, files in os.walk('.'):
        if any(skip in root for skip in ['.git', '__pycache__', 'venv', 'env', '.pytest_cache', 'data']):
            continue

        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                scanned_files += 1
                try:
                    py_compile.compile(filepath, doraise=True)
                except Exception as e:
                    print(f"   ❌ ПОМИЛКА СИНТАКСИСУ: {filepath} -> {e}")
                    error_count += 1
    if error_count == 0:
        print(f"   ✅ Перевірено {scanned_files} файлів. Синтаксис ідеальний.\n")

    print("2️⃣ ПЕРЕВІРКА КРИТИЧНИХ ФАЙЛІВ...")
    critical_files = ['.env', 'requirements.txt', 'docker-compose.yml', 'Dockerfile']
    for cf in critical_files:
        if os.path.exists(cf):
            print(f"   ✅ Файл {cf} знайдено.")
        else:
            print(f"   ⚠️ ПОПЕРЕДЖЕННЯ: Файл {cf} відсутній! (Без нього Docker може не зібратися)")
    print("")

    print("3️⃣ ПЕРЕВІРКА БАЗИ ДАНИХ (Синхронізація Django та Бота)...")
    bot_db = None
    django_db = None

    if os.path.exists('app/config.py'):
        with open('app/config.py', 'r', encoding='utf-8') as f:
            match = re.search(r'sqlite:///(.+?\.db)', f.read())
            if match: bot_db = match.group(1)

    if os.path.exists('web_panel/settings.py'):
        with open('web_panel/settings.py', 'r', encoding='utf-8') as f:
            match = re.search(r"'NAME':\s*['\"](.+?\.db)['\"]", f.read())
            if match: django_db = match.group(1)

    print(f"   Бот (config.py) шукає базу тут:    {bot_db if bot_db else 'Не знайдено'}")
    print(f"   Django (settings.py) шукає базу:   {django_db if django_db else 'Не знайдено'}")

    if bot_db and django_db:
        bot_db_name = os.path.basename(bot_db)
        django_db_name = os.path.basename(django_db)
        if bot_db_name == django_db_name:
            print("   ✅ БАЗИ ДАНИХ СИНХРОНІЗОВАНІ!")
        else:
            print("   ❌ РОЗСИНХРОН БАЗ ДАНИХ! Бот і веб-панель дивляться в різні файли.")
            error_count += 1

    print("=" * 50)
    if error_count == 0:
        print("🚀 ПРОЕКТ ЗДОРОВИЙ! Можна розгортати на сервері.")
    else:
        print(f"🔥 Знайдено проблем: {error_count}. Виправте перед деплоєм.")
        sys.exit(1)

if __name__ == "__main__":
    scan_project()