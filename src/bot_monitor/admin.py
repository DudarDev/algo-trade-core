from typing import Any, Optional

from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html

# Імпортуємо наші дзеркальні моделі з shared додатку
from shared.db.models import ActivePosition, Trade, Wallet


class ReadOnlyAdmin(admin.ModelAdmin):
    """
    Базовий абстрактний клас для Read-Only моделей.
    Блокує будь-які спроби зміни даних через Django Admin.
    """
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Optional[Any] = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Optional[Any] = None) -> bool:
        return False


#@admin.register(Trade)
#class TradeAdmin(ReadOnlyAdmin):
    list_display = (
        'timestamp', 
        'symbol', 
        'colored_side', 
        'price', 
        'amount', 
        'colored_pnl'
    )
    list_filter = ('symbol', 'side')
    search_fields = ('symbol',)
    
    # Оптимізація: пагінація та сортування (нові зверху)
    list_per_page = 50
    ordering = ('-timestamp',)

    @admin.display(description='Тип')
    def colored_side(self, obj: Trade) -> str:
        if not obj.side:
            return "-"
            
        side_upper = obj.side.upper()
        color = 'blue' if side_upper == 'BUY' else 'orange'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>', 
            color, 
            side_upper
        )

    @admin.display(description='PnL (%)')
    def colored_pnl(self, obj: Trade) -> str:
        if not obj.side or obj.side.upper() == 'BUY':
            return "-"
            
        # Захист від None (якщо в БД пусто)
        pnl_value = obj.pnl or 0.0
        color = 'green' if pnl_value > 0 else 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f}%</span>', 
            color, 
            pnl_value
        )


#@admin.register(Wallet)
#class WalletAdmin(ReadOnlyAdmin):
    list_display = ('id', 'formatted_balance', 'status_display')
    
    @admin.display(description='Баланс (USDT)')
    def formatted_balance(self, obj: Wallet) -> str:
        balance = obj.usdt_balance or 0.0
        return f"{balance:.2f} USDT"

    @admin.display(description='Статус')
    def status_display(self, obj: Wallet) -> str:
        return format_html('<span style="color: green; font-weight: bold;">Active</span>')


#@admin.register(ActivePosition)
#class ActivePositionAdmin(ReadOnlyAdmin):
    list_display = (
        'symbol', 
        'amount', 
        'entry_price', 
        'highest_price', 
        'cost', 
        'opened_at'
    )
    search_fields = ('symbol',)
    list_filter = ('symbol',)
    
    list_per_page = 50
    ordering = ('-opened_at',)