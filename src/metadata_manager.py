import glob
import json
import math
import os
from datetime import datetime

import config


class MetadataManager:
    def __init__(self, photo_folder):
        self.photo_folder = photo_folder
        self.metadata_file = os.path.join(photo_folder, ".photo_metadata.json")
        self.metadata = {}

    def _add_new_photos(self):
        """Add metadata entries for new photos (now searches recursively with limits)"""
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

        # Walk through subfolders with depth limit
        for root, dirs, files in os.walk(self.photo_folder):
            # Calculate current depth
            current_depth = root[len(self.photo_folder) :].count(os.sep)

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

                    # Convert to relative path for use as key
                    relative_path = os.path.relpath(full_path, self.photo_folder)

                    # Normalize path separators for consistency (Windows vs Unix)
                    relative_path = relative_path.replace(os.sep, "/")

                    # Add to metadata if not already present
                    if relative_path not in self.metadata:
                        self.metadata[relative_path] = {
                            "keep": None,
                            "rating": None,
                            "tags": [],
                            "last_compared": None,
                            "created_date": datetime.now().isoformat(),
                            "skill": 0,  # Initial skill (s = 0, quantile = 50)
                            "comparisons": 0,  # Number of comparisons (c)
                        }
                        print(f"Added new photo: {relative_path}")  # Debug output

            # Debug output for folder exploration
            if current_depth == 0:
                print(f"Exploring root folder, found {len(dirs)} subfolders: {dirs}")
            elif current_depth == 1:
                folder_name = os.path.basename(root)
                print(
                    f"Exploring subfolder '{folder_name}', found {len(dirs)} sub-subfolders: {dirs}"
                )

    def _remove_missing_photos(self):
        """Remove metadata entries for photos no longer in folder (now searches recursively)"""
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

        existing_relative_paths = set()

        # Walk through subfolders with same logic as _add_new_photos
        for root, dirs, files in os.walk(self.photo_folder):
            # Calculate current depth
            current_depth = root[len(self.photo_folder) :].count(os.sep)

            # Skip if we're too deep (allow 4 levels for year/month/type structure)
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

                    # Convert to relative path to match metadata keys
                    relative_path = os.path.relpath(full_path, self.photo_folder)
                    relative_path = relative_path.replace(os.sep, "/")

                    existing_relative_paths.add(relative_path)

        # Get list of relative paths in metadata
        metadata_paths = set(self.metadata.keys())

        # Find files to remove (in metadata but not in folder)
        files_to_remove = metadata_paths - existing_relative_paths

        # Remove them
        for relative_path in files_to_remove:
            print(f"Removing missing photo from metadata: {relative_path}")
            del self.metadata[relative_path]

        if files_to_remove:
            print(f"Removed {len(files_to_remove)} missing photos from metadata")

    def add_missing_files_to_metadata(self):
        """Add any files that exist in folder but not in metadata (now recursive)"""
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

        added_count = 0

        # Walk through subfolders with same logic as _add_new_photos
        for root, dirs, files in os.walk(self.photo_folder):
            # Calculate current depth
            current_depth = root[len(self.photo_folder) :].count(os.sep)

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

                    # Convert to relative path for use as key
                    relative_path = os.path.relpath(full_path, self.photo_folder)
                    relative_path = relative_path.replace(os.sep, "/")

                    # Add to metadata if not already present
                    if relative_path not in self.metadata:
                        self.metadata[relative_path] = {
                            "keep": None,
                            "rating": None,
                            "tags": [],
                            "last_compared": None,
                            "created_date": datetime.now().isoformat(),
                            "skill": 0,
                            "comparisons": 0,
                        }
                        added_count += 1
                        print(f"Added missing file to metadata: {relative_path}")

        if added_count > 0:
            self.save_metadata()
            print(f"Added {added_count} missing files to metadata")

    def get_photo_data(self, filename):
        """Get metadata for a specific photo"""
        return self.metadata.get(filename, {})

    def get_quantile(self, filename):
        """Get current quantile rank for a photo"""
        if filename not in self.metadata:
            return 50
        skill = self.metadata[filename]["skill"]
        return 100 / (1 + math.exp(-skill))

    def get_comparisons(self, filename):
        """Get current comparisons for a photo"""
        if filename not in self.metadata:
            return 0
        return self.metadata[filename]["comparisons"]

    def load_metadata(self):
        """Load existing metadata or create new file"""
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, "r") as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {}

        # MIGRATION: Convert old-format metadata keys to new format FIRST
        migration_count = self.migrate_old_metadata()

        # Add any new photos found in folder (but don't overwrite migrated ones)
        self._add_new_photos()

        # Add any missing files (including videos)
        self.add_missing_files_to_metadata()

        # Remove any photos no longer in folder
        self._remove_missing_photos()

        if migration_count > 0:
            print(f"Metadata migration completed: {migration_count} entries updated")

        self.save_metadata()

    def migrate_old_metadata(self):
        """Migrate old metadata keys (filenames) to new relative path format"""
        # Get all actual files with their relative paths
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
        actual_files_map = {}  # basename -> [relative_paths]

        # Build map of basename to relative paths for actual files
        for root, dirs, files in os.walk(self.photo_folder):
            current_depth = root[len(self.photo_folder) :].count(os.sep)

            # Skip if we're too deep (allow 4 levels for year/month/type structure)
            if current_depth >= config.MAX_FOLDER_DEPTH:
                continue

            dirs[:] = [d for d in dirs if d.lower() not in skip_folders]

            for file in files:
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in extensions:
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, self.photo_folder)
                    relative_path = relative_path.replace(os.sep, "/")

                    basename = os.path.basename(file)
                    if basename not in actual_files_map:
                        actual_files_map[basename] = []
                    actual_files_map[basename].append(relative_path)

        # Find metadata entries that need migration
        migrated_count = 0
        entries_to_migrate = {}

        for metadata_key, metadata_value in list(self.metadata.items()):
            # Check if this looks like an old-format key (just a filename, no path separators)
            if "/" not in metadata_key:
                basename = metadata_key

                # Look for corresponding actual file(s)
                if basename in actual_files_map:
                    possible_paths = actual_files_map[basename]

                    # If there's only one possible match, migrate it
                    if len(possible_paths) == 1:
                        new_relative_path = possible_paths[0]

                        # Only migrate if the new path doesn't already exist in metadata
                        if new_relative_path not in self.metadata:
                            entries_to_migrate[metadata_key] = new_relative_path
                            print(
                                f"Will migrate: {metadata_key} -> {new_relative_path}"
                            )
                        else:
                            # If new path exists but has 0 comparisons, prefer the old data
                            existing_comparisons = self.metadata[new_relative_path].get(
                                "comparisons", 0
                            )
                            old_comparisons = metadata_value.get("comparisons", 0)

                            if old_comparisons > existing_comparisons:
                                print(
                                    f"Replacing new entry with old data: {metadata_key} -> {new_relative_path}"
                                )
                                entries_to_migrate[metadata_key] = new_relative_path
                            else:
                                print(
                                    f"Keeping existing entry, removing old: {metadata_key}"
                                )

                    elif len(possible_paths) > 1:
                        print(
                            f"Multiple matches for {basename}: {possible_paths}, skipping migration"
                        )
                else:
                    print(f"No actual file found for metadata key: {metadata_key}")

        # Perform the migration
        for old_key, new_key in entries_to_migrate.items():
            # Copy metadata to new key (overwrite if necessary)
            self.metadata[new_key] = self.metadata[old_key]
            # Remove old key
            del self.metadata[old_key]
            migrated_count += 1
            print(f"Migrated: {old_key} -> {new_key}")

        if migrated_count > 0:
            print(f"Migrated {migrated_count} metadata entries to new format")
            self.save_metadata()

        return migrated_count

    def save_metadata(self):
        """Save metadata to JSON file"""
        with open(self.metadata_file, "w") as f:
            json.dump(self.metadata, f, indent=2)

    def update_photo(self, filename, **kwargs):
        """Update metadata for a specific photo"""
        if filename in self.metadata:
            self.metadata[filename].update(kwargs)
            self.save_metadata()

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
