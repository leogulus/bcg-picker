let currentClick = null;

const img = document.getElementById("galaxy");
const marker = document.getElementById("marker");
const wrapper = document.getElementById("image-wrapper");
const xValue = document.getElementById("x");
const yValue = document.getElementById("y");
const raValue = document.getElementById("ra");
const decValue = document.getElementById("dec");
const progressBar = document.getElementById("progress-bar");
const progressText = document.getElementById("progress-text");
const statusText = document.getElementById("status");
const saveButton = document.getElementById("save");
const nextUnannotatedButton = document.getElementById("next-unannotated");
const downloadResultsButton = document.getElementById("download-results");
const downloadAllResultsButton = document.getElementById("download-all-results");
const zoomResetButton = document.getElementById("zoom-reset");
const uploadButton = document.getElementById("upload-btn");
const resetCatalogButton = document.getElementById("reset-catalog");
const uploadStatus = document.getElementById("upload-status");
const catalogFileInput = document.getElementById("catalog-file");

function pixelToRaDec(x, y, ra0, dec0, pixscale) {

    const x0 = img.naturalWidth / 2;
    const y0 = img.naturalHeight / 2;

    const dx_arcsec = -(x - x0) * pixscale;
    const dy_arcsec = -(y - y0) * pixscale;

    const ra =
        ra0 +
        dx_arcsec /
        (3600 * Math.cos(dec0 * Math.PI / 180));

    const dec =
        dec0 +
        dy_arcsec / 3600;

    return { ra, dec };
}

function renderMarker() {
    if (currentClick == null) {
        marker.style.display = "none";
        return;
    }

    const displayX = (currentClick.x / img.naturalWidth) * img.clientWidth;
    const displayY = (currentClick.y / img.naturalHeight) * img.clientHeight;

    marker.style.left = displayX + "px";
    marker.style.top = displayY + "px";
    marker.style.display = "block";
}

function updateMarker(x, y) {

    const { ra, dec } =
        pixelToRaDec(x, y, ra0, dec0, pixscale);

    xValue.textContent = x.toFixed(1);
    yValue.textContent = y.toFixed(1);

    raValue.textContent = ra.toFixed(8);
    decValue.textContent = dec.toFixed(8);

    currentClick = {
        cluster,
        image,
        x,
        y,
        ra,
        dec
    };

    renderMarker();
}

async function loadProgress() {
    const response = await fetch("/progress");
    const data = await response.json();

    const percent = (data.done / data.total) * 100;

    progressBar.value = percent;
    progressText.textContent =
        `${data.done} / ${data.total} done, ${data.skipped} skipped, ${data.remaining} remaining`;
}

function resetZoom() {
    zoom = 1;
    wrapper.style.transform = "scale(1)";
    renderMarker();
}

img.addEventListener("click", function(event){
    const rect = img.getBoundingClientRect();

    const scaleX = img.naturalWidth / rect.width;
    const scaleY = img.naturalHeight / rect.height;

    const x = (event.clientX - rect.left) * scaleX;
    const y = (event.clientY - rect.top) * scaleY;

    updateMarker(x, y);

});

saveButton.onclick = async function(){
    if(currentClick == null){
        alert("Please click on the galaxy first.");
        return;
    }

    try {
        const response = await fetch("/save",{
            method:"POST",
            headers:{
                "Content-Type":"application/json"
            },
            body: JSON.stringify({
                ...currentClick,
                index: currentIndex
            })
        });

        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.message || "Save failed");
        }

        statusText.textContent = result.next_url ? "Saved!" : "Saved! All clusters done for this user.";
        if (result.next_url) {
            setTimeout(() => {
                window.location.href = result.next_url;
            }, 300);
        }
        await loadProgress();
    } catch (error) {
        statusText.textContent = error.message;
    }
};

