const MAX_RETRIES = 3;
let retryCounts = {};

chrome.downloads.onCreated.addListener((delta) => {
    console.log("Download created:", delta);
    sendToNativeApp(delta.url, delta.filename);
    console.log("Sent to native app");
});

function sendToNativeApp(url, filename) {
    const port = chrome.runtime.connectNative("com.neeyatlotlikar.downloader");
    port.postMessage({ url, filename });
    port.onMessage.addListener((message) => {
        // handle progress or completion
        console.log("From native app:", message);
    });
}
