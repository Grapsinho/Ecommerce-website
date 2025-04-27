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
        logger.info(
            f"Starting checkout for user {user.id} "
            f"with shipping_method {shipping_method_id}"
        )
        cart = user.cart

        # 1) Lock & fetch cart items
        items_qs = (
            cart.items
                .select_for_update()
                .select_related('product', 'product__seller')
                .order_by('product__seller__id')
        )
        items = list(items_qs)
        if not items:
            raise ValueError('Cart is empty')
        logger.debug(f"Cart items: {[{'prod': ci.product_id, 'qty': ci.quantity} for ci in items]}")

        for ci in items:
            if ci.product.seller_id == user.id:
                raise ValueError("You cannot purchase your own product.")

        # 2) Validate shipping_method & address
        shipping_method = ShippingMethod.objects.filter(pk=shipping_method_id).first()
        if not shipping_method:
            raise ValueError('Invalid shipping method')

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

        # 3) Lock products + stock check
        product_ids = [ci.product_id for ci in items]
        products = Product.objects.select_for_update().in_bulk(product_ids)
        for ci in items:
            prod = products[ci.product_id]
            if ci.quantity > prod.stock:
                raise ValueError(f'Not enough stock for {prod.name}')

        # 4) Clear cart
        cart.items.all().delete()
        cart.recalc_total()
        logger.info(f"Cleared cart for user {user.id}")

        created_ids = []
        products_to_update = []

        # 5) Create orders & items
        for seller, group in groupby(items, key=lambda ci: ci.product.seller):
            logger.debug(f"Creating order for seller {seller.id}")
            is_pickup = (shipping_method.name == ShippingMethod.PICKUP)

            order = Order.objects.create(
                user=user,
                shipping_method=shipping_method,
                shipping_address=address,
                shipping_fee=shipping_method.flat_fee,
                total_amount=0,  # placeholder
                status=(
                    Order.Status.DELIVERED  # treat pickup as “delivered”
                    if is_pickup else
                    Order.Status.PENDING
                ),
                expected_delivery_date=(
                    timezone.now()  # immediate
                    if is_pickup else
                    Order.calculate_expected_delivery(shipping_method)
                ),
                progress_percentage=100 if is_pickup else 0,
            )

            total = 0
            order_items = []
            for ci in group:
                prod = products[ci.product_id]
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

        # 6) Bulk-update all product stock changes
        Product.objects.bulk_update(products_to_update, ['stock', 'units_sold'])
        logger.info(f"Adjusted stock for products: {[p.pk for p in products_to_update]}")

        # 7) Return fresh QS
        return (
            Order.objects
                 .filter(pk__in=created_ids)
                 .select_related('shipping_method', 'shipping_address')
                 .prefetch_related(
                     Prefetch(
                         'items',
                         queryset=OrderItem.objects
                             .select_related('product', 'product__seller')
                             .prefetch_related(
                                 Prefetch(
                                     'product__media',
                                     ProductMedia.objects.filter(is_feature=True),
                                     to_attr='feature_media'
                                 )
                             ),
                     ),
                 )
                 .order_by('-created_at')
        )
