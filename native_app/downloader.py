#!/usr/bin/env python3

# Another approach for interpreter specification can be
# #!/path/to/venv/bin/python
# hardcoding the path like this, however, can reduce portability
from nativemessenger import get_message
import subprocess
import time
import logging

# Setup logging
logging.basicConfig(
    filename="/home/autumn/Documents/Projects/RapidPyFetch/native_app/download.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


# Decorator for adding a logger to functions
def log_fun_call(func):
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
def download_file(url, output_name=None, connections=16, retries=5, wait_seconds=10):
    cmd = [
        "aria2c",
        "--max-connection-per-server=" + str(connections),
        "--split=" + str(connections),
        "--continue=true",
        "--dir=/home/autumn/Downloads/",
        url,
    ]
    if output_name:
        cmd.append("--out=" + output_name)

    for attempt in range(1, retries + 1):
        logging.info(f"Attempt {attempt} of {retries} for URL: {url}")
        result = subprocess.run(cmd)
        logging.info(result.stdout)
        logging.error(result.stderr)
        if result.returncode == 0:
            logging.info("✅ Download completed successfully.")
            return
        else:
            logging.warning(
                f"⚠️ Download failed on attempt {attempt}. Retrying in {wait_seconds} seconds..."
            )
            time.sleep(wait_seconds)
    else:
        logging.error("❌ All retry attempts failed.")


@log_fun_call
def main():
    message = get_message()
    url = message["url"]
    filename = message.get("filename")
    if url:
        download_file(url, filename)
    else:
        logging.error("No URL received from extension.")


if __name__ == "__main__":
    while True:
        main()
