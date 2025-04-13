from rest_framework.permissions import BasePermission


class IsOwnerOrAdmin(BasePermission):
    """
    Custom permission that restricts product modifications to the owner or an admin.
    
    - **Owner Access**: Grants permission if the current user is the product's seller.
    - **Admin Access**: Grants permission if the current user has admin rights (is_staff=True).
    
    This permission should be applied to update, partial_update, and delete actions.
    """
    def has_object_permission(self, request, view, obj):
        print(request.user)
        return (request.user == obj.seller) or request.user.is_staff