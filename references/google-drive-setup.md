# Google Drive Organization Setup

## Overview

The repository structure can be directly mirrored in Google Drive for collaborative access and organization. This document provides both manual setup instructions and automated scripts.

## Folder Structure in Google Drive

Create this structure in your Google Drive:

```
AIAgenticPlatform/
├── Docs/
│   ├── Architecture/
│   │   ├── Reference Architecture.md
│   │   ├── System Diagram.mmd
│   │   ├── Component Interactions.mmd
│   │   └── Data Model.mmd
│   ├── Functional Specifications/
│   │   ├── [Component A] Functional Spec.md
│   │   ├── [Component B] Functional Spec.md
│   │   └── ...
│   ├── Implementation Specifications/
│   │   ├── [Component A] Implementation.md
│   │   ├── [Component B] Implementation.md
│   │   └── ...
│   ├── Testing/
│   │   ├── Test Matrix.md
│   │   ├── Edge Cases.md
│   │   └── SLA Definitions.md
│   ├── Diagrams/
│   │   ├── Architecture Diagrams/
│   │   ├── Workflow Diagrams/
│   │   ├── State Machines/
│   │   └── Data Diagrams/
│   ├── Decisions Log.md
│   ├── CHANGELOG.md
│   └── Master Index.md
├── Code Scaffolds/
│   ├── Core/
│   ├── Agents/
│   ├── Utils/
│   └── Tests/
└── Resources/
    ├── Documentation Standards.md
    ├── Testing Patterns.md
    ├── Mermaid Conventions.md
    └── Iteration Workflow.md
```

## Manual Setup Instructions

### Step 1: Create Root Folder
1. Go to Google Drive
2. Click "New" → "Folder"
3. Name it: `AIAgenticPlatform` (or your project name)
4. Open the folder

### Step 2: Create Documentation Folders
Inside the root folder, create:
1. "Docs" folder
   - Inside: "Architecture", "Functional Specifications", "Implementation Specifications", "Testing", "Diagrams"
2. "Code Scaffolds" folder
3. "Resources" folder

### Step 3: Organize Specification Documents

**In Functional Specifications:**
- Create one Google Doc per functional specification
- File naming: `[Component Name] - Functional Specification`
- Share with relevant team members

**In Implementation Specifications:**
- Create one Google Doc per implementation spec
- File naming: `[Component Name] - Implementation Specification`
- Include Testing & Acceptance section in each

**In Diagrams:**
Create subfolders for organization:
- Architecture Diagrams
- Workflow Diagrams
- State Machines
- Data Diagrams

### Step 4: Create Master Index
In the root "Docs" folder, create a Google Doc called "Master Index.md"
This becomes your navigation hub linking all documentation.

### Step 5: Create Tracking Documents
1. **CHANGELOG.md** - Track all changes with dates
2. **Decisions Log.md** - Document design decisions and rationale

## Automating Setup with Python Script

Use this Python script to automate folder creation (requires Google Drive API access):

```python
from google.colab import auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def create_drive_structure(parent_folder_id, structure):
    """Recursively create folder structure in Google Drive."""
    auth.authenticate_user()
    drive_service = build('drive', 'v3')
    
    def create_folder(folder_name, parent_id):
        try:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            file = drive_service.files().create(body=file_metadata, fields='id').execute()
            return file.get('id')
        except HttpError as error:
            print(f'An error occurred: {error}')
            return None
    
    def build_structure(current_structure, current_parent):
        for item in current_structure:
            if isinstance(item, dict):
                folder_name = item.get('name')
                children = item.get('children', [])
                folder_id = create_folder(folder_name, current_parent)
                if folder_id and children:
                    build_structure(children, folder_id)
            elif isinstance(item, str):
                create_folder(item, current_parent)
    
    build_structure(structure, parent_folder_id)

# Define the structure
FOLDER_STRUCTURE = [
    {
        'name': 'Docs',
        'children': [
            'Architecture',
            'Functional Specifications',
            'Implementation Specifications',
            'Testing',
            {'name': 'Diagrams', 'children': [
                'Architecture Diagrams',
                'Workflow Diagrams',
                'State Machines',
                'Data Diagrams'
            ]}
        ]
    },
    {
        'name': 'Code Scaffolds',
        'children': [
            'Core',
            'Agents',
            'Utils',
            'Tests'
        ]
    },
    {
        'name': 'Resources',
        'children': []
    }
]

# Run: create_drive_structure(parent_folder_id, FOLDER_STRUCTURE)
```

