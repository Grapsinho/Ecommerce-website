import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils.dateparse import parse_datetime
from django.utils import timezone

logger = logging.getLogger("rest_framework")

@shared_task
def send_order_placed_email(
    order_id, user_email, user_name,
    total_amount, method_display,
    expected_date_iso
):
    try:
        dt = parse_datetime(expected_date_iso)
        if dt is not None and timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        expected_display = timezone.localtime(dt).strftime('%Y-%m-%d %H:%M')
    except Exception:
        expected_display = expected_date_iso

    subject = f"Your order {order_id} has been placed"
    message = (
        f"Hello {user_name},\n"
        f"Your order {order_id} has been successfully placed.\n"
        f"Total: ${total_amount} via {method_display}.\n"
        f"Expected delivery by {expected_display}.\n"
    )
    send_mail(subject, message, settings.EMAIL_HOST_USER, [user_email])
    logger.info(f"Sent 'placed' email for order {order_id}")

@shared_task
def send_order_delivered_email(order_id, user_email, user_name):
    subject = f"Your order {order_id} has been delivered"
    message = (
        f"Hello {user_name},\n"
        f"Your order {order_id} has been delivered. Thank you for shopping!"
    )
    send_mail(subject, message, settings.EMAIL_HOST_USER, [user_email])
    logger.info(f"Sent 'delivered' email for order {order_id}")
