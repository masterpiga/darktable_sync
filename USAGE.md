# darktable XMP Sync Tool - Usage Guide

## Overview

The darktable XMP Sync Tool is a desktop application that helps you synchronize XMP metadata files between two different darktable libraries. It's particularly useful for managing edits across multiple darktable installations or maintaining separate archive and working directories.

## Key Concepts

### Archive vs Session Directories

- **Archive Directory**: Your reference/master library containing the baseline XMP files
- **Session Directory**: Your working library where you make current edits

The workflow assumes that *Session directory* is a copy of (a subset of)
*Archive directory*. The two versions eventually diverge, and you want to reconcile them.

## Common Use Cases

### Scenario 1: Laptop/Desktop Sync
- Archive: Desktop with full library
- Session: Laptop with subset for travel
- Sync: Merge laptop edits back to desktop

### Scenario 2: Archive Maintenance
- Archive: Master library with finished edits
- Session: Working copy for experimentation
- Sync: Promote successful experiments to archive

### Scenario 3: Collaborative Editing
- Archive: Shared reference library
- Session: Individual working copies
- Sync: Merge approved changes to shared library

### Scenario 4: Backup and Recovery
- Archive: Backup of previous edit state
- Session: Current working library
- Sync: Selectively restore previous edits

## Clarification

This program only works on directories that contain
* Two intersecting sets of XMPs and the accompany RAW files
* Organized in a matching hierarchy

This program is not meant to:
* Merge two directories containing disjoint sets of files, or
* Merge two directories where the same files are organized according to different
directory structures.

## Getting Started

### Initial Setup

1. **Launch the application**
   - Run the executable or `python main.py` from the src directory

2. **Configure directories**
   - Click "Archive directory" button to select your reference library
   - Click "Session directory" button to select your working library

    The application will remember these selections for future use

3. **Configure settings** (optional)
   - Go to File → Settings... (or Cmd+, on macOS)
   - Set darktable CLI path if not auto-detected
   - Adjust preview generation settings
   - Configure keyboard shortcuts
   - Enable/disable backup creation

### Basic Workflow

1. **Scan for differences**
   - Click the "Scan" button
   - The application will compare XMP files between directories
   - Results appear in the "XMPs with differences" section

2. **Review differences**
   - Select files from the tree view
   - View edit history differences in the table
   - Compare visual previews side-by-side

3. **Plan actions**
   - For each file, choose an action:
     - **Keep archive**: Copy archive version to session
     - **Keep session**: Copy session version to archive  
     - **Keep both**: Keep both versions (no synchronization)
     - **No action**: Skip this file

4. **Execute changes**
   - Use "Dry run" checkbox to preview changes without applying them
   - Click "Execute planned actions" to apply your decisions
   - Backups are created automatically (if enabled)

## Interface Guide

### Main Window Layout

The interface is divided into two main areas:

#### Left Panel: File Management
- **Input selection**: Directory choosers and scan button
- **XMPs with differences**: Tree view of files with differences
- **Selected XMP**: Details for the currently selected file
- **Planned action**: Action buttons for the selected file

#### Right Panel: Preview Comparison
- **Archive preview**: Shows how the image looks with archive XMP
- **Session preview**: Shows how the image looks with session XMP
- **Toolbar**: Zoom, orientation, and comparison controls

### File Tree View

Files are organized in a hierarchical tree structure matching your directory layout:
- **Folders**: Expandable directory structure
- **Files**: Individual XMP files with differences
- **Labels**: Show planned actions in brackets (e.g., `[Keep session]`)

### Filtering Options

Use the checkboxes at the bottom of the file list to filter:
- **Decided**: Files with planned actions
- **Undecided**: Files without planned actions
- Counter shows number of files in each category

### Edit History Diff Table

Shows differences between archive and session versions:
- **Step**: darktable processing step number
- **Module**: darktable module name (e.g., exposure, color correction)
- **+**: Present in session but not archive
- **-**: Present in archive but not session  
- **P**: Parameters differ between versions
- **M**: Module order differs between versions

## Actions Explained

### Keep Archive
- Copies the archive version of the XMP file to the session directory
- Use when you want to revert session changes to match the archive
- Original session file is backed up (if enabled)

### Keep Session  
- Copies the session version of the XMP file to the archive directory
- Use when you want to promote session changes to the archive
- Original archive file is backed up (if enabled)

### Keep Both
- No files are copied
- Both versions remain unchanged
- Use when you want to maintain divergent edit histories

### No Action
- Default state for all files
- No synchronization occurs
- Files remain in their current state

## Preview System

### Visual Comparison
- **Side-by-side**: Archive and session previews displayed simultaneously
- **Synchronized**: Zoom and pan operations affect both previews
- **Color coding**: Green border indicates the version that will be kept

### Preview Generation
- Previews are generated using darktable-cli
- Generation happens in the background
- Cache system avoids regenerating identical previews
- "Queued..." appears while previews are being generated

### Preview Controls
- **Zoom**: Mouse wheel or keyboard shortcuts
- **Pan**: Click and drag to move around zoomed images
- **Orientation**: Toggle between horizontal and vertical layout
- **Compare in darktable**: Launch darktable with both versions loaded

## Keyboard Shortcuts

### Navigation
- **Up/Down arrows**: Navigate through file list
- **Custom shortcuts**: Navigate to next/previous undecided file

### Actions
- **Number keys**: Apply actions (customizable)
- **Custom shortcuts**: Quick access to specific actions

### Preview Controls
- **+/-**: Zoom in/out
- **Arrow keys**: Pan around zoomed images
- **Custom shortcuts**: Toggle orientation, fine-tune scrolling

*Note: All shortcuts are customizable in File → Settings → Keyboard Shortcuts*

## Advanced Features

### Backup System
- Automatic backups created before overwriting files
- Backup files named with `.dtsync.bak` extension
- Can be enabled/disabled in settings
- Backups are hidden files (dot prefix)

### Compare in darktable
- Launch darktable with both versions loaded
- Make edits directly in darktable
- Changes are detected and previews updated automatically
- Choose which changes to keep after darktable closes

### Batch Operations
- Use filtering to work with specific subsets
- Execute all planned actions at once

## Settings Configuration

### darktable Integration
- **darktable CLI path**: Path to darktable-cli executable
- **Enable OpenCL**: GPU acceleration for preview generation

### Preview Generation
- **Max dimension**: Maximum preview size (affects quality vs speed)
- **Max threads**: Concurrent preview generation jobs
- Adjust based on your system capabilities

### Keyboard Shortcuts
- **Customizable shortcuts**: Assign keys to all actions
- **Default shortcuts**: Sensible defaults provided

### Backups
- **Enable backups**: Toggle backup creation
- **Backup location**: Same directory as original files
- **Backup naming**: Uses `.dtsync.bak` extension

## Tips and Best Practices

### Workflow Efficiency
1. **Use filtering**: Focus on undecided files first
2. **Keyboard shortcuts**: Much faster than mouse clicking
3. **Dry run first**: Always test before applying changes

### File Management
1. **Regular backups**: Even with built-in backups, maintain external copies
2. **Version control**: Consider using git for XMP files. If you do, then you may want to disable backups.

### Troubleshooting
1. **Missing previews**: Check darktable-cli path in settings
2. **Slow performance**: Reduce thread count or preview size
3. **Keyboard shortcuts not working**: Check for conflicts in settings

## Limitations and Considerations

### Performance
- Preview generation is CPU/GPU intensive
- Large libraries may take time to scan