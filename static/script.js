const STORAGE_KEY = "bcg-picker-guest-review-v1";
const MODE_KEY = "bcg-picker-review-mode-v1";
const REVIEWER_KEY = "bcg-picker-reviewer-v1";
const REVIEW_FILENAME_KEY = "bcg-picker-review-filename-v1";
let mode = localStorage.getItem(MODE_KEY) === "guest" ? "guest" : "example";
let exampleAnnotations = new Map();
let guestAnnotations = new Map();
let reviewerName = localStorage.getItem(REVIEWER_KEY) || "guest";
let guestReviewFilename = localStorage.getItem(REVIEW_FILENAME_KEY) || "";
let currentClick = null;
let zoom = 1;
let currentImageVariantIndex = 0;
const requestedFilter = new URLSearchParams(window.location.search).get("filter");
let filterMode = ["all", "skipped", "flagged"].includes(requestedFilter) ? requestedFilter : "all";

const img = document.getElementById("galaxy");
const marker = document.getElementById("marker");
const wrapper = document.getElementById("image-wrapper");
const noteInput = document.getElementById("object-note");
const statusText = document.getElementById("status");
const stateBadge = document.getElementById("annotation-state-badge");
const modeDescription = document.getElementById("review-mode-description");
const xValue = document.getElementById("x");
const yValue = document.getElementById("y");
const raValue = document.getElementById("ra");
const decValue = document.getElementById("dec");
const positionText = document.getElementById("cluster-position");
const catalogFilterSummary = document.getElementById("catalog-filter-summary");
const downloadButton = document.getElementById("download-results");
const angularScale = document.getElementById("angular-scale");
const angularScaleLabel = document.getElementById("angular-scale-label");
const angularScaleBar = document.getElementById("angular-scale-bar");
const clusterTitle = document.getElementById("cluster-title");
const clusterJumpInput = document.getElementById("cluster-jump-input");

function openClusterJump() {
    if (!clusterTitle || !clusterJumpInput) return;
    clusterTitle.hidden = true;
    clusterJumpInput.hidden = false;
    clusterJumpInput.value = String(currentCatalogIndex);
    clusterJumpInput.focus();
    clusterJumpInput.select();
}

function closeClusterJump() {
    if (!clusterTitle || !clusterJumpInput) return;
    clusterTitle.hidden = false;
    clusterJumpInput.hidden = true;
}

function jumpToCluster() {
    if (!clusterJumpInput) return;
    const match = clusterJumpInput.value.trim().match(/^(?:cluster)?0*(\d+)$/i);
    const targetIndex = match ? Number(match[1]) : NaN;
    if (!Number.isInteger(targetIndex) || targetIndex < 0 || targetIndex >= catalogRows.length) {
        setStatus("Enter a cluster number from 0 to " + String(catalogRows.length - 1) + ".");
        clusterJumpInput.focus();
        clusterJumpInput.select();
        return;
    }
    window.location.href = pageUrl(targetIndex);
}

function isTrue(value) {
    return String(value).trim().toLowerCase() === "true";
}

function annotationsFromRows(rows) {
    return new Map(rows.map((row) => [row.cluster, {
        ...row,
        skipped: isTrue(row.skipped),
        flagged: isTrue(row.flagged),
    }]));
}

function loadGuestAnnotations() {
    try {
        const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
        guestAnnotations = annotationsFromRows(saved);
    } catch (error) {
        guestAnnotations = new Map();
    }
}

function persistGuestAnnotations() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...guestAnnotations.values()]));
    localStorage.setItem(REVIEWER_KEY, reviewerName);
    localStorage.setItem(REVIEW_FILENAME_KEY, guestReviewFilename);
}

function activeAnnotations() {
    return mode === "example" ? exampleAnnotations : guestAnnotations;
}

function annotationForCurrentCluster() {
    return activeAnnotations().get(cluster);
}

function setStatus(message) {
    if (statusText) statusText.textContent = message || "";
}

