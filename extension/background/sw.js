const MAX_RETRIES = 3;
let retryCounts = {};
const port = chrome.runtime.connectNative("com.neeyatlotlikar.downloader");

chrome.downloads.onCreated.addListener((delta) => {
    console.log("Download created:", delta);
    if (delta.url) {
        // Cancel Chrome's own downloader immediately
        chrome.downloads.cancel(delta.id);

        port.postMessage({
            url: delta.finalUrl || delta.url,
            filename: delta.filename || undefined
        });

        port.onMessage.addListener((msg) => {
            console.log("Received message from native app:", msg);
            chrome.notifications.create({
                type: "basic",
                iconUrl: chrome.runtime.getURL("assets/icon128.png"),
                title: "Download Manager",
                message: `Status: ${msg.status} | ${msg.file || ""}`
            });
        });
    }
    console.log("Sent to native app");
});
