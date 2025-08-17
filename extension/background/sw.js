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
                const port = chrome.runtime.connectNative('com.neeyatlotlikar.downloader');
                port.postMessage({
                    "command": "add",
                    "url": delta.finalUrl || delta.url,
                    "filename": delta.filename || undefined
                });
                console.log("Sent to native app");
            }
        });
    }
});
