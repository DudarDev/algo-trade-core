import os
import sys
from pathlib import Path

# Додаємо корінь проєкту в PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'src.web_panel.settings')
import django
django.setup()
