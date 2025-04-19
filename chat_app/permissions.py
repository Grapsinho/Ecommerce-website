from rest_framework import permissions


class IsChatParticipant(permissions.BasePermission):
    """
    Allows access only to chat participants or staff.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        return obj.buyer == user or obj.owner == user or user.is_staff