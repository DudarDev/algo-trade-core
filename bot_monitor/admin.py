from django.contrib import admin
from .models import Trade, Wallet
from django.utils.html import format_html

@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    # Які колонки показувати в таблиці
    list_display = ('timestamp', 'symbol', 'colored_side', 'price', 'amount', 'colored_pnl')
    # Фільтри справа
    list_filter = ('symbol', 'side')
    # Пошук
    search_fields = ('symbol',)
    
    # Вимикаємо можливість додавати/видаляти угоди вручну (тільки перегляд)
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

    # Робимо "BUY" зеленим, "SELL" червоним/синім
    def colored_side(self, obj):
        color = 'blue' if obj.side == 'BUY' else 'orange'
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.side)
    colored_side.short_description = 'Тип'

    # Робимо PnL кольоровим
    def colored_pnl(self, obj):
        if obj.side == 'BUY': return "-"
        color = 'green' if obj.pnl > 0 else 'red'
        
        # --- ВИПРАВЛЕННЯ ---
        # Форматуємо число заздалегідь у f-строці
        pnl_text = f"{obj.pnl:.2f}%"
        
        # Передаємо вже готовий текст у format_html
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, pnl_text)
    colored_pnl.short_description = 'PnL (%)'

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('usdt_balance', 'status_display')
    
    def status_display(self, obj):
        return "Active"
    status_display.short_description = 'Статус'
    
    def has_add_permission(self, request):
        return False
