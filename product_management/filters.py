import django_filters
from .models import Product, Category

class ProductFilter(django_filters.FilterSet):
    price_min = django_filters.NumberFilter(field_name="price", lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr='lte')
    condition = django_filters.CharFilter(field_name="condition", lookup_expr='iexact')

    category = django_filters.CharFilter(method='filter_by_category')

    class Meta:
        model = Product
        fields = ['price_min', 'price_max', 'condition', 'category']

    def filter_by_category(self, queryset, name, value):
        """
        Filter products based on the provided category slug.
          - If the category is a parent (has no parent), filter products whose
            category's parent is the provided category.
          - If the category is a child, filter products strictly by that category.
          - If the category does not exist, return an empty queryset.
        """
        try:
            selected_category = Category.objects.get(slug=value)
        except Category.DoesNotExist:
            return queryset.none()

        if selected_category.parent is None:
            # The category is a parent; so we want products whose category has this parent.
            return queryset.filter(category__parent=selected_category)
        else:
            # The category is a child; return products strictly matching it.
            return queryset.filter(category=selected_category)