function setBadge(state) {
    if (!stateBadge) return;
    stateBadge.className = "annotation-state-badge";
    const labels = {
        marked: ["annotation-state-saved", "Marked"],
        skipped: ["annotation-state-skipped", "Skip / unsure"],
        flagged: ["annotation-state-flagged", "Flagged"],
        none: ["annotation-state-none", "Not marked"],
    };
    const [className, label] = labels[state];
    stateBadge.classList.add(className);
    stateBadge.textContent = label;
}

function updateCoordinates(annotation) {
    if (!annotation || annotation.x === "" || annotation.x == null) {
        [xValue, yValue, raValue, decValue].forEach((element) => { if (element) element.textContent = "-"; });
        return;
    }
    xValue.textContent = Number(annotation.x).toFixed(1);
    yValue.textContent = Number(annotation.y).toFixed(1);
    raValue.textContent = Number(annotation.ra).toFixed(8);
    decValue.textContent = Number(annotation.dec).toFixed(8);
}

function renderMarker() {
    if (!img || !marker || !currentClick || !img.naturalWidth) {
        if (marker) marker.style.display = "none";
        return;
    }
    marker.style.left = `${(currentClick.x / img.naturalWidth) * img.clientWidth}px`;
    marker.style.top = `${(currentClick.y / img.naturalHeight) * img.clientHeight}px`;
    marker.style.display = "block";
}

function formatAngularScale(arcseconds) {
    if (arcseconds >= 60 && arcseconds % 60 === 0) return String(arcseconds / 60) + "′";
    return String(arcseconds) + "″";
}

function renderAngularScale() {
    const scaleArcsecPerPixel = Number(pixscale);
    if (!img || !angularScale || !angularScaleLabel || !angularScaleBar || !img.naturalWidth || !Number.isFinite(scaleArcsecPerPixel) || scaleArcsecPerPixel <= 0) {
        if (angularScale) angularScale.hidden = true;
        return;
    }
    const targetArcseconds = img.naturalWidth * scaleArcsecPerPixel * 0.18;
    const candidates = [1, 2, 5, 10, 20, 30, 60, 120, 300, 600];
    const arcseconds = candidates.reduce((best, candidate) => candidate <= targetArcseconds ? candidate : best, candidates[0]);
    angularScaleLabel.textContent = formatAngularScale(arcseconds);
    angularScaleBar.style.width = String((arcseconds / scaleArcsecPerPixel / img.naturalWidth) * 100) + "%";
    angularScale.hidden = false;
}

function showAnnotation() {
    const annotation = annotationForCurrentCluster();
    currentClick = annotation && !annotation.skipped && !annotation.flagged && annotation.x !== "" ? annotation : null;
    renderMarker();
    renderAngularScale();
    updateCoordinates(currentClick);
    if (noteInput) {
        noteInput.value = annotation?.note || "";
        noteInput.disabled = mode === "example";
    }
    if (!annotation) setBadge("none");
    else if (annotation.skipped) setBadge("skipped");
    else if (annotation.flagged) setBadge("flagged");
    else setBadge("marked");
}

function updateModeUi() {
    const exampleMode = mode === "example";
    if (downloadButton) downloadButton.textContent = exampleMode ? "Download taweewat results CSV" : "Download my results CSV";
    modeDescription.textContent = exampleMode
        ? "Viewing taweewat example annotations. This review is read-only."
        : "Guest review: your annotations stay in this browser until you download them.";
    document.getElementById("view-example").classList.toggle("active", exampleMode);
    const guestReviewButton = document.getElementById("view-guest-review");
    guestReviewButton.textContent = guestReviewFilename ? "View " + guestReviewFilename : "View my work";
    guestReviewButton.classList.toggle("active", !exampleMode);
    ["save", "skip-unsure", "flag-interesting", "next-unannotated", "clear-guest-review"].forEach((id) => {
        const button = document.getElementById(id);
        if (button) button.disabled = exampleMode;
    });
    if (img) img.classList.toggle("read-only-image", exampleMode);
    showAnnotation();
    updateProgress();
    updateFilterButtons();
    updateVisiblePosition();
}

