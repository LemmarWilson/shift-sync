"""
Custom authentication backends for ShiftSync.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailAuthenticationBackend(ModelBackend):
    """
    Authenticate users by email address instead of username.

    This allows users to log in using their email while still
    maintaining Django's standard authentication flow.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate a user by email address.

        Args:
            request: The HTTP request
            username: The email address (named username for compatibility)
            password: The user's password

        Returns:
            User instance if authentication succeeds, None otherwise
        """
        UserModel = get_user_model()

        if username is None:
            return None

        try:
            # Try to find user by email (case-insensitive)
            user = UserModel.objects.get(email__iexact=username)
        except UserModel.DoesNotExist:
            # Run the default password hasher to mitigate timing attacks
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            # If multiple users have the same email, get the first active one
            user = UserModel.objects.filter(email__iexact=username).order_by('id').first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
