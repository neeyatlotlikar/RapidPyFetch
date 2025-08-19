import json
import logging
import socket
import struct
import sys
import time
from functools import wraps


# Decorator for adding a logger to functions
def log_fun_call(func):
    """
    Decorator that logs the function call, its arguments, and its result. If the function
    raises an exception, it logs the error and returns None.

    Args:
        func (function): The function to be decorated.

    Returns:
        function: The wrapper function that logs the function call and result.
    """

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


@log_fun_call
def get_message():
    """Native messaging protocol: receive a message from Chromium."""
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) == 0:
        raise EOFError
    message_length = struct.unpack("I", raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode("utf-8")
    return json.loads(message)


@log_fun_call
def send_message(message):
    """Native messaging protocol: send a message to Chromium."""
    encoded = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


@log_fun_call
def is_network_reachable(host="8.8.8.8", port=53, timeout=3):
    """
    Checks if the network is reachable by establishing a TCP connection to a known reliable host.

    Args:
        host (str): IP address to probe (default: Google's DNS 8.8.8.8).
        port (int): Port to connect to (default: 53 DNS service).
        timeout (int): Timeout in seconds for the connect call.

    Returns:
        bool: True if reachable, False otherwise.
    """
    try:
        socket.setdefaulttimeout(timeout)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((host, port))
        return True
    except OSError:
        return False


@log_fun_call
def wait_for_network_probe(
    host="8.8.8.8",
    port=53,
    timeout=3,
    retry_interval=5,
    max_wait=None,
):
    """
    Periodically probes the network until it is reachable.

    Args:
        host (str): Host to probe (default: 8.8.8.8).
        port (int): Port to probe (default: 53).
        timeout (int): Timeout for each probe in seconds.
        retry_interval (int): Seconds to wait between retries.
        max_wait (int|None): Maximum seconds to wait (None = forever).

    Returns:
        bool: True if network is reachable, False if timed out.
    """
    start_time = time.time()

    while True:
        if is_network_reachable(host, port, timeout):
            logging.info(f"Network reachable via {host}:{port}")
            return True
        else:
            logging.warning(f"Network unreachable; retrying in {retry_interval}s...")
            time.sleep(retry_interval)

        if max_wait is not None:
            elapsed = time.time() - start_time
            if elapsed >= max_wait:
                logging.error("Network probe timed out.")
                return False
