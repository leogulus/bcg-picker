# BCG Picker Setup

## Run Locally

Create and activate a Python environment, install Flask, then start the app:

```bash
conda create -n bcg-picker -y
conda activate bcg-picker
python -m pip install Flask
cp .env.example .env
python app.py
```

Open `http://127.0.0.1:5000/` in a browser.

## Access the Linux-Hosted App from a Mac

Use an SSH tunnel to access a BCG Picker instance running on a Linux server without exposing port 5000 to the network.

1. On the Linux server, start the app:

   ```bash
   python app.py
   ```

2. On the Mac, open Terminal and create the tunnel. Replace the login and hostname if needed:

   ```bash
   ssh -L 5000:127.0.0.1:5000 taweewat@chip.phys.sc.chula.ac.th
   ```

3. Keep the SSH Terminal session open, then open either URL in a Mac browser:

   ```text
   http://127.0.0.1:5000/
   http://localhost:5000/0
   ```

Closing the SSH session closes the tunnel and stops browser access from the Mac.

If port 5000 is unavailable on the Mac, use another local port, for example:

```bash
ssh -L 5050:127.0.0.1:5000 taweewat@chip.phys.sc.chula.ac.th
```

Then open `http://localhost:5050/`.

## Guest Review Workflow

The picker opens on the read-only `taweewat` example review by default. Guests can inspect its marked, flagged, and unsure objects without creating an account.

To begin their own work, a guest can choose **View my work** or import a previously downloaded results CSV. Their annotations are stored only in their browser until they use **Download my results CSV**. There is no login, password, or server-side guest-results storage.
