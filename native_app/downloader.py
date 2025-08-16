#!/home/autumn/Documents/Projects/RapidPyFetch/.venv/bin/python3
import logging
import os
import subprocess
import time
from threading import Thread

import aria2p
import dotenv
from utils import get_message, log_fun_call, wait_for_aria2_rpc

dotenv.load_dotenv()

ARIA2_RPC_SECRET = os.getenv("ARIA2_RPC_SECRET", "")
DOWNLOAD_PATH = os.getenv("DOWNLOAD_PATH", os.path.expanduser("~/Downloads"))
RPC_LISTEN_PORT = int(os.getenv("RPC_LISTEN_PORT", 6800))
LOG_PATH = os.getenv("LOG_PATH", os.path.expanduser("~/Downloads/downloader.log"))

# Setup logging
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Track active monitoring threads by GID
monitor_threads = {}


def send_status_update(download):
    status = download.status
    progress = download.progress_string()
    speed = download.download_speed_string()
    message = {
        "status": status,
        "gid": download.gid,
        "progress": progress,
        "speed": speed,
        "file": download.name,
    }
    # Add notification logic here
    # TODO: Remove the logger as it is verbose and not necessary
    logging.info(f"send_status_update | Update: {message}")


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
        send_status_update(download)

        if download.is_complete or download.is_removed:
            # Stop monitoring if the download is complete or removed
            try:
                monitor_threads.pop(gid)
                logging.info(f"monitor_download | {gid}: Stopped monitoring download")
            except KeyError:
                logging.warning(
                    f"monitor_download | {gid}: Not monitoring this GID already"
                )
            break
        time.sleep(1)

    # Final update at the end
    send_status_update(download)


@log_fun_call
def start_monitor_thread(api: aria2p.API, gid: str):
    if gid in monitor_threads and monitor_threads[gid].is_alive():
        # Already monitoring
        return
    thread = Thread(target=monitor_download, args=(api, gid), daemon=True)
    monitor_threads[gid] = thread
    thread.start()


@log_fun_call
def process_command(api: aria2p.API, msg):
    cmd = msg.get("command", "").lower()
    gid = msg.get("gid")
    url = msg.get("url")
    filename = msg.get("filename")
    options = {}
    if filename:
        options["out"] = filename

    if cmd == "add":
        if not url:
            logging.error(f"process_command | {msg=}: No URL provided for add command")
            return
        try:
            download = api.add_uris([url], options=options)
            logging.info(
                f"process_command | {msg=}: Added download {download.gid=} {download.name=} - {url}"
            )
            start_monitor_thread(api, download.gid)
        except Exception as e:
            logging.error(
                f"process_command | {msg=}: Failed to add download: {e}", exc_info=True
            )

    elif cmd == "pause":
        if not gid:
            logging.error(
                f"process_command | {msg=}: No GID provided for pause command"
            )
            return
        try:
            download = api.get_download(gid)
            download.pause()
            logging.info(f"process_command | {msg=}: Paused download {gid}")
        except Exception as e:
            logging.error(
                f"process_command | {msg=}: Failed to pause {gid}: {e}", exc_info=True
            )

    elif cmd == "resume":
        if not gid:
            logging.error(
                f"process_command | {msg=}: No GID provided for resume command"
            )
            return
        try:
            download = api.get_download(gid)
            download.resume()
            logging.info(f"process_command | {msg=}: Resumed download {gid}")
            start_monitor_thread(gid)
        except Exception as e:
            logging.error(
                f"process_command | {msg=}: Failed to resume {gid}: {e}", exc_info=True
            )

    elif cmd == "remove":
        if not gid:
            logging.error(
                f"process_command | {msg=}: No GID provided for remove command"
            )
            return
        try:
            download = api.get_download(gid)
            download.remove(force=True)
            logging.info(f"process_command | {msg=}: Removed download {gid}")
        except Exception as e:
            logging.error(
                f"process_command | {msg=}: Failed to remove {gid}: {e}", exc_info=True
            )

    elif cmd == "list":
        downloads = api.get_downloads()
        data = []
        for d in downloads:
            data.append(
                {
                    "gid": d.gid,
                    "status": d.status,
                    "file": d.name,
                    "progress": d.progress_string(),
                    "speed": d.download_speed_string(),
                }
            )
        logging.info(f"process_command | {msg=}: status=list, downloads={data}")

    else:
        logging.error(f"process_command | {msg=}: Unknown command {cmd=}")


@log_fun_call
def main():
    cmd = [
        "aria2c",
        "--enable-rpc",
        "--rpc-listen-port=" + str(RPC_LISTEN_PORT),
        "--rpc-secret=" + ARIA2_RPC_SECRET,
        "--rpc-allow-origin-all=false",
        "--rpc-listen-all=false",  # Listen on localhost by default
        "--dir=" + DOWNLOAD_PATH,
    ]

    aria2_proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    try:
        logging.info(f"Started aria2c with PID {aria2_proc.pid}")

        if not wait_for_aria2_rpc(port=RPC_LISTEN_PORT, timeout=20):
            logging.error(
                f"Aria2 did not start in time. {aria2_proc.stderr=} {aria2_proc.stdout=}"
            )
            return
        # Connect to the running aria2 RPC server
        aria2 = aria2p.API(
            aria2p.Client(
                host="http://localhost",
                port=RPC_LISTEN_PORT,
                secret=ARIA2_RPC_SECRET,
            )
        )
        # Start the message loop
        while True:
            try:
                msg = get_message()
            except EOFError:
                logging.info("Browser disconnected, exiting helper.")
                break
            except Exception as e:
                logging.error(
                    f"process_command | {msg=}: Failed to get message: {e}",
                    exc_info=True,
                )
                continue

            process_command(aria2, msg)
    finally:
        aria2_proc.terminate()


if __name__ == "__main__":
    main()
