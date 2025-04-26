from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime


@shared_task
def send_order_placed_email(order_id, user_email, user_name,
                            total_amount, method_display,
                            expected_date_iso):
    """
    expected_date_iso is an ISO-format string, e.g. '2025-04-26T22:00:00'
    We parse it here and then format for the user.
    """
    # Try to parse back into a datetime
    try:
        dt = datetime.fromisoformat(expected_date_iso)
        expected_display = dt.strftime('%Y-%m-%d %H:%M')
    except Exception:
        # If parsing fails, just show the raw string
        expected_display = expected_date_iso

    subject = f"Your order {order_id} has been placed"
    message = (
        f"Hello {user_name},\n"
        f"Your order {order_id} has been successfully placed.\n"
        f"Total: ${total_amount} via {method_display}.\n"
        f"Expected delivery by {expected_display}.\n"
    )
    send_mail(subject, message, settings.EMAIL_HOST_USER, [user_email])


@shared_task
def send_order_delivered_email(order_id, user_email, user_name):
    subject = f"Your order {order_id} has been delivered"
    message = (
        f"Hello {user_name},\n"
        f"Your order {order_id} has been delivered. Thank you for shopping!"
    )
    send_mail(subject, message, settings.EMAIL_HOST_USER, [user_email])