function setMode(nextMode) {
    mode = nextMode;
    filterMode = "all";
    window.history.replaceState({}, "", pageUrl(currentCatalogIndex));
    updateFilterButtons();
    localStorage.setItem(MODE_KEY, mode);
    setStatus(nextMode === "guest" ? "Viewing your current review." : "Viewing taweewat example review.");
    updateModeUi();
}

function pixelToRaDec(x, y) {
    const x0 = img.naturalWidth / 2;
    const y0 = img.naturalHeight / 2;
    const dxArcsec = -(x - x0) * Number(pixscale);
    const dyArcsec = -(y - y0) * Number(pixscale);
    return {
        ra: Number(ra0) + dxArcsec / (3600 * Math.cos(Number(dec0) * Math.PI / 180)),
        dec: Number(dec0) + dyArcsec / 3600,
    };
}

function selectMarker(x, y) {
    const coordinates = pixelToRaDec(x, y);
    currentClick = { cluster, image, x, y, ...coordinates };
    updateCoordinates(currentClick);
    renderMarker();
    setBadge("marked");
}

function saveMarker() {
    if (mode !== "guest") return;
    if (!currentClick) { setStatus("Click the galaxy before saving a marker."); return; }
    guestAnnotations.set(cluster, {
        username: reviewerName,
        cluster,
        image,
        x: currentClick.x,
        y: currentClick.y,
        ra: currentClick.ra,
        dec: currentClick.dec,
        skipped: false,
        flagged: false,
        note: noteInput?.value.trim() || "",
        updated_at: new Date().toISOString(),
    });
    persistGuestAnnotations();
    updateProgress();
    setStatus("Saved in this browser.");
    showAnnotation();
    goToNextUnannotated();
}

function saveQuickStatus(kind) {
    if (mode !== "guest") return;
    guestAnnotations.set(cluster, {
        username: reviewerName, cluster, image, x: "", y: "", ra: "", dec: "",
        skipped: kind === "skipped", flagged: kind === "flagged",
        note: noteInput?.value.trim() || "", updated_at: new Date().toISOString(),
    });
    persistGuestAnnotations();
    updateProgress();
    setStatus(kind === "skipped" ? "Marked as skip / unsure." : "Marked as flagged.");
    showAnnotation();
    goToNextUnannotated();
}

function filteredPageUrl(index) {
    const suffix = filterMode === "all" ? "" : `?filter=${encodeURIComponent(filterMode)}`;
    return `${pageUrl(index)}${suffix}`;
}

function updateFilterButtons() {
    ["all", "skipped", "flagged"].forEach((name) => {
        document.getElementById(`filter-${name}`)?.classList.toggle("active", name === filterMode);
    });
}

function visibleRows() {
    const annotations = activeAnnotations();
    if (filterMode === "all") return catalogRows;
    return catalogRows.filter((row) => {
        const annotation = annotations.get(row.cluster);
        return filterMode === "skipped" ? annotation?.skipped : annotation?.flagged;
    });
}

function updateProgress() {
    const progress = { marked: 0, skipped: 0, flagged: 0 };
    activeAnnotations().forEach((annotation) => {
        if (annotation.skipped) progress.skipped += 1;
        else if (annotation.flagged) progress.flagged += 1;
        else if (annotation.x !== "" && annotation.x != null) progress.marked += 1;
    });
    document.getElementById("progress-marked").textContent = progress.marked;
    document.getElementById("progress-skipped").textContent = progress.skipped;
    document.getElementById("progress-flagged").textContent = progress.flagged;
    document.getElementById("progress-remaining").textContent = catalogRows.length - progress.marked - progress.skipped - progress.flagged;
}

function updateVisiblePosition() {
    const rows = visibleRows();
    const position = rows.findIndex((row) => row.cluster === cluster);
    const current = position >= 0 ? position + 1 : 0;
    if (positionText) positionText.textContent = `${current} / ${rows.length}`;
    if (catalogFilterSummary) {
        const labels = { all: "All targets", skipped: "Skip / unsure", flagged: "Flagged" };
        catalogFilterSummary.textContent = `${labels[filterMode]}: ${current} / ${rows.length}`;
    }
    ["previous-cluster", "next-cluster"].forEach((id) => {
        const button = document.getElementById(id);
        if (button) button.disabled = rows.length < 2;
    });
}

