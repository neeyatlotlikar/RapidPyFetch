chrome.downloads.onCreated.addListener((delta) => {
    console.log("Download created:", delta);
    if (delta.url) {
        // Cancel Chrome's own downloader immediately
        chrome.downloads.cancel(delta.id);

        const port = chrome.runtime.connectNative('com.neeyatlotlikar.downloader');
        port.postMessage({
            "command": "add",
            "url": delta.finalUrl || delta.url,
            "filename": delta.filename || undefined
        });
        console.log("Sent to native app");
    }
});
