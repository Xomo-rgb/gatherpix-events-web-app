from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_file
from flask_cors import CORS
from functools import wraps
import pg8000
import cloudinary
import cloudinary.uploader
import qrcode
import io
import os
import uuid
import hashlib
import re
import random
import string
from datetime import datetime
from dotenv import load_dotenv
import zipfile

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-in-production")
CORS(app)

# ─── Cloudinary Init ─────────────────────────────────────────────────────────
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

# ─── DB Connection ───────────────────────────────────────────────────────────
def get_db():
    return pg8000.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "wedding_app"),
        port=int(os.getenv("DB_PORT", "5432"))
    )

def row_to_dict(cursor, row):
    """Convert a row tuple to a dict using cursor description"""
    if row is None:
        return None
    return {cursor.description[i][0]: row[i] for i in range(len(row))}

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60]


def generate_access_code(length=8):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))

# ─── Auth Decorators ─────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

def event_owner_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        event_slug = kwargs.get("event_slug")
        if "user_id" not in session:
            return jsonify({"error": "Unauthorized"}), 401
        db = get_db()
        cur = db.cursor()
        cur.execute("""
            SELECT e.id
            FROM events e
            LEFT JOIN event_members m ON m.event_id = e.id
            WHERE e.slug=%s AND (e.user_id=%s OR m.user_id=%s)
        """, (event_slug, session["user_id"], session["user_id"]))
        result = cur.fetchone()
        cur.close(); db.close()
        if not result:
            return jsonify({"error": "Forbidden"}), 403
        kwargs["event_id"] = result[0]
        return f(*args, **kwargs)
    return decorated

# ─── Pages ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/event/<event_slug>")
def event_upload_page(event_slug):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, name, couple_names, event_date, cover_image_url FROM events WHERE slug=%s", (event_slug,))
    event = row_to_dict(cur, cur.fetchone())
    cur.close(); db.close()
    if not event:
        return "Event not found", 404
    return render_template("event_upload.html", event=event, event_slug=event_slug)

@app.route("/event/<event_slug>/owner")
@login_required
def event_owner_page(event_slug):
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT e.id, e.name, e.couple_names, e.event_date, e.access_code
        FROM events e
        LEFT JOIN event_members m ON m.event_id = e.id
        WHERE e.slug=%s AND (e.user_id=%s OR m.user_id=%s)
    """, (event_slug, session["user_id"], session["user_id"]))
    event = row_to_dict(cur, cur.fetchone())
    cur.close(); db.close()
    if not event:
        return "Not found or not authorized", 403
    return render_template("event_owner.html", event=event, event_slug=event_slug)

# ─── Auth API ─────────────────────────────────────────────────────────────────
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not all([name, email, password]):
        return jsonify({"error": "All fields required"}), 400
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
    if cur.fetchone():
        cur.close(); db.close()
        return jsonify({"error": "Email already registered"}), 409
    cur.execute("INSERT INTO users (name, email, password_hash) VALUES (%s,%s,%s) RETURNING id",
                (name, email, hash_password(password)))
    user_id = cur.fetchone()[0]
    db.commit()
    cur.close(); db.close()
    session["user_id"] = user_id
    session["user_name"] = name
    return jsonify({"success": True})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, name FROM users WHERE email=%s AND password_hash=%s",
                (email, hash_password(password)))
    user = cur.fetchone()
    cur.close(); db.close()
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user[0]
    session["user_name"] = user[1]
    return jsonify({"success": True})

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/me")
def me():
    if "user_id" not in session:
        return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "name": session.get("user_name")})

# ─── Events API ───────────────────────────────────────────────────────────────
@app.route("/api/events", methods=["GET"])
@login_required
def get_events():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        SELECT e.*, COUNT(p.id) as photo_count
        FROM events e
        LEFT JOIN photos p ON p.event_id = e.id
        LEFT JOIN event_members m ON m.event_id = e.id
        WHERE e.user_id = %s OR m.user_id = %s
        GROUP BY e.id
        ORDER BY e.created_at DESC
    """, (session["user_id"], session["user_id"]))
    events = [row_to_dict(cur, row) for row in cur.fetchall()]
    cur.close(); db.close()
    for e in events:
        e["event_date"] = str(e["event_date"]) if e["event_date"] else None
        e["created_at"] = str(e["created_at"])
    return jsonify(events)

