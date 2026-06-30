let currentClick = null;

const img = document.getElementById("galaxy");
const marker = document.getElementById("marker");

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

function updateMarker(x, y) {

    const rect = img.getBoundingClientRect();

    const scaleX = img.naturalWidth / rect.width;
    const scaleY = img.naturalHeight / rect.height;

    marker.style.left = (x / scaleX) + "px";
    marker.style.top = (y / scaleY) + "px";
    marker.style.display = "block";

    const { ra, dec } =
        pixelToRaDec(x, y, ra0, dec0, pixscale);

    document.getElementById("x").textContent = x.toFixed(1);
    document.getElementById("y").textContent = y.toFixed(1);

    document.getElementById("ra").textContent = ra.toFixed(8);
    document.getElementById("dec").textContent = dec.toFixed(8);

    currentClick = {
        cluster,
        image,
        x,
        y,
        ra,
        dec
    };
}

async function loadProgress() {

    const response = await fetch("/progress");
    const data = await response.json();

    console.log("progress:", data);  // IMPORTANT DEBUG

    const percent = (data.done / data.total) * 100;

    document.getElementById("progress-bar").value = percent;
    document.getElementById("progress-text").textContent =
        `${data.done} / ${data.total} done, ${data.skipped} skipped, ${data.remaining} remaining`;
}

function resetZoom() {
    zoom = 1;
    const wrapper = document.getElementById("image-wrapper");
    wrapper.style.transform = "scale(1)";
}

img.addEventListener("click", function(event){
    console.log("clicked", currentClick);
    const rect = img.getBoundingClientRect();

    const scaleX = img.naturalWidth / rect.width;
    const scaleY = img.naturalHeight / rect.height;

    const x = (event.clientX - rect.left) * scaleX;
    const y = (event.clientY - rect.top) * scaleY;

    updateMarker(x, y);

});

document.getElementById("save").onclick = async function(){

    if(currentClick == null){
        alert("Please click on the galaxy first.");
        return;
    }

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
    document.getElementById("status").textContent = "Saved!";
    if (result.next_url) {
        setTimeout(() => {
            window.location.href = result.next_url;
        }, 300);
    }
    await loadProgress();
};

window.onload = async function() {

    await loadProgress();

    const response = await fetch("/load/" + cluster);
    const result = await response.json();

    if (!result.exists) return;

    if (result.skipped) {
        document.getElementById("status").textContent = "Skipped";
        return;
    }

    if (result.x !== undefined && result.y !== undefined) {
        updateMarker(result.x, result.y);
        document.getElementById("status").textContent =
            "Existing annotation loaded.";
    }

};

document.addEventListener("keydown", function(event) {
    
    if (event.key === "s") {
        document.getElementById("save").click();
    }

    if (event.key === "n") {

        fetch("/save", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                cluster: cluster,
                image: image,
                skipped: true
            })
        }).then(() => {
            window.location.href = "/" + (currentIndex + 1);
        });
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

const wrapper = document.getElementById("image-wrapper");

window.addEventListener("wheel", function(event) {

    if (event.deltaY < 0) {
        zoom *= 1.1;
    } else {
        zoom /= 1.1;
    }

    zoom = Math.min(Math.max(zoom, 0.5), 5);

    wrapper.style.transform = `scale(${zoom})`;
});

document.getElementById("zoom-reset").onclick = resetZoom;

document.getElementById("upload-btn").onclick = async function() {

    const fileInput = document.getElementById("catalog-file");

    if (!fileInput.files.length) {
        alert("Please select a CSV file");
        return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    const response = await fetch("/upload_catalog", {
        method: "POST",
        body: formData
    });

    const result = await response.json();

    document.getElementById("upload-status").textContent =
        `Loaded ${result.total} objects`;
};

document.getElementById("reset-catalog").onclick = async function() {

    const response = await fetch("/reset_catalog", {
        method: "POST"
    });

    const result = await response.json();

    document.getElementById("upload-status").textContent =
        `Loaded full catalog (${result.total} objects).`;

    window.location.href = "/0";
};