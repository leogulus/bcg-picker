# BCG Picker

A lightweight web application for interactively identifying the Brightest Cluster Galaxy (BCG) in Legacy Survey image cutouts.

## Features

- Display PNG cutouts from the Legacy Survey
- Click to select the BCG
- Convert image coordinates to RA/Dec
- Save annotations to CSV
- Reload existing annotations for editing

## Requirements

- Python 3
- Flask

Install flask:  

```bash
conda install flask
```

Run:

```bash
python app.py
```

Open:

```
http://127.0.0.1:5000
```

# BCG Picker

BCG Picker is a lightweight Flask web application for interactively identifying the Brightest Cluster Galaxy (BCG) in Legacy Survey images. Users click on an image to place a marker, which is converted into sky coordinates (RA/Dec) and saved for later analysis.

The application is designed for fast manual annotation of galaxy clusters and can be easily customized with different input catalogs.

---

## Features

- Interactive image viewer
- Click to place a BCG marker
- Automatic conversion from pixel coordinates to RA/Dec
- Save annotations to CSV
- Automatically reload previous annotations
- Previous/Next navigation
- Keyboard shortcuts for efficient annotation
- Skip uncertain objects
- Progress tracking
- Upload a custom catalog (subset of the original catalog)
- Return to the full catalog with one click

---

## Installation

Clone the repository:

```bash
git clone https://github.com/your-username/bcg-picker.git
cd bcg-picker
```

Create a virtual environment (optional):

```bash
python -m venv venv
source venv/bin/activate
```

Install the required packages:

```bash
pip install flask
```

Run the application:

```bash
python app.py
```

Open your browser at:

```
http://127.0.0.1:5000/
```

---

## Project Structure

```
bcg-picker/
│
├── app.py
├── data/
│   ├── catalog.csv
│   └── results.csv
├── images/
├── static/
│   ├── script.js
│   └── style.css
├── templates/
│   └── index.html
└── README.md
```

---

## Input Catalog

The application reads a CSV file containing one row per cluster.

Required columns:

```
cluster,image,ra,dec,redshift,pixscale
```

Example:

```csv
cluster,image,ra,dec,redshift,pixscale
Cluster0001,cluster000.jpg,3.17611983,-32.97124401,0.10,0.262
Cluster0002,cluster001.jpg,12.33456000,-41.12345000,0.56,0.262
```

The image filenames must correspond to files in the `images/` directory.

---

## Annotation Workflow

1. Open the application.
2. Navigate to the desired cluster.
3. Zoom if needed using the mouse wheel.
4. Click on the brightest cluster galaxy to place a marker.
5. Press **S** or click **Save**.
6. The annotation is saved and, if enabled, the application automatically advances to the next cluster.

If the correct BCG cannot be confidently identified, press **N** to skip the object.

---

## Navigation

The application supports two ways to navigate directly to a specific cluster.

### By index

Open a cluster by its position in the currently loaded catalog:

```
http://127.0.0.1:5000/0
```

The first cluster has index `0`, the second has index `1`, and so on.

For example:

```
http://127.0.0.1:5000/125
```

opens the 126th cluster in the current catalog.

### By cluster name

Open a cluster directly using its cluster identifier:

```
http://127.0.0.1:5000/cluster/Cluster0001
```

For example:

```
http://127.0.0.1:5000/cluster/Cluster0157
```

This works regardless of the cluster's position in the catalog, provided it exists in the currently loaded catalog.

## Keyboard Shortcuts

| Shortcut | Action |
|-----------|--------|
| **Click image** | Place or move marker |
| **S** | Save annotation |
| **N** | Skip current cluster |
| **←** | Previous cluster |
| **→** | Next cluster |
| **1** | Reset zoom to 1× |
| **Mouse wheel** | Zoom in / out |

---

## Results

Annotations are stored in:

```
data/results.csv
```

Columns:

```
cluster,image,x,y,ra,dec,skipped
```

Example:

```csv
cluster,image,x,y,ra,dec,skipped
Cluster0001,cluster000.jpg,479.6,489.3,3.17581,-32.97221,False
Cluster0002,,,,,,True
```

Objects marked as skipped are recorded with `skipped=True`.

---

## Custom Catalogs

You may upload a custom `catalog.csv` containing any subset of the original catalog.

Requirements:

- Same column names as the original catalog
- Image filenames must exist in the `images/` directory

The uploaded catalog replaces the currently loaded catalog for the current session.

To return to the original dataset, click **Use Full Catalog**.

---

## Notes

- The application is intended for local use.
- Images are not modified.
- Existing annotations are automatically loaded when revisiting a cluster.
- Saving an annotation for the same cluster overwrites the previous entry.

---

## Future Improvements

Potential future features include:

- SQLite backend
- Multi-user annotation
- Review mode
- Confidence scores
- Pan and advanced image navigation
- Session management

---

## Author

Developed for interactive annotation of Brightest Cluster Galaxies (BCGs) in optical survey images.

