let currentClick = null;

const img = document.getElementById("galaxy");
const marker = document.getElementById("marker");
const wrapper = document.getElementById("image-wrapper");
const xValue = document.getElementById("x");
const yValue = document.getElementById("y");
const raValue = document.getElementById("ra");
const decValue = document.getElementById("dec");
const noteInput = document.getElementById("object-note");
const currentImageVariantText = document.getElementById("current-image-variant");
const currentUserSummary = document.getElementById("current-user-summary");
const annotationStateBadge = document.getElementById("annotation-state-badge");
const statusText = document.getElementById("status");
const saveButton = document.getElementById("save");
const skipUnsureButton = document.getElementById("skip-unsure");
const nextUnannotatedButton = document.getElementById("next-unannotated");
const flagInterestingButton = document.getElementById("flag-interesting");
const downloadResultsButton = document.getElementById("download-results");
const downloadAllResultsButton = document.getElementById("download-all-results");
const resetUserResultsButton = document.getElementById("reset-user-results");
const zoomResetButton = document.getElementById("zoom-reset");
const uploadButton = document.getElementById("upload-btn");
const resetCatalogButton = document.getElementById("reset-catalog");
const uploadStatus = document.getElementById("upload-status");
const catalogFileInput = document.getElementById("catalog-file");
const resultsFileInput = document.getElementById("results-file");
const importResultsButton = document.getElementById("import-results-btn");
const importResultsStatus = document.getElementById("import-results-status");
const filterAllButton = document.getElementById("filter-all");
const filterSkippedButton = document.getElementById("filter-skipped");
const filterFlaggedButton = document.getElementById("filter-flagged");
const downloadSkippedCatalogButton = document.getElementById("download-skipped-catalog");
const downloadFlaggedCatalogButton = document.getElementById("download-flagged-catalog");
const previousImageVariantButton = document.getElementById("previous-image-variant");
const nextImageVariantButton = document.getElementById("next-image-variant");
let currentImageVariantIndex = 0;

function pixelToRaDec(x, y, ra0, dec0, pixscale) {
    const numericX = Number(x);
    const numericY = Number(y);
    const numericRa0 = Number(ra0);
    const numericDec0 = Number(dec0);
    const numericPixscale = Number(pixscale);

    const x0 = img.naturalWidth / 2;
    const y0 = img.naturalHeight / 2;

    const dx_arcsec = -(numericX - x0) * numericPixscale;
    const dy_arcsec = -(numericY - y0) * numericPixscale;

    const ra =
        numericRa0 +
        dx_arcsec /
        (3600 * Math.cos(numericDec0 * Math.PI / 180));

    const dec =
        numericDec0 +
        dy_arcsec / 3600;

    return { ra, dec };
}

function renderMarker() {
    if (!img || currentClick == null || !img.naturalWidth || !img.naturalHeight) {
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
    const numericX = Number(x);
    const numericY = Number(y);

    const { ra, dec } =
        pixelToRaDec(numericX, numericY, ra0, dec0, pixscale);

    xValue.textContent = numericX.toFixed(1);
    yValue.textContent = numericY.toFixed(1);

    raValue.textContent = ra.toFixed(8);
    decValue.textContent = dec.toFixed(8);

    currentClick = {
        cluster,
        image,
        x: numericX,
        y: numericY,
        ra,
        dec
    };

    renderMarker();
}

function setImageVariant(index) {
    if (!img || !imageVariants.length) {
        return;
    }

    const totalVariants = imageVariants.length;
    currentImageVariantIndex = ((index % totalVariants) + totalVariants) % totalVariants;
    const variant = imageVariants[currentImageVariantIndex];
    img.src = `/images/${variant.path}`;
    if (currentImageVariantText) {
        currentImageVariantText.textContent = variant.label;
    }
}

function stepImageVariant(direction) {
    if (!imageVariants.length) {
        return;
    }
    setImageVariant(currentImageVariantIndex + direction);
}

function clearMarkerSelection() {
    currentClick = null;
    renderMarker();
    xValue.textContent = "-";
    yValue.textContent = "-";
    raValue.textContent = "-";
    decValue.textContent = "-";
}

function getCurrentNote() {
    if (!noteInput) {
        return "";
    }
    return noteInput.value.trim();
}

function setCurrentNote(note) {
    if (!noteInput) {
        return;
    }
    noteInput.value = note || "";
}

function setAnnotationState(state) {
    if (!annotationStateBadge) {
        return;
    }

    annotationStateBadge.className = "annotation-state-badge";
    if (state === "saved") {
        annotationStateBadge.classList.add("annotation-state-saved");
        annotationStateBadge.textContent = "Saved";
        return;
    }
    if (state === "skipped") {
        annotationStateBadge.classList.add("annotation-state-skipped");
        annotationStateBadge.textContent = "Skipped";
        return;
    }
    if (state === "flagged") {
        annotationStateBadge.classList.add("annotation-state-flagged");
        annotationStateBadge.textContent = "Flagged";
        return;
    }

    annotationStateBadge.classList.add("annotation-state-none");
    annotationStateBadge.textContent = "Not saved";
}

async function submitQuickStatus(payload, finalMessage) {
    const response = await fetch("/save", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            cluster: cluster,
            image: image,
            index: currentIndex,
            note: getCurrentNote(),
            ...payload
        })
    });
    const result = await response.json();
    if (!response.ok) {
        throw new Error(result.message || "Save failed");
    }

    clearMarkerSelection();
    await loadProgress();

    if (result.next_url) {
        window.location.href = result.next_url;
        return;
    }

    if (payload.skipped) {
        setAnnotationState("skipped");
    } else if (payload.flagged) {
        setAnnotationState("flagged");
    }
    statusText.textContent = finalMessage;
}

