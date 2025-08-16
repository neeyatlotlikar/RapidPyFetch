#!/usr/bin/env python3

# Another approach for interpreter specification can be
# #!/path/to/venv/bin/python
# hardcoding the path like this, however, can reduce portability
import logging
import os
import subprocess
import time

import aria2p
import dotenv
from nativemessenger import get_message

# Setup logging
logging.basicConfig(
    filename="/home/autumn/Documents/Projects/RapidPyFetch/native_app/download.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

dotenv.load_dotenv()

ARIA2_RPC_SECRET = os.getenv("ARIA2_RPC_SECRET", "")
DOWNLOAD_PATH = os.getenv("DOWNLOAD_PATH", os.path.expanduser("~/Downloads"))


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
def add_download(api: aria2p.API, url, filename=None):
    options = {}
    if filename:
        options["out"] = filename
    # Add URI to aria2 queue
    download = api.add_uris([url], options=options)
    logging.info(f"Added download: {url} as {filename or 'default name'}")
    return download.gid


@log_fun_call
def monitor_download(api: aria2p.API, gid: str):
    while True:
        download = api.get_download(gid)
        status = download.status
        progress = download.progress_string()
        speed = download.download_speed_string()
        message = {
            "status": status,
            "gid": gid,
            "progress": progress,
            "speed": speed,
            "file": download.name,
        }
        logging.info(f"Download update: {message}")

        if status in ("complete", "error", "removed"):
            break

        time.sleep(1)

    return status


@log_fun_call
def main():
    cmd = [
        "aria2c",
        "--enable-rpc",
        "--rpc-listen-all",
        "--rpc-allow-origin-all",
        "--dir=" + DOWNLOAD_PATH,
    ]

    with subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    ):
        # Connect to the running aria2 RPC server
        aria2 = aria2p.API(
            aria2p.Client(
                host="http://localhost",
                port=6800,
                secret=ARIA2_RPC_SECRET,
            )
        )
        while True:
            try:
                msg = get_message()
            except EOFError:
                logging.info("EOF detected, shutting down helper")
                break

            url = msg["url"]
            filename = msg.get("filename")
            if not url:
                logging.info("main | status: error, message: No URL provided")
                continue

            gid = add_download(url, filename)
            if not gid:
                logging.info("main | status: error, message: Failed to add download")
                continue

            final_status = monitor_download(aria2, gid)
            logging.info(
                f"main | status: {final_status}, gid: {gid}, file: {filename or 'unknown'}"
            )


if __name__ == "__main__":
    main()
