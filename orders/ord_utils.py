from typing import Tuple, List, Optional

from django.db.models import Prefetch, Case, When, IntegerField
from rest_framework.request import Request
from django.db.models.query import QuerySet

from .models import Order, OrderItem
from product_management.models import ProductMedia


def get_pagination_params(request: Request) -> Tuple[int, int]:
    """Extract 'page' and 'page_size' from query params with defaults."""
    try:
        page = int(request.query_params.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    try:
        size = int(request.query_params.get('page_size', 10))
    except (TypeError, ValueError):
        size = 10
    return page, size


def build_order_queryset(page_ids: List[str]) -> QuerySet:
    """Return a queryset for the given page of order IDs, preserving order."""
    preserved = Case(
        *[When(id=pk, then=pos) for pos, pk in enumerate(page_ids)],
        output_field=IntegerField()
    )
    return (
        Order.objects.filter(id__in=page_ids)
             .select_related('shipping_method', 'shipping_address')
             .prefetch_related(
                 Prefetch(
                     'items',
                     queryset=OrderItem.objects
                         .select_related('product', 'product__seller')
                         .prefetch_related(
                             Prefetch(
                                 'product__media',
                                 queryset=ProductMedia.objects.filter(is_feature=True),
                                 to_attr='feature_media'
                             )
                         )
                 )
             )
             .distinct()
             .order_by(preserved)
    )


def build_page_urls(request: Request, page: int, size: int, total: int) -> Tuple[Optional[str], Optional[str]]:
    """Construct 'next' and 'previous' page URLs."""
    def make_url(p: int) -> Optional[str]:
        if p < 1 or size <= 0:
            return None
        max_page = (total - 1) // size + 1
        if p > max_page:
            return None
        query = request.query_params.copy()
        query['page'] = p
        query['page_size'] = size
        return request.build_absolute_uri(f"?{query.urlencode()}")

    return make_url(page + 1), make_url(page - 1)
