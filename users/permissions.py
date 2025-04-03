from rest_framework.permissions import BasePermission
from rest_framework_simplejwt.tokens import AccessToken
from django.core.exceptions import ObjectDoesNotExist
from .models import User
from rest_framework_simplejwt.exceptions import TokenError


import logging

logger = logging.getLogger("rest_framework")

class IsAuthenticatedWithJWT(BasePermission):
    """
    Custom permission to authenticate users using JWT stored in HTTP-only cookies.
    """
    def has_permission(self, request, view):
        access_token = request.COOKIES.get('access_token')
        if not access_token:
            logger.debug("Access token not found in cookies.")
            return False

        try:
            # Validate and decode the access token
            token = AccessToken(access_token)
            user_id = token.get('user_id')
            if not user_id:
                logger.debug("No user_id claim in access token.")
                return False

            user = User.objects.get(id=user_id)
            request.user = user
            return True
        except (ObjectDoesNotExist, TokenError) as e:
            logger.debug("Token error or user not found: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error during token authentication: %s", e)
            return False