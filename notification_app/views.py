# notifications/views.py
from django.db.models import Q
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from chat_app.models import Message
from .serializers import NotificationSerializer
from chat_app.pagination import MessageCursorPagination
from users.authentication import JWTAuthentication

from drf_spectacular.utils import extend_schema, OpenApiParameter


@extend_schema(
    summary="List notifications for the current user",
    parameters=[
        OpenApiParameter('unread_only', OpenApiParameter.QUERY, type=bool, description='Filter unread only'),
        OpenApiParameter('before', OpenApiParameter.QUERY, type=str, description='Cursor ID to paginate before'),
        OpenApiParameter('limit', OpenApiParameter.QUERY, type=int, description='Max items to return'),
    ],
    responses={200: NotificationSerializer(many=True)}
)
class NotificationListView(generics.ListAPIView):
    """
    GET /notifications/?unread_only=<true|false>&before=<msg_id>&limit=<n>
    Returns paginated list of messages *to* the current user (excluding their own sends),
    which the front-end can treat as "notifications."
    """
    serializer_class = NotificationSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = MessageCursorPagination

    def get_queryset(self):
        user = self.request.user
        qs = Message.objects.filter(
            # all chats where user is buyer or owner...
            Q(chat__buyer=user) | Q(chat__owner=user),
            # ...but exclude messages sent by the user
            ~Q(sender=user)
        )
        # optional unread_only filter (default true)
        unread_only = self.request.query_params.get('unread_only', 'true').lower()
        if unread_only in ('true', '1'):
            qs = qs.filter(is_read=False)
        return qs.order_by('-timestamp')
