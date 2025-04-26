from django.db import transaction
from django.db.models import F
from django.dispatch import receiver
from django.db.models.signals import post_save

from .models import Order, OrderStatusHistory
from product_management.models import Product
from django.core.mail import send_mail
from django.conf import settings


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
        expected = order.expected_delivery_date
        subject = f"Your order {order.id} has been placed"
        message = (
            f"Hello {order.user.full_username},\n"
            f"Your order {order.id} has been successfully placed.\n"
            f"Total: ${order.total_amount} via {order.shipping_method.get_name_display()}.\n"
            f"Expected delivery by {expected:%Y-%m-%d %H:%M}.\n"
        )
        from_email = settings.EMAIL_HOST_USER
        send_mail(subject, message, from_email, [order.user.email], fail_silently=False)

    transaction.on_commit(_send)


@receiver(post_save, sender=Order)
@transaction.atomic
def handle_order_status_change(sender, instance, created, **kwargs):
    if created:
        return

    last = OrderStatusHistory.objects.filter(order=instance).order_by('-timestamp').first()
    if last and last.status == instance.status:
        return

    OrderStatusHistory.objects.create(order=instance, status=instance.status)

    pct_map = {
        Order.Status.PENDING: 0,
        Order.Status.PROCESSING: 33,
        Order.Status.SHIPPED: 66,
        Order.Status.DELIVERED: 100,
    }
    new_pct = pct_map.get(instance.status, 0)
    Order.objects.filter(pk=instance.pk).update(progress_percentage=new_pct)

    if instance.status == Order.Status.DELIVERED:
        subject = f"Your order {instance.id} has been delivered"
        message = (
            f"Hello {instance.user.full_username},\n"
            f"Your order {instance.id} has been delivered. Thank you for shopping!"
        )
        from_email = settings.EMAIL_HOST_USER
        transaction.on_commit(lambda: send_mail(subject, message, from_email, [instance.user.email], fail_silently=False))
