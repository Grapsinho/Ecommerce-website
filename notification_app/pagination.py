from rest_framework import pagination

class NotificationCursorPagination(pagination.CursorPagination):
    page_size = 10
    ordering = '-timestamp'
    cursor_query_param = 'before'