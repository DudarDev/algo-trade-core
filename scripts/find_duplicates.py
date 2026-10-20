import os
import hashlib


def hash_file(filename):
    """Рахує унікальний 'відбиток' файлу (MD5)"""
    h = hashlib.md5()
    try:
        with open(filename, "rb") as file:
            chunk = 0
            while chunk != b"":
                chunk = file.read(1024)
                h.update(chunk)
        return h.hexdigest()
    except IsADirectoryError:
        return None


def find_dupes(start_path="."):
    print(f"🔍 Сканую проект в '{start_path}' на наявність клонів...\n")

    # Словник: {hash: [список_шляхів]}
    hashes = {}

    for root, dirs, files in os.walk(start_path):
        # Ігноруємо системні папки
        if (
            ".git" in root
            or "__pycache__" in root
            or "venv" in root
            or ".ipynb_checkpoints" in root
        ):
            continue

        for filename in files:
            # Шукаємо тільки Python файли (можна прибрати перевірку, щоб шукати все)
            if not filename.endswith(".py"):
                continue

            full_path = os.path.join(root, filename)

            file_hash = hash_file(full_path)
            if file_hash:
                if file_hash in hashes:
                    hashes[file_hash].append(full_path)
                else:
                    hashes[file_hash] = [full_path]

    # Виводимо результати
    duplicates_found = False
    for h, paths in hashes.items():
        if len(paths) > 1:
            duplicates_found = True
            print(f"⚠️ Знайдено {len(paths)} однакових файлів:")
            for p in paths:
                print(f"   📄 {p}")
            print("-" * 40)

    if not duplicates_found:
        print("✅ Дублікатів не знайдено. Все чисто!")


if __name__ == "__main__":
    # Запускаємо пошук від поточної папки
    find_dupes(".")
