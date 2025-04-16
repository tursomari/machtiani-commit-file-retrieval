import os
import subprocess
import logging
import magic
from enum import Enum
from typing import List, Dict
from lib.utils.enums import FilePathEntry

logger = logging.getLogger(__name__)

# Define the base path
BASE_PATH = "/data/users/repositories/"

class DataDir(Enum):
    STORE = "store"
    REPO = "repo"
    COMMITS_EMBEDDINGS = "commits/embeddings"
    COMMITS_LOGS = "commits/logs"
    CONTENT_EMBEDDINGS = "contents/embeddings"
    CONTENT_LOGS = "contents/logs"
    CONTENT = "contents"  # New CONTENT directory

    def get_path(self, project_name: str, dir_type: 'DataDir' = None) -> str:
        """
        Gets the full path for a specific project based on the current directory type.

        If the directory type is STORE, it returns only the base path joined with the project name.
        For other directory types, it appends the specific directory value to the project path.

        :param project_name: The name of the project.
        :return: The full path to the requested directory.
        """
        if self == DataDir.STORE:
            return os.path.join(BASE_PATH, project_name)
        return os.path.join(BASE_PATH, project_name, self.value)

    @staticmethod
    def create_all(project_name: str):
        """
        Creates all necessary directories for a project based on the project name.

        :param project_name: The name of the project.
        :return: None
        """
        for dir_type in DataDir:
            path = dir_type.get_path(project_name)
            os.makedirs(path, exist_ok=True)
            logger.debug(f"Created directory: {path}")

        logger.debug(f"All directories created for project '{project_name}'.")

    @staticmethod
    def list_projects() -> list:
        """
        Lists the names of all projects in the BASE_PATH directory.

        :return: A list of project names.
        """
        try:
            projects = [
                name for name in os.listdir(BASE_PATH)
                if os.path.isdir(os.path.join(BASE_PATH, name))
            ]
            logger.debug(f"Found projects: {projects}")
            return projects
        except FileNotFoundError:
            logger.error(f"Base path '{BASE_PATH}' not found.")
            return []

def is_not_common_binary_type(filepath: str) -> bool:
    """Check if the file at the given path is a text file or code file."""
    mime = magic.Magic(mime=True)
    mime_type = mime.from_file(filepath)

    # List of common binary MIME types to exclude
    binary_mime_types = [
        'application/octet-stream',  # Generic binary
        'application/x-archive',     # Archive formats
        'application/x-compress',    # Compressed files
        'application/x-zip',         # Zip files
        'application/x-gzip',        # Gzip files
        'application/x-tar',         # Tar files
        'application/x-7z-compressed', # 7z files
        'application/x-rar',         # RAR files
        'application/pdf',           # PDF files
        'application/vnd.ms-office',  # Office files
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document', # DOCX
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', # XLSX
        'image/',                     # Image files
        'video/',                     # Video files
        'audio/',                     # Audio files
        'application/x-shockwave-flash', # SWF files
        'application/java-archive',   # JAR files
        'application/x-dosexec',      # Windows executables
        'application/x-msdownload',    # Windows executables
        'application/x-mach-bundle',   # Mach bundles (macOS)
        'application/x-bzip2',         # BZ2 files
        'application/x-cpio',          # CPIO files
        'application/x-lz4',           # LZ4 files
        'application/x-lzma',          # LZMA files
        'application/x-sqlite3',       # SQLite databases
        'application/x-tar-compressed', # Compressed tar files
        'application/x-xz',            # XZ files
        'application/x-iso9660-image', # ISO disk images
        'application/x-msi',           # Microsoft Installer packages
        'application/x-deb',           # Debian package files
        'application/x-rpm',           # RPM package files
        'application/x-apk',           # Android APK files
        'application/x-executable',    # Generic executable files
        'application/vnd.apple.installer+xml', # macOS Installer files
        'application/x-elf',           # Executable and Linkable Format files
        'application/x-sharedlib',     # Shared library files
        'application/x-object',        # Object files
        'application/x-firmware',      # Firmware binary files
        'application/x-binary',        # Generic binary files
        'application/x-pem-file',      # PEM certificate files
        'application/pkcs12',          # PKCS#12 certificate files
        'application/x-font-ttf',      # TTF font files
        'application/x-font-woff',     # WOFF font files
        'application/x-font-woff2',    # WOFF2 font files
        'application/vnd.android.package-archive', # Android APK files
        'application/x-ms-shortcut',   # Windows shortcut files (.lnk)
        'application/x-disk-image',    # Generic disk image files
        'application/x-ms-publisher',  # Microsoft Publisher files
        'application/x-chrome-extension', # Chrome extensions
        'application/x-flac',          # FLAC audio files
        'application/x-hdf',           # HDF data files
        'application/x-netcdf',        # NetCDF data files
        'application/x-rdata',         # R data files
        'application/x-matlab-data',   # MATLAB data files
        'application/x-protobuf',      # Protocol Buffers binary format
        'application/x-java-serialized-object', # Serialized Java objects
        'application/vnd.oasis.opendocument.text', # ODT files
        'application/vnd.oasis.opendocument.spreadsheet', # ODS files
        'application/vnd.oasis.opendocument.presentation', # ODP files
        'application/vnd.mozilla.xul+xml', # XUL files
        'application/x-apple-diskimage', # Apple Disk Image files
        'application/x-ms-wim',        # Windows Imaging Format files
        'application/x-lzh-compressed', # LZH compressed files
        'application/x-tar-bz2',       # Tar BZ2 files
        'application/x-tar-lzma',      # Tar LZMA files
        'application/x-tar-xz',        # Tar XZ files
        'application/x-ace-compressed', # ACE compressed files
        'application/x-alz-compressed', # ALZ compressed files
        'application/x-zoo',           # ZOO compressed files
        'application/x-cab',           # Cabinet files
        'application/x-dar',           # DAR archive files
        'application/x-stuffit',       # StuffIt compressed files
        'application/x-gtar',          # GNU Tar files
        'application/x-appleworks',    # AppleWorks files
        'application/x-abiword',       # AbiWord documents
        'application/x-mobipocket-ebook', # Mobipocket eBook files
        'application/x-ms-reader',     # Microsoft Reader eBook files
        'application/x-tgif',          # TGIF vector graphics files
        'application/x-ustar',         # USTAR Tar files
        'application/x-windows-themepack', # Windows Theme Pack files
        'application/x-xar',           # XAR archive files
        'application/x-xpinstall',     # XPInstall installation files
        'application/x-zmachine',      # Z-machine game files
        'application/x-tex',           # TeX files
        'application/x-bittorrent',    # BitTorrent files
        'application/x-blender',       # Blender files
        'application/x-bzip',          # BZip files
        'application/x-cbr',           # Comic Book RAR files
        'application/x-cbz',           # Comic Book ZIP files
        'application/x-cdf',           # CDF files
        'application/x-csh',           # C-Shell scripts
        'application/x-dvi',           # DVI files
        'application/x-font-bdf',      # BDF font files
        'application/x-font-ghostscript', # Ghostscript font files
        'application/x-font-linux-psf', # Linux PSF font files
        'application/x-font-pcf',      # PCF font files
        'application/x-font-snf',      # SNF font files
        'application/x-font-type1',    # Type 1 font files
        'application/x-font-otf',      # OpenType font files
        'application/x-font-woff',     # Web Open Font Format files
        'application/x-font-woff2',    # Web Open Font Format 2 files
        'application/x-gnumeric',      # Gnumeric spreadsheet files
        'application/x-gramps'
    ]
    # Check if the file is binary
    if any(mime_type.startswith(binary_type) for binary_type in binary_mime_types):
        return False

    # If it’s not in the binary list, we consider it a text or code file
    return True

