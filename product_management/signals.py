from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Product
from django.core.cache import caches
import logging

logger = logging.getLogger("rest_framework")

@receiver([post_save, post_delete], sender=Product)
def invalidate_product_list_cache(sender, instance, **kwargs):
    """
    Invalidate product list cache keys.
    """
    try:
        redis_cache = caches['default']
        redis_cache.delete_pattern("views.decorators.cache.cache_page.product_management:product_list*")
        redis_cache.delete_pattern("views.decorators.cache.cache_header.product_management:product_list*")
        logger.info("Product list cache invalidated.")
    except Exception as e:
        logger.warning(f"Cache invalidation error: {e}")