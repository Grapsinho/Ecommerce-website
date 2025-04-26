from itertools import groupby
from django.db import transaction
from django.db.models import Prefetch, F
from django.utils import timezone
from .models import Address, ShippingMethod, Order, OrderItem
from product_management.models import Product, ProductMedia

class OrderService:
    @staticmethod
    @transaction.atomic
    def create_from_cart(user, shipping_method_id, addr_data=None):
        cart = user.cart
        items_qs = (
            cart.items
                .select_for_update()
                .select_related('product', 'product__seller')
                .order_by('product__seller__id')
        )
        if not items_qs.exists():
            raise ValueError('Cart is empty')

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
                    'street':      addr_data.get('street', ''),
                    'city':        addr_data.get('city', ''),
                    'region':      addr_data.get('region', ''),
                    'postal_code': addr_data.get('postal_code', ''),
                }
            )

        # Lock and check stock on each Product
        product_ids = [ci.product_id for ci in items_qs]
        products = (
            Product.objects
                   .select_for_update()
                   .in_bulk(product_ids)
        )
        for ci in items_qs:
            prod = products[ci.product_id]
            if ci.quantity > prod.stock:
                raise ValueError(f'Not enough stock for {prod.name}')

        created_ids = []
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

            total = 0
            items = []
            for ci in group:
                prod = products[ci.product_id]
                subtotal = ci.quantity * ci.unit_price
                items.append(
                    OrderItem(
                        order=order,
                        product=prod,
                        quantity=ci.quantity,
                        unit_price=ci.unit_price,
                        subtotal=subtotal,
                    )
                )
                total += subtotal

                # adjust stock and units_sold
                prod.stock      = F('stock') - ci.quantity
                prod.units_sold = F('units_sold') + ci.quantity
                prod.save(update_fields=['stock', 'units_sold'])

            OrderItem.objects.bulk_create(items)
            order.total_amount = total + shipping_method.flat_fee
            order.save(update_fields=['total_amount'])

            # trigger stock updates & email (history is in signals now)
            from .signals import process_order_creation
            process_order_creation(order)

            created_ids.append(order.pk)

        cart.items.all().delete()
        cart.recalc_total()

        # return a fresh QuerySet (not a list) with featured-media prefetched
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
                                     queryset=ProductMedia.objects.filter(is_feature=True),
                                     to_attr='feature_media'
                                 )
                             ),
                         to_attr='prefetched_items'
                     )
                 )
        )