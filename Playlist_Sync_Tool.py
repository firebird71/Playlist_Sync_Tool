#!/usr/bin/env python3
# Playlist_Sync_Tool.py
# Created to be used on Linux Mint 
# Created by Chris Smith, Grok and Gemini
# MIT License

# Copyright (c) 2026 Chris Smith

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import subprocess
import os
import json
import re
import getpass
from pathlib import Path
import shutil

import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, simpledialog
import ctkmessagebox3 as messagebox

try:
    from mutagen import File as MutagenFile
except ImportError:
    try:
        from mutagen._file import File as MutagenFile
    except ImportError:
        MutagenFile = None

CONFIG_FILE = Path.home() / ".config" / "playlist_sync" / "config.json"
# os.environ["TK_USE_INPUT_METHOD"] = "gtk"  # Signals tkinter to bridge with GTK


class PlaylistSyncGUI(ctk.CTk):
    def __init__(self):
        install_local_icons()
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # --- FORCE NATIVE FILE DIALOGS TO USE DARK COLORS ---
        self.option_add('*Background', '#1F1F1F')       # Match CustomTkinter dark background
        self.option_add('*Foreground', '#DCE4EE')       # Off-white text color
        self.option_add('*Button.Background', '#1F6AA5')# Slightly lighter gray for buttons
        self.option_add('*Button.Foreground', '#DCE4EE')# White text for buttons
        self.option_add('*Entry.Background', '#2A2A2A') # Dark inputs
        self.option_add('*Entry.Foreground', '#DCE4EE')
        # -----------------------------------------------------

        self.title("Playlist Smart Sync Tool")
        self.geometry("950x980")
        self.minsize(850, 740)

        # Variables
        self.playlist_path = ctk.StringVar()
        self.pc_music_root = ctk.StringVar()
        self.destination_root = ctk.StringVar()
        self.verbose = ctk.BooleanVar(value=True)
        self.preserve_structure = ctk.BooleanVar(value=True)
        self.delete_extra = ctk.BooleanVar(value=False)
        self.protected_items = ctk.StringVar(value=".nomedia,.thumbnails,Folder.jpg,cover.jpg,AlbumArt")
        self.upload_playlist = ctk.BooleanVar(value=False)
        self.preserve_playlists_folder = ctk.BooleanVar(value=True)
        # Device tracking
        self.device_mapping = {}   # "Clean Name" → "Full Path"
        self.is_initial_boot = True
        
        # Icon
        icon_path = Path.home() / ".local/share/icons/hicolor/256x256/apps/playlist-sync-tool.png"
        try:
            self.iconphoto(True, tk.PhotoImage(file=str(icon_path)))
        except Exception as e:
            print(f"Warning: Could not find {icon_path}: {e}\n")

        self.load_config()
        self.create_widgets()
        
        # Schedule initial hardware probe loop sequence
        self.after(100, self.refresh_mounts)

    # ====================== Config ======================
    def load_config(self):
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.playlist_path.set(config.get("last_playlist", ""))
                    self.pc_music_root.set(config.get("pc_music_root", ""))
                    self.destination_root.set(config.get("destination_root", ""))
                    self.verbose.set(config.get("verbose", True))
                    self.preserve_structure.set(config.get("preserve_structure", True))
                    self.delete_extra.set(config.get("delete_extra", False))
                    self.protected_items.set(config.get("protected_items", ".nomedia,.thumbnails,Folder.jpg,cover.jpg,AlbumArt"))
                    self.upload_playlist.set(config.get("upload_playlist", False))
                    self.preserve_playlists_folder.set(config.get("preserve_playlists_folder", True))
        except Exception as e:
            print(f"Warning: Could not Load {CONFIG_FILE}: {e}\n")

    def save_config(self):
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            config = {
                "last_playlist": self.playlist_path.get(),
                "pc_music_root": self.pc_music_root.get(),
                "destination_root": self.destination_root.get(),
                "verbose": self.verbose.get(),
                "preserve_structure": self.preserve_structure.get(),
                "delete_extra": self.delete_extra.get(),
                "protected_items": self.protected_items.get(),
                "upload_playlist": self.upload_playlist.get(),
                "preserve_playlists_folder": self.preserve_playlists_folder.get()
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not Save {CONFIG_FILE}: {e}\n")

    # ====================== GUI ======================
    def create_widgets(self):
        header = ctk.CTkLabel(self, text="🎵 Playlist Smart Sync Tool", 
                             font=ctk.CTkFont(size=26, weight="bold"))
        header.pack(pady=20)

        # Rows 1 & 2 Playlist file and PC Music Root
        self._create_input_row("1. Playlist (.m3u8)", self.playlist_path, self.browse_playlist)
        self._create_input_row("2. PC Music Root", self.pc_music_root, self.browse_pc_music)

        # Row 3 Destination Device Frame
        device_frame = ctk.CTkFrame(self)
        device_frame.pack(fill="x", padx=30, pady=10)
        
        # Destination Device Frame
        path_row_frame = ctk.CTkFrame(device_frame, fg_color="transparent")
        path_row_frame.pack(fill="x", padx=5, pady=5)

        # Pack the label to the left
        ctk.CTkLabel(path_row_frame, text="3. Destination Device:", 
                     font=ctk.CTkFont(size=12, weight="bold"), 
                     width=160, anchor="w").pack(side="left")

        # Destination Device Button Row
        btn_row = ctk.CTkFrame(path_row_frame)
        btn_row.pack(pady=8, fill="x")
        self.device_dropdown = ctk.CTkOptionMenu(btn_row, values=["No devices detected"], command=self.on_device_selected, width=365, dynamic_resizing=True)
        self.device_dropdown.pack(side="left", padx=5)
        # Bind mouse-wheel scroll behavior on mouseover hover
        self.device_dropdown.bind("<MouseWheel>", self.handle_dropdown_scroll)  # Windows / macOS
        self.device_dropdown.bind("<Button-4>", self.handle_dropdown_scroll)    # Linux scroll up
        self.device_dropdown.bind("<Button-5>", self.handle_dropdown_scroll)    # Linux scroll down

        ctk.CTkButton(btn_row, text="🔄 Refresh Devices", command=self.refresh_mounts, width=100).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="📁 Browse", command=self.browse_manually, width=100).pack(side="right", padx=5)

        # Destination Device Path Display Label
        self.lbl_target_display = ctk.CTkLabel(device_frame, text="Target Sync Path: None Selected", font=("Helvetica", 12, "italic"), text_color="#bbbbbb", anchor="w")
        self.lbl_target_display.pack(side="left", expand=True, padx=(5, 0))

        # File Options
        opt_frame = ctk.CTkFrame(self)
        opt_frame.pack(pady=15, padx=30)  # , fill="x"
        ctk.CTkCheckBox(opt_frame, text="Show detailed list", variable=self.verbose).pack(side="left", padx=15)
        ctk.CTkCheckBox(opt_frame, text="Preserve Folder Structure", variable=self.preserve_structure).pack(side="left", padx=15)
        
        delete_frame = ctk.CTkFrame(opt_frame)
        delete_frame.pack(side="left", padx=15)
        ctk.CTkCheckBox(delete_frame, text="🗑️ Delete extra files", variable=self.delete_extra, fg_color="#ff5555").pack(side="left")
        ctk.CTkButton(delete_frame, text="Edit Protected", width=130, command=self.edit_protected_list, height=28).pack(side="left", padx=(8,0))

        # PLAYLIST OPTIONS
        playlist_opt_frame = ctk.CTkFrame(self, fg_color="transparent")
        playlist_opt_frame.pack(pady=(0, 10), padx=30)

        ctk.CTkCheckBox(playlist_opt_frame, text="Upload current playlist", variable=self.upload_playlist).pack(side="left", padx=15)
        ctk.CTkCheckBox(playlist_opt_frame, text="Preserve 'Playlists' folder", variable=self.preserve_playlists_folder).pack(side="left", padx=15)
        
        ctk.CTkLabel(playlist_opt_frame, text="* Note: Uploaded playlist must use relative paths.", 
                     text_color="gray", font=ctk.CTkFont(size=12, slant="italic")).pack(side="left", padx=15)

        # Action Buttons
        action_frame = ctk.CTkFrame(self)
        action_frame.pack(pady=20)
        ctk.CTkButton(action_frame, text="📊 Calculate Size", command=self.calculate, width=170).pack(side="left", padx=6)
        ctk.CTkButton(action_frame, text="🔍 Check Duplicates", command=self.check_duplicates, width=170, fg_color="#A5611F").pack(side="left", padx=6)
        ctk.CTkButton(action_frame, text="🔍 Preview Sync", command=self.preview_sync, width=170, fg_color="#A51F9E").pack(side="left", padx=6)
        ctk.CTkButton(action_frame, text="▶ Start Sync", command=self.start_sync, width=170, fg_color="#008643").pack(side="left", padx=6)

        # Results
        self.result_text = ctk.CTkTextbox(self, height=420, font=ctk.CTkFont(family="Consolas", size=11))
        self.result_text.pack(fill="both", expand=True, padx=30, pady=10)

    def _create_input_row(self, label, var, browse_cmd):
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=30, pady=8)
        ctk.CTkLabel(frame, text=label, width=160, anchor="w").pack(side="left", padx=5)
        ctk.CTkEntry(frame, textvariable=var, height=35).pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(frame, text="Browse", width=100, command=browse_cmd).pack(side="right", padx=5)

    def handle_dropdown_scroll(self, event):
        """Allows scrolling up and down with the mouse wheel on mouseover to cycle choices."""
        current_values = self.device_dropdown.cget("values")
        if not current_values or current_values == ["No devices detected"]:
            return

        current_selection = self.device_dropdown.get()
        try:
            current_index = current_values.index(current_selection)
        except ValueError:
            return

        # Determine scroll direction across platforms
        # Linux uses explicit Button-4/5 mouse events, while Windows/macOS reads event.delta
        if event.num == 4 or event.delta > 0:
            # Scroll up -> Go to previous index item
            next_index = max(0, current_index - 1)
        elif event.num == 5 or event.delta < 0:
            # Scroll down -> Go to next index item
            next_index = min(len(current_values) - 1, current_index + 1)
        else:
            return

        # Trigger selection change if the index actually moved
        if next_index != current_index:
            new_selection = current_values[next_index]
            self.device_dropdown.set(new_selection)
            self.on_device_selected(new_selection)

    def show_custom_info(self, title, message):
        popup = ctk.CTkToplevel(self)
        popup.title(title)
        popup.geometry("325x250")
        
        popup.update_idletasks()
        popup.deiconify()
        popup.attributes("-topmost", True)
        popup.grab_set()  
        
        x = self.winfo_x() + (self.winfo_width() // 2) - (popup.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (popup.winfo_height() // 2)
        popup.geometry(f"+{x}+{y}")

        msg_label = ctk.CTkLabel(popup, text=message, justify="left", font=("Arial", 12), wraplength=275)
        msg_label.pack(padx=20, pady=(20, 10), fill="both", expand=True)

        close_btn = ctk.CTkButton(popup, text="Dismiss", width=100, command=popup.destroy)
        close_btn.pack(pady=(0, 20))

    # ====================== Device Management ======================
    def refresh_mounts(self):
        # Cache the user's current selection before refreshing
        previous_selection = self.device_dropdown.get()

        self.device_mapping.clear()
        username = getpass.getuser()
        uid = os.getuid()

        # 1. Scan MTP Devices (Phones)
        gvfs_path = Path(f"/run/user/{uid}/gvfs")
        mtp_list = []
        if gvfs_path.exists():
            for item in gvfs_path.iterdir():
                raw_path = str(item)
                mtp_list.append(raw_path)
                marketing_name = get_device_marketing_name(raw_path)
                clean_name = f"📱 MTP: {marketing_name} ({clean_mtp_path(raw_path)})"
                self.device_mapping[clean_name] = raw_path

        # 2. Scan USB Storage Devices
        user_media_path = Path(f"/media/{username}")
        media_list = []
        if user_media_path.exists():
            for item in user_media_path.iterdir():
                raw_path = str(item)
                media_list.append(raw_path)
                clean_name = f"💾 USB: {item.name} (USB/External Volume)"
                self.device_mapping[clean_name] = raw_path

        # 3. Update Dropdown and preserve previous selection if possible
        if self.device_mapping:
            device_names = list(self.device_mapping.keys())
            self.device_dropdown.configure(values=device_names)
            
            # Grab the path that was loaded from config.json (or currently active)
            saved_dest = self.destination_root.get()
            matched_device = None

            # See if the saved path belongs to any currently connected device
            if saved_dest:
                for name, raw_path in self.device_mapping.items():
                    if saved_dest.startswith(raw_path):
                        matched_device = name
                        break
            
            if matched_device:
                # We found the device! Set the dropdown to its name.
                self.device_dropdown.set(matched_device)
                # Note: We DO NOT call self.on_device_selected() here because that 
                # would overwrite your carefully saved path with a fresh default search.
                self.update_path_display(saved_dest)
            else:
                # Device not found (or first boot). Fallback to the first available device.
                self.device_dropdown.set(device_names[0])
                self.on_device_selected(device_names[0])
        else:
            self.device_dropdown.configure(values=["No devices detected"])
            self.device_dropdown.set("No devices detected")
            self.update_path_display("None")

        # 4. Show popup only after initial boot
        if self.is_initial_boot:
            self.is_initial_boot = False
        else:
            msg = "Detected Devices:\n\n"
            if mtp_list: msg += "📱 MTP:\n" + "\n".join(mtp_list) + "\n\n"
            if media_list: msg += "💾 USB:\n" + "\n".join(media_list)
            if not mtp_list and not media_list:
                msg = "No devices found."
            
            # self.show_custom_info("Devices", msg)
            messagebox.showsuccess(self, "Devices", msg)

    def on_device_selected(self, selection):
        if selection == "No devices detected":
            self.destination_root.set("")
            return
        
        raw_path = self.device_mapping.get(selection, "")
        
        # Call the smart pathfinding function here!
        smart_path = find_media_root(raw_path) 
        
        self.destination_root.set(smart_path)
        self.update_path_display(self.destination_root.get())
        self.save_config()

    def browse_manually(self):
        current = self.device_dropdown.get()
        if current == "No devices detected":
            return
        base = self.device_mapping.get(current, Path.home())
        p = filedialog.askdirectory(initialdir=base)
        if p:
            self.destination_root.set(p)
        self.update_path_display(self.destination_root.get())
        self.save_config()

    def update_path_display(self, path_value):
        self.lbl_target_display.configure(text=f"Target Sync Path: {path_value}")

    # ====================== Browse ======================
    def browse_playlist(self):
        p = filedialog.askopenfilename(
            initialdir=str(Path.home() / "Music" / "Playlists"),
            filetypes=[("M3U8 Files", "*.m3u8")]
        )
        if p: 
            self.playlist_path.set(p)
            self.save_config()

    def browse_pc_music(self):
        p = filedialog.askdirectory(initialdir=str(Path.home() / "Music"))
        if p: 
            self.pc_music_root.set(p)
            self.save_config()

    def quick_browse_destination(self, start_dir):
        initial = str(Path(start_dir).expanduser())
        p = filedialog.askdirectory(initialdir=initial)
        if p:
            self.destination_root.set(p)
            self.save_config()
    
    def edit_protected_list(self):
        current = self.protected_items.get()
        new_list = simpledialog.askstring(
            "Edit Protected Items",
            "Enter items to protect (comma separated):\n\n"
            "Example: .nomedia,.thumbnails,Folder.jpg,cover.jpg,AlbumArt",
            initialvalue=current,
            parent=self
        )
        if new_list is not None:
            self.protected_items.set(new_list.strip())
            self.save_config()

    # ====================== Helpers ======================
    def get_file_size(self, path: str) -> int:
        try: return os.path.getsize(path)
        except: return 0

    def format_size(self, b: int) -> str:
        """Format the Music file size"""
        if b == 0: return "0 B"
        size = float(b)
        for u in ['B','KB','MB','GB','TB']:
            if size < 1024: return f"{size:.2f} {u}"
            size /= 1024
        return f"{size:.2f} PB"

    def get_protected_list(self):
        """Returns set of user-defined protected items from the config.json"""
        raw = self.protected_items.get().strip()
        if not raw:
            return {".nomedia", ".thumbnails", "folder.jpg", "cover.jpg", "albumart"}
        return {item.strip().lower() for item in raw.split(',') if item.strip()}

    def should_delete(self, path: Path) -> bool:
        """Check if file/folder should be deleted (respects protected items and parent directories)"""
        if not self.delete_extra.get():
            return False

        try:
            dest_root = Path(self.destination_root.get().strip())
            # Break down the path relative to your device's Music root folder into lowercase parts
            rel_parts = [p.lower() for p in path.relative_to(dest_root).parts]
        except ValueError:
            rel_parts = [p.lower() for p in path.parts]

        # 1. Protect Playlists folder and its contents if enabled
        if self.preserve_playlists_folder.get() and "playlists" in rel_parts:
            return False

        # 2. Check if the file name OR any of its parent folders match your protected list
        protected = self.get_protected_list()
        for part in rel_parts:
            if any(p in part for p in protected):
                return False

        return True
    
    def needs_update(self, src: Path, target_path: Path, existing_versions: list) -> bool:
        """Returns True if the file needs to be copied/replaced"""
        # Check if correct file already exists in correct location
        correct_file = next((ex for ex in existing_versions 
                           if ex.name == src.name and ex.parent == target_path.parent), None)

        if correct_file:
            # Compare modification times
            try:
                pc_mtime = src.stat().st_mtime
                phone_mtime = correct_file.stat().st_mtime
                # Only update if PC file is significantly newer (>1 hour)
                if pc_mtime > phone_mtime + 3600:
                    return True
                else:
                    return False  # Phone version is newer or same
            except:
                return False  # If we can't compare times, assume it's good

        # No matching file found → needs copy
        return True

    # ====================== Core Logic ======================
    def get_tracks_from_playlist(self):
        playlist_file = self.playlist_path.get().strip()
        if not playlist_file or not os.path.isfile(playlist_file):
            return []
        with open(playlist_file, 'r', encoding='utf-8', errors='ignore') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]

    def build_file_map(self):
        """Returns list of (source_path, clean_relative_path_from_music_root)"""
        pc_root = Path(self.pc_music_root.get()).resolve()
        if not pc_root.exists():
            messagebox.showerror(self, "Error", "PC Music Root not found!")
            return []

        tracks = self.get_tracks_from_playlist()
        file_map = []

        for track in tracks:
            if not track:
                continue
            track_p = Path(track)

            candidates = []

            # 1. Direct from PC Music Root
            if pc_root:
                candidates.append(pc_root / track_p)

            # 2. Relative to playlist location (with normalization)
            playlist_dir = Path(self.playlist_path.get()).parent.resolve()
            candidates.extend([
                playlist_dir / track_p,
                playlist_dir.parent / track_p,
                playlist_dir.parent.parent / track_p
            ])

            for cand in candidates:
                if cand.is_file():
                    # Resolve to absolute path first, then get clean relative path
                    abs_path = cand.resolve()

                    try:
                        rel_path = abs_path.relative_to(pc_root)
                    except ValueError:
                        # Fallback: try to make it relative manually
                        try:
                            rel_path = abs_path.relative_to(pc_root.parent)
                        except ValueError:
                            rel_path = abs_path.name

                    file_map.append((abs_path, rel_path))
                    break
            else:
                # Optional: log missing files
                print(f"Warning: Could not find {track}")

        return file_map

    def build_destination_file_map(self, dest_root: Path):
        file_map = {}
        self.result_text.insert(tk.END, "Scanning destination...\n")
        self.update()
        try:
            for file_path in dest_root.rglob("*"):
                if file_path.is_file():
                    stem = file_path.stem.lower()
                    if stem not in file_map:
                        file_map[stem] = []
                    file_map[stem].append(file_path)
        except Exception as e:
            self.result_text.insert(tk.END, f"Scan warning: {e}\n")
        self.result_text.insert(tk.END, f"Found {len(file_map)} unique tracks on destination.\n")
        return file_map

