from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, CategoryRetrieveAPIView, ParentCategoryListAPIView, LoadProductsFixtures, CreateProductMedia, LoadParentCategories, LoadChildCategories, RebuildCategories

router = DefaultRouter()
router.register(r'items', ProductViewSet, basename='items')

urlpatterns = [
    path('shop/', include(router.urls)),
    path('categories/<slug:slug>/', CategoryRetrieveAPIView.as_view(), name='category-detail'),
    path('parent/categories/', ParentCategoryListAPIView.as_view(), name='parent-categories'),


    # populate database
    path('load-products/',          LoadProductsFixtures.as_view(),   name='load-products'),
    path('populate-media/',         CreateProductMedia.as_view(),     name='populate-product-media'),


    path('load-parent-categories/', LoadParentCategories.as_view(), name='load-parent-categories'),
    path('load-child-categories/',  LoadChildCategories.as_view(),  name='load-child-categories'),
    path('rebuild-categories/',     RebuildCategories.as_view(),     name='rebuild-categories'),
]