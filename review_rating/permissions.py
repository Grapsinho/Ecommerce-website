from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsOwnerOrAdmin(BasePermission):
    """
    Custom permission for reviews:
    
    - Safe methods (GET, HEAD, OPTIONS) are allowed for everyone.
    - DELETE is allowed if the requesting user is either the owner of the review or an admin.
    - PUT/PATCH is allowed only if the requesting user is the review's owner.
      (Admins are not allowed to update someone else's review.)
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        if request.method == 'DELETE':
            return obj.user == request.user or request.user.is_staff

        # For update requests, only allow if the user is the owner
        return obj.user == request.user