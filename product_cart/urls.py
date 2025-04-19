from rest_framework.routers import DefaultRouter
from .views import CartItemViewSet

router = DefaultRouter()
router.register(r'cart-items', CartItemViewSet, basename='cartitem')

urlpatterns = router.urls