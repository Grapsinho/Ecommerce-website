from django.urls import path, include
from rest_framework import routers
from .views import MessageViewSet, ChatViewSet

router = routers.DefaultRouter()
router.register(r'chats', ChatViewSet, basename='chat')

message_list = MessageViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
message_detail = MessageViewSet.as_view({
    'delete': 'destroy'
})

urlpatterns = [
    path('', include(router.urls)),
    path('chats/<uuid:chat_pk>/messages/', message_list, name='chat-messages-list'),
    path('chats/<uuid:chat_pk>/messages/<uuid:pk>/', message_detail, name='chat-messages-detail'),
]
