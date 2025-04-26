from django.contrib import admin
from .models import Order, OrderItem, OrderStatusHistory, ShippingMethod, Address

admin.site.register(OrderStatusHistory)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(ShippingMethod)
admin.site.register(Address)