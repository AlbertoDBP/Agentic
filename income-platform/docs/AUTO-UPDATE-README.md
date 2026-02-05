# Auto Documentation Updater - README

**Version:** 2.0.0  
**Script:** `auto-update-docs.sh`  
**Purpose:** Automatically detect, categorize, copy, commit, and backup documentation files

---

## What It Does

The `auto-update-docs.sh` script is a **fully automated** documentation management tool that:

1. ✅ **Scans** Downloads folder for new documentation files (last 24 hours)
2. ✅ **Categorizes** files intelligently (deployment, functional, implementation, testing, scripts)
3. ✅ **Copies** files to appropriate repository directories
4. ✅ **Stages** changes in Git
5. ✅ **Generates** smart commit messages
6. ✅ **Commits** to local repository
7. ✅ **Pushes** to GitHub
8. ✅ **Backs up** processed files to dated backup directory
9. ✅ **Cleans up** Downloads folder

**All with user confirmations at key steps!**

---

## Quick Start

### **One-Line Usage:**

```bash
chmod +x auto-update-docs.sh && ./auto-update-docs.sh
```

That's it! The script handles everything else interactively.

---

## How It Works

### **Step-by-Step Workflow:**

```
┌─────────────────────────────────────────────┐
│ 1. Scan Downloads (files modified <24h)    │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ 2. Categorize files by name & content      │
│    - deployment/*.md                        │
│    - functional/agent-*.md                  │
│    - implementation/*.md                    │
│    - testing/*.md                           │
│    - scripts/*.sh                           │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ 3. Show files & ask confirmation            │
│    "Copy these files? (y/n)"                │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ 4. Copy to appropriate directories          │
│    - Create structure if needed             │
│    - Make scripts executable                │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ 5. Generate smart commit message            │
│    - Groups files by category               │
│    - Lists all files                        │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ 6. Commit changes                           │
│    "Commit these changes? (y/n)"            │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ 7. Push to GitHub                           │
│    "Push to GitHub? (y/n)"                  │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ 8. Backup processed files                   │
│    "Move to backup? (y/n)"                  │
│    ~/Documents/income-fortress-backups/     │
└─────────────────────────────────────────────┘
```

---

## Features

### **1. Intelligent File Detection**

Scans for files modified in last 24 hours:
- `*.md` - Markdown documentation
- `*.sh` - Shell scripts
- `*.txt` - Text files

Ignores:
- Hidden files (`.DS_Store`, etc.)
- Empty files
- Files older than 24 hours

### **2. Smart Categorization**

**Pattern-based:**
```bash
deployment-checklist.md        → docs/deployment/
agent-01-market-data-sync.md   → docs/functional/
implementation-api-gateway.md  → docs/implementation/
test-matrix.md                 → docs/testing/
quick-update-docs.sh           → scripts/
```

**Content-based fallback:**
If pattern doesn't match, scans file content for keywords:
- "deployment", "docker", "infrastructure" → deployment
- "agent", "specification" → functional
- "implementation", "technical design" → implementation
- "test", "testing" → testing

### **3. Automatic Directory Creation**

Creates directory structure if it doesn't exist:
```
income-platform/
├── docs/
│   ├── deployment/
│   ├── functional/
│   ├── implementation/
│   ├── testing/
│   ├── diagrams/
│   └── misc/
└── scripts/
```

### **4. Smart Commit Messages**

Automatically generates organized commit messages:

```
docs: update documentation (15 files)

Deployment Documentation (4 files):
- deployment-checklist.md
- deployment-checklist-ADDENDUM.md
- operational-runbook.md
- monitoring-guide.md

Functional Specifications (3 files):
- agent-01-market-data-sync.md
- agent-03-income-scoring.md
- agents-5-6-7-9-summary.md

Scripts (2 files):
- quick-update-docs.sh
- auto-update-docs.sh

Auto-generated commit via auto-update-docs.sh
```

### **5. Automatic Backups**