# ====================== Calculate/Sync/Cleanup ======================
    def preview_sync(self):
        """Triggers the sync logic in dry-run mode to show what WILL happen."""
        self.run_sync_logic(dry_run=True)

    def start_sync(self):
        """Triggers the actual execution of the sync."""
        playlist_file = Path(self.playlist_path.get().strip())
        device_name = self.device_dropdown.get()
        msg=f"Sync Playlist: {playlist_file.name}\n to Device: {device_name}"
        if messagebox.askyesno(self, "Start Sync?", msg) == "No": 
            return
        self.run_sync_logic(dry_run=False)

    def run_sync_logic(self, dry_run: bool):
        """Master function that handles both Preview and Execution to ensure they never diverge."""
        self.result_text.delete(1.0, tk.END)
        self.save_config()

        dest_root = Path(self.destination_root.get().strip())
        if not dest_root.exists():
            messagebox.showerror(self, "Error", "Destination not found!")
            return

        file_map = self.build_file_map()
        if not file_map:
            self.result_text.insert(tk.END, "No files found from playlist.\n")
            return

        dest_files = self.build_destination_file_map(dest_root)

        # Action Lists
        to_copy = []
        to_move = []
        to_remove = []
        already_good = 0
        total_transfer_size = 0
        playlist_stems = {src.stem.lower() for src, _ in file_map}

        self.result_text.insert(tk.END, f"Analyzing {len(file_map)} tracks...\n\n")
        self.update()

        # --- 1. CLASSIFY ALL PLAYLIST TRACKS ---
        for src, rel_path in file_map:
            target_path = dest_root / rel_path.with_name(src.name)
            stem = src.stem.lower()
            existing = dest_files.get(stem, [])

            # A. Check if perfect
            correct_exists = any(ex.name == src.name and ex.parent == target_path.parent for ex in existing)
            if correct_exists:
                already_good += 1
                continue

            # B. Look for same file in wrong folder (Rename/Move case)
            wrong_location = next((ex for ex in existing if ex.name == src.name), None)
            if wrong_location:
                to_move.append((wrong_location, target_path))
            else:
                # C. Needs to be copied from PC
                to_copy.append((src, target_path))
                total_transfer_size += self.get_file_size(str(src))
                
                # If we are copying a new one, mark any old/bad versions for deletion
                for old in existing:
                    if self.should_delete(old):
                        to_remove.append(old)

        # --- 2. CLASSIFY EXTRA DESTINATION FILES (If Delete is enabled) ---
        if self.delete_extra.get():
            for stem, paths in dest_files.items():
                if stem not in playlist_stems:
                    for p in paths:
                        if self.should_delete(p):
                            to_remove.append(p)

        # --- 3. INSPECT PLAYLIST CONTENT FOR RESERVED SYMBOLS (#) ---
        playlist_file = Path(self.playlist_path.get().strip())
        sanitized_lines_count = 0
        fixed_playlist_lines = []

        if playlist_file.is_file():
            try:
                playlist_content = playlist_file.read_text(encoding="utf-8")
                for line in playlist_content.splitlines():
                    if line.startswith("#"):
                        # Maintain standard metadata/structural tags
                        fixed_playlist_lines.append(line)
                    else:
                        # Inspect the path for a unsafe '#' character
                        if "#" in line:
                            sanitized_lines_count += 1
                            fixed_playlist_lines.append(line.replace("#", "%23"))
                        else:
                            fixed_playlist_lines.append(line)
            except Exception as e:
                self.result_text.insert(tk.END, f"⚠️ Warning: Could not read local playlist file for analysis: {e}\n")

        # --- 4. PRINT THE PREVIEW SUMMARY ---
        mode_title = "PREVIEW COMPLETE" if dry_run else "STARTING SYNC"
        
        self.result_text.insert(tk.END, "="*90 + "\n")
        self.result_text.insert(tk.END, f"Total tracks in playlist : {len(file_map)}\n")
        self.result_text.insert(tk.END, f"Tracks already correct   : {already_good}\n")
        # self.result_text.insert(tk.END, f"Need to copy             : {len(to_copy)}\n")
        # self.result_text.insert(tk.END, f"Need to move/rename      : {len(to_move)}\n")
        # self.result_text.insert(tk.END, f"Files to delete          : {len(to_remove)}\n")
        self.result_text.insert(tk.END, f"Data to transfer         : {self.format_size(total_transfer_size)}\n\n")

        # Show Playlist Upload & Sanitization Status
        if self.upload_playlist.get() and playlist_file.is_file():
            if sanitized_lines_count > 0:
                self.result_text.insert(tk.END, f"📄 Playlist WILL be uploaded: {playlist_file.name} (Sanitizing {sanitized_lines_count} paths containing '#')\n\n")
            else:
                self.result_text.insert(tk.END, f"📄 Playlist WILL be uploaded: {playlist_file.name} (Paths are already safe)\n\n")

        if to_copy and self.verbose.get():
            self.result_text.insert(tk.END, f"Files to COPY: {len(to_copy)}\n")
            for src, dest in to_copy[:30]:
                self.result_text.insert(tk.END, f"  → {dest.relative_to(dest_root)}\n")

        if to_move and self.verbose.get():
            self.result_text.insert(tk.END, f"\nFiles to MOVE: {len(to_move)}\n")
            for src, dest in to_move[:30]:
                self.result_text.insert(tk.END, f"  → {dest.relative_to(dest_root)}\n")
                
        if to_remove and self.verbose.get():
            self.result_text.insert(tk.END, f"\nFiles to DELETE: {len(to_remove)}\n")
            for p in to_remove[:25]:
                self.result_text.insert(tk.END, f"  ❌ {p.relative_to(dest_root)}\n")

        self.result_text.insert(tk.END, f"\n=== {mode_title} ===\n")
        self.update()

        # --- 5. STOP HERE IF DRY RUN ---
        if dry_run:
            return

        # --- 6. EXECUTE THE ACTIONS ---
        copied = 0
        deleted = 0
        errors = 0

        # Execute Moves
        for wrong_location, target_path in to_move:
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(['gio', 'move', str(wrong_location), str(target_path)], check=True, timeout=30)
                self.result_text.insert(tk.END, f"↷ Renamed/Moved: {target_path.name}\n")
            except Exception as e:
                errors += 1
                self.result_text.insert(tk.END, f"Error moving {target_path.name}: {e}\n")
            self.update()

        # Execute Deletes
        for old in to_remove:
            try:
                subprocess.run(['gio', 'remove', '-f', str(old)], check=True, timeout=15)
                deleted += 1
                self.result_text.insert(tk.END, f"🗑️ Removed: {old.name}\n")
            except Exception as e:
                errors += 1
                self.result_text.insert(tk.END, f"Error deleting {old.name}: {e}\n")
            self.update()

        # Execute Copies
        for src, target_path in to_copy:
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(['gio', 'copy', str(src), str(target_path)], check=True, timeout=60)
                copied += 1
                self.result_text.insert(tk.END, f"→ Copied: {src.name}\n")
            except Exception as e:
                errors += 1
                self.result_text.insert(tk.END, f"✗ Failed copying {src.name}: {e}\n")
            self.update()

        # Upload Sanitized Playlist File
        if self.upload_playlist.get() and playlist_file.is_file() and fixed_playlist_lines:
            dest_playlist_dir = dest_root / "Playlists"
            dest_playlist_dir.mkdir(parents=True, exist_ok=True)
            dest_playlist_path = dest_playlist_dir / playlist_file.name
            
            try:
                # Write pre-calculated clean path array directly to a local home temp cache file
                temp_playlist = Path.home() / ".cache" / playlist_file.name
                temp_playlist.parent.mkdir(parents=True, exist_ok=True)
                temp_playlist.write_text("\n".join(fixed_playlist_lines) + "\n", encoding="utf-8")

                # Push to your Android Device via GIO
                subprocess.run(['gio', 'remove', '-f', str(dest_playlist_path)], check=False, stderr=subprocess.DEVNULL)
                subprocess.run(['gio', 'copy', str(temp_playlist), str(dest_playlist_path)], check=True, timeout=15)
                
                if temp_playlist.exists():
                    temp_playlist.unlink()

                self.result_text.insert(tk.END, f"📄 Copied & Sanitized Playlist: {playlist_file.name}\n")
            except Exception as e:
                errors += 1
                self.result_text.insert(tk.END, f"Error copying playlist: {e}\n")

        # Cleanup Empty Target Directories
        self.clean_empty_folders(dest_root)

        self.result_text.insert(tk.END, "\n" + "="*80 + "\n")
        msg = f"✅ SYNC COMPLETE!\nCopied: {copied} | Deleted: {deleted} | Errors: {errors}\n"
        # self.result_text.insert(tk.END, f"✅ SYNC COMPLETE!\nCopied: {copied} | Deleted: {deleted} | Errors: {errors}\n")
        self.result_text.insert(tk.END, f"{msg}\n")
        # self.show_custom_info("Success", f"{msg}")
        messagebox.showsuccess(self, "Devices", msg)

    def calculate(self):
        playlist_file = self.playlist_path.get().strip()
        if not playlist_file or not os.path.isfile(playlist_file):
            messagebox.showerror(self,"Error", "Please select a valid playlist file!")
            return

        self.save_config()

        pc_root = Path(self.pc_music_root.get()).resolve() if self.pc_music_root.get().strip() else None

        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, f"Analyzing: {Path(playlist_file).name}\n")
        self.result_text.insert(tk.END, "="*90 + "\n\n")
        self.update()

        try:
            with open(playlist_file, 'r', encoding='utf-8', errors='ignore') as f:
                tracks = [line.strip() for line in f if line.strip() and not line.startswith('#')]

            total_size = 0
            total_duration = 0.0
            found = 0
            missing = 0

            for i, track in enumerate(tracks, 1):
                if not track:
                    continue
                track_p = Path(track)
                abs_path = None

                candidates = []
                if pc_root:
                    candidates.append(pc_root / track_p)

                playlist_dir = Path(playlist_file).parent
                candidates.extend([
                    playlist_dir / track_p,
                    playlist_dir.parent / track_p,
                    playlist_dir.parent.parent / track_p
                ])

                for cand in candidates:
                    if cand.is_file():
                        abs_path = cand.resolve()
                        break

                if abs_path:
                    size = self.get_file_size(str(abs_path))
                    total_size += size
                    found += 1

                    if MutagenFile:
                        try:
                            audio = MutagenFile(str(abs_path))
                            if audio and hasattr(audio.info, 'length'):
                                total_duration += audio.info.length
                        except Exception as e:
                            self.result_text.insert(tk.END, f"Error: {e}\n")
                            self.update()
                        # except:
                        #     pass

                    if self.verbose.get():
                        self.result_text.insert(tk.END, f"{i:3d}. {abs_path.name} → {self.format_size(size)}\n")
                else:
                    missing += 1
                    if self.verbose.get():
                        self.result_text.insert(tk.END, f"{i:3d}. ❌ Missing: {track}\n")

                if i % 30 == 0:
                    self.update()

            self.result_text.insert(tk.END, "\n" + "="*90 + "\n")
            self.result_text.insert(tk.END, f"✅ Found  : {found}\n")
            self.result_text.insert(tk.END, f"❌ Missing: {missing}\n")
            self.result_text.insert(tk.END, f"📦 Total Size: {self.format_size(total_size)}\n")
            if total_duration > 60:
                self.result_text.insert(tk.END, f"⏱️  Duration : {total_duration/3600:.1f} hours\n")
            self.result_text.insert(tk.END, "="*90 + "\n")

        except Exception as e:
            messagebox.showerror(self,"Error", str(e))

    def clean_empty_folders(self, dest_root: Path):
        """Bottom-up cleanup: delete truly empty folders, but protect root-level system files"""
        self.result_text.insert(tk.END, "\nCleaning empty folders...\n")
        self.update()

        protected = self.get_protected_list()
        junk = {".ds_store", "thumbs.db", "desktop.ini", ".directory"}

        try:
            for folder in sorted(list(dest_root.rglob("*")), reverse=True):
                if not folder.is_dir() or folder == dest_root:
                    continue

                try:
                    contents = list(folder.iterdir())
                    if not contents:
                        folder.rmdir()
                        self.result_text.insert(tk.END, f"🗑️ Removed empty folder: {folder.relative_to(dest_root)}\n")
                        continue

                    # Special protection for root-level system folders/files
                    if folder.parent == dest_root:  # Direct child of Music root
                        # Never delete .thumbnails folder at root
                        if folder.name.lower() in {".thumbnails", "thumbnails"}:
                            continue
                        if self.preserve_playlists_folder.get() and folder.name.lower() in {"playlists"}:
                            continue

                    # Check if folder contains ONLY protected/junk items
                    all_safe_to_remove = all(
                        (item.name.lower() in junk or any(p in item.name.lower() for p in protected))
                        for item in contents
                    )

                    if all_safe_to_remove:
                        for item in contents:
                            if item.is_file():
                                try:
                                    item.unlink()
                                    self.result_text.insert(tk.END, f"🗑️ Removed: {item.name}\n")
                                except Exception as e:
                                    self.result_text.insert(tk.END, f"Error: {e}\n")
                                    self.update()
                                # except:
                                #     pass

                        # Only delete folder if it's not the root .thumbnails
                        if folder.name.lower() not in {".thumbnails", "thumbnails"}:
                            folder.rmdir()
                            self.result_text.insert(tk.END, f"🗑️ Removed empty folder: {folder.relative_to(dest_root)}\n")
                except:
                    continue
        except Exception as e:
            self.result_text.insert(tk.END, f"Folder cleanup warning: {e}\n")

    def check_duplicates(self):
        self.result_text.delete(1.0, tk.END)
        self.save_config()

        tracks = self.get_tracks_from_playlist()
        if not tracks:
            messagebox.showwarning(self,"No Playlist", "Please load a playlist first.")
            return

        self.result_text.insert(tk.END, "🔍 Scanning playlist for duplicates...\n\n")
        self.update()

        song_map = {}   # Key: (artist_norm, title_norm)
        file_list = []

        for track in tracks:
            track_p = Path(track)
            abs_path = None

            # Find actual file
            pc_root = Path(self.pc_music_root.get()).resolve() if self.pc_music_root.get() else None
            candidates = [pc_root / track_p] if pc_root else []
            
            playlist_dir = Path(self.playlist_path.get()).parent.resolve()
            candidates.extend([
                playlist_dir / track_p,
                playlist_dir.parent / track_p,
                playlist_dir.parent.parent / track_p
            ])

            for cand in candidates:
                if cand.is_file():
                    abs_path = cand.resolve()
                    break

            if not abs_path:
                continue

            file_list.append(abs_path)

            # === Get metadata safely (improved) ===
            artist = "Unknown"
            title = abs_path.stem
            duration = 0.0

            try:
                audio = MutagenFile(str(abs_path))
                if audio is not None:
                    if hasattr(audio.info, 'length'):
                        duration = round(audio.info.length, 1)
                    
                    if audio.tags:
                        artist_tag = audio.tags.get('artist') or audio.tags.get('TPE1')
                        title_tag = audio.tags.get('title') or audio.tags.get('TIT2')
                        
                        if artist_tag:
                            artist = str(artist_tag[0] if isinstance(artist_tag, list) else artist_tag)
                        if title_tag:
                            title = str(title_tag[0] if isinstance(title_tag, list) else title_tag)
            except Exception as e:
                self.result_text.insert(tk.END, f"Error: {e}\n")
                self.update()
            # except:
            #     pass

            artist_norm = artist.lower().strip()
            title_norm = title.lower().strip()
            
            # Aggressive normalization
            for s in ["(edit)", "(remaster)", "(remastered)", "(live)", "(version)", "(radio edit)", "(single)"]:
                title_norm = title_norm.replace(s, "").strip()

            key = (artist_norm, title_norm)
            if key not in song_map:
                song_map[key] = []
            song_map[key].append((abs_path, duration))

        # === Report ===
        duplicates_found = 0
        self.result_text.insert(tk.END, f"Found {len(file_list)} tracks in playlist.\n\n")

        for key, entries in sorted(song_map.items()):
            if len(entries) > 1:
                duplicates_found += 1
                artist, title = key
                self.result_text.insert(tk.END, f"🔁 Duplicate: {artist.title()} - {title.title()}\n")
                for path, dur in entries:
                    self.result_text.insert(tk.END, f"   → {path.relative_to(Path.home())} ({dur}s)\n")
                self.result_text.insert(tk.END, "\n")

        if duplicates_found == 0:
            self.result_text.insert(tk.END, "✅ No duplicates found!\n")
        else:
            self.result_text.insert(tk.END, f"⚠️ Found {duplicates_found} duplicate group(s).\n")

        self.result_text.insert(tk.END, "\nDuplicate check complete.")

