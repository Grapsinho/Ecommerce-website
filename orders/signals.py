from django.db import transaction
from django.db.models import F
from django.dispatch import receiver
from django.db.models.signals import post_save

from .models import Order, OrderStatusHistory
from product_management.models import Product
from .tasks import send_order_placed_email, send_order_delivered_email


def process_order_creation(order):
    updates = {}
    for item in order.items.all():
        updates.setdefault(item.product_id, 0)
        updates[item.product_id] += item.quantity

    for pid, qty in updates.items():
        Product.objects.filter(pk=pid).update(
            stock=F('stock') - qty,
            units_sold=F('units_sold') + qty
        )

    OrderStatusHistory.objects.create(order=order, status=order.status)

    def _send():
        send_order_placed_email.delay(
            str(order.id),
            order.user.email,
            order.user.full_username,
            float(order.total_amount),
            order.shipping_method.get_name_display(),
            order.expected_delivery_date.isoformat(),
        )

    transaction.on_commit(_send)


@receiver(post_save, sender=Order)
def handle_order_status_change(sender, instance, created, **kwargs):
    """
    On any Order.save():
      - If created: record initial history + send “placed” email.
      - If status changed: record new history, update progress_percentage,
        and if delivered send “delivered” email.
    """
    # Fetch the last history entry (if any)
    last = (
        OrderStatusHistory.objects
        .filter(order=instance)
        .order_by('-timestamp')
        .first()
    )

    # 1) Create history on creation or status-change
    if created or (last and last.status != instance.status):
        OrderStatusHistory.objects.create(order=instance, status=instance.status)

    # 2) On creation: send “order placed” email via Celery
    if created:
        transaction.on_commit(lambda: send_order_placed_email.delay(
            str(instance.id),
            instance.user.email,
            instance.user.full_username,
            float(instance.total_amount),
            instance.shipping_method.get_name_display(),
            instance.expected_delivery_date.isoformat(),
        ))

    # 3) On status change: update progress and possibly send “delivered” email
    if not created and last and last.status != instance.status:
        pct_map = {
            Order.Status.PENDING:    0,
            Order.Status.PROCESSING: 33,
            Order.Status.SHIPPED:    66,
            Order.Status.DELIVERED:  100,
        }
        new_pct = pct_map.get(instance.status, 0)
        Order.objects.filter(pk=instance.pk).update(progress_percentage=new_pct)

        if instance.status == Order.Status.DELIVERED:
            transaction.on_commit(lambda: send_order_delivered_email.delay(
                str(instance.id),
                instance.user.email,
                instance.user.full_username,
            ))