nextUnannotatedButton.onclick = async function() {
    try {
        const response = await fetch("/next_unannotated");
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.message || "Jump failed");
        }

        if (result.next_url) {
            window.location.href = result.next_url;
            return;
        }

        statusText.textContent = result.message || "All clusters are already annotated.";
    } catch (error) {
        statusText.textContent = error.message;
    }
};

downloadResultsButton.onclick = async function() {
    try {
        const response = await fetch("/download_results");
        if (!response.ok) {
            const result = await response.json();
            throw new Error(result.message || "Download failed");
        }

        const blob = await response.blob();
        const downloadUrl = URL.createObjectURL(blob);
        const link = document.createElement("a");
        const filename = currentUser ? `${currentUser}_results.csv` : "results.csv";
        link.href = downloadUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(downloadUrl);
    } catch (error) {
        statusText.textContent = error.message;
    }
};

downloadAllResultsButton.onclick = async function() {
    try {
        const response = await fetch("/download_all_results");
        if (!response.ok) {
            const result = await response.json();
            throw new Error(result.message || "Download failed");
        }

        const blob = await response.blob();
        const downloadUrl = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.download = "all_results.csv";
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(downloadUrl);
    } catch (error) {
        statusText.textContent = error.message;
    }
};

window.onload = async function() {

    await loadProgress();

    const response = await fetch("/load/" + cluster);
    const result = await response.json();

    if (!result.exists) return;

    if (result.skipped) {
        statusText.textContent = "Skipped";
        return;
    }

    if (result.x !== undefined && result.y !== undefined) {
        updateMarker(result.x, result.y);
        statusText.textContent = "Existing annotation loaded.";
    }

};

document.addEventListener("keydown", function(event) {
    
    if (event.key === "s") {
        saveButton.click();
    }

    if (event.key === "n") {
        fetch("/save", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                cluster: cluster,
                image: image,
                skipped: true,
                index: currentIndex
            })
        })
            .then(async (response) => {
                const result = await response.json();
                if (!response.ok) {
                    throw new Error(result.message || "Skip failed");
                }

                if (result.next_url) {
                    window.location.href = result.next_url;
                    return;
                }

                statusText.textContent = "Skipped! All clusters done for this user.";
                await loadProgress();
            })
            .catch((error) => {
                statusText.textContent = error.message;
            });
    }

    if (event.key === "u" || event.key === "U") {
        nextUnannotatedButton.click();
    }

    if (event.key === "ArrowLeft") {
        if (currentIndex > 0)
            window.location = "/" + (currentIndex - 1);
    }

    if (event.key === "ArrowRight") {
        if (currentIndex < total - 1)
            window.location = "/" + (currentIndex + 1);
    }

    if (event.key === "1") {
        resetZoom();
    }

});

let zoom = 1;

window.addEventListener("wheel", function(event) {
    if (!wrapper.contains(event.target)) {
        return;
    }

    event.preventDefault();

    if (event.deltaY < 0) {
        zoom *= 1.1;
    } else {
        zoom /= 1.1;
    }

    zoom = Math.min(Math.max(zoom, 0.5), 5);

    wrapper.style.transform = `scale(${zoom})`;
    renderMarker();
}, { passive: false });

zoomResetButton.onclick = resetZoom;

uploadButton.onclick = async function() {
    if (!catalogFileInput.files.length) {
        alert("Please select a CSV file");
        return;
    }

    const formData = new FormData();
    formData.append("file", catalogFileInput.files[0]);

    const response = await fetch("/upload_catalog", {
        method: "POST",
        body: formData
    });

    const result = await response.json();

    uploadStatus.textContent =
        response.ok
            ? `Loaded ${result.total} objects`
            : (result.message || "Upload failed");
};

resetCatalogButton.onclick = async function() {

    const response = await fetch("/reset_catalog", {
        method: "POST"
    });

    const result = await response.json();

    uploadStatus.textContent =
        `Loaded full catalog (${result.total} objects).`;

    window.location.href = "/0";
};
