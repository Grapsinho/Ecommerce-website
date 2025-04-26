from itertools import groupby
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from .models import Address, ShippingMethod, Order, OrderItem
from .signals import process_order_creation


class OrderService:
    @staticmethod
    @transaction.atomic
    def create_from_cart(user, shipping_method_id, addr_data=None):
        cart = user.cart
        # Lock cart items to prevent oversell
        items_qs = (
            cart.items
                .select_related('product', 'product__seller')
                .select_for_update()
                .order_by('product__seller__id')
        )
        if not items_qs.exists():
            raise ValueError('Cart is empty')

        try:
            shipping_method = ShippingMethod.objects.get(pk=shipping_method_id)
        except ShippingMethod.DoesNotExist:
            raise ValueError('Invalid shipping method')

        address = None
        if shipping_method.name in [ShippingMethod.CITY, ShippingMethod.REGIONAL]:
            if not addr_data:
                raise ValueError('Address data required')
            # Update existing or create single address
            address, _ = Address.objects.update_or_create(
                user=user,
                defaults={
                    'street': addr_data.get('street', ''),
                    'city': addr_data.get('city', ''),
                    'region': addr_data.get('region', ''),
                    'postal_code': addr_data.get('postal_code', ''),
                }
            )

        orders = []
        for seller, group in groupby(items_qs, key=lambda ci: ci.product.seller):
            order = Order.objects.create(
                user=user,
                shipping_method=shipping_method,
                shipping_address=address,
                shipping_fee=shipping_method.flat_fee,
                total_amount=0,
                status=Order.Status.PENDING,
                expected_delivery_date=timezone.now() + shipping_method.lead_time_min,
                progress_percentage=0,
            )
            items = []
            total = 0
            for ci in group:
                subtotal = ci.quantity * ci.unit_price
                items.append(
                    OrderItem(
                        order=order,
                        product=ci.product,
                        quantity=ci.quantity,
                        unit_price=ci.unit_price,
                        subtotal=subtotal,
                    )
                )
                total += subtotal

            OrderItem.objects.bulk_create(items)
            order.total_amount = total + shipping_method.flat_fee
            order.save(update_fields=['total_amount'])

            process_order_creation(order)
            orders.append(order)

        cart.items.all().delete()
        cart.recalc_total()

        return (
            Order.objects.filter(pk__in=[o.pk for o in orders])
            .select_related('shipping_method', 'shipping_address')
            .prefetch_related(
                'items',
                'items__product',
                'items__product__seller',
                'items__product__media'
            )
        )