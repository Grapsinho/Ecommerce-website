from itertools import groupby
from django.db import transaction
from django.db.models import F, Prefetch
from django.utils import timezone

from .models import Address, ShippingMethod, Order, OrderItem
from product_management.models import Product, ProductMedia

import logging
logger = logging.getLogger("rest_framework")

class OrderService:
    @staticmethod
    @transaction.atomic
    def create_from_cart(user, shipping_method_id, addr_data=None):
        shipping_method = ShippingMethod.objects.filter(pk=shipping_method_id).first()
        if not shipping_method:
            raise ValueError('Invalid shipping method')

        cart = user.cart
        items_qs = cart.items.select_for_update().select_related('product', 'product__seller').order_by('product__seller__id')
        items = list(items_qs)
        if not items:
            raise ValueError('Cart is empty')
        for ci in items:
            if ci.product.seller_id == user.id:
                raise ValueError("You cannot purchase your own product.")

        address = None
        if shipping_method.name in [ShippingMethod.CITY, ShippingMethod.REGIONAL]:
            if not addr_data:
                raise ValueError('Address data required')
            address, _ = Address.objects.update_or_create(
                user=user,
                defaults={
                    'street': addr_data.get('street', ''),
                    'city': addr_data.get('city', ''),
                    'region': addr_data.get('region', ''),
                    'postal_code': addr_data.get('postal_code', ''),
                }
            )

        # Determine expected delivery
        is_pickup = (shipping_method.name == ShippingMethod.PICKUP)
        now = timezone.now()
        expected_date = now if is_pickup else Order.calculate_expected_delivery(shipping_method)

        created_ids = []
        products_to_update = []

        for seller, group in groupby(items, key=lambda ci: ci.product.seller):
            order = Order.objects.create(
                user=user,
                shipping_method=shipping_method,
                shipping_address=address,
                shipping_fee=shipping_method.flat_fee,
                total_amount=0,
                expected_delivery_date=expected_date,
            )

            total = 0
            order_items = []
            for ci in group:
                prod = Product.objects.select_for_update().get(pk=ci.product_id)
                subtotal = ci.quantity * ci.unit_price
                order_items.append(OrderItem(
                    order=order,
                    product=prod,
                    quantity=ci.quantity,
                    unit_price=ci.unit_price,
                    subtotal=subtotal,
                ))
                total += subtotal
                prod.stock = F('stock') - ci.quantity
                prod.units_sold = F('units_sold') + ci.quantity
                products_to_update.append(prod)

            OrderItem.objects.bulk_create(order_items)
            order.total_amount = total + shipping_method.flat_fee
            order.save(update_fields=['total_amount'])
            created_ids.append(order.pk)

        Product.objects.bulk_update(products_to_update, ['stock', 'units_sold'])
        cart.items.all().delete()
        cart.recalc_total()

        return (
            Order.objects.filter(pk__in=created_ids)
                 .select_related('shipping_method', 'shipping_address')
                 .prefetch_related(
                     Prefetch('items', queryset=OrderItem.objects
                         .select_related('product', 'product__seller')
                         .prefetch_related(Prefetch('product__media', ProductMedia.objects.filter(is_feature=True), 'feature_media'))
                     )
                 )
                 .order_by('-created_at')
        )