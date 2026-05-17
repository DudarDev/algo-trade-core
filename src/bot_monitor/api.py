from ninja import Router

router = Router()

# Роути для керування ботом та статусу ми вже перенесли у views.py
# Цей файл залишаємо для майбутніх API-ендпоінтів

@router.get("/ping")
def ping(request):
    return {"status": "ok"}