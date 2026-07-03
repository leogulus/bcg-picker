# BCG Picker

BCG Picker is a lightweight Flask app for interactively identifying the Brightest Cluster Galaxy (BCG) in Legacy Survey image cutouts.

It now uses SQLite for shared catalog storage and per-user annotations, so multiple people can work on the same cluster set while keeping separate results.

## Screenshot

![BCG Picker interface](screenshots/bcg-picker.png)

## Features

- Interactive image viewer for cluster cutouts
- Click-to-mark BCG selection
- Pixel-to-RA/Dec conversion from the selected marker
- Marker placement that stays aligned while zooming
- Save and reload annotations per active user
- Skip uncertain objects
- Progress tracking for the active user only
- Jump to the next unannotated cluster for the current user
- Download the current user's partial results as CSV at any time
- Download all users' raw annotations as a combined CSV from the admin tools area
- Upload a custom catalog and reset to the default catalog
- Existing-user picker plus simple new-user creation in the UI

## Requirements

- Python 3
- Flask

Install from the repo manifest:

```bash
pip install -r requirements.txt
```

Or install Flask directly:

```bash
pip install flask
```

## Run the App

Start the app with:

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
├── db.py
├── data/
│   ├── catalog.csv
│   └── bcg_picker.sqlite3
├── images/
├── static/
│   ├── script.js
│   └── style.css
├── templates/
│   └── index.html
├── tests/
│   └── test_app.py
├── schema.sql
├── requirements.txt
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

## SQLite Setup

The app uses SQLite to store:

- catalog rows
- user records
- per-user annotations

Initialize the database with:

```bash
flask --app app init-db
```

Import the default catalog into SQLite with:

```bash
flask --app app import-catalog
```

If the database is empty, the app can also seed the default catalog automatically at startup.

SQLite data is stored in `data/bcg_picker.sqlite3`.

## User Workflow

1. Open the app.
2. Choose an existing user from the dropdown, or enter a new username.
3. Navigate to a cluster.
4. Zoom if needed using the mouse wheel.
5. Click the galaxy to place or move the marker.
6. Press `S` or click `Save`.
7. Press `N` to skip an uncertain object.
8. Use `Next Unannotated` or press `U` to jump to the next remaining cluster for that user.
9. Use `Download Results CSV` anytime to export the current user's current results.

Each user sees only their own saved positions, skip states, and progress counts.

## Admin Tools

The right-side panel includes a small admin area with:

- `Download All Results CSV`
- `Review All Results`

That button downloads the combined raw annotations across all users as:

```text
all_results.csv
```

The review page groups annotations by cluster, shows each user's saved position or skip state, and highlights clusters where users disagree.

Clicking a reviewed cluster opens a detail page that:

- displays the cluster image
- overlays all non-skipped user markers on the same image
- assigns a different color to each user marker
- shows a legend so you can match colors to users

For review purposes, two marked positions are treated as agreement when their separation is `<= 1.5` arcsec. The comparison uses the small-angle approximation:

```text
sqrt((delta_RA)^2 + (delta_Dec)^2)
```

with `RA` and `Dec` both in degrees.

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
| `U` | Jump to next unannotated cluster |
| `←` | Previous cluster |
| `→` | Next cluster |
| `1` | Reset zoom to 1× |
| Mouse wheel | Zoom in / out |

## Results Export

Downloaded annotation exports use columns:

```text
cluster,image,x,y,ra,dec,skipped
```

Example:

```csv
cluster,image,x,y,ra,dec,skipped
Cluster0001,cluster000.jpg,479.6,489.3,3.17581,-32.97221,False
Cluster0002,,,,,,True
```

Saving an annotation for the same user and cluster overwrites that user's previous entry.

The download filename is based on the current user, for example:

```text
alice_results.csv
```

The admin export includes:

```text
username,cluster,image,x,y,ra,dec,skipped,updated_at
```

## Custom Catalogs

You can upload a custom CSV catalog as long as it uses the same column names as the default catalog and references images present in `images/`.

Use `Use Full Catalog` in the UI to restore the default dataset.

Custom and default catalogs are tracked as separate catalog sources in SQLite.

## Tests

Run the lightweight test suite with:

```bash
python -m unittest discover -s tests
```

You can also do a quick syntax check with:

```bash
python -m py_compile app.py db.py tests/test_app.py
```

## Notes

- The app is intended for local use right now.
- Images are never modified.
- RA/Dec is derived from the stored marker position and the catalog center coordinates.
- The current user must be set before saving, skipping, jumping, or downloading results.
