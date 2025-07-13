import glob
import os
import random
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk

from metadata_manager import MetadataManager


class PhotoManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Photo Manager")
        self.root.geometry("1200x600")
        self.metadata_manager = None

        self.photo_folder = None
        self.image_files = []

        self.setup_ui()

    def setup_ui(self):
        # Folder selection button
        select_btn = tk.Button(
            self.root,
            text="Select Photo Folder",
            command=self.select_folder,
            font=("Arial", 12),
        )
        select_btn.pack(pady=10)

        # Frame for images
        self.image_frame = tk.Frame(self.root)
        self.image_frame.pack(expand=True, fill="both", padx=10, pady=10)

        # Labels for images
        self.img1_label = tk.Label(self.image_frame)
        self.img1_label.pack(side="left", expand=True, fill="both", padx=5)

        self.img2_label = tk.Label(self.image_frame)
        self.img2_label.pack(side="right", expand=True, fill="both", padx=5)

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.photo_folder = folder
            self.metadata_manager = MetadataManager(folder)
            self.metadata_manager.load_metadata()
            self.load_images()
            self.display_random_pair()

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
            return

        # Select 2 random images
        selected = random.sample(self.image_files, 2)

        # Load and display images
        self.show_image(selected[0], self.img1_label)
        self.show_image(selected[1], self.img2_label)

    def show_image(self, path, label):
        try:
            img = Image.open(path)
            # Resize to fit in half the window
            img.thumbnail((580, 500), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            label.configure(image=photo)
            label.image = photo  # Keep reference
        except Exception as e:
            label.configure(text=f"Error loading image: {os.path.basename(path)}")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = PhotoManager()
    app.run()
