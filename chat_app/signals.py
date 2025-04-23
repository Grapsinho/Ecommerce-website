from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Message, Chat

@receiver(post_save, sender=Message)
def update_chat_denorm_fields(sender, instance, created, **kwargs):
    if not created:
        return
    # atomically bump both updated_at and last_message
    Chat.objects.filter(pk=instance.chat_id).update(
        updated_at=instance.timestamp or timezone.now(),
        last_message_id=instance.id
    )