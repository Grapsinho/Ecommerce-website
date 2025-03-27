from django.urls import path
from .views import EmailConfirmationView, RegisterView

urlpatterns = [
    path('api/auth/email_confirmation/', EmailConfirmationView.as_view(), name='email-confirmation'),
    path('api/auth/register/', RegisterView.as_view(), name='register'),
]