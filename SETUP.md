# Setup Instructions - Push to GitHub

## Prerequisites

1. **Git installed**: https://git-scm.com/downloads
2. **GitHub account**: https://github.com
3. **Repository created**: Create an empty repository named `Agentic` on GitHub

## Step-by-Step: Push to GitHub

### Step 1: Navigate to the Repository

```bash
cd /path/to/Agentic
```

### Step 2: Configure Git (First Time Only)

```bash
git config user.name "Alberto"
git config user.email "alberto.chacin@dbp.it.com"
```

### Step 3: Add All Files

```bash
git add .
```

### Step 4: Create Initial Commit

```bash
git commit -m "Initial commit: Platform Documentation Orchestrator skill"
```

### Step 5: Add Remote Repository

Replace `AlbertoDBP` with your GitHub username:AlbertoDBP

```bash
git remote add origin https://github.com/AlbertoDBP/Agentic.git
```

### Step 6: Rename Branch (if needed)

GitHub uses `main` as default, git uses `master`. Align them:

```bash
git branch -M main
```

### Step 7: Push to GitHub

```bash
git push -u origin main
```

You'll be prompted for authentication:
- **Username**: Your GitHub username
- **Password**: Your GitHub personal access token (or password)

## Authentication Options

### Option A: Personal Access Token (Recommended)

1. Go to https://github.com/settings/tokens
2. Click "Generate new token"
3. Select scopes: `repo` (full control)
4. Generate and copy the token
5. Use token as password when prompted

### Option B: SSH Key

1. Generate SSH key:
   ```bash
   ssh-keygen -t ed25519 -C "your.email@example.com"
   ```
2. Add to GitHub: https://github.com/settings/keys
3. Use SSH URL instead:
   ```bash
   git remote add origin git@github.com:AlbertoDBP/Agentic.git
   ```

### Option C: GitHub CLI

```bash
# Install: https://cli.github.com/
gh repo create Agentic --public --source=. --remote=origin --push
```

## Quick Command Summary

```bash
# Navigate to repo
cd Agentic

# Configure git
git config user.name "Your Name"
git config user.email "your@email.com"

# Add and commit
git add .
git commit -m "Initial commit: Platform Documentation Orchestrator"

# Add remote and push
git remote add origin https://github.com/AlbertoDBP/Agentic.git
git branch -M main
git push -u origin main
```

## Verify It Worked

After pushing, verify on GitHub:
1. Go to https://github.com/AlbertoDBP/Agentic
2. You should see all files and folders
3. Click on a file to view its content

## Using with Claude After GitHub Push

Once the repository is on GitHub, tell Claude:

```
I've set up the Platform Documentation Orchestrator skill at:
https://github.com/AlbertoDBP/Agentic

Please use this to generate documentation for [your design].

The SKILL is in the SKILL/ folder, and reference documents 
are in the references/ folder.
```

## Making Updates

After pushing, if you make changes:

```bash
# Make changes to files...

# Commit changes
git add .
git commit -m "Update: [describe what changed]"

# Push to GitHub
git push
```

## Viewing Raw Files

To get raw file URLs for Claude to reference:

```
Raw file URL format:
https://raw.githubusercontent.com/AlbertoDBP/Agentic/main/[path-to-file]

Example:
https://raw.githubusercontent.com/AlbertoDBP/Agentic/main/SKILL/SKILL.md
```

## Troubleshooting

### "fatal: not a git repository"
Make sure you're in the `Agentic` directory:
```bash
cd Agentic
git status
```

### "Permission denied (publickey)"
Use HTTPS instead of SSH, or set up SSH keys correctly.

### "repository not found"
Check that:
1. You created the repository on GitHub first
2. Repository name matches exactly
3. You're using correct username

### "Updates were rejected"
Pull latest first:
```bash
git pull origin main
git push origin main
```

## Next Steps

After pushing to GitHub:

1. **Share the link**: https://github.com/AlbertoDBP/Agentic
2. **Start using with Claude**: Reference the repository in your prompts
3. **Make updates**: Push changes as you refine the skill
4. **Invite collaborators**: Add team members to the repository

---

Need help? Check GitHub's documentation: https://docs.github.com/
