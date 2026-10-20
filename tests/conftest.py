import os
import sys
from pathlib import Path

# Корінь проєкту
ROOT_DIR = Path(__file__).resolve().parent.parent
# Додаємо src, щоб Django знайшов bot_monitor, shared тощо
sys.path.insert(0, str(ROOT_DIR / "src"))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_panel.settings')
import django
django.setup()
