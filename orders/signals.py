import logging
from django.db import transaction
from django.dispatch import receiver
from django.db.models.signals import post_save

from .models import Order, ShippingMethod
from .tasks import send_order_placed_email, send_order_delivered_email

logger = logging.getLogger("rest_framework")

@receiver(post_save, sender=Order)
def on_order_created(sender, instance, created, **kwargs):
    if not created:
        return

    # Send placed email
    transaction.on_commit(lambda: send_order_placed_email.delay(
        str(instance.id),
        instance.user.email,
        instance.user.get_full_name(),
        float(instance.total_amount),
        instance.shipping_method.get_name_display(),
        instance.expected_delivery_date.isoformat(),
    ))

    # Schedule delivered email if not pickup
    if instance.shipping_method.name != ShippingMethod.PICKUP:
        transaction.on_commit(lambda: send_order_delivered_email.apply_async(
            args=[str(instance.id), instance.user.email, instance.user.get_full_name()],
            eta=instance.expected_delivery_date
        ))