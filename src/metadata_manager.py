import glob
import json
import os
from datetime import datetime


class MetadataManager:
    def __init__(self, photo_folder):
        self.photo_folder = photo_folder
        self.metadata_file = os.path.join(photo_folder, ".photo_metadata.json")
        self.metadata = {}

    def load_metadata(self):
        """Load existing metadata or create new file"""
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, "r") as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {}

        # Add any new photos found in folder
        self._add_new_photos()
        self.save_metadata()

    def _add_new_photos(self):
        """Add metadata entries for new photos"""
        extensions = ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.gif", "*.tiff"]
        image_files = []

        for ext in extensions:
            image_files.extend(glob.glob(os.path.join(self.photo_folder, ext)))
            image_files.extend(glob.glob(os.path.join(self.photo_folder, ext.upper())))

        for file_path in image_files:
            filename = os.path.basename(file_path)
            if filename not in self.metadata:
                self.metadata[filename] = {
                    "keep": None,
                    "rating": None,
                    "tags": [],
                    "last_compared": None,
                    "created_date": datetime.now().isoformat(),
                }

    def save_metadata(self):
        """Save metadata to JSON file"""
        with open(self.metadata_file, "w") as f:
            json.dump(self.metadata, f, indent=2)

    def update_photo(self, filename, **kwargs):
        """Update metadata for a specific photo"""
        if filename in self.metadata:
            self.metadata[filename].update(kwargs)
            self.save_metadata()

    def get_photo_data(self, filename):
        """Get metadata for a specific photo"""
        return self.metadata.get(filename, {})
