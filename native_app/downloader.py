#!/home/autumn/Documents/Projects/RapidPyFetch/.venv/bin/python3
import logging
import os
import subprocess
import time
from threading import Thread

import aria2p
import dotenv
from utils import get_message, log_fun_call, wait_for_aria2_rpc, wait_for_network_probe

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
download_url = {}
retry_count = {}


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
    logging.info(f"send_status_update | Update: {message}")


@log_fun_call
def auto_retry_failed_download(api, download, max_retries=3, wait_seconds=5):
    """
    Automatically retries a failed download using aria2p.

    Arguments:
    - api: aria2p.API instance connected to your aria2 RPC daemon.
    - download: aria2p Download object.
    - max_retries: Maximum number of retry attempts.
    - wait_seconds: Seconds to wait between retries.
    """
    url = download_url.get(download.gid)
    if not url:
        logging.error(
            f"auto_retry_failed_download | Download {download.gid} has no associated URI. Cannot retry."
        )
        return False

    while retry_count.get(url, 0) < max_retries:
        # Check current download status
        download = api.get_download(download.gid)
        if download.status != "error":
            logging.info(
                f"auto_retry_failed_download | Download {download.gid} status is '{download.status}'"
                ", no retry needed."
            )
            return True

        wait_for_network_probe()

        logging.warning(
            f"auto_retry_failed_download | Download {download.gid} failed (error). "
            f"Attempting retry {retry_count.get(url, 0) + 1} of {max_retries}."
        )

        try:
            # Remove the failed download from aria2 queue (but keep files)
            remove_results = api.remove([download], force=True, files=False, clean=True)
            logging.info(
                f"auto_retry_failed_download | Removed download {download.gid}: {remove_results}"
            )

            # Stop monitoring the failed download
            monitor_threads.pop(download.gid, None)
            logging.info(
                f"monitor_download | {download.gid}: Stopped monitoring download"
            )

            # Re-add the same URI with original output name
            new_download = api.add_uris([url], options={"out": download.name})
            start_monitor_thread(api, new_download.gid)
            download_url[new_download.gid] = url
            logging.info(
                f"auto_retry_failed_download | Re-added download as new GID: {new_download.gid}"
            )

            # Wait before next status check
            time.sleep(wait_seconds)

            # Update download reference to new GID
            download = api.get_download(new_download.gid)

            if download.status == "active":
                logging.info(
                    f"auto_retry_failed_download | Download {new_download.gid} restarted successfully."
                )
                return True
        except Exception as e:
            logging.error(
                f"auto_retry_failed_download | Exception while retrying download {download.gid}: {e}",
                exc_info=True,
            )

        retry_count[url] = retry_count.get(url, 0) + 1
        time.sleep(wait_seconds)

    logging.error(
        f"auto_retry_failed_download | All retry attempts exhausted for download {download.gid}."
    )
    return False


@log_fun_call
def cleanup_download(gid: str):
    """
    Clean up resources associated with a completed or failed download.

    Args:
        gid (str): The GID of the download to clean up.

    This function removes any references to the download from global dictionaries
    and performs any necessary cleanup actions.
    """
    mt = monitor_threads.pop(gid, None)
    logging.info(f"cleanup_download | Stopped monitoring download {mt=}")

    url = download_url.get(gid)
    if not url:
        logging.warning(f"monitor_download | Download {gid} has no associated URI.")
    else:
        if retry_count.get(url):
            logging.info(f"monitor_download | {gid}: Clear existing retry count {url=}")
            del retry_count[url]

        # Remove the download URL mapping
        del download_url[gid]

    logging.info(f"cleanup_download | Cleaned up resources for download {gid}")


@log_fun_call
def monitor_download(api: aria2p.API, gid: str):
    """
    Monitor the status of a download until it is complete or removed.

    Args:
    - api (aria2p.API): The aria2p API instance connected to the aria2 RPC daemon.
    - gid (str): The GID of the download to monitor.

    This function continuously queries the status of the download and sends status updates.
    If the download is complete or removed, the function stops monitoring.
    If the download fails with an error, the function attempts to retry the download automatically.
    The function sleeps for a short period before the next status update to avoid excessive CPU usage.
    """
    while True:
        download = api.get_download(gid)
        send_status_update(download)

        # Stop monitoring if the download is complete
        if download.is_complete:
            cleanup_download(gid)
            break

        if download.status == "error":
            logging.warning(
                f"monitor_download | {gid}: Download failed - {download.error_message}"
            )
            auto_retry_failed_download(api, download)
            break

        # Sleep for a while before the next status update
        time.sleep(1)

    # Final update at the end
    send_status_update(download)


@log_fun_call
def start_monitor_thread(api: aria2p.API, gid: str):
    """
    Starts a new thread to monitor the download with the given GID.

    Args:
        api (aria2p.API): The aria2p API instance connected to the aria2 RPC daemon.
        gid (str): The GID of the download to monitor.

    This function checks if the download is already being monitored and returns without
    starting a new thread if it is. Otherwise, it creates a new thread and starts it.
    The new thread calls the `monitor_download` function to continuously monitor the
    download status until it is complete or removed.

    Returns:
        None
    """
    if gid in monitor_threads and monitor_threads[gid].is_alive():
        # Already monitoring
        return
    thread = Thread(
        target=monitor_download, name=f"monitor-{gid}", args=(api, gid), daemon=True
    )
    monitor_threads[gid] = thread
    thread.start()


@log_fun_call
def process_command(api: aria2p.API, msg):
    """
    Process a command received from the extension and perform the corresponding action on the download.

    Args:
        api (aria2p.API): The aria2p API instance connected to the aria2 RPC daemon.
        msg (dict): The message received from the extension containing the command and its parameters.

    This function processes the command received from the extension and performs the corresponding action on the download.
    The supported commands are "add", "pause", "resume", "remove", and "list".

    Returns:
        None
    """
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
            download_url[download.gid] = url
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
            cleanup_download(gid)
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
    """
    The main function that runs the aria2 RPC server and handles browser
    messages.

    Starts the aria2 RPC server, connects to it, and enters a message loop
    where it waits for messages from the browser extension. For each message,
    it processes the command and updates the aria2 RPC server accordingly.

    The function terminates the aria2 RPC server when it finishes.
    """
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
