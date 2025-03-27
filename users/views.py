import random
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import RegisterSerializer
from utils.store_jwt import set_jwt_cookie
from .throttles import EmailConfirmationRateThrottle

logger = logging.getLogger("rest_framework")



class EmailConfirmationView(APIView):
    """
    This view generates code for email confirmation.
    And after user writes hes code then it will validate it.
    """

    throttle_classes = [EmailConfirmationRateThrottle]

    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code', None)

        if not email:
            logger.warning("Email is missing in email confirmation request.")
            return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            logger.info(f"User with email {email} attempted to register but is already registered.")
            return Response({"detail": "You are already registered."}, status=status.HTTP_400_BAD_REQUEST)

        code_cache_key = f"email_confirmation_code_{email}"
        confirmed_cache_key = f"email_confirmed_{email}"

        if not code:
            generated_code = str(random.randint(100000, 999999))
            try:
                subject = 'Your Confirmation Code'
                text_content = f"Hello,\n\nYour confirmation code is: {generated_code}\n\nPlease enter this code within the next 60 seconds to confirm your email.\nIf you did not request this, please ignore this email."

                from_email = settings.EMAIL_HOST_USER

                send_mail(subject, text_content, from_email, [email])

                logger.info(f"Confirmation code sent to {email}")
            except Exception as e:
                logger.error(f"Failed to send email to {email}: {str(e)}")
                return Response({"detail": "Failed to send email. Try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            cache.set(code_cache_key, generated_code, timeout=60)
            return Response({"detail": "Confirmation code sent to email."}, status=status.HTTP_200_OK)
        else:
            cached_code = cache.get(code_cache_key)
            if not cached_code:
                logger.warning(f"Expired or missing confirmation code for email {email}")
                return Response({"detail": "Confirmation code expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)

            if code != cached_code:
                logger.warning(f"Invalid confirmation code attempt for email {email}")
                return Response({"detail": "Invalid confirmation code."}, status=status.HTTP_400_BAD_REQUEST)

            cache.set(confirmed_cache_key, True, timeout=300)
            cache.delete(code_cache_key)
            logger.info(f"Email {email} successfully confirmed.")
            return Response({"detail": "Email confirmed."}, status=status.HTTP_200_OK)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            # Create the response
            response = Response({
                'message': 'User registered successfully',
            }, status=status.HTTP_201_CREATED)

            # store jwt token in a secure way
            set_jwt_cookie(response, access_token, refresh_token)

            logger.info(f"User {user.email} registered successfully.")

            return response

        logger.warning(f"Registration failed for email {request.data.get('email')}: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)