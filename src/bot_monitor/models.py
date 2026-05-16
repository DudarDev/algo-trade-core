from django.db import models

class Trade(models.Model):
    id = models.AutoField(primary_key=True)
    symbol = models.CharField(max_length=20)
    side = models.CharField(max_length=10)
    price = models.FloatField()
    amount = models.FloatField()
    cost = models.FloatField()
    pnl = models.FloatField(default=0.0)
    timestamp = models.DateTimeField()

    class Meta:
        managed = False  
        db_table = 'trades'  
        verbose_name = 'Угода'
        verbose_name_plural = 'Угоди'

    def __str__(self) -> str:
        return f"{self.side} {self.amount} {self.symbol} @ {self.price}"


class Wallet(models.Model):
    id = models.AutoField(primary_key=True)
    usdt_balance = models.FloatField()

    class Meta:
        managed = False
        db_table = 'wallet'
        verbose_name = 'Гаманець'
        verbose_name_plural = 'Гаманці'

    def __str__(self) -> str:
        return f"Баланс: {self.usdt_balance} USDT"


class ActivePosition(models.Model):
    symbol = models.CharField(max_length=20, primary_key=True)
    amount = models.FloatField()
    entry_price = models.FloatField()
    highest_price = models.FloatField()
    cost = models.FloatField()
    opened_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'active_positions'
        verbose_name = 'Активна позиція'
        verbose_name_plural = 'Активні позиції'

    def __str__(self) -> str:
        return f"Позиція {self.symbol} (Вхід: {self.entry_price})"


class BotConfig(models.Model):
    """
    Таблиця для керування станом бота (Singleton). 
    Django виступає 'майстром', тому managed = True.
    """
    id = models.AutoField(primary_key=True)
    status = models.CharField(max_length=20, default='stopped') 
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = True
        db_table = 'bot_config'
        verbose_name = 'Конфігурація бота'

    def __str__(self) -> str:
        return f"Bot Status: {self.status}"