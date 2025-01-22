import time
from functools import wraps


def throttle(wait_time: int = 0.1):
    def decorator(func):
        last_called = [0]

        @wraps(func)
        def wrapped(*args, **kwargs):
            current_time = time.time()
            if current_time - last_called[0] >= wait_time:
                result = func(*args, **kwargs)
                last_called[0] = current_time
                return result
        return wrapped
    return decorator