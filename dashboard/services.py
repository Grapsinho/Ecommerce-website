from django.db.models import Q, Prefetch
from product_management.models import Product, Category, ProductMedia
from product_cart.models import CartItem
from orders.models import OrderItem

class Recommendations:
    @staticmethod
    def for_user(user, limit=10):
        """
        Optimized cross-sell recommendations: single DB pass for sibling-category fetch,
        then fallback bestsellers.
        Returns up to `limit` Product instances.
        """
        # 1. Normalize limit
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, 10))

        # 2. Build base queryset
        exclude_ids = set(
            OrderItem.objects.filter(order__user=user).values_list('product_id', flat=True)
        ) | set(
            CartItem.objects.filter(cart__user=user).values_list('product_id', flat=True)
        )

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

        # 3. Gather all relevant category IDs from cart, wishlist, and past orders
        wishlist_cat_ids = set(
            CartItem.objects.filter(cart__user=user)
                    .values_list('product__category_id', flat=True)
        )
        cart_cat_ids = set(
            CartItem.objects.filter(cart__user=user)
                    .values_list('product__category_id', flat=True)
        )
        bought_cat_ids = set(
            OrderItem.objects.filter(order__user=user)
                    .values_list('product__category_id', flat=True)
                    .distinct()
        )
        all_cat_ids = wishlist_cat_ids | cart_cat_ids | bought_cat_ids

        recs = []
        if all_cat_ids:
            # 4. Compute sibling categories in one go
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

            # 5. Cross-sell: fetch top products from these sibling categories
            recs = list(
                base_qs
                    .filter(category_id__in=sibling_cat_ids)
                    .order_by('-units_sold')[:limit]
            )

        # 6. Fallback to bestsellers if needed
        if len(recs) < limit:
            needed = limit - len(recs)
            used_ids = {p.id for p in recs}
            fallback_qs = (
                base_qs
                    .exclude(id__in=used_ids)
                    .order_by('-units_sold')[:needed]
            )
            recs.extend(fallback_qs)

        return recs
