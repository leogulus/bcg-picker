# BCG Picker

BCG Picker is a lightweight Flask app for interactively identifying the Brightest Cluster Galaxy (BCG) in Legacy Survey image cutouts.

## Screenshot

![BCG Picker interface](screenshots/bcg-picker.png)

## Features

- Interactive image viewer for cluster cutouts
- Click-to-mark BCG selection
- Pixel-to-RA/Dec conversion
- Save and reload annotations from CSV
- Previous/next navigation and keyboard shortcuts
- Skip uncertain objects
- Progress tracking
- Upload a custom catalog and reset to the default catalog

## Requirements

- Python 3
- Flask

Install Flask with either:

```bash
pip install flask
```

or:

```bash
conda install flask
```

Or install from the repo manifest:

```bash
pip install -r requirements.txt
```

## Run the App

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000/
```

## Project Structure

```text
bcg-picker/
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
├── tests/
│   └── test_app.py
└── README.md
```

## Input Catalog

The catalog must contain these columns:

```text
cluster,image,ra,dec,redshift,pixscale
```

Example:

```csv
cluster,image,ra,dec,redshift,pixscale
Cluster0001,cluster000.jpg,3.17611983,-32.97124401,0.10,0.262
Cluster0002,cluster001.jpg,12.33456000,-41.12345000,0.56,0.262
```

Image filenames must correspond to files in `images/`.

## Annotation Workflow

1. Open the app.
2. Navigate to a cluster.
3. Zoom if needed using the mouse wheel.
4. Click the galaxy to place or move the marker.
5. Press `S` or click `Save`.
6. Press `N` to skip uncertain objects.

Existing annotations are automatically loaded when revisiting a cluster.

## Navigation

Open a cluster by index:

```text
http://127.0.0.1:5000/0
```

Open a cluster by cluster name:

```text
http://127.0.0.1:5000/cluster/Cluster0001
```

## Keyboard Shortcuts

| Shortcut | Action |
| --- | --- |
| Click image | Place or move marker |
| `S` | Save annotation |
| `N` | Skip current cluster |
| `←` | Previous cluster |
| `→` | Next cluster |
| `1` | Reset zoom to 1× |
| Mouse wheel | Zoom in / out |

## Results

Annotations are stored in `data/results.csv` with columns:

```text
cluster,image,x,y,ra,dec,skipped
```

Example:

```csv
cluster,image,x,y,ra,dec,skipped
Cluster0001,cluster000.jpg,479.6,489.3,3.17581,-32.97221,False
Cluster0002,,,,,,True
```

Saving an annotation for the same cluster overwrites the previous entry.

## Custom Catalogs

You can upload a custom CSV catalog as long as it uses the same column names as the default catalog and references images present in `images/`.

Use `Use Full Catalog` in the UI to restore the default dataset.

## Tests

Run the lightweight test suite with:

```bash
python -m unittest discover -s tests
```

## Notes

- The app is intended for local use.
- Images are never modified.
- Results are written to `data/results.csv`.