Creates dated backup directories:
```
~/Documents/income-fortress-docs-backups/
├── backup-20260203-143022/
│   ├── deployment-checklist.md
│   ├── agent-01-market-data-sync.md
│   └── ...
├── backup-20260204-091545/
│   └── ...
└── ...
```

### **6. User Control**

Asks for confirmation at critical steps:
1. Before copying files
2. Before committing
3. Before pushing to GitHub
4. Before backing up files

You can abort at any step without damage.

### **7. Color-Coded Output**

- 🟢 Green: Success messages
- 🔵 Blue: Informational
- 🟡 Yellow: Warnings
- 🔴 Red: Errors
- 🔵 Cyan: Info messages

---

## Examples

### **Example 1: First-time Full Documentation Update**

```bash
$ ./auto-update-docs.sh

========================================
Income Fortress Auto Documentation Updater
========================================

[14:30:22] Verifying repository location...
[INFO] Repository: /Volumes/CH-DataOne/AlbertoDBP/Agentic

[14:30:22] Pulling latest changes from remote...
Already up to date.

[14:30:23] Scanning Downloads for documentation files...
[INFO] Found 15 new file(s)

[14:30:23] Categorizing files...

  [deployment] deployment-checklist.md → deployment/
  [deployment] deployment-checklist-ADDENDUM.md → deployment/
  [deployment] operational-runbook.md → deployment/
  [deployment] monitoring-guide.md → deployment/
  [deployment] disaster-recovery.md → deployment/
  [deployment] circuit-breaker-monitoring-update.md → deployment/
  [functional] agent-01-market-data-sync.md → functional/
  [functional] agent-03-income-scoring.md → functional/
  [functional] agents-5-6-7-9-summary.md → functional/
  [root] DOCUMENTATION-MANIFEST.md → docs/
  [root] PACKAGE-SUMMARY.md → docs/
  [scripts] quick-update-docs.sh → scripts/
  [scripts] update-docs-from-downloads.sh → scripts/
  [scripts] auto-update-docs.sh → scripts/
  [scripts] SCRIPTS-README.md → docs/

Copy these files to repository? (y/n) y

[14:30:25] Creating documentation directory structure...
[14:30:25] Copying files to repository...
[INFO]   ✓ Copied: deployment-checklist.md → deployment/
[INFO]   ✓ Copied: deployment-checklist-ADDENDUM.md → deployment/
... (15 files copied)
[INFO]     Made executable: quick-update-docs.sh
[INFO]     Made executable: auto-update-docs.sh

[14:30:26] Successfully copied 15 file(s)

[14:30:26] Git status:
 M docs/DOCUMENTATION-MANIFEST.md
 M docs/PACKAGE-SUMMARY.md
 M docs/deployment/deployment-checklist-ADDENDUM.md
 M docs/deployment/deployment-checklist.md
 ... (more files)

[14:30:26] Generating commit message...

Commit message:
---
docs: update documentation (15 files)

Deployment Documentation (6 files):
- deployment-checklist.md
- deployment-checklist-ADDENDUM.md
...

Auto-generated commit via auto-update-docs.sh
---

Commit these changes? (y/n) y

[14:30:28] Staging changes...
[14:30:28] Committing changes...
[INFO] Commit successful!

[14:30:28] Commit details:
commit a1b2c3d4...
...

Push to GitHub? (y/n) y

[14:30:30] Pushing to GitHub...

========================================
✓ SUCCESS! Documentation updated on GitHub
========================================

View changes: https://github.com/AlbertoDBP/Agentic/tree/main/income-platform/docs

Move processed files to backup folder? (y/n) y

[14:30:32] Creating backup directory...
[14:30:32] Moving processed files to backup...
[INFO]   ✓ Moved: deployment-checklist.md
[INFO]   ✓ Moved: agent-01-market-data-sync.md
... (15 files moved)

[14:30:33] Backup complete!
[INFO] Location: ~/Documents/income-fortress-docs-backups/backup-20260203-143022
[INFO] Files backed up: 15

========================================
All Done!
========================================

Summary:
  Files processed: 15
  Files backed up: 15
  Commit: ✓
  Push: ✓

Next steps:
  1. Verify on GitHub
  2. Deploy to staging
  3. Set up monitoring
```

