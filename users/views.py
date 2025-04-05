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
from .serializers import RegisterSerializer, LoginUserSerializer, PasswordResetConfirmSerializer, PasswordResetRequestSerializer, UserProfileSerializer
from .throttles import EmailConfirmationRateThrottle, LoginRateThrottle
from utils import email_confirm, set_jwt_token
from .authentication import JWTAuthentication

from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

logger = logging.getLogger("rest_framework")



class EmailConfirmationView(APIView):
    """
    post:
    Handle email confirmation for a new user.

    - If only the email is provided, sends a confirmation code via email.
    - If the email and a code are provided, validates the code.

    Request body parameters:
      - email (str): The email address to confirm.
      - code (str, optional): The confirmation code sent to the email.

    Responses:
      - 200 OK: Confirmation code sent or email confirmed.
      - 400 Bad Request: Missing email or invalid/expired confirmation code.
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
    post:
    Register a new user after confirming their email.
    
    Request body parameters:
      - username, email, age, password, city, phone_number, avatar

    On success:
      - Issues JWT access and refresh tokens as secure cookies.
      - Returns a message confirming registration.

    Responses:
      - 201 Created: Registration successful.
      - 400 Bad Request: Validation errors (e.g., email not confirmed).
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
    post:
    Authenticate a user with email and password.

    Request body parameters:
      - email (str)
      - password (str)

    On success:
      - Issues JWT access and refresh tokens as secure cookies.
      - Returns a login success message.

    Responses:
      - 200 OK: Login successful.
      - 400 Bad Request: Invalid credentials.
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
    post:
    Log out the current user by blacklisting the refresh token and deleting JWT cookies.

    Responses:
      - 200 OK: Logout successful.
      - 400 Bad Request: Error during logout (e.g., token already blacklisted).
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
                token.blacklist()  # Blacklist the token
        except Exception as e:
            logger.warning(f"Logout failed: {e}")
            response.data = {
                "error": "Invalid token or token already blacklisted.",
                "details": str(e)
            }
            response.status_code = status.HTTP_400_BAD_REQUEST

        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')

        return response
    


class ProtectedView(APIView):

    """
    get:
    A protected endpoint that requires a valid JWT access token.

    Responses:
      - 200 OK: Returns a welcome message if the token is valid.
      - 401 Unauthorized: If the token is missing or invalid, returns a message:
        "Access token expired. Please refresh your session."
    """

    serializer_class = None
    authentication_classes = [JWTAuthentication]

    def get(self, request):

        response = Response(
            {"message": "message successful"},
            status=status.HTTP_200_OK,
        )

        return response
    

class UserProfileView(APIView):

    authentication_classes = [JWTAuthentication]

    @extend_schema(
        summary="Get User Profile by ID",
        description="Returns public profile information of a user by their UUID. Authentication is required.",
        parameters=[
            OpenApiParameter(
                name='user_id',
                description='UUID of the user whose profile is being fetched.',
                required=True,
                type={'type': 'string', 'format': 'uuid'},
                location=OpenApiParameter.PATH,
            )
        ],
        responses={
            200: OpenApiResponse(
                response=UserProfileSerializer,
                description="User profile retrieved successfully."
            ),
            401: OpenApiResponse(description="Unauthorized. Access token is missing or invalid."),
            404: OpenApiResponse(description="User not found."),
        },
        tags=["Users"]
    )

    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserProfileSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

class PasswordResetRequestView(APIView):

    """
    post:
    Request a password reset email.

    Request body parameters:
      - email (str)

    Responses:
      - 200 OK: Indicates that if the email exists, a password reset email has been sent.
      - 400 Bad Request: Validation errors.
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
                
                pass

            return Response(
                {"detail": "If the email exists in our system, a password reset email has been sent."},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):

    """
    post:
    Confirm and process a password reset request.

    Request body parameters:
      - email (str)
      - token (str)
      - new_password (str)

    Responses:
      - 200 OK: Password reset successfully.
      - 400 Bad Request: Invalid or expired token, or validation errors.
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
    post:
    Refresh the JWT access token using the refresh token stored in cookies.

    - If the refresh token is valid:
        Returns new access and refresh tokens as secure cookies.
    - If the refresh token is invalid or expired:
        Returns a 401 Unauthorized with message: 
        "Invalid or expired refresh token. Please log in again."

    Responses:
      - 200 OK: New tokens issued.
      - 401 Unauthorized: Invalid or expired refresh token.
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
    

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
@csrf_exempt  # Optional: disable CSRF for quick access, but only if it's safe
def create_superuser_view(request):

    # Prevent accidental duplicate creation
    if User.objects.filter(is_superuser=True).exists():
        return JsonResponse({"message": "Superuser already exists."}, status=400)

    # Customize the credentials here
    user = User.objects.create_superuser(
        username="admin",
        email="giguuag@gmail.com",
        password="giorgi123",
        age=21,
        phone_number="+995598351432",
        full_username="admin_vaa",
        city="Gori"
    )

    print(user.avatar.url)
    return JsonResponse({"message": "Superuser created successfully."})