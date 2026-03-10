# TactiReader — Tactical Reader User Guide  
**Make digital reading as intuitive as a physical book**

---

## 💡 Tip  
This help document can be opened at any time via the top menu: 【Help】→【Help】.  
Every menu item displays its corresponding shortcut key for easy learning while using.

---

## 📖 A Short Story: The Maze Within a Single Document

Xie is studying a 1200-page industrial communication protocol standard.  
The message frame structure appears at the beginning of Chapter 3,  
error code 0x1A is in the middle of Chapter 7,  
the typical communication timing diagram is hidden in Appendix B,  
and physical layer electrical parameters are scattered across multiple subsections of Chapter 5.  

All content resides in a single PDF, yet chapters interleave and cross-references abound.  

He tried WPS and Adobe Reader:  
Though bookmarks were possible, each use required opening the sidebar with the mouse, scrolling to find entries, and clicking to jump-  
frequent hand-eye switching constantly broke his train of thought, snapping newly formed logical connections instantly.  

"I don't need scrolling-I need to see the structure, error codes, timing, and parameters all at once, and switch between them instantly with my keyboard!"  

TactiReader makes this possible-no multiple windows, one PDF, multiple pages on screen, ten-finger blind operation, free comparison.

---

## 🎯 Core Design Philosophy

TactiReader is built for any long-form document with high cross-reference density, including but not limited to:  
- Technical standards and protocol specifications (e.g., IEEE, ISO)  
- Academic monographs and textbooks  
- Legal statutes and policy documents  
- Engineering manuals and design guides  
- Medical guidelines and pharmacopoeias  

We believe:  
- Professional reading is about comparison and connection, not linear scrolling.  
- Efficiency comes from muscle memory: ten fingers over Q to P, ten pages at your fingertips.  
- The system should understand your intent, not force manual configuration.  

Thus, TactiReader introduces these core mechanisms:  
- Smart Dual-Pane Locking: left pane fixed as reference, right pane free to browse  
- Home Progress Tracking: automatically records the farthest page you've reached  
- Instant Bookmarks (Q-P): set/jump/delete bookmarks via ten-key blind operation  
- TOC Navigation: auto-parses embedded PDF table of contents for one-click chapter jumps  
- Numeric Multiplier Navigation (1-9 + <-/->): rapid page skipping  
- Full-Text Search Highlighting: after pressing F, all matches are auto-highlighted  
- Single-Step Navigation Back (Ctrl+A): returns only to the position before the last jump  
- Precise Page Jump (G + Ctrl+G): supports physical page number calibration  
- Focus Pane Mechanism: all operations apply precisely to the current focus pane  

Navigate thousand-page documents like reading your palm-without interrupting your thoughts.

---

## ⌨️ Precise Shortcut Reference

### 🔁 Basic Navigation

- `A` / `D`: Previous / Next page  
- `<-` / `->`: Jump backward or forward by N pages (N set by 1-9)  
- `1`-`9`: Set jump multiplier N  
- `F`: Full-text search (text-based PDFs only)  
  - Matches are auto-highlighted; press Enter to jump to next match  
- `G`: Jump to a specific page number (type number and press Enter)  
- `Ctrl + G`: Calibrate physical page offset  
  - Enter the actual logical page number for the current page (e.g., "this should be page 1")  
  - After calibration, `G` jumps and bookmarks use the corrected logical numbering  
- `Ctrl + Shift + G`: Clear physical page offset, restore original numbering  
- `Ctrl + A`: Single-step navigation back  
  - Returns only to the position before the last cross-page jump  
  - Left and right panes track history independently; only one step is supported  

### 🏠 Home: Your Reading Frontier

Home is not a fixed anchor-it's the farthest page you've reached.  
When you jump (via D, ->, G, search, or bookmarks) to a page beyond the current Home, Home updates automatically.  
Scrolling backward (A) does not reduce Home.  

- `Space`: Instantly return to Home-the frontier of your reading progress  
- `Ctrl + Space`: Manually reset Home to the current focus pane's page  

Use Space to resume main-line reading; use Ctrl+A for quick round-trips to references.

### 📌 Instant Bookmarks: Ten Keys, Instant Access

- `Ctrl + [Q, W, E, R, T, Y, U, I, O, P]`: Set a bookmark on the current focus pane's page  
  - You may name it (e.g., "Frame Structure") or leave it blank  
- `[Q-P]`: Jump to the corresponding bookmark page  
  - Always targets the currently focused pane  
- `Alt + [Q-P]`: Clear the corresponding bookmark  

Q to P spans the top row of the keyboard-no finger movement needed. This is the soul of TactiReader.

### 📚 Table of Contents & Bookmark Panel

- If the PDF contains an embedded table of contents, TactiReader auto-parses it into a clickable tree  
- Click any TOC entry to jump directly to that section (applies to the current focus pane)  
- Click the TOC icon to collapse or expand the outline

### 🔍 Focus Pane Mechanism

All page operations in TactiReader apply to the current focus pane.

- Click left pane -> left pane gains focus (border turns red)  
- Click right pane -> right pane gains focus  
- Initial state: right pane has focus by default  
- All shortcuts (D, G, [Q-P], TOC clicks, etc.) affect only the focus pane  