def find_media_root(base_path):
    """
    Intelligently maps the destination root to avoid dumping files onto the bare root
    if an inner media subdirectory layout is preferred. Standard USB block mounts
    under /media/ or /run/media/ are preserved exactly as-is.
    """
    if not base_path:
        return ""

    # --- NEW PROTECTION FOR STANDALONE USB DRIVES ---
    # If the user selects a standard USB storage mount under /media or /run/media,
    # use that explicit base directory directly. Do not try to scan for inner targets.
    path_str = str(base_path)
    if path_str.startswith("/media/") or path_str.startswith("/run/media/"):
        return path_str

    # --- EXISTING ENHANCED ANDROID/MTP ROUTINES ---
    # Inner folder naming conventions for various external devices
    music_folder_names = {"music", "audio", "internal shared storage/music", "internal storage/music"}
    android_internal_stems = {"internal shared storage", "internal storage", "sd card"}

    try:
        item = Path(base_path)
        if item.exists() and item.is_dir():
            # Strategy A: Check if an inner target folder exists directly beneath the base
            for sub_item in item.iterdir():
                if sub_item.is_dir() and sub_item.name.lower() in music_folder_names:
                    return str(sub_item)

            # Strategy B: Check if we are at the device root pointing to Android internal structures
            for sub_item in item.iterdir():
                if sub_item.is_dir() and sub_item.name.lower() in android_internal_stems:
                    for inner_item in sub_item.iterdir():
                        if inner_item.is_dir() and inner_item.name.lower() in music_folder_names:
                            return str(inner_item)
                    return str(sub_item)
    except Exception as e:
        print(f"Warning: Could not search path tree for target {base_path}: {e}\n")

    return str(base_path)

