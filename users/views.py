import random
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.contrib.auth.tokens import PasswordResetTokenGenerator

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import User
from .serializers import RegisterSerializer, LoginUserSerializer, PasswordResetConfirmSerializer, PasswordResetRequestSerializer
from .throttles import EmailConfirmationRateThrottle, LoginRateThrottle
from utils import email_confirm, set_jwt_token

logger = logging.getLogger("rest_framework")



class EmailConfirmationView(APIView):
    """
    EmailConfirmationView

    Handles email confirmation for new user registration in two steps:
    
    1. **Requesting a confirmation code:**
       - When only the email is provided, the endpoint generates a 6-digit confirmation code.
       - The code is sent to the provided email address and cached for 60 seconds.
       
    2. **Validating a confirmation code:**
       - When both email and code are provided, the endpoint validates the confirmation code.
       - If valid, the email is marked as confirmed for 10 minutes.

    **Request Body Parameters:**
      - **email (str):** The email address to be confirmed.
      - **code (str, optional):** The 6-digit confirmation code sent to the email.

    **Responses:**
      - **200 OK:**
          - When a confirmation code is successfully sent.
          - When the provided confirmation code is validated and the email is confirmed.
      - **400 Bad Request:**
          - If the email is missing.
          - If the user with the email already exists.
          - If the confirmation code is missing, expired, or invalid.
      - **500 Internal Server Error:**
          - If there is a failure sending the email.
    """

    throttle_classes = [EmailConfirmationRateThrottle]
    serializer_class = None

    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')  # Defaults to None if not provided

        if not email:
            logger.warning("Email is missing in email confirmation request.")
            return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        email = email.lower()
        if User.objects.filter(email=email).exists():
            logger.info(f"User with email {email} attempted to register but is already registered.")
            return Response({"detail": "You are already registered."}, status=status.HTTP_400_BAD_REQUEST)

        code_cache_key = email_confirm.get_email_confirmation_code_key(email)
        confirmed_cache_key = email_confirm.get_email_confirmed_key(email)

        if not code:
            return self.send_confirmation_code(email, code_cache_key)
        else:
            return self.validate_confirmation_code(email, code, code_cache_key, confirmed_cache_key)

    def send_confirmation_code(self, email, code_cache_key):
        """
        Generates and sends a confirmation code to the provided email.
        Stores the code in cache with a 60-second timeout.

        **Parameters:**
          - email (str): The target email address.
          - code_cache_key (str): The cache key used to store the confirmation code.

        **Returns:**
          - 200 OK with a success message if email sent.
          - 500 Internal Server Error if email sending fails.
        """
        generated_code = str(random.randint(100000, 999999))
        subject = 'Your Confirmation Code'
        text_content = (
            f"Hello,\n\nYour confirmation code is: {generated_code}\n\n"
            "Please enter this code within the next 60 seconds to confirm your email.\n"
            "If you did not request this, please ignore this email."
        )
        from_email = settings.EMAIL_HOST_USER

        try:
            send_mail(subject, text_content, from_email, [email])
            logger.info(f"Confirmation code sent to {email}")
        except Exception as e:
            logger.error(f"Failed to send email to {email}: {str(e)}")

            return Response({"detail": "Failed to send email. Try again later."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        cache.set(code_cache_key, generated_code, timeout=60)
        return Response({"detail": "Confirmation code sent to email."}, status=status.HTTP_200_OK)

    def validate_confirmation_code(self, email, code, code_cache_key, confirmed_cache_key):
        """
        Validates the confirmation code provided by the user.
        If valid, sets a cache flag to mark the email as confirmed.

        **Parameters:**
          - email (str): The email being confirmed.
          - code (str): The confirmation code provided by the user.
          - code_cache_key (str): Cache key where the correct code is stored.
          - confirmed_cache_key (str): Cache key used to store the confirmation status.

        **Returns:**
          - 200 OK with a success message if the code is valid.
          - 400 Bad Request if the code is expired or invalid.
        """
        cached_code = cache.get(code_cache_key)
        if not cached_code:
            logger.warning(f"Expired or missing confirmation code for email {email}")
            return Response({"detail": "Confirmation code expired. Please request a new one."},
                            status=status.HTTP_400_BAD_REQUEST)
        
        if code != cached_code:
            logger.warning(f"Invalid confirmation code attempt for email {email}")
            return Response({"detail": "Invalid confirmation code."}, status=status.HTTP_400_BAD_REQUEST)

        cache.set(confirmed_cache_key, True, timeout=600)
        cache.delete(code_cache_key)
        logger.info(f"Email {email} successfully confirmed.")
        return Response({"detail": "Email confirmed."}, status=status.HTTP_200_OK)


class RegisterView(generics.CreateAPIView):
    """
    RegisterView

    Registers a new user once the email has been confirmed. Upon successful registration,
    JWT access and refresh tokens are issued as secure cookies.

    **Request Body Parameters:**
      - **username (str)**
      - **email (str)**
      - **age (int)**
      - **password (str)**
      - **city (str)**
      - **phone_number (str)**
      - **avatar (file or URL)**

    **Responses:**
      - **201 Created:** User registration successful, tokens set in secure cookies.
      - **400 Bad Request:** Registration validation errors (e.g., unconfirmed email or invalid data).
    """

    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            access_token, refresh_token = email_confirm.generate_tokens_for_user(user)

            logger.info(f"User {user.email} registered successfully.")

            response = Response({
                'message': 'User registered successfully.'
            }, status=status.HTTP_201_CREATED)

            set_jwt_token.set_secure_jwt_cookie(response, access_token, refresh_token)

            return response

        logger.warning(f"Registration failed for email {request.data.get('email')}: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginUser(APIView):
    """
    LoginUser

    Authenticates a user using email and password credentials. On successful authentication,
    issues JWT tokens as secure cookies.

    **Request Body Parameters:**
      - **email (str):** User's email address.
      - **password (str):** User's password.

    **Responses:**
      - **200 OK:** Login successful with JWT tokens issued.
      - **400 Bad Request:** Invalid credentials or validation errors.
    """

    permission_classes = [AllowAny]
    serializer_class = LoginUserSerializer
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            access_token, refresh_token = email_confirm.generate_tokens_for_user(user)

            logger.info(f"User {user.email} logged in successfully.")

            response = Response({
                'message': 'Login successful',
            }, status=status.HTTP_200_OK)

            set_jwt_token.set_secure_jwt_cookie(response, access_token, refresh_token)

            return response

        logger.warning(f"Login failed for email {request.data.get('email')}: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutUser(APIView):
    """
    LogoutUser

    Logs out the current user by blacklisting the provided refresh token (if available)
    and removing the JWT cookies.

    **Responses:**
      - **200 OK:** Logout successful.
      - **400 Bad Request:** An error occurred during logout (e.g., token already blacklisted <- SKIP THIS IT'S NOTHING IMPORTANT).
    """

    serializer_class = None
    permission_classes = [AllowAny]

    def post(self, request):
        response = Response(
            {"message": "Logout successful"},
            status=status.HTTP_200_OK,
        )

        try:
            refresh_token = request.COOKIES.get("refresh_token")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()  # Blacklist the token to invalidate it
        except Exception as e:
            logger.warning(f"Logout failed: {e}")
            response.data = {
                "error": "Invalid token or token already blacklisted.",
                "details": str(e)
            }
            response.status_code = status.HTTP_400_BAD_REQUEST

        response.delete_cookie('access_token', samesite='None')
        response.delete_cookie('refresh_token', samesite='None')

        return response


class PasswordResetRequestView(APIView):
    """
    PasswordResetRequestView

    Initiates a password reset request. If the provided email is associated with an account,
    a password reset email containing a unique token and reset URL is sent to the user.

    **Request Body Parameters:**
      - **email (str):** The email address of the user requesting a password reset.

    **Responses:**
      - **200 OK:** A message indicating that if the email exists, a reset email has been sent.
      - **400 Bad Request:** Validation errors in the provided email.
    
    **Note:**
      - Even if the email is not found, the same success response is returned to avoid email enumeration.
    """

    serializer_class = None

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
                token_generator = PasswordResetTokenGenerator()
                token = token_generator.make_token(user)

                # Construct the password reset URL
                reset_url = f"{request.scheme}://{request.get_host()}/reset-password-confirm/?email={email}&token={token}"
                
                # Send the email (consider using asynchronous sending in production)
                subject = "Password Reset Request"
                message = (
                    f"Hi {user.username},\n\n"
                    f"Click the link below to reset your password:\n{reset_url}\n\n"
                    "If you did not request this, please ignore this email."
                )
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
            except User.DoesNotExist:
                # Do not reveal that the email does not exist in the system
                pass

            return Response(
                {"detail": "If the email exists in our system, a password reset email has been sent."},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    """
    PasswordResetConfirmView

    Confirms a password reset request by validating the token and updating the user's password.

    **Request Body Parameters:**
      - **email (str):** The user's email address.
      - **token (str):** The token provided in the password reset email.
      - **new_password (str):** The new password for the user.

    **Responses:**
      - **200 OK:** Password has been reset successfully.
      - **400 Bad Request:** Token is invalid/expired or other validation errors.
    """

    serializer_class = None

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()  # Updates the user's password
            return Response({"detail": "Password has been reset successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RefreshAccessTokenView(APIView):
    """
    RefreshAccessTokenView

    Refreshes the JWT access token using the refresh token stored in cookies.
    If the refresh token is valid, new JWT access and refresh tokens are issued as secure cookies.
    If the refresh token is invalid or expired, a 401 Unauthorized response is returned.

    **Responses:**
      - **200 OK:** New tokens issued and returned in secure cookies.
      - **401 Unauthorized:** If the refresh token is missing, invalid, or expired.
    """

    permission_classes = [AllowAny]
    serializer_class = None

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            logger.info("Refresh token not provided in cookies.")
            return Response(
                {"message": "Invalid or expired token. Please log in again."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            # Validate the provided refresh token
            refresh = RefreshToken(refresh_token)
        except TokenError as e:
            logger.info("Invalid or expired refresh token: %s", e)
            return Response(
                {"message": "Invalid or expired token. Please log in again."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # At this point the refresh token is valid. Issue new tokens.
        new_access_token = str(refresh.access_token)
        new_refresh_token = str(refresh)  # Using the same refresh instance for rotation

        try:
            # Blacklist the used refresh token (if not automatically handled)
            refresh.blacklist()
        except Exception as e:
            logger.warning("Failed to blacklist refresh token: %s", e)

        response = Response(
            {"message": "Access token refreshed"},
            status=status.HTTP_200_OK
        )

        # Update cookies with new tokens
        set_jwt_token.set_secure_jwt_cookie(response, new_access_token, new_refresh_token)
        return response