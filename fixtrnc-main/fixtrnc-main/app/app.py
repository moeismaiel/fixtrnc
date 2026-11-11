import hmac
import json
import os
import secrets
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, abort
from dataclasses import dataclass, field
from typing import List
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
ADMIN_PASSWORDS = [password.strip() for password in os.environ.get(
    "FIXTRNC_ADMIN_PASSWORDS", os.environ.get("FIXTRNC_ADMIN_PASSWORD", "")
).split(",") if password.strip()]


CATEGORIES = [
    "AC Repair", "Washing Machine", "Dishwasher",
    "Painting", "Plumbing", "Electrician", "TV Repair",
]
REGIONS = ["Nicosia", "Kyrenia", "Famagusta", "Morphou", "Iskele", "Lefke"]


@dataclass
class Professional:
    name: str
    phone: str
    category: str
    region: str
    description: str = ""
    approved: bool = False
    application_id: str = field(default_factory=lambda: secrets.token_urlsafe(12))
    persistent: bool = False
    profile_image: str = ""

    @property
    def digits(self) -> str:
        return "".join(c for c in self.phone if c.isdigit())

    @property
    def whatsapp_link(self) -> str:
        digits = self.digits
        if digits.startswith("0"):
            digits = "90" + digits[1:]
        elif not digits.startswith("90"):
            digits = "90" + digits
        return f"https://wa.me/{digits}"

    @staticmethod
    def is_valid_phone(phone: str) -> bool:
        return sum(c.isdigit() for c in phone) >= 10


PROFESSIONALS = [
    Professional("Demo Technician One", "0000000000", "Plumbing", "Kyrenia", "Sample profile for demonstration.", approved=True),
    Professional("Demo Technician Two", "0000000000", "AC Repair", "Nicosia", "Sample profile for demonstration.", approved=True),
]
APPLICATIONS_FILE = Path(__file__).with_name("technician_applications.json")

def save_professionals():
    APPLICATIONS_FILE.write_text(
        json.dumps([p.__dict__ for p in PROFESSIONALS if p.persistent], indent=2),
        encoding="utf-8",
    )

def load_applications():
    if not APPLICATIONS_FILE.exists():
        return
    try:
        records = json.loads(APPLICATIONS_FILE.read_text(encoding="utf-8"))
        for record in records:
            PROFESSIONALS.append(Professional(**record))
    except (OSError, ValueError, TypeError):
        app.logger.exception("Could not load saved technician applications")

load_applications()

@app.route("/")
def index():
    region_filter = request.args.get("region", "All")
    category_filter = request.args.get("category", "All")

    # Filter approved professionals
    filtered = [p for p in PROFESSIONALS if p.approved]

    if region_filter != "All":
        filtered = [p for p in filtered if p.region == region_filter]
    if category_filter != "All":
        filtered = [p for p in filtered if p.category == category_filter]

    return render_template(
        "index.html",
        professionals=filtered,
        categories=CATEGORIES,
        regions=REGIONS,
        selected_region=region_filter,
        selected_category=category_filter,
        pending_professionals=[p for p in PROFESSIONALS if not p.approved]
    )

@app.route("/register", methods=["POST"])
def register():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    category = request.form.get("category", "")
    region = request.form.get("region", "")
    description = request.form.get("description", "").strip()
    photo = request.files.get("profile_image")
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    photo_extension = Path(secure_filename(photo.filename or "")).suffix.lower() if photo else ""
    has_photo = bool(photo and photo.filename)

    if (name and phone and Professional.is_valid_phone(phone)
            and category in CATEGORIES and region in REGIONS
            and (not has_photo or photo_extension in allowed_extensions)):
        profile_image = ""
        if has_photo:
            upload_dir = Path(app.static_folder) / "uploads" / "profiles"
            upload_dir.mkdir(parents=True, exist_ok=True)
            profile_image = f"{secrets.token_hex(16)}{photo_extension}"
            photo.save(upload_dir / profile_image)
        new_pro = Professional(
            name=name,
            phone=phone,
            category=category,
            region=region,
            description=description,
            profile_image=profile_image,
            approved=False,  # Requires admin approval
            persistent=True,
        )
        PROFESSIONALS.append(new_pro)
        save_professionals()

        return redirect(url_for("index", application="submitted") + "#apply")
    return redirect(url_for("index", application="invalid") + "#apply")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not ADMIN_PASSWORDS:
        return "Admin access is not configured. Set FIXTRNC_ADMIN_PASSWORDS and FLASK_SECRET_KEY, then restart the app.", 503
    if request.method == "POST" and request.form.get("action") == "login":
        submitted_password = request.form.get("password", "")
        if any(hmac.compare_digest(submitted_password, password) for password in ADMIN_PASSWORDS):
            session["is_admin"] = True
            return redirect(url_for("admin"))
        return render_template("admin.html", error="Incorrect password.", logged_in=False), 401
    if not session.get("is_admin"):
        return render_template("admin.html", error=None, logged_in=False)
    return render_template("admin.html", error=None, logged_in=True,
                           pending=[p for p in PROFESSIONALS if not p.approved])

@app.route("/admin/approve/<application_id>", methods=["POST"])
def approve(application_id):
    if not session.get("is_admin"):
        abort(403)
    pro = next((p for p in PROFESSIONALS if p.application_id == application_id and not p.approved), None)
    if pro:
        pro.approved = True
        save_professionals()
    return redirect(url_for("admin"))

@app.route("/admin/decline/<application_id>", methods=["POST"])
def decline(application_id):
    if not session.get("is_admin"):
        abort(403)
    pro = next((p for p in PROFESSIONALS if p.application_id == application_id and not p.approved), None)
    if pro:
        PROFESSIONALS.remove(pro)
        save_professionals()
    return redirect(url_for("admin"))

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin"))

if __name__ == "__main__":
    app.run(debug=True, port=7878)