def clean_mtp_path(raw_path):
    match = re.search(r"host=(.+)", raw_path)
    if not match: return "Unknown Device"
    device_info = match.group(1)
    parts = device_info.split("_")
    clean_parts = []
    for part in parts:
        if not clean_parts or part.lower() != clean_parts[-1].lower():
            clean_parts.append(part)
    filtered_parts = []
    for p in clean_parts:
        if p.lower() == "android" or any(char.isdigit() for char in p): continue
        filtered_parts.append(p.capitalize())
    display_name = " ".join(filtered_parts)
    return display_name if display_name else "Android Device"

def get_device_marketing_name(gvfs_path):
    try:
        result = subprocess.run(["gio", "info", gvfs_path], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if "display-name:" in line:
                return line.split("display-name:")[1].strip()
    except Exception as e:
        print(f"Warning: gio info command failed: {e}\n")
    return clean_mtp_path(gvfs_path)

def install_local_icons():
    """Checks if app icons exist in ~/.local/share/icons and copies them if missing."""
    # 1. Define source and destination paths
    script_dir = Path(__file__).parent.resolve()
    source_icons_root = script_dir / "icons"
    dest_icons_root = Path.home() / ".local" / "share" / "icons"

    # If the source 'icons' folder doesn't exist next to the script, skip silently
    if not source_icons_root.exists():
        return

    # 2. Walk through the source icons directory recursively
    for source_file in source_icons_root.rglob("*"):
        if source_file.is_file():
            # Calculate the relative path (e.g., hicolor/48x48/apps/Playlist-Sync-Tool.png)
            relative_path = source_file.relative_to(source_icons_root)
            target_file = dest_icons_root / relative_path

            # 3. If the icon doesn't exist in the target system directory, copy it over
            if not target_file.exists():
                try:
                    # Ensure the destination subdirectories exist (like apps/)
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_file, target_file)
                    print(f"Installed system icon: {relative_path}")
                except Exception as e:
                    print(f"Warning: Could not copy icon {relative_path}: {e}")

if __name__ == "__main__":
    app = PlaylistSyncGUI()
    app.mainloop()