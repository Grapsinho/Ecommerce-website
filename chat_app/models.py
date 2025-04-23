from django.db import models
from django.db.models import F
from django.conf import settings
import uuid
from product_management.models import Product

User = settings.AUTH_USER_MODEL


class Chat(models.Model):
    """
    One persistent chat between a buyer and product owner.
    The 'product' field is updated if buyer starts chatting about a new product.
    """

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
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

    last_message = models.ForeignKey(
        'Message',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Denormalized pointer to the last Message in this chat"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['buyer', 'owner'], name='unique_owner_buyer')
        ]
        indexes = [
            models.Index(fields=['buyer', 'owner']),
            models.Index(fields=['updated_at']),
            models.Index(fields=['last_message']),
        ]

    def get_other_user(self, user):
        return self.owner if self.buyer == user else self.buyer

    def __str__(self):
        return f"Chat {self.id} between {self.buyer} and {self.owner}"


class Message(models.Model):
    """
    A chat message. 'is_read' toggles when recipient fetches messages.
    Overrides save() to bump Chat denorm fields.
    """

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
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
        ordering = ['-timestamp']  # default newest-first
        indexes = [
            models.Index(fields=['chat', 'timestamp']),
            models.Index(fields=['chat', 'is_read']),
            models.Index(
                fields=['chat', 'is_read', 'timestamp'],
                name='msg_chat_isread_ts_idx'
            ),
        ]

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            Chat.objects.filter(pk=self.chat_id).update(
                updated_at=F('timestamp'),
                last_message_id=self.id
            )

    def __str__(self):
        return f"Message {self.id} in Chat {self.chat.id}"