from django.db import models

class Trade(models.Model):
    """
    Історія виконаних угод.
    Таблиця наповнюється торговим ядром (algo_engine), тому managed = False.
    """
    id = models.AutoField(primary_key=True)
    symbol = models.CharField(max_length=20, help_text="Торгова пара, наприклад STRAX/USDT")
    side = models.CharField(max_length=10, help_text="Напрямок: BUY або SELL")
    
    # TODO (Tech Debt): Здійснити міграцію на DecimalField для уникнення проблем з float rounding
    price = models.FloatField(help_text="Ціна виконання ордера")
    amount = models.FloatField(help_text="Кількість куплених/проданих монет")
    cost = models.FloatField(help_text="Об'єм інвестиції в базовій валюті (USDT)")
    pnl = models.FloatField(default=0.0, help_text="Чистий прибуток/збиток в базовій валюті (USDT)")
    exit_reason = models.CharField(max_length=50, default="UNKNOWN", blank=True, help_text="Причина закриття (TP, SL, Trailing, Panic)")
    regime = models.CharField(max_length=30, default="CHOPPY_FLAT", blank=True, help_text="Ринковий режим на момент входу")
    ai_confidence = models.FloatField(default=0.0, help_text="Впевненість ШІ моделі при вході")
    target_label = models.IntegerField(default=0, help_text="1 = Win (TP), 0 = Loss (SL)")
    features_json = models.TextField(default="{}", blank=True, help_text="Зріз усіх квант-індикаторів на момент відкриття")
    timestamp = models.DateTimeField(help_text="Час виконання угоди")

    class Meta:
        managed = False  
        db_table = 'trades'  
        verbose_name = 'Угода'
        verbose_name_plural = 'Угоди'

    def __str__(self) -> str:
        return f"{self.side} {self.amount} {self.symbol} @ {self.price}"


class Wallet(models.Model):
    """
    Поточний стан гаманця. 
    Відображає виключно вільний баланс (кеш), не враховуючи кошти у відкритих позиціях.
    """
    id = models.AutoField(primary_key=True)
    usdt_balance = models.FloatField(help_text="Вільний залишок USDT доступний для торгівлі")

    class Meta:
        managed = False
        db_table = 'wallet'
        verbose_name = 'Гаманець'
        verbose_name_plural = 'Гаманці'

    def __str__(self) -> str:
        return f"Вільний баланс: {self.usdt_balance:.2f} USDT"


class ActivePosition(models.Model):
    """
    Реєстр поточних відкритих позицій алгоритму.
    Тут зберігаються "заморожені" кошти (cost).
    """
    symbol = models.CharField(max_length=20, primary_key=True, help_text="Торгова пара (унікальний ідентифікатор позиції)")
    amount = models.FloatField(help_text="Кількість монет в утриманні")
    entry_price = models.FloatField(help_text="Середня ціна входу")
    highest_price = models.FloatField(help_text="Максимально досягнута ціна (використовується для Trailing Stop)")
    cost = models.FloatField(help_text="Сума вкладених USDT (заморожений баланс)")
    regime = models.CharField(max_length=30, default="CHOPPY_FLAT", blank=True, help_text="Ринковий режим на момент входу")
    ai_confidence = models.FloatField(default=0.0, help_text="Впевненість ШІ моделі при вході")
    features_json = models.TextField(default="{}", blank=True, help_text="Зріз усіх квант-індикаторів на момент відкриття")
    opened_at = models.DateTimeField(help_text="Час відкриття позиції")

    class Meta:
        managed = False
        db_table = 'active_positions'
        verbose_name = 'Активна позиція'
        verbose_name_plural = 'Активні позиції'

    def __str__(self) -> str:
        return f"Позиція {self.symbol} | Вхід: {self.entry_price} | Інвестиція: {self.cost} USDT"


class BotConfig(models.Model):
    """
    Таблиця для керування станом бота (Singleton патерн). 
    Django виступає 'майстром', тому managed = True.
    """
    id = models.AutoField(primary_key=True)
    status = models.CharField(
        max_length=20, 
        default='stopped',
        help_text="Поточний статус системи (running, stopped, error)"
    ) 
    updated_at = models.DateTimeField(auto_now=True, help_text="Час останньої зміни статусу")

    class Meta:
        managed = True
        db_table = 'bot_config'
        verbose_name = 'Конфігурація бота'
        verbose_name_plural = 'Конфігурації бота'

    def __str__(self) -> str:
        return f"System Status: {self.status.upper()}"