async function loadProgress() {
    const response = await fetch("/progress");
    const data = await response.json();
    if (currentUserSummary) {
        currentUserSummary.innerHTML =
            `Done: ${data.done}<br>` +
            `Skipped: ${data.skipped}<br>` +
            `Flagged: ${data.flagged}<br>` +
            `Remaining: ${data.remaining}`;
    }
}

function resetZoom() {
    zoom = 1;
    if (wrapper) {
        wrapper.style.transform = "scale(1)";
        renderMarker();
    }
}

function setActiveCatalogFilter(filterMode) {
    const filterButtons = [
        [filterAllButton, "all"],
        [filterSkippedButton, "skipped"],
        [filterFlaggedButton, "flagged"]
    ];

    for (const [button, buttonMode] of filterButtons) {
        if (!button) {
            continue;
        }
        button.classList.toggle("active", filterMode === buttonMode);
    }
}

async function applyCatalogFilter(filterMode) {
    try {
        const response = await fetch("/set_catalog_filter", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                filter_mode: filterMode,
                cluster: cluster
            })
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.message || "Could not update catalog filter");
        }

        setActiveCatalogFilter(result.filter_mode);
        window.location.href = result.next_url;
    } catch (error) {
        statusText.textContent = error.message;
    }
}

async function downloadCatalogSubset(filterMode) {
    try {
        const response = await fetch(`/download_catalog_subset/${filterMode}`);
        if (!response.ok) {
            const result = await response.json();
            throw new Error(result.message || "Download failed");
        }

        const blob = await response.blob();
        const downloadUrl = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.download = `${currentUser}_${filterMode}_catalog.csv`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(downloadUrl);
    } catch (error) {
        statusText.textContent = error.message;
    }
}

if (img) {
    img.addEventListener("load", function() {
        renderMarker();
    });

    img.addEventListener("click", function(event){
        const rect = img.getBoundingClientRect();

        const scaleX = img.naturalWidth / rect.width;
        const scaleY = img.naturalHeight / rect.height;

        const x = (event.clientX - rect.left) * scaleX;
        const y = (event.clientY - rect.top) * scaleY;

        updateMarker(x, y);

    });
}

if (saveButton) {
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
                note: getCurrentNote(),
                index: currentIndex
            })
        });

        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.message || "Save failed");
        }

        setAnnotationState("saved");
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
}

if (nextUnannotatedButton) {
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
}

if (downloadResultsButton) {
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
}

if (downloadAllResultsButton) {
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
}

if (flagInterestingButton) {
flagInterestingButton.onclick = async function() {
    try {
        await submitQuickStatus(
            { flagged: true },
            "Flagged! All clusters done for this user."
        );
    } catch (error) {
        statusText.textContent = error.message;
    }
};
}

if (skipUnsureButton) {
skipUnsureButton.onclick = async function() {
    try {
        await submitQuickStatus(
            { skipped: true },
            "Skipped! All clusters done for this user."
        );
    } catch (error) {
        statusText.textContent = error.message;
    }
};
}

