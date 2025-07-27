import glob
import os
from pathlib import Path

try:
    from moviepy.editor import VideoFileClip
except ImportError:
    print("moviepy not installed. Install with: pip install moviepy")
    exit(1)


def convert_avi_to_mp4_moviepy(input_folder, output_folder=None, delete_original=False):
    """
    Convert all AVI files in a folder to MP4 using MoviePy

    Args:
        input_folder: Path to folder containing AVI files
        output_folder: Path to output folder (None = same as input)
        delete_original: Whether to delete original AVI files after conversion
    """

    # Set output folder
    if output_folder is None:
        output_folder = input_folder
    else:
        os.makedirs(output_folder, exist_ok=True)

    # Find all AVI files
    avi_files = glob.glob(os.path.join(input_folder, "*.avi"))
    avi_files.extend(glob.glob(os.path.join(input_folder, "*.AVI")))

    if not avi_files:
        print(f"No AVI files found in {input_folder}")
        return True

    print(f"Found {len(avi_files)} AVI files to convert")

    success_count = 0
    failed_files = []

    for i, avi_file in enumerate(avi_files, 1):
        # Create output filename
        base_name = Path(avi_file).stem
        mp4_file = os.path.join(output_folder, f"{base_name}.mp4")

        print(f"[{i}/{len(avi_files)}] Converting: {os.path.basename(avi_file)}")

        # Skip if MP4 already exists
        if os.path.exists(mp4_file):
            print(f"  -> Skipping: {os.path.basename(mp4_file)} already exists")
            continue

        try:
            # Load video file
            video = VideoFileClip(avi_file)

            # Write to MP4 with good compression settings
            video.write_videofile(
                mp4_file,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile="temp-audio.m4a",
                remove_temp=True,
                verbose=False,  # Suppress moviepy output
                logger=None,  # Suppress progress bar
            )

            # Close the video file to free memory
            video.close()

            print(f"  -> Success: {os.path.basename(mp4_file)}")
            success_count += 1

            # Delete original if requested
            if delete_original:
                os.remove(avi_file)
                print(f"  -> Deleted original: {os.path.basename(avi_file)}")

        except Exception as e:
            print(f"  -> Error: {e}")
            failed_files.append(os.path.basename(avi_file))

            # Make sure to close video file even if error occurs
            try:
                if "video" in locals():
                    video.close()
            except:
                pass

    # Summary
    print(f"\nConversion complete!")
    print(f"Successfully converted: {success_count}/{len(avi_files)} files")

    if failed_files:
        print(f"Failed files: {', '.join(failed_files)}")

    return len(failed_files) == 0


def main():
    """Simple command line interface"""
    print("AVI to MP4 Converter (using MoviePy)")
    print("====================================")

    # Get input folder
    input_folder = input("Enter path to folder with AVI files: ").strip().strip('"')

    if not os.path.exists(input_folder):
        print("Error: Folder does not exist!")
        return

    # Ask about output folder
    use_same_folder = input("Convert in same folder? (y/n): ").lower().startswith("y")

    if use_same_folder:
        output_folder = None
    else:
        output_folder = input("Enter output folder path: ").strip().strip('"')

    # Ask about deleting originals
    delete_original = (
        input("Delete original AVI files after conversion? (y/n): ")
        .lower()
        .startswith("y")
    )

    if delete_original:
        confirm = input("Are you sure? This cannot be undone! (yes/no): ").lower()
        if confirm != "yes":
            delete_original = False
            print("Will keep original files.")

    # Run conversion
    print(f"\nStarting conversion...")
    success = convert_avi_to_mp4_moviepy(input_folder, output_folder, delete_original)

    if success:
        print("All conversions completed successfully!")
    else:
        print("Some conversions failed. Check the output above.")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    # Quick conversion for your test folder (uncomment to use):
    # convert_avi_to_mp4_moviepy(r"C:\Users\Admin\Desktop\Photos and Videos\test", delete_original=True)

    # Or use the interactive version:
    main()