@app.route("/api/events", methods=["POST"])
@login_required
def create_event():
    data = request.json
    name = data.get("name", "").strip()
    couple_names = data.get("couple_names", "").strip()
    event_date = data.get("event_date")
    if not name:
        return jsonify({"error": "Event name required"}), 400
    base_slug = slugify(name)
    slug = base_slug
    db = get_db()
    cur = db.cursor()
    # ensure unique slug and access code
    counter = 1
    while True:
        cur.execute("SELECT id FROM events WHERE slug=%s", (slug,))
        if not cur.fetchone():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1
    access_code = generate_access_code()
    while True:
        cur.execute("SELECT id FROM events WHERE access_code=%s", (access_code,))
        if not cur.fetchone():
            break
        access_code = generate_access_code()
    cur.execute(
        "INSERT INTO events (user_id, name, couple_names, event_date, slug, access_code) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (session["user_id"], name, couple_names, event_date or None, slug, access_code)
    )
    event_id = cur.fetchone()[0]
    db.commit()
    cur.close(); db.close()
    return jsonify({"success": True, "slug": slug, "event_id": event_id, "access_code": access_code})

@app.route("/api/events/join", methods=["POST"])
@login_required
def join_event():
    data = request.json
    slug = data.get("slug", "").strip()
    access_code = data.get("access_code", "").strip().upper()
    if not slug or not access_code:
        return jsonify({"error": "Event slug and access code required"}), 400
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, access_code FROM events WHERE slug=%s", (slug,))
    event = cur.fetchone()
    if not event or event[1] != access_code:
        cur.close(); db.close()
        return jsonify({"error": "Invalid event or access code"}), 404
    event_id = event[0]
    cur.execute(
        "INSERT INTO event_members (event_id, user_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
        (event_id, session["user_id"])
    )
    db.commit()
    cur.close(); db.close()
    return jsonify({"success": True, "event_id": event_id})

@app.route("/api/events/<event_slug>", methods=["DELETE"])
@login_required
def delete_event(event_slug):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM events WHERE slug=%s AND user_id=%s", (event_slug, session["user_id"]))
    event = cur.fetchone()
    if not event:
        cur.close(); db.close()
        return jsonify({"error": "Not found"}), 404
    # Delete all photos from Cloudinary
    cur.execute("SELECT firebase_path FROM photos WHERE event_id=%s", (event[0],))
    photos = cur.fetchall()
    for photo in photos:
        try:
            cloudinary.uploader.destroy(photo[0], resource_type="image", invalidate=True)
        except Exception:
            pass
    cur.execute("DELETE FROM photos WHERE event_id=%s", (event[0],))
    cur.execute("DELETE FROM events WHERE id=%s", (event[0],))
    db.commit()
    cur.close(); db.close()
    return jsonify({"success": True})

# ─── QR Code ─────────────────────────────────────────────────────────────────
@app.route("/api/events/<event_slug>/qr")
@login_required
def get_qr(event_slug):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM events WHERE slug=%s AND user_id=%s", (event_slug, session["user_id"]))
    if not cur.fetchone():
        cur.close(); db.close()
        return jsonify({"error": "Not found"}), 404
    cur.close(); db.close()
    base_url = os.getenv("APP_BASE_URL", request.host_url.rstrip("/"))
    event_url = f"{base_url}/event/{event_slug}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4,
                       error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(event_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png",
                     download_name=f"{event_slug}-qr.png", as_attachment=False)

# ─── Photos API ───────────────────────────────────────────────────────────────
@app.route("/api/events/<event_slug>/photos", methods=["GET"])
def get_photos(event_slug):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM events WHERE slug=%s", (event_slug,))
    event = cur.fetchone()
    if not event:
        cur.close(); db.close()
        return jsonify({"error": "Event not found"}), 404
    cur.execute("""
        SELECT id, image_url, uploader_name, upload_timestamp
        FROM photos WHERE event_id=%s ORDER BY upload_timestamp DESC
    """, (event[0],))
    photos = [row_to_dict(cur, row) for row in cur.fetchall()]
    cur.close(); db.close()
    for p in photos:
        p["upload_timestamp"] = str(p["upload_timestamp"])
    # Only owners can see photos (check session)
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(photos)