### **Example 2: No New Files**

```bash
$ ./auto-update-docs.sh

========================================
Income Fortress Auto Documentation Updater
========================================

[09:15:10] Scanning Downloads for documentation files...
[WARNING] No new documentation files found in Downloads (last 24 hours)

Looking for files matching patterns:
  - *.md (Markdown documentation)
  - *.sh (Shell scripts)
  - *.txt (Text files)

In directory: /Users/alberto/Downloads
```

### **Example 3: Abort Before Commit**

```bash
$ ./auto-update-docs.sh

... (scanning and categorizing)

Copy these files to repository? (y/n) y

... (copying files)

Commit these changes? (y/n) n

[WARNING] Changes staged but not committed.
To commit manually:
  cd /Volumes/CH-DataOne/AlbertoDBP/Agentic/income-platform
  git commit -m "Your message"
```

---

## Configuration

### **Customizable Paths:**

Edit these variables at the top of the script:

```bash
# Repository location
REPO_ROOT="/Volumes/CH-DataOne/AlbertoDBP/Agentic"
PROJECT_DIR="$REPO_ROOT/income-platform"

# Source directory (where to look for new files)
DOWNLOADS_DIR="$HOME/Downloads"

# Backup location
BACKUP_BASE="$HOME/Documents/income-fortress-docs-backups"
```

### **Time Window:**

By default, scans for files modified in last **24 hours**.

To change:
```bash
# Line ~105 in the script
find "$DOWNLOADS_DIR" -maxdepth 1 -type f -mtime -1 -print0
#                                              ^^^^
# -1 = last 24 hours
# -2 = last 48 hours
# -0.5 = last 12 hours
```

### **File Patterns:**

To add new file patterns, edit these variables:

```bash
OPERATIONAL_PATTERN="(deployment-checklist|operational-runbook|...)"
FUNCTIONAL_PATTERN="(agent-[0-9]+-.*|agents-[0-9]+-.*)"
# Add more patterns as needed
```

---

## Troubleshooting

### **Issue: "No new files found"**

**Cause:** Files are older than 24 hours or don't match patterns

**Solution:**
```bash
# Check file modification time
ls -lt ~/Downloads/*.md | head -10

# If files are older, change time window in script (see Configuration)

# Or copy files manually using quick-update-docs.sh
```

### **Issue: "Permission denied" when running script**

**Solution:**
```bash
chmod +x auto-update-docs.sh
```

### **Issue: Files categorized incorrectly**

**Cause:** Pattern or content detection failed

**Solution:**
1. Check filename matches patterns (see Configuration)
2. Manually move file to correct directory after script runs
3. Or update patterns in script for future runs

### **Issue: "Failed to push to GitHub"**

**Causes:**
- No internet connection
- GitHub authentication expired
- Conflicts with remote branch

**Solution:**
```bash
# Check Git status
cd /Volumes/CH-DataOne/AlbertoDBP/Agentic
git status

# Try pulling first
git pull origin main

# Resolve conflicts if any
git status

# Try pushing again
git push origin main
```

### **Issue: Backup directory filling up**

**Solution:**
```bash
# Clean up old backups (keep last 30 days)
find ~/Documents/income-fortress-docs-backups/ -type d -mtime +30 -exec rm -rf {} +
```

---

## Comparison with Other Scripts

| Feature | auto-update-docs.sh | quick-update-docs.sh | update-docs-from-downloads.sh |
|---------|---------------------|----------------------|-------------------------------|
| **Auto-detect files** | ✅ Yes (24h window) | ❌ Requires manual list | ❌ Requires manual list |
| **Smart categorization** | ✅ Pattern + content | ❌ Manual paths | ❌ Manual paths |
| **Auto-backup** | ✅ Yes (dated dirs) | ❌ No | ✅ Optional |
| **Commit message** | ✅ Auto-generated | ✅ Template | ✅ Template |
| **User confirmations** | ✅ 4 checkpoints | ✅ 1 checkpoint | ✅ 4 checkpoints |
| **Best for** | **Daily updates** | Quick one-time | First-time setup |

