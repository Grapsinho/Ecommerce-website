from django.core.cache import cache
from django.db.models import Case, When, IntegerField, Prefetch

from product_management.models import Product, ProductMedia
from .services import Recommendations

CACHE_VERSION = 1  # so this will stay same for simplicity
CACHE_TTL = 30 * 60  # 30 minutes


def _cache_key(user_id):
    return f"recs:v{CACHE_VERSION}:user:{user_id}"


def get_cached_recommendations(user, limit=10):
    """
    Returns a QuerySet of recommended Products for `user`, using
    Redis to cache the ordered list of IDs.
    """
    key = _cache_key(user.id)
    rec_ids = cache.get(key)

    if rec_ids is None:
        # Cold: compute fresh recs and cache ID list
        recs_qs = Recommendations.for_user(user, limit)
        rec_ids = list(recs_qs.values_list('id', flat=True))
        cache.set(key, rec_ids, CACHE_TTL)
    # Rehydrate queryset preserving order
    preserved = Case(
        *[When(id=pk, then=pos) for pos, pk in enumerate(rec_ids)],
        output_field=IntegerField(),
    )

    feature_prefetch = Prefetch(
        'media', queryset=ProductMedia.objects.filter(is_feature=True), to_attr='feature_media'
    )

    return (
        Product.objects
               .filter(id__in=rec_ids)
               .order_by(preserved)
               .prefetch_related(feature_prefetch)
    )


def _cache_key_products(user_id):
    return f"own_products:v{CACHE_VERSION}:user:{user_id}"


def get_my_product_ids(user):
    """
    Returns a list of product IDs for `user` from cache (or recomputes and caches).
    """
    key = _cache_key_products(user.id)
    ids = cache.get(key)
    if ids is None:
        # Cold cache: fetch IDs and store
        ids = list(
            Product.objects
                   .filter(seller=user)
                   .values_list('id', flat=True)
        )
        cache.set(key, ids, CACHE_TTL)
    return ids
