import django_filters
from .models import Product, Category

class ProductFilter(django_filters.FilterSet):
    price_min = django_filters.NumberFilter(field_name="price", lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr='lte')
    condition = django_filters.CharFilter(field_name="condition", lookup_expr='iexact')
    category = django_filters.CharFilter(method="filter_category_by_slug")

    class Meta:
        model = Product
        fields = ['price_min', 'price_max', 'condition', 'category']

    def filter_category_by_slug(self, queryset, name, value):
        try:
            category = Category.objects.get(slug=value)
        except Category.DoesNotExist:
            return queryset.none()

        # If this category has children, we want to filter by its children only
        children = category.get_children()

        if children.exists():
            # Filter products whose category is in those children
            return queryset.filter(category__in=children)
        else:
            # If no children, filter by this category only
            return queryset.filter(category=category)
