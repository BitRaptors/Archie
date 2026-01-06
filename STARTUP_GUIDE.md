# Startup Guide

## Quick Start Scripts

We've created startup scripts that automatically start both the backend and frontend servers.

### Available Scripts

1. **`start-dev.sh`** - Bash script for Linux/Mac
2. **`start-dev.bat`** - Batch script for Windows
3. **`start-dev.py`** - Python script (cross-platform)

### Usage

**Linux/Mac:**
```bash
./start-dev.sh
```

**Windows:**
```batch
start-dev.bat
```

**Python (Cross-platform):**
```bash
python start-dev.py
```

### What the Scripts Do

1. ✅ **Check Environment Files**
   - Verifies `backend/.env.local` exists
   - Verifies `frontend/.env.local` exists

2. ✅ **Setup Backend**
   - Creates virtual environment if needed
   - Installs Python dependencies if needed
   - Starts backend server on http://localhost:8000

3. ✅ **Setup Frontend**
   - Installs npm dependencies if needed
   - Starts frontend server on http://localhost:3000

4. ✅ **Display Status**
   - Shows server URLs
   - Shows process IDs
   - Provides instructions

### Stopping the Servers

Press `Ctrl+C` in the terminal where you ran the script. The script will automatically stop both servers.

### Output

When running, you'll see:

```
🚀 Starting Repository Analysis System...

📦 Starting backend server...
✅ Backend running on http://localhost:8000 (PID: 12345)

📦 Starting frontend server...
✅ Frontend running on http://localhost:3000 (PID: 12346)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✨ Repository Analysis System is running!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Backend:  http://localhost:8000
Frontend: http://localhost:3000
API Docs: http://localhost:8000/docs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Press Ctrl+C to stop both servers
```

### Troubleshooting

**Backend fails to start:**
- Check that `SUPABASE_JWT_SECRET` and `ANTHROPIC_API_KEY` are set in `backend/.env.local`
- Check that port 8000 is not already in use

**Frontend fails to start:**
- Check that port 3000 is not already in use
- Ensure `NEXT_PUBLIC_API_URL` is set in `frontend/.env.local`

**Script permissions (Linux/Mac):**
```bash
chmod +x start-dev.sh
```

### Manual Start (Alternative)

If you prefer to start servers manually, see `README.md` for individual server startup instructions.


