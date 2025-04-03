from rest_framework.authentication import BaseAuthentication
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError, AuthenticationFailed
from django.core.exceptions import ObjectDoesNotExist
import logging
from .models import User

logger = logging.getLogger("django")

class JWTAuthentication(BaseAuthentication):
    """
    Custom authentication using JWT stored in HTTP-only cookies.
    """
    def authenticate(self, request):
        access_token = request.COOKIES.get("access_token")
        
        if not access_token:
            raise AuthenticationFailed(
                detail={"code": "token_expired", "message": "Access token expired. Please refresh your session."}
            )

        try:
            # Decode the access token
            token = AccessToken(access_token)
            user_id = token.get("user_id")

            if not user_id:
                raise AuthenticationFailed(
                    detail={"code": "token_expired", "message": "Access token expired. Please refresh your session."}
                )

            # Fetch user from database
            try:
                user = User.objects.get(id=user_id)
            except ObjectDoesNotExist:
                raise AuthenticationFailed(
                    detail={"code": "invalid_token", "message": "Invalid or expired token. Please log in again."}
                )

            return (user, None)  # User is authenticated

        except TokenError:
            logger.debug("Access token expired.")
            raise AuthenticationFailed(
                detail={"code": "token_expired", "message": "Access token expired. Please refresh your session."}
            )

        except Exception as e:
            logger.error("Unexpected error during authentication: %s", str(e))
            raise AuthenticationFailed(
                detail={"code": "invalid_token", "message": "Invalid or expired token. Please log in again."}
            )
        

# class IsAuthenticatedWithJWT(BasePermission):
#     """
#     Custom permission to authenticate users using JWT stored in HTTP-only cookies.
#     """
#     def has_permission(self, request, view):
#         access_token = request.COOKIES.get("access_token")
#         if not access_token:
#             logger.debug("Access token not found in cookies.")
#             raise AuthenticationFailed("Access token expired. Please refresh your session.")

#         try:
#             # Validate and decode the access token
#             token = AccessToken(access_token)
#             user_id = token.get("user_id")

#             if not user_id:
#                 logger.debug("No user_id claim in access token.")
#                 raise AuthenticationFailed("Invalid or expired refresh token. Please log in again.")

#             user = User.objects.get(id=user_id)
#             request.user = user
#             return True

#         except ObjectDoesNotExist:
#             logger.debug("User not found for given token.")
#             raise AuthenticationFailed("Invalid or expired refresh token. Please log in again.")

#         except TokenError:
#             logger.debug("Invalid or expired access token.")
#             raise AuthenticationFailed("Access token expired. Please refresh your session.")

#         except Exception as e:
#             logger.error("Unexpected error during token authentication: %s", e)
#             raise AuthenticationFailed("Authentication failed. Please try again.")