from django.contrib import admin
from .models import Order, OrderItem, ShippingMethod, Address

admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(ShippingMethod)
admin.site.register(Address)