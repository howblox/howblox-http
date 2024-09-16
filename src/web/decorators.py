import logging
from functools import wraps

from blacksheep import Request, unauthorized
from blacksheep.server.normalization import ensure_response

from config import CONFIG

UNAUTHORISED_RESPONSE = unauthorized("You are not authorized to use this endpoint.")


def authenticate():
    """Decorator to authenticate a request."""

    def decorator(handler):
        @wraps(handler)
        async def wrapped(*args, **kwargs):
            # In case we ever omit the server auth config, we forbid all requests.
            if not CONFIG.HTTP_BOT_AUTH:
                logging.error("No HTTP_BOT_AUTH was set! Blocking all requests.")
                return UNAUTHORISED_RESPONSE
            
            # Find the Request typed argument. Will not work if the handler does not want the Request obj.
            request = next((arg for arg in args if isinstance(arg, Request)), None)
            if request is None:
                return UNAUTHORISED_RESPONSE
            
            auth_header = (
                request.get_first_header(b"Authorization").decode()
                if request.has_header(b"Authorization")
                else None
            )
            if auth_header != CONFIG.HTTP_BOT_AUTH:
                return UNAUTHORISED_RESPONSE
            
            return ensure_response(await handler(*args, **kwargs))
        
        return wrapped
    
    return decorator