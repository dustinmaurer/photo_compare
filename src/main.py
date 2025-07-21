import glob
import os
import random
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk

from metadata_manager import MetadataManager


class PhotoManager:
    def __init__(self, test_mode=False):
        self.root = tk.Tk()
        self.root.title("Photo Manager")
        self.root.geometry("1200x600")
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

    def process_comparison(self, left_score, right_score):
        if not self.metadata_manager:
            return

        left_filename = os.path.basename(self.current_images[0])
        right_filename = os.path.basename(self.current_images[1])

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

        # Show next pair
        self.display_random_pair()

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.photo_folder = folder
            self.metadata_manager = MetadataManager(folder)
            self.metadata_manager.load_metadata()
            self.load_images()
            self.show_summary_page()  # Show summary instead of going directly to comparison

    def load_images(self):
        extensions = ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.gif", "*.tiff"]
        self.image_files = []

        for ext in extensions:
            self.image_files.extend(glob.glob(os.path.join(self.photo_folder, ext)))
            self.image_files.extend(
                glob.glob(os.path.join(self.photo_folder, ext.upper()))
            )

        if len(self.image_files) < 2:
            messagebox.showwarning("Warning", "Need at least 2 images in folder")

    def display_random_pair(self):
        if len(self.image_files) < 2:
            print("Need at least 2 different images")
            return

        # Ensure we get 2 different images
        self.current_images = random.sample(self.image_files, 2)

        # Double-check they're different (shouldn't happen with random.sample, but just in case)
        while self.current_images[0] == self.current_images[1]:
            self.current_images = random.sample(self.image_files, 2)

        # Load and display images
        self.show_image(self.current_images[0], self.img1_label)
        self.show_image(self.current_images[1], self.img2_label)

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

    def show_image(self, path, label):
        try:
            img = Image.open(path)
            # Resize to fit in half the window
            img.thumbnail((580, 400), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            filename = os.path.basename(path)

            # # Get metadata
            skill = self.metadata_manager.metadata[filename]["skill"]
            comparisons = self.metadata_manager.metadata[filename]["comparisons"]
            quantile = self.metadata_manager.get_quantile(filename)

            # Create info text
            info_text = f"{filename}\nSkill: {skill:.2f} | Quantile: {quantile:.1f} | Comparisons: {comparisons}"

            label.configure(
                image=photo, text=info_text, compound="top", font=("Arial", 10)
            )
            label.image = photo  # Keep reference
        except Exception as e:
            label.configure(text=f"Error loading image: {os.path.basename(path)}")

    def show_summary_page(self):
        """Display summary of photos ordered by skill"""
        # Clear existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        # Calculate window size for 10 photos (2 rows × 5 columns)
        # Each photo: 280px + padding, plus scrollbar and buttons
        window_width = (280 + 20) * 5 + 40  # 5 columns * (image + padding) + margins
        window_height = (
            280 + 80
        ) * 2 + 200  # 2 rows * (image + text + padding) + buttons/header

        self.root.geometry(f"{window_width}x{window_height}")

        # Button to start comparing
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

        # Header
        header = tk.Label(
            self.root,
            text="Photo Summary (Ordered by Skill)",
            font=("Arial", 16, "bold"),
        )
        header.pack(pady=10)

        # Get photos sorted by skill (lowest first)
        photos_data = []
        for filename, data in self.metadata_manager.metadata.items():
            if os.path.exists(os.path.join(self.photo_folder, filename)):
                quantile = self.metadata_manager.get_quantile(filename)
                photos_data.append(
                    (filename, data["skill"], quantile, data["comparisons"])
                )

        photos_data.sort(key=lambda x: x[1])  # Sort by skill

        # Show up to 10 photos (2 rows × 5 columns)
        display_count = min(len(photos_data), 10)
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

        # Display photos in grid (2 rows, 5 columns)
        for i, (filename, skill, quantile, comparisons) in enumerate(photos_to_show):
            row = i // 5  # New row every 5 items
            col = i % 5  # Column cycles 0-4

            # Photo frame
            photo_frame = tk.Frame(scrollable_frame, relief="raised", borderwidth=2)
            photo_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            # Load and display image
            try:
                img_path = os.path.join(self.photo_folder, filename)
                img = Image.open(img_path)
                img.thumbnail((280, 280), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)

                img_label = tk.Label(photo_frame, image=photo)
                img_label.image = photo  # Keep reference
                img_label.pack()

                # Info text
                info_text = f"{filename}\nSkill: {skill:.2f} | Quantile: {quantile:.1f}\nComparisons: {comparisons}"
                info_label = tk.Label(photo_frame, text=info_text, font=("Arial", 9))
                info_label.pack(pady=5)

            except Exception as e:
                error_label = tk.Label(photo_frame, text=f"Error: {filename}")
                error_label.pack()

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def start_comparison_mode(self):
        """Switch to comparison mode"""
        # Clear and rebuild UI
        for widget in self.root.winfo_children():
            widget.destroy()

        self.setup_ui()
        self.display_random_pair()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    # Set to True for testing, False for normal use
    app = PhotoManager(test_mode=True)
    app.run()
