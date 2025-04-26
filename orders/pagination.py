from rest_framework.response import Response
from rest_framework.pagination import CursorPagination

class OrderCursorPagination(CursorPagination):
    page_size = 10
    ordering = '-created_at'
    cursor_query_param = 'cursor'

    def get_paginated_response(self, data):
        return Response({
            'next':     self.get_next_link(),
            'previous': self.get_previous_link(),
            'orders':   data,
        })