function sendDownloadToNative(url, filename) {
    chrome.runtime.sendNativeMessage(
        'com.neeyatlotlikar.downloader',
        {
            command: 'add',
            url: url,
            filename: filename
        },
        (response) => {
            if (chrome.runtime.lastError) {
                console.error('Native message error:', chrome.runtime.lastError.message);
                return;
            }
            console.log('Response from native:', response);
            if (response.status === 'success') {
                console.log('Download initiated successfully.');
            } else {
                console.error('Failed to initiate download:', response.error);
            }
        }
    );
}

chrome.downloads.onCreated.addListener((delta) => {
    console.log("Download created:", delta);
    if (delta && delta.id && delta.url) {
        // Cancel Chrome's own downloader immediately
        chrome.downloads.cancel(delta.id, () => {
            if (chrome.runtime.lastError) {
                console.error("Could not cancel download:", chrome.runtime.lastError.message);
            } else {
                console.log("Chrome download canceled.");

                // Start native download only after cancel completes
                sendDownloadToNative(delta.finalUrl || delta.url, delta.filename);
                console.log("Sent to native app");
            }
        });
    }
});
