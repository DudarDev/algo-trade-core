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
        ordering = ['-timestamp']
        verbose_name = 'Торгова Операція'
        verbose_name_plural = 'Історія Угод'

    def __str__(self):
        return f"{self.timestamp} - {self.side} {self.symbol}"

class Wallet(models.Model):
    id = models.AutoField(primary_key=True)
    usdt_balance = models.FloatField()

    class Meta:
        managed = False
        db_table = 'wallet'
        verbose_name = 'Баланс Гаманця'
        verbose_name_plural = 'Баланс'

    def __str__(self):
        return f"Баланс: {self.usdt_balance} USDT"
