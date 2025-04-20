from rest_framework import viewsets, mixins, permissions
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.db.models import Subquery, OuterRef, Count, Q, Prefetch

from .models import Chat, Message
from .serializers import (
    ChatCreateSerializer, ChatListSerializer, MessageSerializer
)
from .pagination import MessageCursorPagination, ChatCursorPagination

from users.authentication import JWTAuthentication
from product_management.models import ProductMedia

from drf_spectacular.utils import (
    extend_schema, extend_schema_view,
    OpenApiParameter, OpenApiResponse,
)


@extend_schema_view(
    create=extend_schema(
        summary="Start or retrieve a chat",
        request=ChatCreateSerializer,
        responses={201: ChatListSerializer}
    ),
    list=extend_schema(
        summary="List chats for authenticated user",
        responses={200: ChatListSerializer(many=True)}
    ),
)
class ChatViewSet(viewsets.GenericViewSet,
                  mixins.CreateModelMixin,
                  mixins.ListModelMixin):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ChatCursorPagination

    # only needed for create(); list() uses get_queryset()
    queryset = Chat.objects.all()

    def get_serializer_class(self):
        if self.action == 'create':
            return ChatCreateSerializer
        return ChatListSerializer

    def get_queryset(self):
        user = self.request.user
        base = Chat.objects.filter(Q(buyer=user) | Q(owner=user))
        last_msg = Message.objects.filter(chat=OuterRef('id')).order_by('-timestamp')
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


@extend_schema_view(
    list=extend_schema(
        summary="List messages in a chat",
        parameters=[
            OpenApiParameter(
                name='chat_pk',
                description='Chat UUID',
                required=True,
                type=str,
                location=OpenApiParameter.PATH
            )
        ],
        responses={200: MessageSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Send a new message in a chat",
        request=MessageSerializer,
        responses={201: MessageSerializer}
    ),
    destroy=extend_schema(
        summary="Delete a message",
        responses={204: None}
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

    def get_chat(self):
        # we only use chat_pk
        chat = get_object_or_404(Chat, id=self.kwargs['chat_pk'])
        user = self.request.user
        if not (chat.buyer == user or chat.owner == user or user.is_staff):
            raise PermissionDenied('Not a participant.')
        return chat

    def get_queryset(self):
        return (
            Message.objects
                   .filter(chat=self.get_chat())
                   .select_related('sender')
        )

    def list(self, request, *args, **kwargs):
        chat = self.get_chat()
        # mark unread messages as read in one query
        chat.messages.filter(is_read=False).exclude(sender=request.user) \
            .update(is_read=True)
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(chat=self.get_chat(), sender=self.request.user)

    def destroy(self, request, *args, **kwargs):
        chat = self.get_chat()
        msg = get_object_or_404(Message, id=self.kwargs['pk'], chat=chat)
        user = request.user

        if not (msg.sender == user or user.is_staff):
            raise PermissionDenied('Cannot delete this message.')
        
        return super().destroy(request, *args, **kwargs)
