#!/usr/bin/env python3

# Another approach for interpreter specification can be
# #!/path/to/venv/bin/python
# hardcoding the path like this, however, can reduce portability
from nativemessenger import get_message, send_message


def download_file(url, output):
    return f"Downloading {url} to {output}"


def main():
    message = get_message()
    url = message["url"]
    path = message.get("filename", "output.file")
    file_msg = download_file(url, path)
    send_message({"status": "done", "file": file_msg})


if __name__ == "__main__":
    while True:
        main()
