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

img.addEventListener("click", function(event){

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
        body:JSON.stringify(currentClick)
    });

    const result = await response.json();
    document.getElementById("status").textContent =
        "Saved!";
};

window.onload = async function(){

    const response =
        await fetch("/load/" + cluster);

    const result =
        await response.json();

    if(result.exists){
        updateMarker(result.x, result.y);
        document.getElementById("status").textContent =
            "Existing annotation loaded.";
    }

};