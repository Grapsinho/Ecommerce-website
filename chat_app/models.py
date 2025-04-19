from django.db import models
from django.conf import settings

from product_management.models import Product

User = settings.AUTH_USER_MODEL


class Chat(models.Model):
    """
    One persistent chat between a buyer and product owner.
    The 'product' field is updated if buyer starts chatting about a new product.
    """
    buyer = models.ForeignKey(
        User, related_name='chats_as_buyer', on_delete=models.CASCADE
    )
    owner = models.ForeignKey(
        User, related_name='chats_as_owner', on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product, related_name='chats', on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['buyer', 'owner'], name='unique_owner_buyer')
        ]
        indexes = [
            models.Index(fields=['buyer', 'owner']),
            models.Index(fields=['updated_at']),
        ]

    def __str__(self):
        return f"Chat {self.pk} between {self.buyer} and {self.owner}"


class Message(models.Model):
    """
    A chat message. 'is_read' toggles when recipient fetches messages.
    """
    chat = models.ForeignKey(
        Chat, related_name='messages', on_delete=models.CASCADE
    )
    sender = models.ForeignKey(
        User, related_name='sent_messages', on_delete=models.CASCADE
    )
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['chat', 'timestamp']),
            models.Index(fields=['chat', 'is_read']),
        ]

    def __str__(self):
        return f"Message {self.pk} in Chat {self.chat.pk}"