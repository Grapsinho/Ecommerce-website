from rest_framework import viewsets, mixins, permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.throttling import ScopedRateThrottle
from django.shortcuts import get_object_or_404
from django.db.models import (
    Prefetch, Q, OuterRef, Subquery,
    F
)

from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import Chat, Message
from .serializers import (
    ChatCreateSerializer, ChatListSerializer, MessageSerializer
)
from .pagination import MessageCursorPagination, ChatCursorPagination

from users.authentication import JWTAuthentication
from product_management.models import ProductMedia


@extend_schema_view(
    list=extend_schema(
        summary='List all chats for the user',
        responses={200: ChatListSerializer(many=True)},
        tags=['Chats'],
    ),
    create=extend_schema(
        summary='Create or get existing chat',
        request=ChatCreateSerializer,
        responses={201: ChatListSerializer},
        tags=['Chats'],
    ),
)
class ChatViewSet(viewsets.GenericViewSet,
                  mixins.CreateModelMixin,
                  mixins.ListModelMixin):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ChatCursorPagination
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'chat_create'

    # only needed for create(); list() uses get_queryset()
    queryset = Chat.objects.all()

    def get_serializer_class(self):
        return ChatCreateSerializer if self.action == 'create' else ChatListSerializer

    def get_queryset(self):
        user = self.request.user
        base = Chat.objects.filter(Q(buyer=user) | Q(owner=user))

        feature_prefetch = Prefetch(
            'product__media',
            queryset=ProductMedia.objects.filter(is_feature=True),
            to_attr='feature_media'
        )

        # annotate last message fields
        last_msg = Message.objects.filter(chat=OuterRef('pk')).order_by('-timestamp')

        return (
            base
            .select_related('buyer', 'owner', 'product')
            .only(
                'id', 'updated_at',
                'buyer__id', 'buyer__full_username', 'buyer__avatar', 'buyer__city',
                'owner__id', 'owner__full_username', 'owner__avatar', 'owner__city',
                'product__slug', 'product__name', 'product__price', 'product__condition',
                'unread_count'
            )
            .prefetch_related(feature_prefetch)
            .annotate(
                last_message_text=Subquery(last_msg.values('text')[:1]),
                last_message_timestamp=Subquery(last_msg.values('timestamp')[:1])
            )
            .order_by('-updated_at')
        )


from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@extend_schema_view(
    list=extend_schema(
        summary='Retrieve messages and mark unread as read',
        responses={200: MessageSerializer(many=True)},
        tags=['Messages'],
    ),
    create=extend_schema(
        summary='Send a new message in a chat',
        request=MessageSerializer,
        responses={201: MessageSerializer},
        tags=['Messages'],
    ),
)
class MessageViewSet(viewsets.GenericViewSet,
                     mixins.ListModelMixin,
                     mixins.CreateModelMixin,
                     mixins.DestroyModelMixin):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MessageSerializer
    pagination_class = MessageCursorPagination
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'message_send'

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
        chat_id = kwargs['chat_pk']
        user = request.user

        qs = Message.objects.filter(chat_id=chat_id, is_read=False).exclude(sender=user)
        unread_count = qs.count()

        qs.update(is_read=True)

        Chat.objects.filter(pk=chat_id).update(unread_count=F('unread_count') - unread_count)
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