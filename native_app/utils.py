import json
import logging
import socket
import struct
import sys
import time
from functools import wraps


# Decorator for adding a logger to functions
def log_fun_call(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.info(
            f"Calling function: {func.__name__} | Args: {args} | Kwargs: {kwargs}"
        )
        try:
            result = func(*args, **kwargs)
            logging.info(f"Function completed: {func.__name__} | Result: {result}")
            return result
        except Exception as e:
            logging.error(
                f"Function errored out: {func.__name__} | Error: {e}", exc_info=True
            )
            return None

    return wrapper


def get_message():
    """Native messaging protocol: receive a message from Chromium."""
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) == 0:
        raise EOFError
    message_length = struct.unpack("I", raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode("utf-8")
    return json.loads(message)


def send_message(message):
    """Native messaging protocol: send a message to Chromium."""
    encoded = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


@log_fun_call
def wait_for_aria2_rpc(host="localhost", port=6800, timeout=10):
    start = time.monotonic()
    while (time.monotonic() - start) < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False
