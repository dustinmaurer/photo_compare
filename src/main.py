import gc
import glob
import math
import os
import platform
import random
import subprocess
import tkinter as tk
import tkinter.ttk as ttk
from datetime import datetime
from tkinter import filedialog, messagebox

import cv2
import pythoncom
import win32api
import win32com.shell.shell as shell
import win32con
from mutagen import File
from PIL import Image, ImageDraw, ImageFont, ImageTk
from win32com.shell import shellcon

import config
from metadata_manager import MetadataManager


class PhotoManager:
    def __init__(self, test_mode=False):
        self.root = tk.Tk()
        self.root.title("Photo Manager")
        self.root.geometry("1200x600")

        # Center the window on screen
        self.root.update_idletasks()  # Ensure window size is calculated
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        window_width = 1200
        window_height = 600

        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 10

        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self.metadata_manager = None
        self.test_mode = test_mode

        self.photo_folder = None
        self.image_files = []

        self.setup_ui()

        # Auto-load test folder if in test mode
        if self.test_mode:
            self.auto_load_test_folder()

    def _rename_files_with_progress(self, files_to_rename, add_prefix=True):
        """Helper method to rename files with progress dialog"""
        # Create progress window
        progress_window = tk.Toplevel(self.root)
        action = "Adding" if add_prefix else "Removing"
        progress_window.title(f"{action} Prefixes")
        progress_window.geometry("500x150")
        progress_window.grab_set()

        # Center the window
        progress_window.transient(self.root)
        progress_window.geometry(
            "+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50)
        )

        progress_label = tk.Label(progress_window, text="Starting...", wraplength=450)
        progress_label.pack(pady=10)

        progress_bar = ttk.Progressbar(progress_window, mode="determinate")
        progress_bar.pack(pady=10, padx=20, fill="x")
        progress_bar["maximum"] = len(files_to_rename)

        status_label = tk.Label(progress_window, text="", font=("Arial", 8))
        status_label.pack(pady=5)

        success_count = 0
        failed_renames = []
        new_metadata = {}

        for i, (file_path, old_relative_path) in enumerate(files_to_rename):
            action_text = "Adding prefix to" if add_prefix else "Removing prefix from"
            progress_label.config(text=f"{action_text}: {old_relative_path}")
            progress_bar["value"] = i + 1
            status_label.config(text=f"{i+1}/{len(files_to_rename)} files processed")
            progress_window.update()

            try:
                # Get the folder part and filename part
                folder_part = os.path.dirname(old_relative_path)
                old_filename = os.path.basename(old_relative_path)

                if add_prefix:
                    # Calculate new filename with prefix
                    quantile = self.metadata_manager.get_quantile(old_relative_path)
                    quantile_int = int(quantile * 10)
                    quantile_prefix = f"Q{quantile_int:03d}_"

                    # Remove old quantile prefix if it exists
                    if old_filename.startswith("Q") and "_" in old_filename[:5]:
                        underscore_pos = old_filename.find("_")
                        base_filename = old_filename[underscore_pos + 1 :]
                    else:
                        base_filename = old_filename

                    new_filename = quantile_prefix + base_filename
                else:
                    # Remove prefix to get base filename
                    if old_filename.startswith("Q") and "_" in old_filename[:5]:
                        underscore_pos = old_filename.find("_")
                        new_filename = old_filename[underscore_pos + 1 :]
                    else:
                        # No prefix to remove, skip
                        continue

                # Construct new relative path (preserve folder structure)
                if folder_part:
                    new_relative_path = folder_part + "/" + new_filename
                else:
                    new_relative_path = new_filename

                # Construct new full path
                new_file_path = os.path.join(self.photo_folder, new_relative_path)

                # Check if new filename already exists
                if os.path.exists(new_file_path) and new_file_path != file_path:
                    print(
                        f"Warning: {new_relative_path} already exists, skipping {old_relative_path}"
                    )
                    failed_renames.append((old_relative_path, "File already exists"))
                    continue

                # Rename the file
                os.rename(file_path, new_file_path)

                # Update metadata with new relative path
                old_data = self.metadata_manager.metadata[old_relative_path]
                new_metadata[new_relative_path] = old_data

                print(f"Renamed: {old_relative_path} -> {new_relative_path}")
                success_count += 1

            except Exception as e:
                print(f"Failed to rename {old_relative_path}: {e}")
                failed_renames.append((old_relative_path, str(e)))

        # Update metadata with new relative paths
        if new_metadata:
            # Remove old entries and add new ones
            for old_relative_path, _ in files_to_rename:
                if old_relative_path in self.metadata_manager.metadata:
                    # Check if we successfully renamed this file
                    folder_part = os.path.dirname(old_relative_path)
                    old_filename = os.path.basename(old_relative_path)

                    if add_prefix:
                        quantile = self.metadata_manager.get_quantile(old_relative_path)
                        quantile_int = int(quantile * 10)
                        quantile_prefix = f"Q{quantile_int:03d}_"

                        if old_filename.startswith("Q") and "_" in old_filename[:5]:
                            underscore_pos = old_filename.find("_")
                            base_filename = old_filename[underscore_pos + 1 :]
                        else:
                            base_filename = old_filename

                        new_filename = quantile_prefix + base_filename
                    else:
                        if old_filename.startswith("Q") and "_" in old_filename[:5]:
                            underscore_pos = old_filename.find("_")
                            new_filename = old_filename[underscore_pos + 1 :]
                        else:
                            continue

                    # Construct expected new relative path
                    if folder_part:
                        expected_new_relative = folder_part + "/" + new_filename
                    else:
                        expected_new_relative = new_filename

                    if expected_new_relative in new_metadata:
                        # Successfully renamed, remove old entry
                        del self.metadata_manager.metadata[old_relative_path]

            # Add new entries
            self.metadata_manager.metadata.update(new_metadata)
            self.metadata_manager.save_metadata()

        progress_window.destroy()

        # Show errors if any
        if failed_renames:
            error_msg = f"Processed {success_count}/{len(files_to_rename)} files\n\nFailed renames:\n"
            error_msg += "\n".join(
                [f"• {name}: {error}" for name, error in failed_renames[:10]]
            )
            if len(failed_renames) > 10:
                error_msg += f"\n... and {len(failed_renames) - 10} more"
            messagebox.showwarning("Some Files Failed", error_msg)

        return success_count

    def add_prefix_to_files(self):
        """Add quantile prefix to files that don't have it or need updating"""
        if not self.metadata_manager:
            messagebox.showwarning("No Folder", "Please select a photo folder first")
            return

        # Collect files that need prefix added/updated
        files_to_rename = []
        already_prefixed = []

        for relative_path, data in self.metadata_manager.metadata.items():
            # Convert relative path to full path
            file_path = os.path.join(self.photo_folder, relative_path)

            if not os.path.exists(file_path):
                continue

            # Get just the filename (without folder path) to check for prefix
            filename = os.path.basename(relative_path)

            # Check if file already has correct quantile prefix
            if filename.startswith("Q") and "_" in filename[:5]:
                # Check if it matches current quantile
                current_quantile = self.metadata_manager.get_quantile(relative_path)
                quantile_int = int(current_quantile * 10)
                expected_prefix = f"Q{quantile_int:03d}_"

                if filename.startswith(expected_prefix):
                    already_prefixed.append(relative_path)
                    continue
                else:
                    # File has old/wrong quantile prefix, needs updating
                    files_to_rename.append((file_path, relative_path))
            else:
                # File has no quantile prefix
                files_to_rename.append((file_path, relative_path))

        if not files_to_rename:
            messagebox.showinfo(
                "Already Prefixed",
                f"All {len(already_prefixed)} files already have correct quantile prefixes",
            )
            return

        # Show confirmation dialog
        if not messagebox.askyesno(
            "Add Prefixes",
            f"This will add/update quantile prefixes on {len(files_to_rename)} files.\n"
            f"{len(already_prefixed)} files already have correct prefixes.\n\n"
            "Do you want to continue?",
        ):
            return

        success_count = self._rename_files_with_progress(
            files_to_rename, add_prefix=True
        )

        # Show results
        messagebox.showinfo(
            "Prefixes Added",
            f"Successfully added prefixes to {success_count}/{len(files_to_rename)} files!",
        )

        # Refresh the summary page
        self.show_summary_page()

    def auto_load_test_folder(self):

        # Use config value instead of hardcoded path
        test_folder = config.TEST_FOLDER_PATH  # Instead of hardcoded path

        if os.path.exists(test_folder):
            self.photo_folder = test_folder
            self.metadata_manager = MetadataManager(test_folder)
            self.metadata_manager.load_metadata()
            self.load_images()
            self.show_summary_page()  # Show summary in test mode too
        else:
            print(f"Test folder not found: {test_folder}")
        # Set your test folder path here

    def clear_image_references(self):
        """Clear all image references to free memory"""
        if hasattr(self, "img1_label"):
            self.img1_label.image = None
        if hasattr(self, "img2_label"):
            self.img2_label.image = None

    def display_random_pair(self):
        # Clear previous images first
        self.clear_image_references()

        # Filter out images below 5th quantile before each comparison
        available_images = []
        for file_path in self.image_files:
            # Convert to relative path to match metadata keys
            relative_path = os.path.relpath(file_path, self.photo_folder)
            relative_path = relative_path.replace(os.sep, "/")  # Normalize separators

            quantile = self.metadata_manager.get_quantile(relative_path)
            if quantile >= 5:  # quantile is 0-100
                available_images.append(file_path)
                # print(f"Quantile for {relative_path}: {quantile}")

        print(f"Available images: {len(available_images)}")  # Debug line

        if len(available_images) < 2:
            print("Not enough images above 5th percentile for comparison!")
            from tkinter import messagebox

            messagebox.showinfo(
                "No More Comparisons",
                "All remaining photos are below 5th percentile. Returning to summary.",
            )
            self.show_summary_page()
            return

        self.current_images = self.get_weighted_selection_from_list(available_images, 2)

        # Additional safety check
        if len(self.current_images) < 2:
            print("Not enough images returned from selection!")
            self.show_summary_page()
            return

        # Debug check for duplicates
        if (
            len(self.current_images) == 2
            and self.current_images[0] == self.current_images[1]
        ):
            print(f"DUPLICATE DETECTED: {self.current_images}")
            return

        # Load and display images with better error handling
        try:
            self.show_image(self.current_images[0], self.img1_label)
        except Exception as e:
            print(f"Error loading left image {self.current_images[0]}: {e}")
            self.show_error_image(self.img1_label, self.current_images[0], str(e))

        try:
            self.show_image(self.current_images[1], self.img2_label)
        except Exception as e:
            print(f"Error loading right image {self.current_images[1]}: {e}")
            self.show_error_image(self.img2_label, self.current_images[1], str(e))

    def cleanup_duplicate_metadata(self):
        """Remove duplicate metadata entries where both prefixed and non-prefixed versions exist"""
        if not self.metadata_manager:
            messagebox.showwarning("No Folder", "Please select a photo folder first")
            return

        # Get all actual files that exist
        extensions = [
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".gif",
            ".tiff",
            ".mp4",
            ".mov",
            ".mkv",
            ".wmv",
            ".flv",
        ]

        skip_folders = {"delete", "keep"}
        actual_files = set()

        # Walk through subfolders to find actual files
        for root, dirs, files in os.walk(self.photo_folder):
            current_depth = root[len(self.photo_folder) :].count(os.sep)

            if current_depth >= config.MAX_FOLDER_DEPTH:
                dirs[:] = []
                continue

            dirs[:] = [d for d in dirs if d.lower() not in skip_folders]

            for file in files:
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in extensions:
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, self.photo_folder)
                    relative_path = relative_path.replace(os.sep, "/")
                    actual_files.add(relative_path)

        # Find metadata entries that don't correspond to actual files
        metadata_keys = set(self.metadata_manager.metadata.keys())
        orphaned_entries = metadata_keys - actual_files

        # Group orphaned entries by base filename
        base_to_entries = {}
        for entry in orphaned_entries:
            base_filename = self.get_base_filename(os.path.basename(entry))
            folder_part = os.path.dirname(entry)
            base_key = (folder_part, base_filename)  # (folder, base_filename)

            if base_key not in base_to_entries:
                base_to_entries[base_key] = []
            base_to_entries[base_key].append(entry)

        # Find duplicates: cases where we have both prefixed and non-prefixed versions
        # but only one actually exists
        entries_to_remove = []

        for (folder_part, base_filename), entries in base_to_entries.items():
            if len(entries) > 1:
                print(
                    f"Found duplicate entries for {folder_part}/{base_filename}: {entries}"
                )

                # Look for the corresponding actual file
                corresponding_actual = None
                for actual_file in actual_files:
                    if (
                        os.path.dirname(actual_file) == folder_part
                        and self.get_base_filename(os.path.basename(actual_file))
                        == base_filename
                    ):
                        corresponding_actual = actual_file
                        break

                if corresponding_actual:
                    # Keep the metadata entry that matches the actual file, remove others
                    for entry in entries:
                        if entry != corresponding_actual:
                            entries_to_remove.append(entry)
                            print(f"  - Will remove orphaned entry: {entry}")
                            print(
                                f"  - Keeping actual file entry: {corresponding_actual}"
                            )
                else:
                    # No corresponding actual file, remove all but the most recent
                    # (keep the one with the most comparisons as it's likely more valuable)
                    entries_with_comparisons = [
                        (
                            entry,
                            self.metadata_manager.metadata[entry].get("comparisons", 0),
                        )
                        for entry in entries
                    ]
                    entries_with_comparisons.sort(key=lambda x: x[1], reverse=True)

                    # Keep the first (most comparisons), remove the rest
                    for entry, _ in entries_with_comparisons[1:]:
                        entries_to_remove.append(entry)
                        print(f"  - Will remove duplicate entry: {entry}")
                    print(
                        f"  - Keeping entry with most comparisons: {entries_with_comparisons[0][0]}"
                    )

        # Remove the orphaned entries
        if entries_to_remove:
            for entry in entries_to_remove:
                if entry in self.metadata_manager.metadata:
                    del self.metadata_manager.metadata[entry]

            self.metadata_manager.save_metadata()

            messagebox.showinfo(
                "Cleanup Complete",
                f"Removed {len(entries_to_remove)} duplicate metadata entries.\n\n"
                f"Metadata now contains {len(self.metadata_manager.metadata)} entries.",
            )

            # Refresh the display
            self.show_summary_page()
        else:
            messagebox.showinfo("No Duplicates", "No duplicate metadata entries found.")

    def clear_image_references(self):
        """Clear all image references to free memory and prevent display issues"""
        if hasattr(self, "img1_label"):
            self.img1_label.configure(image="", text="")
            self.img1_label.image = None
            self.img1_label.unbind("<Button-1>")  # Remove any click events
            self.img1_label.configure(cursor="")  # Reset cursor
        if hasattr(self, "img2_label"):
            self.img2_label.configure(image="", text="")
            self.img2_label.image = None
            self.img2_label.unbind("<Button-1>")  # Remove any click events
            self.img2_label.configure(cursor="")  # Reset cursor

    def extract_video_frame(self, video_path):
        """Extract first frame from video file"""
        try:
            print(f"Opening video: {video_path}")  # Debug line

            # Open video
            cap = cv2.VideoCapture(video_path)

            if not cap.isOpened():
                print(f"Failed to open video: {video_path}")
                return Image.new("RGB", (400, 300), color="red")

            # Read first frame
            ret, frame = cap.read()
            cap.release()

            if ret:
                print("Successfully extracted frame")  # Debug line
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Convert to PIL Image
                img = Image.fromarray(frame_rgb)
                return img
            else:
                print("Failed to read frame from video")
                # Fallback: create a placeholder image
                return Image.new("RGB", (400, 300), color="gray")

        except ImportError:
            print("OpenCV not installed. Install with: pip install opencv-python")
            return Image.new("RGB", (400, 300), color="red")
        except Exception as e:
            print(f"Error extracting frame: {e}")
            return Image.new("RGB", (400, 300), color="gray")
        finally:
            # Always release the video capture
            if cap is not None:
                cap.release()

    def get_base_filename(self, filename):
        """Get the base filename without quantile prefix"""
        if filename.startswith("Q") and "_" in filename[:5]:
            underscore_pos = filename.find("_")
            return filename[underscore_pos + 1 :]
        return filename

    def get_weighted_selection_from_list(self, image_list, k=2):
        """Select images from provided list with weighting based on distance from quantile 30"""

        # Remove any duplicate paths first
        unique_images = list(set(image_list))
        # print(f"Original list: {len(image_list)}, Unique: {len(unique_images)}")

        if len(unique_images) < k:
            print(f"Warning: Only {len(unique_images)} unique images available")
            return unique_images

        # Calculate weights based on distance from quantile 30
        weights = []
        valid_images = []  # Only images that are in metadata

        for img_path in unique_images:
            # Convert to relative path to match metadata keys
            relative_path = os.path.relpath(img_path, self.photo_folder)
            relative_path = relative_path.replace(os.sep, "/")  # Normalize separators

            # Check if this image is in metadata
            if relative_path not in self.metadata_manager.metadata:
                print(f"Warning: {relative_path} not found in metadata, skipping")
                continue

            quantile = self.metadata_manager.get_quantile(relative_path)
            # Distance from 30th quantile - images closer to 30 get higher weight
            distance_from_30 = abs(quantile - 30)
            # Invert the distance so closer images get higher weight
            # Add 1 to avoid division by zero when quantile is exactly 30
            weight = 1 / (distance_from_30 + 1)
            weights.append(weight)
            valid_images.append(img_path)

        if len(valid_images) < k:
            print(f"Warning: Only {len(valid_images)} valid images in metadata")
            return valid_images

        # Use weighted selection without replacement
        import random

        selected = []
        available_images = valid_images.copy()
        available_weights = weights.copy()

        for _ in range(k):
            if not available_images:
                break

            # Select one image based on weights
            chosen = random.choices(available_images, weights=available_weights, k=1)[0]
            selected.append(chosen)

            # Remove the selected image and its weight from available options
            chosen_index = available_images.index(chosen)
            available_images.pop(chosen_index)
            available_weights.pop(chosen_index)

        # Convert to relative paths for debug output
        selected_relative = []
        selected_quantiles = []
        for img_path in selected:
            relative_path = os.path.relpath(img_path, self.photo_folder)
            relative_path = relative_path.replace(os.sep, "/")
            selected_relative.append(relative_path)
            selected_quantiles.append(self.metadata_manager.get_quantile(relative_path))

        print(f"Selected: {selected_relative}")
        print(f"Quantiles: {selected_quantiles}")

        return selected

    def handle_keypress(self, event):
        if not hasattr(self, "current_images") or len(self.current_images) != 2:
            return

        # Arrow keys
        if event.keysym == "Left":
            self.process_comparison(1, 0)  # Left wins
        elif event.keysym == "Right":
            self.process_comparison(0, 1)  # Right wins
        elif event.keysym == "Up":
            self.process_comparison(1, 1)  # Both win
        elif event.keysym == "Down":
            self.process_comparison(0, 0)  # Both lose

        # WASD keys (same mappings)
        elif event.keysym.lower() == "a":
            self.process_comparison(1, 0)  # Left wins (A = left)
        elif event.keysym.lower() == "d":
            self.process_comparison(0, 1)  # Right wins (D = right)
        elif event.keysym.lower() == "w":
            self.process_comparison(1, 1)  # Both win (W = up)
        elif event.keysym.lower() == "s":
            self.process_comparison(0, 0)  # Both lose (S = down)

        elif event.keysym == "space":
            self.process_comparison(0.5, 0.5)  # Tie

    def load_images(self):
        """Load images recursively from subfolders"""
        extensions = [
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".gif",
            ".tiff",
            ".mp4",
            ".mov",
            ".mkv",
            ".wmv",
            ".flv",
        ]

        # Folders to skip (decisions already made)
        skip_folders = {"delete", "keep"}

        all_image_files = []

        # Walk through subfolders with depth limit (same logic as _add_new_photos)
        for root, dirs, files in os.walk(self.photo_folder):
            # Calculate current depth
            current_depth = root[len(self.photo_folder) :].count(os.sep)

            # Skip if we're too deep (allow 4 levels: year/month/type/files)
            if current_depth >= config.MAX_FOLDER_DEPTH:
                dirs[:] = []  # Don't descend further
                continue

            # Remove skip folders from dirs list to prevent os.walk from entering them
            dirs[:] = [d for d in dirs if d.lower() not in skip_folders]

            # Process files in current directory
            for file in files:
                # Check if file has supported extension
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in extensions:
                    # Get full path for the file list
                    full_path = os.path.join(root, file)
                    all_image_files.append(full_path)

        print(f"Found {len(all_image_files)} total image files")  # Debug

        # Filter out images with quantile below 10 for comparisons
        self.image_files = []
        masked_count = 0

        for file_path in all_image_files:
            # Convert to relative path to match metadata keys
            relative_path = os.path.relpath(file_path, self.photo_folder)
            relative_path = relative_path.replace(os.sep, "/")  # Normalize separators

            if (
                self.metadata_manager
                and relative_path in self.metadata_manager.metadata
            ):
                quantile = self.metadata_manager.get_quantile(relative_path)
                if quantile < 10:
                    masked_count += 1
                    continue  # Skip this image for comparisons
            else:
                print(f"Warning: {relative_path} not found in metadata")  # Debug

            self.image_files.append(file_path)

        print(f"Available for comparison: {len(self.image_files)} images")  # Debug
        if masked_count > 0:
            print(f"Masked due to low quantile: {masked_count} images")

        if len(self.image_files) < 2:
            print(
                f"Warning: Only {len(self.image_files)} images available for comparison"
            )
            if masked_count > 0:
                print(f"({masked_count} images masked due to low quantile)")

    def load_images_with_sync(self):
        """Load images and auto-sync any filename changes"""
        # First try the normal load
        self.load_images_original()

        # Then sync any discrepancies
        if hasattr(self, "metadata_manager") and self.metadata_manager:
            self.sync_metadata_with_files()
            # Reload after sync
            self.load_images_original()

    def load_images_original(self):
        """Original load_images method (rename your current one to this)"""
        extensions = [
            "*.jpg",
            "*.jpeg",
            "*.png",
            "*.bmp",
            "*.gif",
            "*.tiff",
            "*.mp4",
            # "*.avi",
            "*.mov",
            "*.mkv",
            "*.wmv",
            "*.flv",
        ]
        all_image_files = []

        for ext in extensions:
            all_image_files.extend(glob.glob(os.path.join(self.photo_folder, ext)))
            all_image_files.extend(
                glob.glob(os.path.join(self.photo_folder, ext.upper()))
            )

        # Filter out images with quantile below 0.10 for comparisons
        self.image_files = []
        masked_count = 0

        for file_path in all_image_files:
            filename = os.path.basename(file_path)
            if self.metadata_manager and filename in self.metadata_manager.metadata:
                quantile = self.metadata_manager.get_quantile(filename)
                if quantile < 10:
                    masked_count += 1
                    continue  # Skip this image for comparisons

            self.image_files.append(file_path)

        if len(self.image_files) < 2:
            print(
                f"Warning: Only {len(self.image_files)} images available for comparison"
            )
            if masked_count > 0:
                print(f"({masked_count} images masked due to low quantile)")

    def open_video(self, video_path):
        """Open video file with preferred video player"""

        # Debug output
        print(f"Attempting to open video: {video_path}")
        print(f"File exists: {os.path.exists(video_path)}")

        try:
            # Ensure we have an absolute path
            if not os.path.isabs(video_path):
                video_path = os.path.abspath(video_path)
                print(f"Converted to absolute path: {video_path}")

            if not os.path.exists(video_path):
                print(f"Error: Video file does not exist: {video_path}")
                from tkinter import messagebox

                messagebox.showerror(
                    "File Not Found", f"Video file not found:\n{video_path}"
                )
                return

            if platform.system() == "Windows":
                # Try different players in order of preference
                players = [
                    # VLC with autoplay flag
                    (r"C:\Program Files\VideoLAN\VLC\vlc.exe", ["--play-and-exit"]),
                    (
                        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
                        ["--play-and-exit"],
                    ),
                    # Windows Media Player
                    (r"C:\Program Files\Windows Media Player\wmplayer.exe", []),
                ]

                for player_info in players:
                    if len(player_info) == 2:
                        player_path, args = player_info
                    else:
                        player_path, args = player_info[0], []

                    if os.path.exists(player_path):
                        # Build command with arguments
                        cmd = [player_path] + args + [video_path]
                        print(f"Executing command: {cmd}")  # Debug
                        subprocess.Popen(cmd)
                        print(
                            f"Opening video with {os.path.basename(player_path)}: {os.path.basename(video_path)}"
                        )
                        return

                # Fallback to default association
                print("No specific player found, using default association")
                os.startfile(video_path)
                print(f"Opening video with default app: {os.path.basename(video_path)}")

            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", video_path])
            else:  # Linux
                subprocess.Popen(["xdg-open", video_path])

        except Exception as e:
            print(f"Error opening video {video_path}: {e}")
            from tkinter import messagebox

            messagebox.showerror("Error", f"Could not open video: {e}")

    def process_comparison(self, left_score, right_score):
        if not self.metadata_manager:
            return

        # Convert full paths to relative paths for metadata lookup
        left_relative = os.path.relpath(self.current_images[0], self.photo_folder)
        left_relative = left_relative.replace(os.sep, "/")  # Normalize separators

        right_relative = os.path.relpath(self.current_images[1], self.photo_folder)
        right_relative = right_relative.replace(os.sep, "/")  # Normalize separators

        # Debug lines
        print(f"Left image: {self.current_images[0]}")
        print(f"Right image: {self.current_images[1]}")
        print(f"Left relative: {left_relative}")
        print(f"Right relative: {right_relative}")
        print(f"Left in metadata: {left_relative in self.metadata_manager.metadata}")
        print(f"Right in metadata: {right_relative in self.metadata_manager.metadata}")

        # Convert scores to outcome for Elo system
        if left_score == 1 and right_score == 0:  # Left wins
            outcome = "left"
        elif left_score == 0 and right_score == 1:  # Right wins
            outcome = "right"
        elif left_score == 1 and right_score == 1:  # Both win
            outcome = "both"
        elif left_score == 0 and right_score == 0:  # Both lose
            outcome = "neither"
        else:  # Tie
            outcome = "tie"

        # Update Elo ratings using relative paths
        self.metadata_manager.update_skills(left_relative, right_relative, outcome)

        # Show next pair
        self.display_random_pair()

        # Force garbage collection every 10 comparisons
        if not hasattr(self, "comparison_count"):
            self.comparison_count = 0
        self.comparison_count += 1

        if self.comparison_count % 10 == 0:
            gc.collect()

    def reset_all_scores(self):
        """Reset all photo skills and comparison counts"""
        if not self.metadata_manager:
            return

        # Confirm reset
        from tkinter import messagebox

        if messagebox.askyesno(
            "Reset Scores",
            "Are you sure you want to reset all photo scores? This cannot be undone.",
        ):
            for filename in self.metadata_manager.metadata:
                self.metadata_manager.metadata[filename]["skill"] = 0
                self.metadata_manager.metadata[filename]["comparisons"] = 0

            self.metadata_manager.save_metadata()
            print("All scores reset to default")

            # Refresh the summary page
            self.show_summary_page()

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.photo_folder = folder
            self.metadata_manager = MetadataManager(folder)
            self.metadata_manager.load_metadata()
            self.load_images()
            self.show_summary_page()  # Show summary instead of going directly to comparison

    def setup_ui(self):
        # Top button frame
        top_frame = tk.Frame(self.root)
        top_frame.pack(pady=5)

        # # Folder selection button
        # select_btn = tk.Button(
        #     self.root,
        #     text="Select Photo Folder",
        #     command=self.select_folder,
        #     font=("Arial", 12),
        # )
        # select_btn.pack(pady=10)

        # Back to summary button (only show if we have metadata loaded)
        if self.metadata_manager:
            summary_btn = tk.Button(
                top_frame,
                text="Back to Summary",
                command=self.show_summary_page,
                font=("Arial", 12),
                bg="lightgreen",
            )
            summary_btn.pack(side="right", padx=5)

        # Add instructions
        instructions = tk.Label(
            self.root,
            text="← Left Wins | → Right Wins | ↑ Both Win | ↓ Both Lose | Space = Tie",
            font=("Arial", 10),
        )
        instructions.pack(pady=5)

        # Frame for images
        self.image_frame = tk.Frame(self.root)
        self.image_frame.pack(expand=True, fill="both", padx=10, pady=10)

        # Labels for images
        self.img1_label = tk.Label(self.image_frame)
        self.img1_label.pack(side="left", expand=True, fill="both", padx=5)

        self.img2_label = tk.Label(self.image_frame)
        self.img2_label.pack(side="right", expand=True, fill="both", padx=5)

        # Bind keyboard events
        self.root.bind("<Key>", self.handle_keypress)
        self.root.focus_set()  # Ensure window can receive key events

    def show_error_image(self, label, path, error_msg):
        """Display an error placeholder when image loading fails"""
        try:
            # Create a simple error image

            error_img = Image.new("RGB", (400, 300), color="red")
            draw = ImageDraw.Draw(error_img)

            # Add error text
            filename = os.path.basename(path)
            error_text = f"ERROR\n{filename}\n{error_msg[:50]}..."

            # Try to use a font, fall back to default if not available
            try:
                font = ImageFont.truetype("arial.ttf", 16)
            except:
                font = ImageFont.load_default()

            # Get text size and center it
            bbox = draw.textbbox((0, 0), error_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (400 - text_width) // 2
            y = (300 - text_height) // 2

            draw.text((x, y), error_text, fill="white", font=font, align="center")

            photo = ImageTk.PhotoImage(error_img)
            label.configure(
                image=photo,
                text=f"Error loading: {filename}",
                compound="top",
                font=("Arial", 10),
                bg="red",
                relief="solid",
                borderwidth=2,
            )
            label.image = photo  # Keep reference
            label.configure(cursor="")
            label.unbind("<Button-1>")

        except Exception as fallback_error:
            # Ultimate fallback - just show text
            print(f"Error creating error image: {fallback_error}")
            label.configure(
                image="",
                text=f"ERROR: Could not load\n{os.path.basename(path)}\n{error_msg}",
                compound="top",
                font=("Arial", 10),
                bg="red",
                fg="white",
                relief="solid",
                borderwidth=2,
            )
            label.image = None

    def show_image(self, path, label):
        """Show image with improved error handling and cleanup"""
        try:
            # Convert to relative path for metadata lookup
            relative_path = os.path.relpath(path, self.photo_folder)
            relative_path = relative_path.replace(os.sep, "/")  # Normalize separators

            filename = os.path.basename(path)  # For display purposes
            file_ext = os.path.splitext(path)[1].lower()

            # Check if it's a video file
            video_extensions = [".mp4", ".mov", ".mkv", ".wmv", ".flv"]

            if file_ext in video_extensions:
                # Extract first frame from video
                img = self.extract_video_frame(path)
                is_video = True
            else:
                # Regular image
                img = Image.open(path)
                is_video = False

            # Resize to fit in half the window
            img.thumbnail((580, 400), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            # Get metadata safely using relative path
            if relative_path in self.metadata_manager.metadata:
                skill = self.metadata_manager.metadata[relative_path]["skill"]
                comparisons = self.metadata_manager.metadata[relative_path][
                    "comparisons"
                ]
                quantile = self.metadata_manager.get_quantile(relative_path)
            else:
                print(f"Warning: {relative_path} not found in metadata")
                skill = 0
                comparisons = 0
                quantile = 50

            # Create info text with file type indicator and folder context
            file_type = "VIDEO" if is_video else "IMAGE"

            # Show folder context if file is in a subfolder
            if os.path.dirname(relative_path):
                display_name = relative_path.replace(
                    "/", " / "
                )  # Make path separators readable
                info_text = f"{display_name} ({file_type})\nSkill: {skill:.2f} | Quantile: {quantile:.1f} | Comparisons: {comparisons}"
            else:
                # File is in root folder, just show filename
                info_text = f"{filename} ({file_type})\nSkill: {skill:.2f} | Quantile: {quantile:.1f} | Comparisons: {comparisons}"

            # Set border color based on file type
            border_color = "red" if is_video else "blue"

            label.configure(
                image=photo,
                text=info_text,
                compound="top",
                font=("Arial", 10),
                bg=border_color,
                relief="solid",
                borderwidth=2,
            )
            label.image = photo  # Keep reference

            # Clear any existing click bindings first
            label.unbind("<Button-1>")

            # Add click event for videos with absolute path
            if is_video:
                label.configure(cursor="hand2")
                # Use absolute path and ensure it exists
                abs_path = os.path.abspath(path)
                if os.path.exists(abs_path):
                    # Create a closure that captures the absolute path
                    def video_click_handler(event, video_path=abs_path):
                        print(f"Video clicked: {video_path}")  # Debug
                        self.open_video(video_path)

                    label.bind("<Button-1>", video_click_handler)
                    print(f"Bound video click handler for: {abs_path}")  # Debug
                else:
                    print(f"Warning: Video file not found: {abs_path}")
            else:
                label.configure(cursor="")

        except Exception as e:
            print(f"Exception in show_image for {path}: {e}")
            # Don't let the exception propagate - show error image instead
            self.show_error_image(label, path, str(e))

    def show_summary_page(self):
        """Display summary of photos ordered by skill with colored borders"""
        # Clear existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        self.load_images()  # Reload image list
        self.sync_files(silent=True)  # Sync metadata with files (no popup)

        # Calculate window size for 10 photos (2 rows × 4 columns)
        # Each photo: 280px + padding, plus scrollbar and buttons
        window_width = (280 + 20) * 4 + 80  # 4 columns * (image + padding) + margins
        window_height = (
            280 + 80
        ) * 2 + 200  # 2 rows * (image + text + padding) + buttons/header

        self.root.geometry(f"{window_width}x{window_height}")

        # Button frame
        button_frame = tk.Frame(self.root)
        button_frame.pack(side="top", pady=10)

        # Folder selection button
        select_btn = tk.Button(
            button_frame,
            text="Select Photo Folder",
            command=self.select_folder,
            font=("Arial", 12),
        )
        select_btn.pack(side="left", padx=10)

        # Button to start comparison mode
        compare_btn = tk.Button(
            button_frame,
            text="Start Comparing Photos",
            command=self.start_comparison_mode,
            font=("Arial", 12),
            bg="lightblue",
        )
        compare_btn.pack(side="left", padx=10)

        # Button to reset all scores
        reset_btn = tk.Button(
            button_frame,
            text="Reset All Scores",
            command=self.reset_all_scores,
            font=("Arial", 12),
            bg="lightcoral",
        )
        reset_btn.pack(side="left", padx=10)

        # Button to add quantile prefixes
        add_prefix_btn = tk.Button(
            button_frame,
            text="Add Prefix",
            command=self.add_prefix_to_files,
            font=("Arial", 12),
            bg="lightgreen",
        )
        add_prefix_btn.pack(side="left", padx=5)

        # Button to remove quantile prefixes
        remove_prefix_btn = tk.Button(
            button_frame,
            text="Remove Prefix",
            command=self.remove_prefix_from_files,
            font=("Arial", 12),
            bg="lightyellow",
        )
        remove_prefix_btn.pack(side="left", padx=5)

        # Button to sync metadata with manually renamed files
        sync_btn = tk.Button(
            button_frame,
            text="Sync Files",
            command=self.sync_files,  # Fixed function name
            font=("Arial", 12),
            bg="lightcyan",
        )
        sync_btn.pack(side="left", padx=10)

        # Header with folder info and legend
        header_frame = tk.Frame(self.root)
        header_frame.pack(pady=10)

        # Main title
        header = tk.Label(
            header_frame,
            text="Photo Summary (Ordered by Skill)",
            font=("Arial", 16, "bold"),
        )
        header.pack()

        # Folder path display
        if self.photo_folder:
            # Get just the folder name (last part of path) for cleaner display
            folder_name = os.path.basename(self.photo_folder)
            # Also show the full path in smaller text
            folder_info = tk.Label(
                header_frame,
                text=f"Folder: {folder_name}",
                font=("Arial", 14, "bold"),
                fg="darkblue",
            )
            folder_info.pack(pady=2)

            # Full path in smaller text
            full_path = tk.Label(
                header_frame,
                text=f"Path: {self.photo_folder}",
                font=("Arial", 9),
                fg="gray",
            )
            full_path.pack(pady=1)

            # Photo count
            total_photos = (
                len(self.metadata_manager.metadata) if self.metadata_manager else 0
            )
            available_photos = (
                len(self.image_files) if hasattr(self, "image_files") else 0
            )
            count_info = tk.Label(
                header_frame,
                text=f"Photos: {available_photos} available / {total_photos} total",
                font=("Arial", 10),
                fg="darkgreen",
            )
            count_info.pack(pady=2)
        else:
            no_folder = tk.Label(
                header_frame,
                text="No folder selected",
                font=("Arial", 12),
                fg="red",
            )
            no_folder.pack(pady=2)

        # Legend for border colors
        legend_frame = tk.Frame(header_frame)
        legend_frame.pack(pady=5)

        tk.Label(legend_frame, text="Legend:", font=("Arial", 10, "bold")).pack(
            side="left"
        )

        # Blue box for images
        img_legend = tk.Label(
            legend_frame,
            text=" IMAGE ",
            bg="blue",
            fg="white",
            font=("Arial", 8, "bold"),
            relief="solid",
            borderwidth=2,
        )
        img_legend.pack(side="left", padx=5)

        # Red box for videos
        vid_legend = tk.Label(
            legend_frame,
            text=" VIDEO ",
            bg="red",
            fg="white",
            font=("Arial", 8, "bold"),
            relief="solid",
            borderwidth=2,
        )
        vid_legend.pack(side="left", padx=5)

        # Get photos sorted by skill (lowest first)
        photos_data = []
        for relative_path, data in self.metadata_manager.metadata.items():
            # Convert relative path to full path for file existence check
            full_path = os.path.join(self.photo_folder, relative_path)

            if os.path.exists(full_path):
                quantile = self.metadata_manager.get_quantile(relative_path)
                photos_data.append(
                    (relative_path, data["skill"], quantile, data["comparisons"])
                )
            else:
                print(f"File not found: {full_path}")

        photos_data.sort(key=lambda x: x[1])  # Sort by skill

        # Show up to 20 photos (5 rows × 4 columns)
        display_count = min(len(photos_data), 20)
        photos_to_show = photos_data[:display_count]

        # Create scrollable frame
        canvas = tk.Canvas(self.root)
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # Bind mousewheel to canvas and scrollable_frame
        canvas.bind("<MouseWheel>", on_mousewheel)
        scrollable_frame.bind("<MouseWheel>", on_mousewheel)

        # Also bind to the root window when mouse is over the summary
        self.root.bind("<MouseWheel>", on_mousewheel)

        # Display photos in grid (5 rows, 4 columns)
        for i, (relative_path, skill, quantile, comparisons) in enumerate(
            photos_to_show
        ):
            row = i // 4  # New row every 4 items
            col = i % 4  # Column cycles 0-3

            # Load and display image with colored border
            try:
                # Convert relative path to full path
                img_path = os.path.join(self.photo_folder, relative_path)

                # Ensure the path exists
                if not os.path.exists(img_path):
                    print(f"File not found in summary: {img_path}")
                    continue

                file_ext = os.path.splitext(relative_path)[1].lower()
                video_extensions = [
                    ".mp4",
                    ".mov",
                    ".mkv",
                    ".wmv",
                    ".flv",
                ]

                if file_ext in video_extensions:
                    # Extract first frame from video
                    img = self.extract_video_frame(img_path)
                    is_video = True
                else:
                    # Regular image
                    img = Image.open(img_path)
                    is_video = False

                img.thumbnail((280, 280), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)

                # Set border color based on file type
                border_color = "red" if is_video else "blue"

                # Photo frame with thin colored border
                photo_frame = tk.Frame(
                    scrollable_frame,
                    relief="solid",
                    borderwidth=2,
                    bg=border_color,
                )
                photo_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

                img_label = tk.Label(photo_frame, image=photo, bg=border_color)
                img_label.image = photo  # Keep reference
                img_label.pack(padx=1, pady=1)

                # Add click event for videos with proper path handling
                if is_video:
                    img_label.configure(cursor="hand2")
                    # Use absolute path to ensure reliability
                    abs_path = os.path.abspath(img_path)
                    if os.path.exists(abs_path):
                        # Create closure that captures the absolute path
                        def create_video_handler(video_path):
                            def handler(event):
                                print(f"Summary video clicked: {video_path}")  # Debug
                                self.open_video(video_path)

                            return handler

                        img_label.bind("<Button-1>", create_video_handler(abs_path))
                        print(f"Bound summary video handler for: {abs_path}")  # Debug
                    else:
                        print(f"Warning: Video file not found for summary: {abs_path}")

                # Info text with file type indicator and folder context
                file_type = "VIDEO" if is_video else "IMAGE"
                # Show folder context in the display
                display_name = relative_path.replace(
                    "/", " / "
                )  # Make path separators more readable
                info_text = f"{display_name} ({file_type})\nSkill: {skill:.2f} | Quantile: {quantile:.1f}\nComparisons: {comparisons}"
                info_label = tk.Label(
                    photo_frame,
                    text=info_text,
                    font=("Arial", 9),
                    bg=border_color,
                    fg="white",
                )
                info_label.pack(pady=2)

            except Exception as e:
                print(f"Error loading {relative_path} in summary: {e}")
                # Create error frame
                photo_frame = tk.Frame(
                    scrollable_frame,
                    relief="solid",
                    borderwidth=2,
                    bg="red",
                )
                photo_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

                error_label = tk.Label(
                    photo_frame, text=f"Error: {relative_path}", bg="red", fg="white"
                )
                error_label.pack()

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def start_comparison_mode(self):
        """Switch to comparison mode"""
        # Unbind mousewheel events before clearing widgets
        self.root.unbind("<MouseWheel>")

        # Clear and rebuild UI
        for widget in self.root.winfo_children():
            widget.destroy()

        self.setup_ui()
        self.display_random_pair()

    def update_file_names(self):
        """Update all file names to include quantile prefix (QXXX_)"""
        if not self.metadata_manager:
            messagebox.showwarning("No Folder", "Please select a photo folder first")
            return

        # Collect files that need renaming
        files_to_rename = []
        already_renamed = []

        for filename, data in self.metadata_manager.metadata.items():
            file_path = os.path.join(self.photo_folder, filename)

            if not os.path.exists(file_path):
                continue

            # Check if file already has quantile prefix
            if filename.startswith("Q") and "_" in filename[:5]:
                # Check if it matches current quantile
                current_quantile = self.metadata_manager.get_quantile(filename)
                # Convert to 3 digits including first decimal place: 50.6 -> 506
                quantile_int = int(current_quantile * 10)
                expected_prefix = f"Q{quantile_int:03d}_"

                if filename.startswith(expected_prefix):
                    already_renamed.append(filename)
                    continue
                else:
                    # File has old quantile prefix, needs updating
                    files_to_rename.append((file_path, filename))
            else:
                # File has no quantile prefix
                files_to_rename.append((file_path, filename))

        if not files_to_rename:
            messagebox.showinfo(
                "Already Updated",
                f"All {len(already_renamed)} files already have correct quantile prefixes",
            )
            return

        # Show confirmation dialog
        if not messagebox.askyesno(
            "Rename Files",
            f"This will rename {len(files_to_rename)} files with quantile prefixes.\n"
            f"{len(already_renamed)} files already have correct prefixes.\n\n"
            "Do you want to continue?",
        ):
            return

        # Create progress window
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Renaming Files")
        progress_window.geometry("500x150")
        progress_window.grab_set()

        # Center the window
        progress_window.transient(self.root)
        progress_window.geometry(
            "+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50)
        )

        progress_label = tk.Label(progress_window, text="Starting...", wraplength=450)
        progress_label.pack(pady=10)

        progress_bar = ttk.Progressbar(progress_window, mode="determinate")
        progress_bar.pack(pady=10, padx=20, fill="x")
        progress_bar["maximum"] = len(files_to_rename)

        status_label = tk.Label(progress_window, text="", font=("Arial", 8))
        status_label.pack(pady=5)

        success_count = 0
        failed_renames = []
        new_metadata = {}

        for i, (file_path, old_filename) in enumerate(files_to_rename):
            progress_label.config(text=f"Renaming: {old_filename}")
            progress_bar["value"] = i + 1
            status_label.config(text=f"{i+1}/{len(files_to_rename)} files processed")
            progress_window.update()

            try:
                # Calculate new filename
                quantile = self.metadata_manager.get_quantile(old_filename)
                # Convert to 3 digits including first decimal place: 50.6 -> 506
                quantile_int = int(quantile * 10)
                quantile_prefix = f"Q{quantile_int:03d}_"

                # Remove old quantile prefix if it exists
                if old_filename.startswith("Q") and "_" in old_filename[:5]:
                    # Find the first underscore and take everything after it
                    underscore_pos = old_filename.find("_")
                    base_filename = old_filename[underscore_pos + 1 :]
                else:
                    base_filename = old_filename

                new_filename = quantile_prefix + base_filename
                new_file_path = os.path.join(self.photo_folder, new_filename)

                # Check if new filename already exists
                if os.path.exists(new_file_path) and new_file_path != file_path:
                    print(
                        f"Warning: {new_filename} already exists, skipping {old_filename}"
                    )
                    failed_renames.append((old_filename, "File already exists"))
                    continue

                # Rename the file
                os.rename(file_path, new_file_path)

                # Update metadata with new filename
                old_data = self.metadata_manager.metadata[old_filename]
                new_metadata[new_filename] = old_data

                print(f"Renamed: {old_filename} -> {new_filename}")
                success_count += 1

            except Exception as e:
                print(f"Failed to rename {old_filename}: {e}")
                failed_renames.append((old_filename, str(e)))

        # Update metadata with new filenames
        if new_metadata:
            # Remove old entries and add new ones
            for old_filename, _ in files_to_rename:
                if old_filename in self.metadata_manager.metadata:
                    # Check if we successfully renamed this file
                    quantile = self.metadata_manager.get_quantile(old_filename)
                    # Convert to 3 digits including first decimal place: 50.6 -> 506
                    quantile_int = int(quantile * 10)
                    quantile_prefix = f"Q{quantile_int:03d}_"

                    if old_filename.startswith("Q") and "_" in old_filename[:5]:
                        underscore_pos = old_filename.find("_")
                        base_filename = old_filename[underscore_pos + 1 :]
                    else:
                        base_filename = old_filename

                    new_filename = quantile_prefix + base_filename

                    if new_filename in new_metadata:
                        # Successfully renamed, remove old entry
                        del self.metadata_manager.metadata[old_filename]

            # Add new entries
            self.metadata_manager.metadata.update(new_metadata)
            self.metadata_manager.save_metadata()

        progress_window.destroy()

        # Show results
        if failed_renames:
            error_msg = f"Renamed {success_count}/{len(files_to_rename)} files\n\nFailed renames:\n"
            error_msg += "\n".join(
                [f"• {name}: {error}" for name, error in failed_renames[:10]]
            )
            if len(failed_renames) > 10:
                error_msg += f"\n... and {len(failed_renames) - 10} more"
            messagebox.showwarning("Rename Complete with Errors", error_msg)
        else:
            messagebox.showinfo(
                "Rename Complete",
                f"Successfully renamed {success_count} files with quantile prefixes!",
            )

        # Refresh the summary page to show new names
        self.show_summary_page()

    def remove_prefix_from_files(self):
        """Remove quantile prefix from files that have it"""
        if not self.metadata_manager:
            messagebox.showwarning("No Folder", "Please select a photo folder first")
            return

        # Collect files that have prefixes to remove
        files_to_rename = []
        no_prefix = []

        for relative_path, data in self.metadata_manager.metadata.items():
            # Convert relative path to full path
            file_path = os.path.join(self.photo_folder, relative_path)

            if not os.path.exists(file_path):
                continue

            # Get just the filename (without folder path) to check for prefix
            filename = os.path.basename(relative_path)

            # Check if file has quantile prefix
            if filename.startswith("Q") and "_" in filename[:5]:
                files_to_rename.append((file_path, relative_path))
            else:
                no_prefix.append(relative_path)

        if not files_to_rename:
            messagebox.showinfo(
                "No Prefixes",
                f"No files have quantile prefixes to remove.\n"
                f"All {len(no_prefix)} files are already without prefixes.",
            )
            return

        # Show confirmation dialog
        if not messagebox.askyesno(
            "Remove Prefixes",
            f"This will remove quantile prefixes from {len(files_to_rename)} files.\n"
            f"{len(no_prefix)} files already have no prefixes.\n\n"
            "Do you want to continue?",
        ):
            return

        success_count = self._rename_files_with_progress(
            files_to_rename, add_prefix=False
        )

        # Show results
        messagebox.showinfo(
            "Prefixes Removed",
            f"Successfully removed prefixes from {success_count}/{len(files_to_rename)} files!",
        )

        # Refresh the summary page
        self.show_summary_page()

    def get_quantile_from_filename(self, filename):
        """Extract quantile from filename if it has the QXXX_ prefix"""
        if filename.startswith("Q") and "_" in filename[:5]:
            try:
                # Extract the number between Q and _
                underscore_pos = filename.find("_")
                quantile_str = filename[1:underscore_pos]
                # Convert back from 3-digit format: 506 -> 50.6
                quantile_int = int(quantile_str)
                return quantile_int / 10.0
            except (ValueError, IndexError):
                pass
        return None

    def sync_metadata_with_files(self):
        """Sync metadata when files have been manually renamed"""
        if not self.metadata_manager:
            return

        # Get all actual files in the directory
        extensions = [
            "*.jpg",
            "*.jpeg",
            "*.png",
            "*.bmp",
            "*.gif",
            "*.tiff",
            "*.mp4",
            # "*.avi",
            "*.mov",
            "*.mkv",
            "*.wmv",
            "*.flv",
        ]
        actual_files = set()

        for ext in extensions:
            actual_files.update(glob.glob(os.path.join(self.photo_folder, ext)))
            actual_files.update(glob.glob(os.path.join(self.photo_folder, ext.upper())))

        actual_filenames = {os.path.basename(f) for f in actual_files}
        metadata_filenames = set(self.metadata_manager.metadata.keys())

        # Find files that exist but aren't in metadata (manually renamed)
        missing_from_metadata = actual_filenames - metadata_filenames

        # Find metadata entries that don't have corresponding files
        missing_files = metadata_filenames - actual_filenames

        updates_made = 0

        # Try to match missing files with existing files
        for missing_metadata_name in missing_files:
            # Get the base name without quantile prefix
            base_name = self.get_base_filename(missing_metadata_name)

            # Look for this base name in the actual files
            for actual_name in missing_from_metadata:
                actual_base = self.get_base_filename(actual_name)

                if base_name == actual_base:
                    # Found a match! Update metadata
                    old_data = self.metadata_manager.metadata[missing_metadata_name]
                    self.metadata_manager.metadata[actual_name] = old_data
                    del self.metadata_manager.metadata[missing_metadata_name]

                    print(f"Synced: {missing_metadata_name} -> {actual_name}")
                    updates_made += 1
                    break

        # Add any completely new files
        remaining_new_files = actual_filenames - set(
            self.metadata_manager.metadata.keys()
        )
        for new_file in remaining_new_files:
            self.metadata_manager.metadata[new_file] = {
                "keep": None,
                "rating": None,
                "tags": [],
                "last_compared": None,
                "created_date": datetime.now().isoformat(),
                "skill": 0,
                "comparisons": 0,
            }
            print(f"Added new file: {new_file}")
            updates_made += 1

        if updates_made > 0:
            self.metadata_manager.save_metadata()
            print(f"Synced {updates_made} file changes")
            return True

        return False

    def sync_files(self, silent=False):
        """Synchronize metadata file with actual files present in folder (with duplicate cleanup)"""
        if not self.metadata_manager:
            if not silent:
                messagebox.showwarning(
                    "No Folder", "Please select a photo folder first"
                )
            return

        # Get all actual files recursively (same logic as _add_new_photos)
        extensions = [
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".gif",
            ".tiff",
            ".mp4",
            ".mov",
            ".mkv",
            ".wmv",
            ".flv",
        ]

        # Folders to skip (decisions already made)
        skip_folders = {"delete", "keep"}

        actual_files = []

        # Walk through subfolders with depth limit (same logic as _add_new_photos)
        for root, dirs, files in os.walk(self.photo_folder):
            # Calculate current depth
            current_depth = root[len(self.photo_folder) :].count(os.sep)

            # Skip if we're too deep (allow 4 levels: year/month/type/files)
            if current_depth >= config.MAX_FOLDER_DEPTH:
                dirs[:] = []  # Don't descend further
                continue

            # Remove skip folders from dirs list to prevent os.walk from entering them
            dirs[:] = [d for d in dirs if d.lower() not in skip_folders]

            # Process files in current directory
            for file in files:
                # Check if file has supported extension
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in extensions:
                    # Get full path
                    full_path = os.path.join(root, file)
                    actual_files.append(full_path)

        # Convert to relative paths for comparison with metadata keys
        actual_relative_paths = set()
        for file_path in actual_files:
            relative_path = os.path.relpath(file_path, self.photo_folder)
            relative_path = relative_path.replace(os.sep, "/")  # Normalize separators
            actual_relative_paths.add(relative_path)

        metadata_filenames = set(self.metadata_manager.metadata.keys())

        print(f"Actual files found: {len(actual_relative_paths)}")
        print(f"Metadata entries: {len(metadata_filenames)}")

        # Files that exist but aren't in metadata (need to be added)
        missing_from_metadata = actual_relative_paths - metadata_filenames

        # Files in metadata but don't exist (need to be removed)
        missing_files = metadata_filenames - actual_relative_paths

        changes_made = 0
        duplicates_removed = 0

        # DUPLICATE CLEANUP: Before removing missing files, check for duplicates
        # Group missing files by base filename to find potential duplicates
        base_to_missing = {}
        for missing_entry in missing_files:
            base_filename = self.get_base_filename(os.path.basename(missing_entry))
            folder_part = os.path.dirname(missing_entry)
            base_key = (folder_part, base_filename)

            if base_key not in base_to_missing:
                base_to_missing[base_key] = []
            base_to_missing[base_key].append(missing_entry)

        # Check for cases where we have both a missing file and an actual file with the same base name
        duplicates_to_remove = []
        for (folder_part, base_filename), missing_entries in base_to_missing.items():
            # Look for corresponding actual file with same base name
            corresponding_actual = None
            for actual_file in actual_relative_paths:
                if (
                    os.path.dirname(actual_file) == folder_part
                    and self.get_base_filename(os.path.basename(actual_file))
                    == base_filename
                ):
                    corresponding_actual = actual_file
                    break

            if corresponding_actual and len(missing_entries) >= 1:
                # We have actual file and missing metadata entries with same base name
                # This indicates duplicates from renaming operations

                # If the actual file doesn't have metadata, transfer from the missing entry
                if corresponding_actual not in metadata_filenames:
                    # Find the missing entry with the most comparisons (most valuable data)
                    best_missing = max(
                        missing_entries,
                        key=lambda x: self.metadata_manager.metadata[x].get(
                            "comparisons", 0
                        ),
                    )

                    # Transfer metadata from missing entry to actual file
                    self.metadata_manager.metadata[corresponding_actual] = (
                        self.metadata_manager.metadata[best_missing]
                    )
                    print(
                        f"Transferred metadata: {best_missing} -> {corresponding_actual}"
                    )
                    changes_made += 1

                    # Mark missing entries for removal
                    duplicates_to_remove.extend(missing_entries)
                else:
                    # Actual file already has metadata, just remove the duplicates
                    duplicates_to_remove.extend(missing_entries)

        # Remove duplicate entries
        for duplicate in duplicates_to_remove:
            if duplicate in self.metadata_manager.metadata:
                del self.metadata_manager.metadata[duplicate]
                duplicates_removed += 1
                print(f"Removed duplicate metadata entry: {duplicate}")

        # Update the missing_files set after removing duplicates
        missing_files = missing_files - set(duplicates_to_remove)

        # Remove remaining metadata entries for files that no longer exist
        if missing_files:
            print(f"Removing {len(missing_files)} missing files from metadata:")
            for relative_path in missing_files:
                print(f"  - Removing: {relative_path}")
                del self.metadata_manager.metadata[relative_path]
                changes_made += 1

        # Add metadata entries for new files found
        if missing_from_metadata:
            print(f"Adding {len(missing_from_metadata)} new files to metadata:")
            for relative_path in missing_from_metadata:
                print(f"  - Adding: {relative_path}")
                self.metadata_manager.metadata[relative_path] = {
                    "keep": None,
                    "rating": None,
                    "tags": [],
                    "last_compared": None,
                    "created_date": datetime.now().isoformat(),
                    "skill": 0,
                    "comparisons": 0,
                }
                changes_made += 1

        # Save changes if any were made
        total_changes = changes_made + duplicates_removed
        if total_changes > 0:
            self.metadata_manager.save_metadata()

            # Reload the image list to reflect changes
            self.load_images()

            # Show detailed results only if not silent
            if not silent:
                result_msg = f"Synchronization complete!\n\n"
                if duplicates_removed > 0:
                    result_msg += (
                        f"• Removed {duplicates_removed} duplicate metadata entries\n"
                    )
                if missing_files:
                    result_msg += (
                        f"• Removed {len(missing_files)} missing files from metadata\n"
                    )
                if missing_from_metadata:
                    result_msg += (
                        f"• Added {len(missing_from_metadata)} new files to metadata\n"
                    )

                result_msg += f"\nTotal changes: {total_changes}"

                messagebox.showinfo("Files Synchronized", result_msg)
                self.show_summary_page()  # Only refresh if not already in summary page
            else:
                # Silent mode: just print to console for debugging
                print(
                    f"Silent sync: {total_changes} changes made ({duplicates_removed} duplicates removed)"
                )
        else:
            if not silent:
                messagebox.showinfo(
                    "No Changes",
                    "Metadata is already synchronized with folder contents",
                )
            else:
                print("Silent sync: no changes needed")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    # Set to True for testing, False for normal use
    app = PhotoManager(test_mode=True)
    app.run()
