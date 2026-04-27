# GatherPix — Event Photo and Short Video Sharing Platform

A multi-event media sharing web application. Event owners create events, generate QR codes, and manage photos and short videos. Guests scan the QR code and upload media without an account.

---

## Tech Stack

| Layer         | Technology                          |
|---------------|-------------------------------------|
| Backend       | Python 3.11 + Flask                 |
| Database      | PostgreSQL (Supabase)               |
| Media Storage | Cloudinary (CDN-delivered)          |
| QR Generation | qrcode[pil] library                 |
| Frontend      | Jinja2 templates + Vanilla JS       |
| Auth          | Session-based (Flask sessions)      |

---

## Project Structure

```
wedding_app/
├── app.py                  ← Flask application (all routes & logic)
├── schema.sql              ← PostgreSQL database schema
├── requirements.txt        ← Python dependencies
├── .env.example            ← Environment variable template
└── templates/
    ├── base.html           ← Shared layout, nav, toast system
    ├── index.html          ← Landing page
    ├── login.html          ← Owner login
    ├── register.html       ← Owner registration
    ├── dashboard.html      ← Event management dashboard
    ├── event_upload.html   ← Guest upload page (via QR)
    └── event_owner.html    ← Owner gallery & admin view
```

---

## Setup Instructions

### 1. Clone & Install

```bash
git clone <your-repo>
cd wedding_app
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Supabase Setup

1. Sign up at https://supabase.com and create a new project
2. In your project dashboard, go to **Settings → Database**
3. Copy the connection details:
   - Host
   - Password
   - Port (usually 5432)
4. Go to the **SQL Editor** and run the contents of `schema.sql` to create tables
5. Supabase provides PostgreSQL with built-in security and scaling

### 3. Cloudinary Setup

1. Go to https://cloudinary.com and sign up for a free account
2. Open the Cloudinary dashboard and copy your:
   - Cloud name
   - API key
   - API secret
3. In the dashboard, go to **Settings → Upload** and confirm that image uploads are allowed
4. Cloudinary stores uploaded images and serves them through its built-in CDN automatically

### 4. Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
SECRET_KEY=your-very-long-random-secret-key
APP_BASE_URL=https://yourdomain.com

DB_HOST=db.your-project-ref.supabase.co
DB_USER=postgres
DB_PASSWORD=your-supabase-password
DB_NAME=postgres
DB_PORT=5432

CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

### 5. Run (Development)

```bash
python app.py
```

Visit: http://localhost:5000

### 6. Production Deployment (Recommended)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

Use **Nginx** as a reverse proxy in front of Gunicorn. Set `APP_BASE_URL` to your real domain so QR codes point to the correct URL.

---

## How It Works

### For Event Owners
1. Register an account at `/register`
2. Log in and create events from the dashboard
3. Each event gets:
   - A unique URL: `https://yourdomain.com/event/my-event`
   - A downloadable QR code pointing to that URL
   - A shared access code so a second account can join the same event
4. Print/display the QR code at the venue
5. View, download, or delete photos and short videos from the owner gallery

### For Guests
1. Scan the QR code with their phone camera
2. Enter their name (optional) and select photos or short videos
3. Videos are limited to 15 seconds and files must be 50MB or smaller
4. Media uploads go directly to Cloudinary — done!
5. Guests cannot view other guests' photos or delete anything

---

## Permission Model

| Action              | Guest | Owner |
|---------------------|-------|-------|
| Upload photos       | ✅    | ✅    |
| View all photos     | ❌    | ✅    |
| Delete photos       | ❌    | ✅    |
| Download all (ZIP)  | ❌    | ✅    |
| Manage event        | ❌    | ✅    |
| View/download QR    | ❌    | ✅    |

---

## Provider migration notes

The schema stores image metadata separately from the public CDN URL, so switching providers remains straightforward:

1. **Copy files**: Download from the current provider and upload to the new provider
2. **Update URLs**: Update `image_url` in the `photos` table to point to the new provider URLs
3. **Update app.py**: Replace old upload/delete/storage logic with the new provider SDK
4. **Optional**: Add a provider-specific path column if you need both the old and new storage IDs during transition

The `firebase_path` column is used as a generic storage identifier, so it works as the Cloudinary public ID after migration.

---

## Security Notes

- Passwords are hashed with SHA-256. For production, upgrade to **bcrypt** (`pip install flask-bcrypt`)
- Add CSRF protection with **Flask-WTF** for production
- Tighten Cloudinary upload settings and allowed image formats for security
- Set `SESSION_COOKIE_SECURE=True` and `SESSION_COOKIE_HTTPONLY=True` in Flask config for HTTPS deployments
- Never commit `.env` to version control

---

## Adding More Features (Ideas)

- **Co-owner sharing**: Add an `event_owners` join table and share events by email
- **Photo moderation**: Add an `approved` flag so owners review before photos are visible
- **Event PIN**: Optional guest PIN for private events
- **Thumbnails**: Use Cloudinary image transformation URLs to auto-generate thumbnails
- **Email notifications**: Notify owners when new photos are uploaded
