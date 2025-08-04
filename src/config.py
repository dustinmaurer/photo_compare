"""
Configuration file for Photo Manager
Modify these values to customize behavior without touching main code
"""

# File traversal settings
MAX_FOLDER_DEPTH = 4  # Maximum depth for recursive folder traversal
SKIP_FOLDERS = {"delete", "keep"}  # Folders to skip during traversal

# Supported file extensions
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff"]
VIDEO_EXTENSIONS = [".mp4", ".mov", ".mkv", ".wmv", ".flv"]
ALL_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS

# Performance settings
QUANTILE_THRESHOLD_FOR_COMPARISON = 5  # Minimum quantile to include in comparisons
QUANTILE_THRESHOLD_FOR_MASKING = 10  # Minimum quantile to show in image list

# UI settings
THUMBNAIL_SIZE = (600, 400)  # Size for comparison view thumbnails
SUMMARY_THUMBNAIL_SIZE = (280, 280)  # Size for summary view thumbnails
# Window settings
WINDOW_WIDTH = 1300
WINDOW_HEIGHT = 900
ALLOW_WINDOW_RESIZE = True
REMEMBER_WINDOW_SIZE = True

# Caching settings (for performance optimization)
MAX_IMAGE_CACHE = 10  # Maximum number of images to keep in memory cache
GARBAGE_COLLECTION_INTERVAL = 10  # Force GC every N comparisons

# Skill calculation settings
DEFAULT_K_VALUE = 2  # K value for Elo-style skill updates

# Summary page settings
DEFAULT_SHOW_WORST = True  # True = show worst first, False = show best first
SUMMARY_PHOTOS_COUNT = 20  # Number of photos to show in summary
SUMMARY_GRID_COLUMNS = 4  # Number of columns in summary grid

# File naming settings
QUANTILE_PREFIX_FORMAT = "Q{:03d}_"  # Format for quantile prefixes (Q567_)

# Video player settings (Windows)
VLC_PATHS = [
    r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
]
WMP_PATH = r"C:\Program Files\Windows Media Player\wmplayer.exe"
VLC_ARGS = ["--play-and-exit"]  # Arguments for VLC autoplay

# Test mode settings
TEST_FOLDER_PATH = r"C:\Users\Admin\Desktop\Photos and Videos\test"

# Debug settings
DEBUG_MODE = False  # Set to True for extra debug output
VERBOSE_FOLDER_EXPLORATION = True  # Show folder traversal details