function goToVisibleOffset(offset) {
    const rows = visibleRows();
    if (!rows.length) { setStatus("No objects match this filter."); return; }
    let position = rows.findIndex((row) => row.cluster === cluster);
    if (position < 0) position = 0;
    const target = rows[(position + offset + rows.length) % rows.length];
    window.location.href = filteredPageUrl(catalogRows.findIndex((row) => row.cluster === target.cluster));
}

function goToNextUnannotated() {
    if (mode !== "guest") return;
    for (let offset = 1; offset <= catalogRows.length; offset += 1) {
        const nextIndex = (currentCatalogIndex + offset) % catalogRows.length;
        const target = catalogRows[nextIndex];
        if (!guestAnnotations.has(target.cluster)) {
            window.location.href = pageUrl(nextIndex);
            return;
        }
    }
    setStatus("All clusters are annotated in this guest review.");
}

function setFilter(nextFilter) {
    filterMode = nextFilter;
    updateFilterButtons();
    const rows = visibleRows();
    if (!rows.length) {
        setStatus(nextFilter === "skipped" ? "No skip / unsure targets selected yet." : "No flagged targets selected yet.");
        updateVisiblePosition();
        return;
    }
    const currentRow = rows.find((row) => row.cluster === cluster);
    const target = currentRow || rows[0];
    window.location.href = filteredPageUrl(catalogRows.findIndex((row) => row.cluster === target.cluster));
}

function setImageVariant(index) {
    if (!img || !imageVariants.length) return;
    currentImageVariantIndex = (index + imageVariants.length) % imageVariants.length;
    const variant = imageVariants[currentImageVariantIndex];
    img.src = `${assetPrefix}images/${variant.path}`;
    document.getElementById("current-image-variant").textContent = variant.label;
}

function parseCsv(text) {
    const rows = []; let row = []; let value = ""; let quoted = false;
    for (let index = 0; index < text.length; index += 1) {
        const character = text[index];
        if (character === "\"") { if (quoted && text[index + 1] === "\"") { value += "\""; index += 1; } else quoted = !quoted; }
        else if (character === "," && !quoted) { row.push(value); value = ""; }
        else if ((character === "\n" || character === "\r") && !quoted) { if (character === "\r" && text[index + 1] === "\n") index += 1; row.push(value); if (row.some((cell) => cell !== "")) rows.push(row); row = []; value = ""; }
        else value += character;
    }
    if (value || row.length) { row.push(value); rows.push(row); }
    const [headers, ...records] = rows;
    if (!headers) throw new Error("The CSV file is empty.");
    const required = ["cluster", "image", "x", "y", "ra", "dec", "skipped", "flagged"];
    if (required.some((name) => !headers.includes(name))) throw new Error("This file is not a compatible results CSV.");
    return records.map((record) => Object.fromEntries(headers.map((header, index) => [header, record[index] || ""])));
}

