# Fixtrnc

Flask app for the Fixtrnc repair service website.

## Run locally

Install Flask, set the admin credentials in your environment, then run `python app.py`.

Set `FIXTRNC_ADMIN_PASSWORDS` to two or more passwords separated by commas to allow multiple admins. Set `FLASK_SECRET_KEY` to a long, random, stable value. The app runs on port 7878; open `http://127.0.0.1:7878/` for the site and `/admin` to review technician applications.

Technician applications are stored locally in `technician_applications.json`. That file is ignored by Git because it may contain personal information. The virtual environment and IDE settings are also excluded.
