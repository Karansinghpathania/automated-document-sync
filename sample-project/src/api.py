"""Example API used to demonstrate documentation synchronization."""


def get_users():
    """Return all users."""
    return [{"id": "u-1", "name": "alice"}]


def get_user(user_id: str):
    """Return a single user by ID."""
    return {"id": user_id, "name": "alice"}


def get_user_by_email(email: str):
    """Return a user record by email lookup."""
    return {"email": email, "name": "alice"}