function csvEscape(value) {
    const text = String(value ?? "");
    return /[",\n\r]/.test(text) ? `"${text.replaceAll("\"", "\"\"")}"` : text;
}

function downloadResults() {
    const headers = ["username", "cluster", "image", "x", "y", "ra", "dec", "skipped", "flagged", "note", "updated_at"];
    const lines = [headers.join(","), ...[...activeAnnotations().values()].map((row) => headers.map((header) => csvEscape(row[header])).join(","))];
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    link.download = mode === "example" ? "taweewat_results.csv" : (guestReviewFilename || "guest_results.csv");
    link.click();
    URL.revokeObjectURL(link.href);
}

async function loadExample() {
    const response = await fetch(exampleResultsUrl);
    if (!response.ok) throw new Error("Could not load the taweewat example results.");
    const payload = await response.json();
    exampleAnnotations = annotationsFromRows(payload.annotations);
}

function wireEvents() {
    img?.addEventListener("load", () => { renderMarker(); renderAngularScale(); });
    img?.addEventListener("click", (event) => {
        if (mode !== "guest") { setStatus("The taweewat example is read-only. Select View my work to annotate."); return; }
        const rect = img.getBoundingClientRect();
        selectMarker((event.clientX - rect.left) * img.naturalWidth / rect.width, (event.clientY - rect.top) * img.naturalHeight / rect.height);
    });
    clusterTitle?.addEventListener("click", openClusterJump);
    clusterTitle?.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openClusterJump(); } });
    clusterJumpInput?.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); jumpToCluster(); } if (event.key === "Escape") { closeClusterJump(); } });
    clusterJumpInput?.addEventListener("blur", closeClusterJump);
    document.getElementById("view-example").onclick = () => setMode("example");
    document.getElementById("view-guest-review").onclick = () => setMode("guest");
    document.getElementById("save")?.addEventListener("click", saveMarker);
    document.getElementById("skip-unsure")?.addEventListener("click", () => saveQuickStatus("skipped"));
    document.getElementById("flag-interesting")?.addEventListener("click", () => saveQuickStatus("flagged"));
    document.getElementById("next-unannotated")?.addEventListener("click", goToNextUnannotated);
    document.getElementById("previous-cluster")?.addEventListener("click", () => goToVisibleOffset(-1));
    document.getElementById("next-cluster")?.addEventListener("click", () => goToVisibleOffset(1));
    document.getElementById("previous-image-variant")?.addEventListener("click", () => setImageVariant(currentImageVariantIndex - 1));
    document.getElementById("next-image-variant")?.addEventListener("click", () => setImageVariant(currentImageVariantIndex + 1));
    document.getElementById("zoom-reset")?.addEventListener("click", () => { zoom = 1; wrapper.style.transform = "scale(1)"; renderMarker(); });
    ["all", "skipped", "flagged"].forEach((name) => document.getElementById(`filter-${name}`).onclick = () => setFilter(name));
    document.getElementById("download-results").onclick = downloadResults;
    document.getElementById("clear-guest-review").onclick = () => { if (window.confirm("Clear this browser-only guest draft?")) { guestAnnotations = new Map(); guestReviewFilename = ""; persistGuestAnnotations(); setStatus("Local guest draft cleared."); updateModeUi(); } };
    document.getElementById("results-file").addEventListener("change", async (event) => {
        const file = event.target.files[0]; if (!file) return;
        try { const rows = parseCsv(await file.text()); reviewerName = rows.find((row) => row.username)?.username || "guest"; guestAnnotations = annotationsFromRows(rows); guestReviewFilename = file.name; persistGuestAnnotations(); setMode("guest"); setStatus(`Imported ${rows.length} annotations into this browser.`); } catch (error) { setStatus(error.message); } finally { event.target.value = ""; }
    });
    window.addEventListener("wheel", (event) => { if (!wrapper?.contains(event.target)) return; event.preventDefault(); zoom = Math.max(0.5, Math.min(5, zoom * (event.deltaY < 0 ? 1.1 : 1 / 1.1))); wrapper.style.transform = `scale(${zoom})`; renderMarker(); }, { passive: false });
    document.addEventListener("keydown", (event) => { if (["input", "textarea"].includes(event.target.tagName.toLowerCase())) return; const key = event.key.toLowerCase(); if (key === "s") saveMarker(); if (["n", "w"].includes(key)) saveQuickStatus("skipped"); if (["e", "g"].includes(key)) saveQuickStatus("flagged"); if (key === "u") goToNextUnannotated(); if (key === "j") setImageVariant(currentImageVariantIndex - 1); if (key === "k") setImageVariant(currentImageVariantIndex + 1); if (event.key === "ArrowLeft") goToVisibleOffset(-1); if (event.key === "ArrowRight") goToVisibleOffset(1); });
}

async function init() {
    loadGuestAnnotations();
    wireEvents();
    try { await loadExample(); updateModeUi(); } catch (error) { setStatus(error.message); }
}

init();
