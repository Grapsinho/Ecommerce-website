from django.core.cache import cache
from .models import Order

# Cache settings
CACHE_VERSION = 1  # so this will stay same for simplicity
CACHE_TTL = 30 * 60  # 30 minutes


def _cache_key(user_id):
    return f"orders:v{CACHE_VERSION}:user:{user_id}"


def get_cached_order_ids(user):
    """
    Returns a list of Order IDs for `user` from cache (or recomputes and caches).
    """
    key = _cache_key(user.id)
    ids = cache.get(key)
    if ids is None:
        # Cold cache: fetch and store sorted IDs by created_at desc
        ids = list(
            Order.objects
                 .filter(user=user)
                 .order_by('-created_at')
                 .values_list('id', flat=True)
        )
        cache.set(key, ids, CACHE_TTL)
    return ids