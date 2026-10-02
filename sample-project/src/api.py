"""Example API used to demonstrate documentation synchronization."""


def get_users():
    """Return all users."""
    
    return []

def get_user(user_id: str):
    return {"id": user_id, "name": "alice"}