@app.route("/api/events/<event_slug>/photos/upload", methods=["POST"])
def upload_photo(event_slug):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM events WHERE slug=%s", (event_slug,))
    event = cur.fetchone()
    if not event:
        cur.close(); db.close()
        return jsonify({"error": "Event not found"}), 404
    if "file" not in request.files:
        cur.close(); db.close()
        return jsonify({"error": "No file"}), 400
    file = request.files["file"]
    uploader_name = request.form.get("uploader_name", "Guest").strip() or "Guest"
    allowed_images = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/heic"}
    allowed_videos = {"video/mp4", "video/quicktime", "video/avi", "video/mov", "video/webm", "video/3gpp"}
    max_bytes = 50 * 1024 * 1024
    file.stream.seek(0, io.SEEK_END)
    file_size = file.stream.tell()
    file.stream.seek(0)
    if file_size > max_bytes:
        cur.close(); db.close()
        return jsonify({"error": "File must be 50MB or smaller"}), 400
    if file.content_type in allowed_images:
        resource_type = "image"
    elif file.content_type in allowed_videos:
        resource_type = "video"
    else:
        cur.close(); db.close()
        return jsonify({"error": "Only image and short video files allowed"}), 400
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ("jpg" if resource_type == "image" else "mp4")
    public_id = f"events/{event_slug}/{uuid.uuid4().hex}"
    upload_result = cloudinary.uploader.upload(
        file,
        public_id=public_id,
        resource_type=resource_type,
        overwrite=False
    )
    if resource_type == "video":
        duration = upload_result.get("duration", 0)
        if duration and duration > 15:
            cloudinary.uploader.destroy(public_id, resource_type="video", invalidate=True)
            cur.close(); db.close()
            return jsonify({"error": "Videos must be 15 seconds or shorter"}), 400
    image_url = upload_result.get("secure_url") or upload_result.get("url")
    cur.execute(
        "INSERT INTO photos (event_id, image_url, firebase_path, uploader_name) VALUES (%s,%s,%s,%s) RETURNING id",
        (event[0], image_url, public_id, uploader_name)
    )
    photo_id = cur.fetchone()[0]
    db.commit()
    cur.close(); db.close()
    return jsonify({"success": True, "photo_id": photo_id, "image_url": image_url})

@app.route("/api/events/<event_slug>/photos/<int:photo_id>", methods=["DELETE"])
def delete_photo(event_slug, photo_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM events WHERE slug=%s", (event_slug,))
    event = cur.fetchone()
    if not event:
        cur.close(); db.close()
        return jsonify({"error": "Not found"}), 404
    # Only owners can delete
    if "user_id" not in session:
        cur.close(); db.close()
        return jsonify({"error": "Unauthorized"}), 401
    cur.execute("SELECT id, firebase_path FROM photos WHERE id=%s AND event_id=%s",
                (photo_id, event[0]))
    photo = cur.fetchone()
    if not photo:
        cur.close(); db.close()
        return jsonify({"error": "Photo not found"}), 404
    try:
        cloudinary.uploader.destroy(photo[1], resource_type="image", invalidate=True)
    except Exception:
        pass
    cur.execute("DELETE FROM photos WHERE id=%s", (photo_id,))
    db.commit()
    cur.close(); db.close()
    return jsonify({"success": True})

@app.route("/api/events/<event_slug>/photos/download-all")
@login_required
def download_all_photos(event_slug):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM events WHERE slug=%s AND user_id=%s", (event_slug, session["user_id"]))
    event = cur.fetchone()
    if not event:
        cur.close(); db.close()
        return jsonify({"error": "Not authorized"}), 403
    cur.execute("SELECT firebase_path, uploader_name, upload_timestamp FROM photos WHERE event_id=%s",
                (event[0],))
    photos = [row_to_dict(cur, row) for row in cur.fetchall()]
    cur.close(); db.close()
    import requests as req_lib
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, photo in enumerate(photos):
            response = req_lib.get(photo["image_url"], timeout=15)
            response.raise_for_status()
            img_bytes = response.content
            ext = photo["image_url"].rsplit(".", 1)[-1].split("?")[0]
            zf.writestr(f"photo_{i+1}_{photo['uploader_name']}.{ext}", img_bytes)
    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype="application/zip",
                     download_name=f"{event_slug}-photos.zip", as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
