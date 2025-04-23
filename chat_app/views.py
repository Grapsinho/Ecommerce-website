from rest_framework import viewsets, mixins, permissions
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.db.models import (
    Prefetch, Q, OuterRef, Subquery,
    IntegerField, Value, Count
)
from django.db.models.functions import Coalesce


from .models import Chat, Message
from .serializers import (
    ChatCreateSerializer, ChatListSerializer, MessageSerializer
)
from .pagination import MessageCursorPagination, ChatCursorPagination

from users.authentication import JWTAuthentication
from product_management.models import ProductMedia


class ChatViewSet(viewsets.GenericViewSet,
                  mixins.CreateModelMixin,
                  mixins.ListModelMixin):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ChatCursorPagination

    # only needed for create(); list() uses get_queryset()
    queryset = Chat.objects.all()

    def get_serializer_class(self):
        return ChatCreateSerializer if self.action == 'create' else ChatListSerializer

    def get_queryset(self):
        user = self.request.user
        base = Chat.objects.filter(Q(buyer=user) | Q(owner=user))

        # Prefetch only feature image
        feature_prefetch = Prefetch(
            'product__media',
            queryset=ProductMedia.objects.filter(is_feature=True),
            to_attr='feature_media'
        )

        # Annotate unread count
        unread_subq = Message.objects.filter(
            chat=OuterRef('pk'), is_read=False
        ).exclude(sender=user).values('chat') \
         .annotate(c=Count('id')).values('c')

        # Annotate last message fields via Subquery to avoid join
        last_msg_qs = Message.objects.filter(chat=OuterRef('pk')).order_by('-timestamp')

        return (
            base
            .select_related('buyer', 'owner', 'product')
            .only(
                'id','updated_at',
                'buyer__id','buyer__full_username','buyer__avatar','buyer__city',
                'owner__id','owner__full_username','owner__avatar','owner__city',
                'product__slug','product__name','product__price','product__condition',
            )
            .prefetch_related(feature_prefetch)
            .annotate(
                unread=Coalesce(Subquery(unread_subq[:1], output_field=IntegerField()), Value(0)),
                last_message_text=Subquery(last_msg_qs.values('text')[:1]),
                last_message_timestamp=Subquery(last_msg_qs.values('timestamp')[:1])
            )
            .order_by('-updated_at')
        )

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
class MessageViewSet(viewsets.GenericViewSet,
                     mixins.ListModelMixin,
                     mixins.CreateModelMixin,
                     mixins.DestroyModelMixin):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MessageSerializer
    pagination_class = MessageCursorPagination

    def get_chat(self):
        
        chat = get_object_or_404(Chat, id=self.kwargs['chat_pk'])
        user = self.request.user
        if not (chat.buyer == user or chat.owner == user or user.is_staff):
            raise PermissionDenied('Not a participant.')
        return chat

    def get_queryset(self):
        return (
            Message.objects
                   .filter(chat_id=self.kwargs['chat_pk'])
                   .select_related('chat')
                   .order_by('-timestamp')
        )

    def list(self, request, *args, **kwargs):
        
        Message.objects.filter(
            chat_id=kwargs['chat_pk'],
            is_read=False
        ).exclude(sender=request.user).update(is_read=True)
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(chat=self.get_chat(), sender=self.request.user)

    def destroy(self, request, *args, **kwargs):
        chat = self.get_chat()
        msg = get_object_or_404(Message, id=self.kwargs['pk'], chat=chat)
        user = request.user

        if not (msg.sender == user):
            raise PermissionDenied('Cannot delete this message.')
        
        # notify through WS
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{str(chat.id)}",
            {
                'type': 'message.deleted',
                'message_id': str(self.kwargs['pk']),
            }
        )
        
        return super().destroy(request, *args, **kwargs)