## Organizing Generated Documentation in Google Drive

### After Claude Generates Documentation

1. **Copy reference architecture** → Docs/Architecture/Reference Architecture.md
2. **Copy functional specs** → Docs/Functional Specifications/[Component Name] Functional Spec.md
3. **Copy implementation specs** → Docs/Implementation Specifications/[Component Name] Implementation.md
4. **Copy diagrams** → Docs/Diagrams/[Category]/[Diagram Name].mmd
5. **Copy testing specs** → Docs/Testing/[Test Type].md
6. **Copy code scaffolds** → Code Scaffolds/[Component Name]/
7. **Copy master index** → Docs/Master Index.md

### Maintaining Version Control

**In Google Drive, use:**
- File naming with dates: `Component Name - Implementation [2025-01-23].md`
- Keep old versions for 2-3 iterations, then archive
- Use Google Drive's version history feature for detailed tracking

**Better approach: Keep canonical versions in GitHub, share links in Google Drive**
- Store actual files in GitHub (Markdown, Mermaid)
- In Google Drive, create a master index with links to GitHub files
- Use Google Docs only for collaborative editing/review
- Once stable, commit to GitHub and reference from Drive

## Sharing & Collaboration

### Team Access
1. Right-click the main folder → Share
2. Add team members with appropriate permissions
   - **Editors**: Team actively developing
   - **Commenters**: Stakeholders reviewing
   - **Viewers**: Read-only reference

### Documentation Review Process
1. Claude generates new docs
2. Upload to Google Drive in appropriate folders
3. Team reviews and comments
4. Update based on feedback
5. Once approved, commit final versions to GitHub
6. Update master index with finalized versions

## Cross-Platform Workflow

### Recommended Setup
1. **Google Drive** - For collaborative review and discussion
2. **GitHub** - For version control and canonical storage
3. **README in both** - Link Drive docs to GitHub files for redundancy

### Syncing Workflow
1. Claude generates documentation → Upload to Drive for review
2. Team comments and requests changes in Drive
3. Update documents based on feedback
4. Commit final versions to GitHub
5. Update GitHub with links to Drive master index
6. Archive old versions in Drive dated folder

## Markdown & Mermaid Rendering in Google Drive

**Important**: Google Drive doesn't natively render Markdown or Mermaid diagrams.

**Options:**
1. **Upload as Google Docs** - Copy/paste content and format in Google Docs
2. **Use Markdown editor add-on** - Install "Markdown Preview" or similar
3. **Link to GitHub** - Store files in GitHub, embed links in Drive
4. **Use online renderers** - Reference with links to Mermaid.live or similar

**Recommended**: 
- Store actual Markdown/Mermaid files in GitHub
- In Google Drive, create index with links to GitHub
- Use Google Docs only for review documents
- This maintains version control and searchability

## Organization Checklist

- [ ] Created root folder: `AIAgenticPlatform`
- [ ] Created `/Docs` subfolder structure
- [ ] Created `/Code Scaffolds` subfolder structure
- [ ] Created `/Resources` subfolder
- [ ] Set up sharing permissions
- [ ] Created Master Index.md document
- [ ] Created CHANGELOG.md document
- [ ] Created Decisions Log.md document
- [ ] Linked to GitHub repository (if using both)
- [ ] Established file naming conventions with team
- [ ] Documented review/approval process

## Best Practices for Google Drive Documentation

1. **Use consistent naming** - Agree on naming convention with team
2. **Always date updates** - Add date when significant changes made
3. **Maintain master index** - Keep it current with all docs
4. **Link extensively** - Cross-reference related specs
5. **Use comments for questions** - Don't edit others' docs without discussion
6. **Archive old versions** - Keep folder clean, move old docs to "Archive" folder
7. **Status indicators** - Use [DRAFT], [REVIEW], [APPROVED], [STABLE] in document names
