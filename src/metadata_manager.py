import glob
import json
import math
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
        # Remove any photos no longer in folder
        self._remove_missing_photos()
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
                    "skill": 0,  # Initial skill (s = 0, quantile = 50)
                    "comparisons": 0,  # Number of comparisons (c)
                }

    def _remove_missing_photos(self):
        """Remove metadata entries for photos no longer in folder"""
        extensions = ["*.jpg", "*.jpeg", "*.png", "*.bmp", "*.gif", "*.tiff"]
        image_files = []

        for ext in extensions:
            image_files.extend(glob.glob(os.path.join(self.photo_folder, ext)))
            image_files.extend(glob.glob(os.path.join(self.photo_folder, ext.upper())))

        # Get list of filenames that actually exist
        existing_filenames = set(
            os.path.basename(file_path) for file_path in image_files
        )

        # Get list of filenames in metadata
        metadata_filenames = set(self.metadata.keys())

        # Find files to remove (in metadata but not in folder)
        files_to_remove = metadata_filenames - existing_filenames

        # Remove them
        for filename in files_to_remove:
            print(f"Removing missing photo from metadata: {filename}")
            del self.metadata[filename]

        if files_to_remove:
            print(f"Removed {len(files_to_remove)} missing photos from metadata")

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

    def get_quantile(self, filename):
        """Get current quantile rank for a photo"""
        if filename not in self.metadata:
            return 50
        skill = self.metadata[filename]["skill"]
        return 100 / (1 + math.exp(-skill))

    def update_skills(self, filename_a, filename_b, outcome, k_0=2):
        """Update skills and comparison counts.
        Outcome: 1 (A wins), 0 (B wins), 0.5 (tie), 1.5 (both win), -0.5 (both lose)"""

        # Get current data
        data_a = self.metadata[filename_a]
        data_b = self.metadata[filename_b]

        s_a, c_a = data_a["skill"], data_a["comparisons"]
        s_b, c_b = data_b["skill"], data_b["comparisons"]

        # Calculate dynamic k values
        k_a = k_0 / math.sqrt(c_a + 1)
        k_b = k_0 / math.sqrt(c_b + 1)

        # Calculate expected outcomes
        e_a = 1 / (1 + math.exp(-(s_a - s_b)))
        e_b = 1 - e_a

        # Handle special cases
        match outcome:
            case "both":  # Both win
                outcome_a, outcome_b = 1, 1
            case "neither":  # Both lose
                outcome_a, outcome_b = 0, 0
            case "tie":  # Tie
                outcome_a, outcome_b = 0.5, 0.5
            case "left":  # left wins
                outcome_a, outcome_b = 1, 0
            case "right":  # right wins
                outcome_a, outcome_b = 0, 1

        # Update skills
        s_a_new = s_a + k_a * (outcome_a - e_a)
        s_b_new = s_b + k_b * (outcome_b - e_b)

        # Update metadata
        self.metadata[filename_a]["skill"] = s_a_new
        self.metadata[filename_a]["comparisons"] = c_a + 1
        self.metadata[filename_b]["skill"] = s_b_new
        self.metadata[filename_b]["comparisons"] = c_b + 1

        self.save_metadata()

        print(f"Updated {filename_a}: skill {s_a:.2f} -> {s_a_new:.2f}")
        print(f"Updated {filename_b}: skill {s_b:.2f} -> {s_b_new:.2f}")
