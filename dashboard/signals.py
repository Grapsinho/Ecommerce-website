from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from product_cart.models import CartItem
from wishlist_app.models import WishlistItem
from orders.models import OrderItem
from .dsh_cache import _cache_key, _cache_key_products
from product_management.models import Product

def invalidate_user_recs(user_id):
    cache.delete(_cache_key(user_id))


@receiver([post_save, post_delete], sender=CartItem)
def _on_cart_change(sender, instance, **kwargs):
    invalidate_user_recs(instance.cart.user_id)


@receiver([post_save, post_delete], sender=WishlistItem)
def _on_wishlist_change(sender, instance, **kwargs):
    invalidate_user_recs(instance.wishlist.user_id)


@receiver(post_save, sender=OrderItem)
def _on_order_item_created(sender, instance, created, **kwargs):
    if created:
        invalidate_user_recs(instance.order.user_id)


@receiver([post_save, post_delete], sender=Product)
def invalidate_my_products_cache(sender, instance, **kwargs):
    """
    Invalidate cache for a user's own-product list when they add/update/delete.
    """
    cache.delete(_cache_key_products(instance.seller_id))