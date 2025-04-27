import logging
from django.db import transaction
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_save

from .models import Order, OrderStatusHistory
from .tasks import (
    send_order_placed_email,
    send_order_delivered_email
)

logger = logging.getLogger("rest_framework")

@receiver(pre_save, sender=Order)
def cache_old_status(sender, instance, **kwargs):
    """
    Before saving, stash the current status on the instance for comparison.
    """
    if instance.pk:
        try:
            # Fetch only the status field for efficiency
            instance._old_status = sender.objects.values_list('status', flat=True).get(pk=instance.pk)
        except sender.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Order)
def handle_order_status_change(sender, instance, created, **kwargs):
    """
    Only run when the Order is first created or its status actually changes.
    """
    old = getattr(instance, '_old_status', None)
    new = instance.status

    # 1) Record history on create or real status-change
    if created or old != new:
        OrderStatusHistory.objects.create(order=instance, status=new)
        logger.info(f"Order {instance.id} history recorded: {old!r} → {new!r}")

    # 2) On creation → enqueue "placed" email
    if created:
        transaction.on_commit(lambda: send_order_placed_email.delay(
            str(instance.id),
            instance.user.email,
            instance.user.full_username,
            float(instance.total_amount),
            instance.shipping_method.get_name_display(),
            instance.expected_delivery_date.isoformat(),
        ))
        logger.info(f"Enqueued placed email for order {instance.id}")

    # 3) On *real* status-change to DELIVERED → enqueue "delivered" email
    if not created and old != new and new == Order.Status.DELIVERED:
        transaction.on_commit(lambda: send_order_delivered_email.delay(
            str(instance.id),
            instance.user.email,
            instance.user.full_username,
        ))
        logger.info(f"Enqueued delivered email for order {instance.id}")
