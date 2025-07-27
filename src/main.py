import datetime
import gc
import glob
import math
import os
import random
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog, messagebox

import cv2
import pythoncom
import win32api
import win32com.shell.shell as shell
import win32con
from mutagen import File
from PIL import Image, ImageTk
from win32com.shell import shellcon

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

    def auto_load_test_folder(self):
        test_folder = (
            r"C:\Users\Admin\Desktop\Photos and Videos\test"  # Update this path
        )

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
        # Filter out images below 0.10 quantile before each comparison
        available_images = []
        for file_path in self.image_files:
            filename = os.path.basename(file_path)
            quantile = self.metadata_manager.get_quantile(filename)
            if quantile >= 10:  # quantile is 0-100
                available_images.append(file_path)
                print(f"Quantile for {filename}: {quantile}")

        print(f"Available images: {len(available_images)}")  # Debug line

        if len(available_images) < 2:
            print("Not enough images above 10th percentile for comparison!")
            from tkinter import messagebox

            messagebox.showinfo(
                "No More Comparisons",
                "All remaining photos are below 10th percentile. Returning to summary.",
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

        # Load and display images
        self.show_image(self.current_images[0], self.img1_label)
        self.show_image(self.current_images[1], self.img2_label)

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

    def get_weighted_selection_from_list(self, image_list, k=2):
        """Select images from provided list with weighting based on distance from 0.10 quantile"""

        # Remove any duplicate paths first
        unique_images = list(set(image_list))
        print(f"Original list: {len(image_list)}, Unique: {len(unique_images)}")

        if len(unique_images) < k:
            print(f"Warning: Only {len(unique_images)} unique images available")
            return unique_images

        # For now, let's just use random selection to eliminate the duplicate issue
        # We can add weighting back once we confirm duplicates are gone
        selected = random.sample(unique_images, k)

        print(f"Selected: {[os.path.basename(img) for img in selected]}")
        return selected

    def handle_keypress(self, event):
        if not hasattr(self, "current_images") or len(self.current_images) != 2:
            return

        if event.keysym == "Left":
            self.process_comparison(1, 0)  # Left wins
        elif event.keysym == "Right":
            self.process_comparison(0, 1)  # Right wins
        elif event.keysym == "Up":
            self.process_comparison(1, 1)  # Both win
        elif event.keysym == "Down":
            self.process_comparison(0, 0)  # Both lose
        elif event.keysym == "space":
            self.process_comparison(0.5, 0.5)  # Tie

    def load_images(self):
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
        import os
        import platform
        import subprocess

        try:
            if platform.system() == "Windows":
                # Try different players in order of preference
                players = [
                    r"C:\Program Files\Windows Media Player\wmplayer.exe",
                    r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                    r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
                ]

                for player in players:
                    if os.path.exists(player):
                        subprocess.Popen([player, video_path])
                        # print(
                        #     # f"Opening video with {os.path.basename(player)}: {os.path.basename(video_path)}"
                        # )
                        return

                # Fallback to default association
                os.startfile(video_path)
                # print(f"Opening video with default app: {os.path.basename(video_path)}")

            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", video_path])
            else:  # Linux
                subprocess.Popen(["xdg-open", video_path])

        except Exception as e:
            # print(f"Error opening video {video_path}: {e}")
            from tkinter import messagebox

            messagebox.showerror("Error", f"Could not open video: {e}")

    def process_comparison(self, left_score, right_score):
        if not self.metadata_manager:
            return

        left_filename = os.path.basename(self.current_images[0])
        right_filename = os.path.basename(self.current_images[1])

        # Debug lines
        # print(f"Left image: {self.current_images[0]}")
        # print(f"Right image: {self.current_images[1]}")
        # print(f"Left filename: {left_filename}")
        # print(f"Right filename: {right_filename}")
        # print(f"Left in metadata: {left_filename in self.metadata_manager.metadata}")
        # print(f"Right in metadata: {right_filename in self.metadata_manager.metadata}")
        # print(f"Metadata keys: {list(self.metadata_manager.metadata.keys())}")

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

        # Update Elo ratings
        self.metadata_manager.update_skills(left_filename, right_filename, outcome)

        # Update file tags with new quantiles
        left_path = self.current_images[0]
        right_path = self.current_images[1]
        left_quantile = self.metadata_manager.get_quantile(left_filename)
        right_quantile = self.metadata_manager.get_quantile(right_filename)

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

    def show_image(self, path, label):
        try:
            filename = os.path.basename(path)
            file_ext = os.path.splitext(path)[1].lower()

            # Check if it's a video file
            video_extensions = [".mp4", ".mov", ".mkv", ".wmv", ".flv"]  # removed .avi

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

            # Get metadata
            skill = self.metadata_manager.metadata[filename]["skill"]
            comparisons = self.metadata_manager.metadata[filename]["comparisons"]
            quantile = self.metadata_manager.get_quantile(filename)

            # Create info text with file type indicator
            file_type = "VIDEO" if is_video else "IMAGE"
            info_text = f"{filename} ({file_type})\nSkill: {skill:.2f} | Quantile: {quantile:.1f} | Comparisons: {comparisons}"

            # Set border color based on file type
            border_color = "red" if is_video else "blue"

            label.configure(
                image=photo,
                text=info_text,
                compound="top",
                font=("Arial", 10),
                bg=border_color,  # Background color for border
                relief="solid",  # Solid border style
                borderwidth=2,  # Thinner border
            )
            label.image = photo  # Keep reference

            # Add click event for videos
            if is_video:
                label.configure(cursor="hand2")  # Change cursor to indicate clickable
                label.bind("<Button-1>", lambda e: self.open_video(path))
            else:
                label.unbind("<Button-1>")  # Remove click event for images
                label.configure(cursor="")

        except Exception as e:
            label.configure(text=f"Error loading image: {os.path.basename(path)}")

    def show_summary_page(self):
        """Display summary of photos ordered by skill with colored borders"""
        # Clear existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        self.load_images()  # Reload image list

        # Calculate window size for 10 photos (2 rows × 4 columns)
        # Each photo: 280px + padding, plus scrollbar and buttons
        window_width = (280 + 20) * 4 + 60  # 4 columns * (image + padding) + margins
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
            command=self.fix_invisible_files,
            font=("Arial", 12),
            bg="lightcyan",
        )
        sync_btn.pack(side="left", padx=10)

        # Header with legend
        header_frame = tk.Frame(self.root)
        header_frame.pack(pady=10)

        header = tk.Label(
            header_frame,
            text="Photo Summary (Ordered by Skill)",
            font=("Arial", 16, "bold"),
        )
        header.pack()

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
        for filename, data in self.metadata_manager.metadata.items():
            if os.path.exists(os.path.join(self.photo_folder, filename)):
                quantile = self.metadata_manager.get_quantile(filename)
                photos_data.append(
                    (filename, data["skill"], quantile, data["comparisons"])
                )

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
        for i, (filename, skill, quantile, comparisons) in enumerate(photos_to_show):
            row = i // 4  # New row every 4 items
            col = i % 4  # Column cycles 0-3

            # Load and display image with colored border
            try:
                img_path = os.path.join(self.photo_folder, filename)
                file_ext = os.path.splitext(filename)[1].lower()
                video_extensions = [
                    ".mp4",
                    ".mov",
                    ".mkv",
                    ".wmv",
                    ".flv",
                ]  # removed .avi

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
                    borderwidth=2,  # Thinner border
                    bg=border_color,  # Colored border
                )
                photo_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

                img_label = tk.Label(photo_frame, image=photo, bg=border_color)
                img_label.image = photo  # Keep reference
                img_label.pack(padx=1, pady=1)  # Minimal padding inside border

                # Add click event for videos
                if is_video:
                    img_label.configure(cursor="hand2")
                    img_label.bind(
                        "<Button-1>", lambda e, path=img_path: self.open_video(path)
                    )

                # Info text with file type indicator
                file_type = "VIDEO" if is_video else "IMAGE"
                info_text = f"{filename} ({file_type})\nSkill: {skill:.2f} | Quantile: {quantile:.1f}\nComparisons: {comparisons}"
                info_label = tk.Label(
                    photo_frame,
                    text=info_text,
                    font=("Arial", 9),
                    bg=border_color,
                    fg="white",
                )
                info_label.pack(pady=2)  # Less padding

            except Exception as e:
                print(f"Error loading {filename} in summary: {e}")
                error_label = tk.Label(photo_frame, text=f"Error: {filename}")
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

    def add_prefix_to_files(self):
        """Add quantile prefix to files that don't have it or need updating"""
        if not self.metadata_manager:
            messagebox.showwarning("No Folder", "Please select a photo folder first")
            return

        # Collect files that need prefix added/updated
        files_to_rename = []
        already_prefixed = []

        for filename, data in self.metadata_manager.metadata.items():
            file_path = os.path.join(self.photo_folder, filename)

            if not os.path.exists(file_path):
                continue

            # Check if file already has correct quantile prefix
            if filename.startswith("Q") and "_" in filename[:5]:
                # Check if it matches current quantile
                current_quantile = self.metadata_manager.get_quantile(filename)
                quantile_int = int(current_quantile * 10)
                expected_prefix = f"Q{quantile_int:03d}_"

                if filename.startswith(expected_prefix):
                    already_prefixed.append(filename)
                    continue
                else:
                    # File has old/wrong quantile prefix, needs updating
                    files_to_rename.append((file_path, filename))
            else:
                # File has no quantile prefix
                files_to_rename.append((file_path, filename))

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

    def remove_prefix_from_files(self):
        """Remove quantile prefix from files that have it"""
        if not self.metadata_manager:
            messagebox.showwarning("No Folder", "Please select a photo folder first")
            return

        # Collect files that have prefixes to remove
        files_to_rename = []
        no_prefix = []

        for filename, data in self.metadata_manager.metadata.items():
            file_path = os.path.join(self.photo_folder, filename)

            if not os.path.exists(file_path):
                continue

            # Check if file has quantile prefix
            if filename.startswith("Q") and "_" in filename[:5]:
                files_to_rename.append((file_path, filename))
            else:
                no_prefix.append(filename)

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

        for i, (file_path, old_filename) in enumerate(files_to_rename):
            action_text = "Adding prefix to" if add_prefix else "Removing prefix from"
            progress_label.config(text=f"{action_text}: {old_filename}")
            progress_bar["value"] = i + 1
            status_label.config(text=f"{i+1}/{len(files_to_rename)} files processed")
            progress_window.update()

            try:
                if add_prefix:
                    # Calculate new filename with prefix
                    quantile = self.metadata_manager.get_quantile(old_filename)
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
                if (
                    old_filename in self.metadata_manager.metadata
                    and old_filename not in new_metadata.values()
                ):
                    # Only delete if we successfully created a new entry
                    for new_name in new_metadata.keys():
                        if (
                            new_metadata[new_name]
                            == self.metadata_manager.metadata[old_filename]
                        ):
                            del self.metadata_manager.metadata[old_filename]
                            break

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

    def get_base_filename(self, filename):
        """Get the base filename without quantile prefix"""
        if filename.startswith("Q") and "_" in filename[:5]:
            underscore_pos = filename.find("_")
            return filename[underscore_pos + 1 :]
        return filename

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

    def fix_invisible_files(self):
        """Fix files that became invisible after manual renaming"""
        if not self.metadata_manager:
            messagebox.showwarning("No Folder", "Please select a photo folder first")
            return

        # Count how many files need syncing
        if self.sync_metadata_with_files():
            messagebox.showinfo(
                "Files Synced",
                "Successfully synced metadata with manually renamed files!",
            )
            self.show_summary_page()  # Refresh display
        else:
            messagebox.showinfo("No Changes", "All files are already in sync")

    # Alternative: Auto-sync method to call whenever loading images
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

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    # Set to True for testing, False for normal use
    app = PhotoManager(test_mode=True)
    app.run()
