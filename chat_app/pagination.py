from rest_framework import pagination

class MessageCursorPagination(pagination.CursorPagination):
    page_size = 30
    ordering = '-timestamp'
    cursor_query_param = 'cursor'


class ChatCursorPagination(pagination.CursorPagination):
    page_size = 7
    ordering = '-updated_at'
    cursor_query_param = 'cursor'