In dual-pane mode, the left pane can be locked:  
- Once you actively operate the left pane (click + page turn or bookmark jump), it locks automatically and stops following the right pane  
- Thereafter, the right pane browses freely while the left remains fixed as a reference.You can also browse the left pane independently.The two panes are both independent.  

- `C`: Toggle the left pane between locked and following states.
- When in the following mode,the left pane remains the last page before the right pane.  
- When in the lock mode, the left pane will not follow the right pane.But you can browse the left pane independently.

### 🔄 View & Layout

- `Z`: Toggle single-page / dual-page view  
- `N`: Show or hide the left-side bookmark and TOC panel  
- `S`: Immediately save current configuration (bookmarks, annotations, rotation, Home, page offset, etc.)  
- `F11`: Enter or exit full-screen mode  

#### Mouse Operations
- Drag page: Pan view  
- Ctrl + Mouse Wheel: Zoom in/out  
- Drag center divider: Adjust left/right pane width ratio

### 🧭 Page Operations

- `~` (key above Tab): Rotate current focus pane 90 degrees clockwise  
- `X`: Reset current focus pane (zoom, pan, rotation)  
- `Ctrl + X`: Reset dual-pane layout, center the divider  
- `Ctrl + Shift + X`: Clear rotation state for all pages in the document  
- `Ctrl + Shift + R`: Global reset  
  - Clears all bookmarks, annotations, Home, rotations, page offsets, etc.  
  - Restores the document to its initial state upon first opening  
  - This action is irreversible-use with caution  

Left and right panes maintain independent zoom, rotation, and pan states.

### ✏️ Annotation System

- `B`: Enter freehand drawing mode  
- `H`: Enter rectangular highlight mode  
- `V`: Enter text annotation mode (box rotates with page, text always upright)  
  - Press Ctrl + Enter to confirm (Enter inserts a line break)  
- `Esc`: Exit current annotation or text selection mode  

#### Annotation Management
- `Ctrl + Z`: Undo the last annotation  
- `Ctrl + Shift + C`: Clear all annotations on the current page

### 📝 Text Interaction

- `J`: Toggle text selection mode  
  - Once enabled, drag to select text with the mouse  
  - Selected text can be copied via Ctrl+C or right-click -> "Copy"  
- Exit selection mode: press `J` again or press `Esc`

### 📁 File & Data Mechanism

#### File Operations (via Menu)
- Open PDF: Load a new document  
- Save As PDF: Export current annotated pages as a new PDF  
- Export Notebook: Package all annotations, bookmarks, and settings into a `.tactinote` file  
- Open Notebook: Load a `.tactinote` file (includes PDF + full session state)  

A notebook is a compressed archive containing the original PDF and a `session.json` file (recording all states).  
Share a `.tactinote` file to give others an identical reading environment.
### 🗂️ Multi-Tab Support: Parallel Reading, Zero Interference

TactiReader now supports opening multiple PDFs or `.tactinote` notebooks simultaneously, with each document residing in its own tab and maintaining fully isolated state.

- A new tab is automatically created when opening a document  
- Tabs can be reordered by dragging; hovering over the right side of a tab reveals a close button for quick dismissal  
- The content of the active tab is displayed in the main window  

#### Open in New Window (via Right-Click)
- Right-click on any tab  
- Select **【Open in New Window】**  
- This launches an independent TactiReader instance, enabling true side-by-side document comparison  

> This feature is especially useful for:  
> - Comparing two different versions of a technical standard  
> - Reading a textbook while referencing solution manuals  
> - Separating a main document from its appendix or reference guide  

All tabs share the same recent files list, but each preserves its own bookmarks, annotations, Home position, and page offset. Switching tabs instantly restores the complete reading context.

#### Data Persistence
All data (annotations, bookmarks, rotations, Home, page offsets, etc.) is auto-saved to:  
`%APPDATA%\TactiReader\tactireader_bookmarks\`  
Each PDF has its own config file. States are fully restored when reopening the software.

---

## 💡 How Xie Uses It

1. Open `Industrial Protocol Standard.pdf`  
2. Notice pages 1-9 are cover/table of contents; real page 1 starts at PDF page 10  
3. On PDF page 10, press `Ctrl+G`, enter `1` to calibrate physical page numbering  
4. Press `G`, type `87`, Enter-to jump to the true page 87 (frame structure definition)  
5. Press `Ctrl+Q`, name bookmark "Frame Structure"  
6. Use TOC to enter Chapter 7, press `3` + `->` to locate error code 0x1A, press `Ctrl+W` to bookmark  
7. In Appendix B, find the timing diagram, press `Ctrl+E` to bookmark  
8. In Chapter 5, locate the electrical parameter table, press `Ctrl+R` to bookmark  
9. Click left pane, press `Q` to lock frame structure; click right pane, press `W` to view error code  
10. Press `F`, search `0x1A`-all matches highlighted. Irrelevant result? Press `Ctrl+A` to return instantly. Main reading interrupted? Press `Space` to go back to Home. When done, press `S` to save.

---

> **TactiReader — Not a PDF reader, but your tactical cognitive exoskeleton.**  
> Let knowledge connect faster than your thoughts can jump.

© 2026 Personal Project · Independently developed by Xie  
Version 2.0 — Tactical Complete Edition
