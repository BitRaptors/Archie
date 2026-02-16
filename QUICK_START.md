# Quick Start Guide

## ✅ Completed Setup Steps

1. **Database Setup** - All migrations applied successfully to Supabase project "ArchitectureMCP"
2. **Dependencies Installed** - Backend Python packages and frontend npm packages installed
3. **Environment Files Created** - `.env.local` files created for both backend and frontend

## ⚠️ Required Configuration

Before running the application, you need to configure:

### 1. Supabase JWT Secret

Get your JWT secret from Supabase Dashboard:
- Go to: https://supabase.com/dashboard/project/jxkfqiotreydrlgglsrt/settings/api
- Copy the "JWT Secret"
- Update `backend/.env.local`:
  ```
  SUPABASE_JWT_SECRET=your-actual-jwt-secret-here
  ```

### 2. Anthropic API Key

Get your Anthropic API key:
- Go to: https://console.anthropic.com/
- Create an API key
- Update `backend/.env.local`:
  ```
  ANTHROPIC_API_KEY=your-actual-api-key-here
  ```

### 3. Optional: Redis (for background tasks)

If you want to use background analysis tasks:
- Install Redis locally: `brew install redis` (Mac) or use Docker
- Or use Redis Cloud and update `REDIS_URL` in `backend/.env.local`

## 🔑 Getting a GitHub Token

Before you can use the application, you need a GitHub Personal Access Token:

1. **Go to GitHub Settings**: https://github.com/settings/tokens
2. **Click**: "Generate new token (classic)"
3. **Name it**: "Repository Analysis System"
4. **Select scopes**:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `read:user` (Read user profile information)
5. **Click**: "Generate token"
6. **Copy the token** (starts with `ghp_`) - you won't see it again!

📖 **Detailed guide**: See [GITHUB_TOKEN_GUIDE.md](./GITHUB_TOKEN_GUIDE.md)

## 🚀 Running the Application

### Quick Start (Recommended)

**Use the startup script to run both servers:**

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

This automatically:
- Checks for environment files
- Creates virtual environment if needed
- Installs dependencies if needed
- Starts both backend and frontend
- Shows status and URLs

Press `Ctrl+C` to stop both servers.

### Manual Start

**Backend:**

```bash
cd backend
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python src/main.py
```

The API will be available at: http://localhost:8000

Test it:
```bash
curl http://localhost:8000/health
```

**Frontend:**

```bash
cd frontend
npm run dev
```

The frontend will be available at: http://localhost:3000

## 📋 Verification Checklist

- [ ] Supabase JWT Secret configured in `backend/.env.local`
- [ ] Anthropic API Key configured in `backend/.env.local`
- [ ] Backend server starts without errors
- [ ] Frontend dev server starts without errors
- [ ] Health endpoint responds: `curl http://localhost:8000/health`

## 🎯 Next Steps

1. Configure the required API keys (see above)
2. Start the backend server
3. Start the frontend server
4. Test authentication with a GitHub token
5. Try analyzing a repository

## 📚 Documentation

- See `SETUP.md` for detailed setup instructions
- See `README.md` for project overview
- See the plan document for architecture details

