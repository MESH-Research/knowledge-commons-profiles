"""
A decorator that records a start time when the function is entered,

"""

import threading
import time
from functools import wraps

# thread-local storage for start-time stacks
_thread_locals = threading.local()


def get_elapsed() -> float:
    """
    Return the elapsed time (in seconds) since the current
    top-of-stack function was entered.
    """
    stack = getattr(_thread_locals, "start_times", [])
    if not stack:
        message = "get_elapsed() called outside of a @rest_timer function"
        raise RuntimeError(message)
    return time.perf_counter() - stack[-1]


def rest_timer(func):
    """
    Decorator that records a start time when the function is entered,
    and clears it when the function exits.  Use get_elapsed() inside
    the function to see how many seconds have passed so far.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # ensure we have a stack
        if not hasattr(_thread_locals, "start_times"):
            _thread_locals.start_times = []
        # push start time
        _thread_locals.start_times.append(time.perf_counter())
        try:
            return func(*args, **kwargs)
        finally:
            # pop start time when done
            _thread_locals.start_times.pop()

    return wrapper