---

## Best Practices

### **Daily Workflow:**

```bash
# 1. Download files from Claude to ~/Downloads
#    (Claude generates documentation)

# 2. Run auto-update script
./auto-update-docs.sh

# 3. Script handles everything:
#    - Detects files
#    - Categorizes
#    - Commits
#    - Pushes
#    - Backs up

# 4. Verify on GitHub
open https://github.com/AlbertoDBP/Agentic
```

**Time:** ~2 minutes (mostly confirmations)

### **Before Running:**

1. ✅ Download all files from Claude to Downloads
2. ✅ Ensure files were modified recently (<24 hours)
3. ✅ Close any editors with files open
4. ✅ Have internet connection for Git push

### **After Running:**

1. ✅ Verify commit on GitHub
2. ✅ Check backup directory has files
3. ✅ Downloads folder should be clean
4. ✅ Pull changes on other machines if needed

---

## Advanced Usage

### **Dry Run Mode:**

To see what would happen without making changes:

```bash
# Comment out the actual operations in the script:
# - Line ~280: cp "$file" "$target_dir/" → echo "Would copy..."
# - Line ~350: git add ... → echo "Would add..."
# - Line ~355: git commit ... → echo "Would commit..."
```

### **Silent Mode:**

To run without confirmations (dangerous!):

```bash
# Replace all read -p commands with automatic "yes"
# Not recommended - use with caution
```

### **Batch Processing:**

To process multiple documentation generations:

```bash
# Generate docs in Claude multiple times
# Wait 1 hour between generations (files will accumulate)
# Run script once - processes all files from last 24 hours
```

---

## FAQ

**Q: What if I want to keep files in Downloads?**
A: Say "n" when asked to backup. Files will be copied but not moved.

**Q: Can I review changes before pushing?**
A: Yes! Say "y" to commit, then review with `git show` before deciding to push.

**Q: What if script mis-categorizes a file?**
A: After script runs, manually move the file:
```bash
mv docs/deployment/wrongfile.md docs/functional/
git add docs/
git commit --amend --no-edit
```

**Q: Can I customize commit messages?**
A: The script generates smart messages automatically. To customize, edit the commit message generation section (line ~330).

**Q: Does it work with subdirectories in Downloads?**
A: No, only scans top-level Downloads directory. This prevents accidentally processing unrelated files.

**Q: What if I already committed manually?**
A: Script detects this and won't try to commit again.

**Q: Can I use this for other projects?**
A: Yes! Edit the `REPO_ROOT` and patterns to match your project structure.

---

## Support

**Script Issues:**
- Check troubleshooting section
- Review error messages (color-coded red)
- Run with `-x` for debug output: `bash -x auto-update-docs.sh`

**Git Issues:**
- Check `git status`
- Review `git log`
- See main SCRIPTS-README.md

---

## Changelog

**v2.0.0 (2026-02-04)**
- ✅ Automatic file detection (24-hour window)
- ✅ Smart categorization (pattern + content)
- ✅ Auto-generated commit messages
- ✅ Automatic backups to dated directories
- ✅ Color-coded output
- ✅ Multiple confirmation points

**v1.0.0 (2026-02-03)**
- Initial scripts (quick-update, full-update)

---

## Scripts Package

This is part of the Income Fortress documentation update script suite:

1. **auto-update-docs.sh** ⭐ (This script - Recommended for daily use)
2. quick-update-docs.sh (Simple manual update)
3. update-docs-from-downloads.sh (Full manual update)
4. SCRIPTS-README.md (General documentation)

---

**Script Version:** 2.0.0  
**Last Updated:** February 4, 2026  
**Recommended for:** Daily documentation updates
