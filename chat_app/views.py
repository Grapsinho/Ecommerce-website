from rest_framework import viewsets, mixins, permissions, pagination
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.db.models import Subquery, OuterRef, Count, Q, Prefetch

from .models import Chat, Message
from .serializers import (
    ChatCreateSerializer, ChatListSerializer, MessageSerializer
)
from users.authentication import JWTAuthentication
from product_management.models import ProductMedia


class MessageCursorPagination(pagination.CursorPagination):
    page_size = 30
    ordering = '-timestamp'
    cursor_query_param = 'cursor'

class ChatViewSet(viewsets.GenericViewSet,
                  mixins.CreateModelMixin,
                  mixins.ListModelMixin):
    """
    list:
    Return all chats for the authenticated user, annotated with last message and unread count.

    create:
    Create a new chat or return existing chat for a buyer-owner pair, updating product if needed.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    queryset = Chat.objects.select_related('buyer', 'owner', 'product')

    def get_serializer_class(self):
        if self.request and self.action == 'create':
            return ChatCreateSerializer
        return ChatListSerializer

    def get_queryset(self):
        user = self.request.user
        base = Chat.objects.filter(Q(buyer=user) | Q(owner=user))
        last_msg = Message.objects.filter(chat=OuterRef('pk')).order_by('-timestamp')
        feature_prefetch = Prefetch(
            'product__media',
            queryset=ProductMedia.objects.filter(is_feature=True),
            to_attr='feature_media'
        )

        return (
            base
            .select_related('buyer', 'owner', 'product__seller')
            .prefetch_related(feature_prefetch)
            .annotate(
                last_text=Subquery(last_msg.values('text')[:1]),
                last_ts=Subquery(last_msg.values('timestamp')[:1]),
                unread=Count(
                    'messages',
                    filter=Q(messages__is_read=False) & ~Q(messages__sender=user)
                )
            )
            .order_by('-updated_at')
        )


class MessageViewSet(viewsets.GenericViewSet,
                     mixins.ListModelMixin,
                     mixins.CreateModelMixin,
                     mixins.DestroyModelMixin):
    """
    list:
    List messages in a chat (cursor-paginated) and mark unread messages as read.

    create:
    Send a new message in a chat.

    destroy:
    Delete a message if sender or admin.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MessageSerializer
    pagination_class = MessageCursorPagination

    def get_chat(self):
        chat_id = self.kwargs.get('chat_pk') or self.kwargs.get('chat_id')
        chat = get_object_or_404(Chat, id=chat_id)
        user = self.request.user
        if not (chat.buyer == user or chat.owner == user or user.is_staff):
            raise PermissionDenied(detail='Not a participant.')
        return chat

    def get_queryset(self):
        chat = self.get_chat()
        return Message.objects.filter(chat=chat)

    def list(self, request, *args, **kwargs):
        chat = self.get_chat()
        # mark unread messages for this user as read
        Message.objects.filter(chat=chat, is_read=False).exclude(sender=request.user).update(is_read=True)
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        chat = self.get_chat()
        serializer.save(chat=chat, sender=self.request.user)
        # Broadcast via Channels here (omitted)

    def destroy(self, request, *args, **kwargs):
        msg = get_object_or_404(Message, id=self.kwargs['pk'])
        user = request.user
        if not (msg.sender == user or user.is_staff):
            raise PermissionDenied(detail='Cannot delete this message.')
        return super().destroy(request, *args, **kwargs)