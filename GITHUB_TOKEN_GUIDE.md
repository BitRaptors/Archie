# How to Get a GitHub Personal Access Token

This guide will walk you through creating a GitHub Personal Access Token (PAT) for the Repository Analysis System.

## What is a GitHub Token?

A GitHub Personal Access Token (PAT) is a secure way to authenticate with GitHub's API. It allows the Repository Analysis System to:
- Access your repositories
- Read repository information
- Clone repositories for analysis
- Validate your GitHub account

## Step-by-Step Instructions

### 1. Go to GitHub Settings

1. Log in to your GitHub account
2. Click your profile picture in the top-right corner
3. Select **Settings** from the dropdown menu
4. Or go directly to: https://github.com/settings/profile

### 2. Navigate to Developer Settings

1. Scroll down in the left sidebar
2. Click **Developer settings** (at the bottom)
3. Or go directly to: https://github.com/settings/apps

### 3. Create a Personal Access Token

1. In the left sidebar, click **Personal access tokens**
2. Click **Tokens (classic)** or **Fine-grained tokens** (recommended for new tokens)
3. Click **Generate new token** → **Generate new token (classic)** or **Generate new token (fine-grained)**

### 4. Configure Token Settings

#### For Classic Tokens:
1. **Note**: Give it a descriptive name (e.g., "Repository Analysis System")
2. **Expiration**: Choose an expiration period:
   - **30 days** (for testing)
   - **90 days** (recommended)
   - **1 year** (for long-term use)
   - **No expiration** (not recommended for security)
3. **Select scopes** (permissions):
   - ✅ **`repo`** - Full control of private repositories
     - This includes: `repo:status`, `repo_deployment`, `public_repo`, `repo:invite`, `security_events`
   - ✅ **`read:user`** - Read user profile information
   - ✅ **`user:email`** - Access user email addresses

#### For Fine-grained Tokens (Recommended):
1. **Token name**: Give it a descriptive name (e.g., "Repository Analysis System")
2. **Expiration**: Choose an expiration period
3. **Repository access**: 
   - Select **All repositories** (if you want to analyze all repos)
   - Or select **Only select repositories** and choose specific ones
4. **Repository permissions**:
   - **Contents**: Read-only (to read repository files)
   - **Metadata**: Read-only (to read repository information)
5. **Account permissions**:
   - **Email addresses**: Read-only (to access your email)

### 5. Generate and Copy Token

1. Click **Generate token** (or **Generate token (classic)**)
2. **⚠️ IMPORTANT**: Copy the token immediately! 
   - You won't be able to see it again
   - It will look like: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
3. Store it securely (password manager, secure note, etc.)

### 6. Use Token in the Application

#### Option 1: Via Web UI (Recommended)
1. Start the application:
   ```bash
   ./start-dev.sh
   ```
2. Open the frontend: http://localhost:3000 (or the port shown)
3. Navigate to the **Authentication** page (or `/auth`)
4. Paste your token in the input field
5. Click **Authenticate**

#### Option 2: Via API
```bash
curl -X POST http://localhost:8000/api/v1/auth/github \
  -H "Content-Type: application/json" \
  -d '{"token": "ghp_your_token_here"}'
```

## Required Permissions Summary

The token needs these permissions to work properly:

| Permission | Why It's Needed |
|------------|----------------|
| `repo` (classic) or `Contents: Read` (fine-grained) | To read repository files and clone repos for analysis |
| `read:user` or `Metadata: Read` | To validate the token and get user information |
| `user:email` or `Email addresses: Read` | To access user email (optional but recommended) |

## Security Best Practices

1. ✅ **Use Fine-grained Tokens** when possible (more secure, least privilege)
2. ✅ **Set an expiration date** (don't use "No expiration")
3. ✅ **Store tokens securely** (password manager, environment variables)
4. ✅ **Rotate tokens regularly** (every 90 days recommended)
5. ✅ **Revoke unused tokens** (go to Settings → Developer settings → Personal access tokens)
6. ❌ **Never commit tokens to Git** (they will be exposed)
7. ❌ **Don't share tokens** (each user should have their own)

## Troubleshooting

### "Invalid GitHub token" Error

- **Check token expiration**: Tokens expire after the set period
- **Verify permissions**: Make sure the token has `repo` or `Contents: Read` permission
- **Check token format**: Should start with `ghp_` for classic tokens or `github_pat_` for fine-grained tokens
- **Regenerate token**: Create a new token if the old one doesn't work

### "Repository not found" Error

- **Check repository access**: Make sure the token has access to the repository
- **Private repositories**: Ensure the token has `repo` scope (classic) or access to private repos (fine-grained)
- **Organization repositories**: You may need organization approval for fine-grained tokens

### Token Not Working After Some Time

- **Check expiration**: Tokens expire based on the expiration date you set
- **Check if revoked**: Go to GitHub Settings → Developer settings → Personal access tokens
- **Regenerate**: Create a new token if needed

## Quick Reference

- **GitHub Settings**: https://github.com/settings/profile
- **Developer Settings**: https://github.com/settings/apps
- **Personal Access Tokens (Classic)**: https://github.com/settings/tokens
- **Fine-grained Tokens**: https://github.com/settings/tokens?type=beta

## Example Token Format

- **Classic Token**: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- **Fine-grained Token**: `github_pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## Need Help?

- GitHub Documentation: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token
- GitHub Support: https://support.github.com/


