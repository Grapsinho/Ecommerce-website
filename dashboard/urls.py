from django.urls import path
from .views import ProfileUpdateRetrieveView, MyProductListView, RecommendationView, UserProfileView

urlpatterns = [
    path('dashboard/me/', ProfileUpdateRetrieveView.as_view(), name='profile-me'),
    path('dashboard/me/products/', MyProductListView.as_view(), name='my-products'),
    path('dashboard/me/recommendations/', RecommendationView.as_view(), name='recommendations'),
    path('dashboard/profile/<uuid:user_id>/', UserProfileView.as_view(), name='users-profile'),
]