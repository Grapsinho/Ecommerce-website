from django.db.models import Q, Prefetch
from product_management.models import Product, Category, ProductMedia
from product_cart.models import CartItem
from orders.models import OrderItem
from wishlist_app.models import WishlistItem

class Recommendations:
    @staticmethod
    def for_user(user, limit=10):
        """
        Optimized cross-sell recommendations:
          - Include wishlist, cart, and past purchases for category seeds
          - Exclude wishlist/cart/purchased products
          - Single DB pass for sibling-category cross-sells
          - Fallback bestsellers
        Returns up to `limit` Product instances.
        """
        # 1. Normalize limit
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 10))

        # 2. Load all wishlist, cart, and purchased items at once
        wishlist_items = list(
            WishlistItem.objects
                .filter(wishlist__user=user)
                .select_related('product__category')
        )
        cart_items = list(
            CartItem.objects
                .filter(cart__user=user)
                .select_related('product__category')
        )
        purchased_items = list(
            OrderItem.objects
                .filter(order__user=user)
                .select_related('product__category')
        )

        # 3. Build exclusion and category sets in Python
        exclude_ids = {
            *{wi.product_id for wi in wishlist_items},
            *{ci.product_id for ci in cart_items},
            *{oi.product_id for oi in purchased_items},
        }
        all_cat_ids = {
            *{wi.product.category_id for wi in wishlist_items},
            *{ci.product.category_id for ci in cart_items},
            *{oi.product.category_id for oi in purchased_items},
        }

        # 4. Base queryset for products
        feature_media_prefetch = Prefetch(
            'media',
            queryset=ProductMedia.objects.filter(is_feature=True),
            to_attr='feature_media'
        )
        base_qs = (
            Product.objects
                   .filter(is_active=True, stock__gt=0)
                   .exclude(Q(id__in=exclude_ids) | Q(seller=user))
                   .prefetch_related(feature_media_prefetch)
        )

        recs = []
        if all_cat_ids:
            # 5. Get sibling categories in two queries
            parent_ids = (
                Category.objects
                        .filter(pk__in=all_cat_ids)
                        .values_list('parent_id', flat=True)
                        .distinct()
            )
            sibling_cat_ids = (
                Category.objects
                        .filter(parent_id__in=parent_ids)
                        .exclude(pk__in=all_cat_ids)
                        .values_list('pk', flat=True)
            )

            # 6. Cross-sell products in a single query
            recs = list(
                base_qs
                    .filter(category_id__in=sibling_cat_ids)
                    .order_by('-units_sold')[:limit]
            )

        # 7. Fallback bestsellers (single query)
        if len(recs) < limit:
            needed = limit - len(recs)
            used_ids = {p.id for p in recs}
            fallback_qs = (
                base_qs
                    .exclude(id__in=used_ids)
                    .order_by('-units_sold')[:needed]
            )
            recs.extend(list(fallback_qs))

        return recs