def retrieve_file_contents(project_name: str, file_paths: List[FilePathEntry], ignore_files: List[str]) -> Dict[str, str]:
    file_contents = {}
    repo_path = DataDir.REPO.get_path(project_name)


    logger.info(f"Retrieving contents for project: {project_name}")
    logger.debug(f"Repo path resolved as: {repo_path}")
    logger.debug(f"Ignore files: {ignore_files}")
    logger.debug(f"File paths: {[entry.path for entry in file_paths]}")

    for entry in file_paths:
        full_path = os.path.join(repo_path, "git", entry.path)
        logger.debug(f"Checking file: {full_path}")

        if entry.path in ignore_files:
            logger.warning(f"Skipping ignored file: {entry.path}")
            continue

        if not os.path.isfile(full_path):
            logger.error(f"File not found: {full_path}")
            continue

        try:
            if not is_not_common_binary_type(full_path):
                logger.warning(f"Skipping binary file: {entry.path}")
                continue
        except Exception as e:
            logger.error(f"Error detecting mime type for {entry.path}: {e}")
            continue

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                file_contents[entry.path] = content

                logger.debug(f"Successfully read file: {entry.path}")
        except UnicodeDecodeError as e:
            logger.warning(f"Unicode decode error in {entry.path}: {e}")
        except IOError as e:
            logger.error(f"I/O error reading {entry.path}: {e}")

    logger.info(f"Total files retrieved: {len(file_contents)}")
    return file_contents

def count_tokens(text: str) -> int:
    # Simple estimation: 1 token is approximately 4 characters (including spaces)
    return len(text) // 4 + 1

def add_git_safe_directory(path: str):
    """
    Ensures the given path is added to git's global safe.directory config.
    """
    try:
        # Check if it's already set
        result = subprocess.run(
            ["git", "config", "--global", "--get-all", "safe.directory"],
            capture_output=True, text=True, check=False,
            cwd=path
        )
        already_set = False
        if result.returncode == 0:
            dirs = result.stdout.strip().split('\n')
            already_set = path in dirs
        if not already_set:
            subprocess.run(
                ["git", "config", "--global", "--add", "safe.directory", path],
                cwd=path,
                check=True
            )
            logging.info(f"Added {path} to git safe.directory")
        else:
            logging.info(f"{path} already present in git safe.directory")
    except Exception as e:
        logging.error(f"Failed to add {path} to git safe.directory: {e}")

def add_all_existing_repos_as_safe(base_path: str):
    """
    Traverse all first-level dirs under base_path, and add <base>/<dir>/repo/git as safe.directory if .git exists.
    """
    if not os.path.isdir(base_path):
        logging.warning(f"Base path does not exist: {base_path}")
        return

    for project in os.listdir(base_path):
        project_path = os.path.join(base_path, project)
        repo_git_path = os.path.join(project_path, "repo", "git")
        git_dir = os.path.join(repo_git_path, ".git")
        if os.path.isdir(repo_git_path) and os.path.isdir(git_dir):
            add_git_safe_directory(repo_git_path)