if (resetUserResultsButton) {
    resetUserResultsButton.onclick = async function() {
        if (!currentUser) {
            statusText.textContent = "Set a user before resetting results.";
            return;
        }

        const confirmed = window.confirm(
            `Reset all saved results for user "${currentUser}" in the current catalog?`
        );
        if (!confirmed) {
            return;
        }

        try {
            const response = await fetch("/reset_user_results", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                }
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.message || "Reset failed");
            }

            clearMarkerSelection();
            statusText.textContent = `Reset results for ${result.username}.`;
            await loadProgress();
            window.location.reload();
        } catch (error) {
            statusText.textContent = error.message;
        }
    };
}

window.onload = async function() {
    setActiveCatalogFilter(currentFilterMode);
    if (imageVariants.length) {
        setImageVariant(0);
    }
    await loadProgress();

    if (!hasGalaxy) {
        return;
    }

    const response = await fetch("/load/" + cluster);
    const result = await response.json();

    if (!result.exists) {
        setCurrentNote("");
        return;
    }

    if (result.skipped) {
        clearMarkerSelection();
        setCurrentNote(result.note || "");
        setAnnotationState("skipped");
        statusText.textContent = "Skipped";
        return;
    }

    if (result.flagged) {
        clearMarkerSelection();
        setCurrentNote(result.note || "");
        setAnnotationState("flagged");
        statusText.textContent = "Flagged";
        return;
    }

    if (result.x !== undefined && result.y !== undefined) {
        updateMarker(result.x, result.y);
        setCurrentNote(result.note || "");
        setAnnotationState("saved");
        statusText.textContent = "Existing annotation loaded.";
    }
};

document.addEventListener("keydown", function(event) {
    if (!hasGalaxy) {
        return;
    }

    const targetTag = event.target && event.target.tagName
        ? event.target.tagName.toLowerCase()
        : "";
    if (["input", "textarea", "select"].includes(targetTag)) {
        return;
    }

    if (event.key === "s") {
        saveButton.click();
    }

    if (["n", "N", "w", "W"].includes(event.key)) {
        skipUnsureButton.click();
    }

    if (["e", "E", "g", "G"].includes(event.key)) {
        flagInterestingButton.click();
    }

    if (event.key === "u" || event.key === "U") {
        nextUnannotatedButton.click();
    }

    if (["j", "J", "d", "D"].includes(event.key)) {
        stepImageVariant(-1);
    }

    if (["k", "K", "f", "F"].includes(event.key)) {
        stepImageVariant(1);
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
    if (!wrapper || !wrapper.contains(event.target)) {
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

if (zoomResetButton) {
    zoomResetButton.onclick = resetZoom;
}

if (previousImageVariantButton) {
    previousImageVariantButton.onclick = function() {
        stepImageVariant(-1);
    };
}

if (nextImageVariantButton) {
    nextImageVariantButton.onclick = function() {
        stepImageVariant(1);
    };
}

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

if (filterAllButton) {
    filterAllButton.onclick = function() {
        applyCatalogFilter("all");
    };
}

if (filterSkippedButton) {
    filterSkippedButton.onclick = function() {
        applyCatalogFilter("skipped");
    };
}

if (filterFlaggedButton) {
    filterFlaggedButton.onclick = function() {
        applyCatalogFilter("flagged");
    };
}

if (downloadSkippedCatalogButton) {
    downloadSkippedCatalogButton.onclick = function() {
        downloadCatalogSubset("skipped");
    };
}

if (downloadFlaggedCatalogButton) {
    downloadFlaggedCatalogButton.onclick = function() {
        downloadCatalogSubset("flagged");
    };
}

if (importResultsButton) {
    importResultsButton.onclick = async function() {
        if (!resultsFileInput.files.length) {
            importResultsStatus.textContent = "Please select a reviewer results CSV.";
            return;
        }

        const submitImport = async function(replaceExisting) {
            const formData = new FormData();
            formData.append("file", resultsFileInput.files[0]);
            if (replaceExisting) {
                formData.append("replace_existing", "true");
            }

            const response = await fetch("/import_results", {
                method: "POST",
                body: formData
            });
            const result = await response.json();

            if (response.status === 409 && result.collision) {
                const confirmed = window.confirm(
                    `Results for "${result.username}" already exist. Replace the existing local file?`
                );
                if (!confirmed) {
                    importResultsStatus.textContent = "Import canceled.";
                    return;
                }
                await submitImport(true);
                return;
            }

            importResultsStatus.textContent = response.ok
                ? `Imported ${result.rows_imported} rows for ${result.username}${result.replaced ? " (replaced existing file)" : ""}.`
                : (result.message || "Import failed");
        };

        try {
            await submitImport(false);
        } catch (error) {
            importResultsStatus.textContent = error.message;
        }
    };
}
