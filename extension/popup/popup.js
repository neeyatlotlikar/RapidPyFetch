console.log("Popup script loaded");

document.getElementById("startDemo").addEventListener("click", () => {
    console.log("Starting native download...");
    chrome.downloads.download({
        url: "https://example.com/file.zip",
        filename: "file.zip"
    });
    console.log("Native download initiated.");
});