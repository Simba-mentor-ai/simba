"""
Logic shared by the web pages (views.py) and the JSON API (api.py).

The pages used to reach this logic by calling the site's own API over HTTP. Each such page then keeps two
Gunicorn workers busy (the page, and the API call it waits for); production has 4 workers, so 4 simultaneous
logins left no worker free for the API calls and froze the whole site until Gunicorn killed the workers after
240 s. Pages call these functions directly instead; the API endpoints call the same functions, so the API
answers exactly as before.
"""
import time
from http import HTTPStatus

from django.contrib.auth.hashers import check_password

from .eventTracking import loggedIn
from .models import User


def authenticate_user(username, password):
    """
    Checks a username and password and records the login event.
    Returns (status, data), the same answer as POST /api/auth/login:
    200 with the user's id, username and email, otherwise 401/404/500 with a message.
    """
    try:
        user = User.objects.get(username=username)
        if check_password(password, user.password_hash):
            if not user.is_email_verified:
                return HTTPStatus.UNAUTHORIZED, {"message": "Please verify your email address before logging in."}

            loggedIn(user, time.time())

            user_data = {
                "id": str(user.id),
                "username": user.username,
                "email": user.email
            }
            return HTTPStatus.OK, user_data
        else:
            return HTTPStatus.UNAUTHORIZED, {"message": "Invalid credentials."}
    except User.DoesNotExist:
        return HTTPStatus.NOT_FOUND, {"message": "User does not exist."}
    except Exception as e:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"message": f"Login failed: {str(e)}"}
