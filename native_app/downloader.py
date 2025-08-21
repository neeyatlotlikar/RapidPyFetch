#!/home/autumn/Documents/Projects/RapidPyFetch/.venv/bin/python3
import logging
import os
import time
from threading import Thread

import aria2p
import dotenv
from utils import (
    get_message,
    send_message,
    log_fun_call,
    wait_for_network_probe,
)

dotenv.load_dotenv()

ARIA2_RPC_SECRET = os.getenv("ARIA2_RPC_SECRET", "")
DOWNLOAD_PATH = os.path.expanduser(os.getenv("DOWNLOAD_PATH", "~/Downloads"))
RPC_LISTEN_PORT = int(os.getenv("RPC_LISTEN_PORT", 6800))
LOG_PATH = os.path.expanduser(os.getenv("LOG_PATH", "~/Downloads/downloader.log"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
WAIT_SECS = int(os.getenv("WAIT_SECS", 5))
ARIA2_RPC_CONN_TIMEOUT = int(os.getenv("ARIA2_RPC_CONN_TIMEOUT", 10))
ARIA2_RPC_HOSTNAME = os.getenv("ARIA2_RPC_HOSTNAME", "http://localhost")


# Setup logging
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class DownloadManager:
    def __init__(self, api):
        """
        Initializes a DownloadManager instance.

        Args:
            api (aria2p.API): An instance of the aria2p API.

        Initializes the following instance variables:
            - api: The aria2p API.
            - monitor_thread: A thread to monitor the download progress.
            - download_url: A string to keep track of the download URL.
            - retry_count: An integer to keep track of the number of retries.
        """
        self.api = api
        self.monitor_thread = None
        self.download_url = ""
        self.retry_count = 0

    def __repr__(self):
        return (
            f"DownloadManager(api={self.api}, "
            f"monitor_thread={self.monitor_thread}, "
            f"download_url={self.download_url}, "
            f"retry_count={self.retry_count})"
        )

    @log_fun_call
    def add_download(self, url, filename=None):
        """
        Adds a download to the aria2 RPC server.

        Args:
            url (str): The URL of the download.
            filename (str, optional): The name of the output file. Defaults to None.

        Returns:
            aria2p.Download: The aria2p Download object representing the added download.

        This function adds a download to the aria2 RPC server and starts monitoring its progress.
        It also updates the download URL mapping and returns the added download object.
        """
        download: aria2p.Download = self.api.add_uris([url], options={"out": filename})
        self.start_monitor_thread(download.gid)
        self.download_url = url
        return download

    @log_fun_call
    def pause_download(self, gid):
        """
        Pauses a download with the given GID.

        Args:
            gid (str): The GID of the download to pause.

        This function retrieves the download with the given GID and pauses it using the aria2p API.
        If the download is not found, an error is logged.
        """
        download = self.api.get_download(gid)
        if download:
            download.pause()
            logging.info(f"Paused download {gid=}")
        else:
            logging.error(f"Download Not found {gid=}", exc_info=True)

    @log_fun_call
    def resume_download(self, gid):
        """
        Resumes a download with the given GID.

        Args:
            gid (str): The GID of the download to resume.

        This function retrieves the download with the given GID and resumes it using the aria2p API.
        If the download is not found, an error is logged.
        """
        download = self.api.get_download(gid)
        if download:
            download.resume()
            logging.info(f"Resumed download {gid=}")
        else:
            logging.error(f"Download Not found {gid=}", exc_info=True)

    @log_fun_call
    def remove_download(self, gid, options={}):
        """
        Removes a download with the given GID.

        Args:
            gid (str): The GID of the download to remove.
            options (dict): Optional parameters to pass to the aria2p.API.remove() method.

        Returns:
            list: A list of results from the aria2p.API.remove() method.

        This function retrieves the download with the given GID and removes it using the aria2p API.
        If the download is not found, a warning is logged.
        """
        download = self.api.get_download(gid)
        if download:
            remove_results = self.api.remove([download], **options)
            logging.info(f"Removed download {gid}")
            return remove_results
        else:
            logging.warning(f"Download Not found {gid=}", exc_info=True)

    @log_fun_call
    def retry_download(
        self, download: aria2p.Download, max_retries=MAX_RETRIES, wait_seconds=WAIT_SECS
    ):
        """
        Automatically retries a failed download using aria2p.

        Arguments:
        - download: aria2p Download object.
        - max_retries: Maximum number of retry attempts.
        - wait_seconds: Seconds to wait between retries.
        """

        while self.retry_count < max_retries:
            # Check current download status
            download = self.api.get_download(download.gid)
            if download.status != "error":
                logging.info(
                    f"Download {download.gid} status is '{download.status}', no retry needed."
                )
                return True

            wait_for_network_probe()

            logging.warning(
                f"Download {download.gid} failed (error). "
                f"Attempting retry {self.retry_count + 1} of {max_retries}."
            )

            try:
                # Remove the failed download from aria2 queue (but keep files)
                options = {"force": True, "files": False, "clean": True}
                remove_results = self.remove_download(download.gid, options)
                logging.info(f"Removed download {download.gid}: {remove_results}")

                # Stop monitoring the failed download
                self.monitor_threads.pop(download.gid, None)
                logging.info(f"Stopped monitoring download {download.gid=}")

                # Re-add the same URI with original output name
                new_download = self.add_download(self.download_url, download.name)
                logging.info(f"Re-added download as new GID: {new_download.gid}")

                # Wait before next status check
                time.sleep(wait_seconds)

                # Update download reference to new GID
                download = self.api.get_download(new_download.gid)

                if download.status == "active":
                    logging.info(f"Download {download.gid} restarted successfully.")
                    return True
            except Exception as e:
                logging.error(
                    f"Error while retrying download {download.gid}: {e}", exc_info=1
                )

            self.retry_count += 1
            time.sleep(wait_seconds)

        logging.error(f"All retry attempts exhausted for download {download.gid}.")
        return False

    @log_fun_call
    def start_monitor_thread(self, gid):
        """
        Starts a new thread to monitor the download with the given GID.

        Args:
            gid (str): The GID of the download to monitor.

        This function creates a new thread and starts it.
        The new thread calls the `monitor_download` function to continuously monitor the
        download status until it is complete or removed.

        Returns:
            None
        """
        thread = Thread(
            target=self.monitor_download,
            name=f"monitor-{gid}",
            args=(gid,),
            daemon=True,
        )
        thread.start()
        self.monitor_thread = thread
        logging.info(f"Started monitoring {thread=}")

    @log_fun_call
    def monitor_download(self, gid):
        """
        Monitor the status of a download until it is complete or removed.

        Args:
        - gid (str): The GID of the download to monitor.

        This function continuously queries the status of the download and sends status updates.
        If the download is complete or removed, the function stops monitoring.
        If the download fails with an error, the function attempts to retry the download automatically.
        The function sleeps for a short period before the next status update to avoid excessive CPU usage.
        """
        while True:
            # Get the current download status (need to fetch repeatedly for updates)
            download = self.api.get_download(gid)
            if not download:
                logging.warning(f"Download not found - {gid=}", exc_info=True)
                break
            # Stop monitoring if the download is complete
            if download.is_complete:
                break
            if download.status == "error":
                logging.warning(
                    f"Download failed - {gid=} {download.error_message}", exc_info=1
                )
                self.retry_download(download)
                break
            self.send_status_update(download)
            time.sleep(1)
        # Final update at the end
        self.send_status_update(download)

    # log_fun_call decorator not required here
    def send_status_update(self, download: aria2p.Download):
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
def process_command(mgr: DownloadManager, msg: dict):
    """
    Process a command received from the extension and perform the corresponding action on the download.

    Args:
        mgr (DownloadManager): The DownloadManager instance.
        msg (dict): The message received from the extension containing the command and its parameters.

    This function processes the command received from the extension and performs the corresponding action on the download.
    The supported commands are "add", "pause", "resume", "remove", and "list".

    JSON message format:

    1. Add a new download
    {
        "command": "add",
        "url": "http://example.com/file.zip",
        "filename": "file.zip"
    }

    2. Pause a download
    {
        "command": "pause",
        "gid": "TheGIDofDownload"
    }

    3. Resume a download
    {
        "command": "resume",
        "gid": "TheGIDofDownload"
    }

    4. Remove a download
    {
        "command": "remove",
        "gid": "TheGIDofDownload"
    }

    5. List all downloads
    {
        "command": "list"
    }


    Returns:
        None
    """
    cmd = msg.get("command", "").lower()
    gid = msg.get("gid")
    url = msg.get("url")
    filename = msg.get("filename")

    match cmd:
        case "add":
            if not url:
                logging.error(f"No URL provided for add command {msg=}", exc_info=1)
                return

            mgr.add_download(url, filename)
            send_message(
                {"status": "success", "message": "Download added successfully"}
            )

        case "pause":
            if not gid:
                logging.error(f"No GID provided for pause command {msg=}", exc_info=1)
                return

            mgr.pause_download(gid)

        case "resume":
            if not gid:
                logging.error(f"No GID provided for resume command {msg=}", exc_info=1)
                return

            mgr.resume_download(gid)

        case "remove":
            if not gid:
                logging.error(f"No GID provided for remove command {msg=}", exc_info=1)
                return

            mgr.remove_download(gid)

        case "list":
            downloads = mgr.api.get_downloads()
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
            logging.info(f"List of Downloads: {msg=}, downloads={data}")

        case _:
            logging.error(f"Unknown command {cmd=} {msg=}", exc_info=True)


if __name__ == "__main__":
    # Connect to the running aria2 RPC server
    aria2 = aria2p.API(
        aria2p.Client(
            host=ARIA2_RPC_HOSTNAME,
            port=RPC_LISTEN_PORT,
            secret=ARIA2_RPC_SECRET,
        )
    )

    dwnld_mgr = DownloadManager(aria2)
    msg = get_message()

    # Process the command received from the extension
    process_command(dwnld_mgr, msg)
