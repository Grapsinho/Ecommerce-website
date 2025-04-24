from django.db.models import Q, OuterRef, Subquery
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from chat_app.models import Message, Chat
from .serializers import NotificationSerializer
from .pagination import NotificationCursorPagination
from users.authentication import JWTAuthentication


class NotificationListView(generics.ListAPIView):
    """
    GET /notifications/?unread_only=<true|false>&before=<msg_id>&limit=<n>
    Returns paginated list of messages *to* the current user (excluding their own sends),
    which the front-end can treat as "notifications."
    """
    serializer_class = NotificationSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationCursorPagination

    def get_queryset(self):
        user = self.request.user

        # 1) find chats of mine
        chats = Chat.objects.filter(Q(buyer=user) | Q(owner=user))

        # 2) subquery to grab the latest unread msg‑id per chat
        latest_unread = (
            Message.objects
                   .filter(chat=OuterRef('pk'), is_read=False)
                   .exclude(sender=user)
                   .order_by('-timestamp')
        )

        chats = (
            chats
            .annotate(last_unread_msg_id=Subquery(latest_unread.values('id')[:1]))
            .filter(last_unread_msg_id__isnull=False)
        )

        # 3) pull exactly those Messages, plus sender & chat in one query
        return (
            Message.objects
                   .filter(id__in=chats.values('last_unread_msg_id'))
                   .select_related('sender', 'chat')
                   .order_by('-timestamp')
        )