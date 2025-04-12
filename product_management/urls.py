from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, CategoryListView, CategoryDetailView

router = DefaultRouter()
router.register(r'items', ProductViewSet, basename='items')

urlpatterns = [
    path('shop/', include(router.urls)),
    path('categories/', CategoryListView.as_view(), name="category-list"),
    path('categories/<slug:slug>', CategoryDetailView.as_view(), name="category-detail"),
]