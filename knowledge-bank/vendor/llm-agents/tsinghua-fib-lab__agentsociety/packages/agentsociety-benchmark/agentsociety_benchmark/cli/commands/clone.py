"""
Clone command for downloading benchmark datasets from various sources
"""

import os
import shutil
import subprocess
import sys
from typing import Optional
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import click
from git import Repo

try:
    from tqdm import tqdm

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False


def check_lfc_support() -> bool:
    """
    Check if the current environment supports Large File Storage (LFS)

    This function checks if Git LFS (Large File Storage) is properly configured
    and available in the current environment. LFS is required for handling
    large files in Git repositories.

    Returns:
        bool: True if LFS is supported, False otherwise
    """
    try:
        # Check if git-lfs is installed
        result = subprocess.run(
            ["git", "lfs", "version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return False

        # Check if git-lfs is initialized in the current repository
        result = subprocess.run(
            ["git", "lfs", "install"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return False

        return True

    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False


def show_lfc_installation_guide():
    """
    Display installation guide for Large File Storage (LFS)

    This function provides detailed instructions for installing and configuring
    Git LFS (Large File Storage) on different operating systems.
    """
    click.echo("\n" + "=" * 60)
    click.echo(
        click.style(
            "Large File Storage (LFS) Installation Guide", fg="yellow", bold=True
        )
    )
    click.echo("=" * 60)

    click.echo(
        "\nGit LFS (Large File Storage) is required to handle large files in Git repositories."
    )
    click.echo("Please install Git LFS using one of the following methods:\n")

    # Linux installation
    click.echo(click.style("Linux (Ubuntu/Debian):", fg="green", bold=True))
    click.echo(
        "  curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | sudo bash"
    )
    click.echo("  sudo apt-get install git-lfs")
    click.echo("  git lfs install")

    click.echo(click.style("\nLinux (CentOS/RHEL/Fedora):", fg="green", bold=True))
    click.echo(
        "  curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.rpm.sh | sudo bash"
    )
    click.echo("  sudo yum install git-lfs")
    click.echo("  git lfs install")

    # macOS installation
    click.echo(click.style("\nmacOS:", fg="green", bold=True))
    click.echo("  # Using Homebrew:")
    click.echo("  brew install git-lfs")
    click.echo("  git lfs install")
    click.echo("  # Using MacPorts:")
    click.echo("  sudo port install git-lfs")
    click.echo("  git lfs install")

    # Windows installation
    click.echo(click.style("\nWindows:", fg="green", bold=True))
    click.echo("  # Download from: https://git-lfs.github.com/")
    click.echo("  # Or using Chocolatey:")
    click.echo("  choco install git-lfs")
    click.echo("  git lfs install")
    click.echo("  # Or using Scoop:")
    click.echo("  scoop install git-lfs")
    click.echo("  git lfs install")

    # Manual installation
    click.echo(click.style("\nManual Installation:", fg="green", bold=True))
    click.echo("  1. Download from: https://git-lfs.github.com/")
    click.echo("  2. Extract and add to PATH")
    click.echo("  3. Run: git lfs install")

    click.echo(click.style("\nAfter Installation:", fg="yellow", bold=True))
    click.echo("  1. Restart your terminal/command prompt")
    click.echo("  2. Run: git lfs install")
    click.echo("  3. Try the clone command again")

    click.echo("\n" + "=" * 60)
    click.echo("For more information, visit: https://git-lfs.github.com/")
    click.echo("=" * 60 + "\n")


class CloneProgress:
    """
    Progress callback for Git clone operations

    This class provides progress tracking for Git clone operations using tqdm.
    """

    def __init__(self, repo_url: str):
        """
        Initialize the progress tracker

        Args:
            repo_url (str): The repository URL being cloned
        """
        self.repo_url = repo_url
        self.pbar = None
        self.last_count = 0

    def __call__(self, op_code, cur_count, max_count=None, message=""):
        """
        Progress callback function called by GitPython

        Args:
            op_code (int): Operation code from GitPython
            cur_count (int): Current count
            max_count (int): Maximum count (if available)
            message (str): Progress message
        """
        if not TQDM_AVAILABLE:
            return

        # Initialize progress bar on first call
        if self.pbar is None and max_count is not None:
            self.pbar = tqdm(
                total=max_count,
                desc=f"Cloning {self.repo_url.split('/')[-1]}",
                unit="objects",
                leave=False,
            )

        # Update progress bar
        if self.pbar is not None:
            if cur_count > self.last_count:
                self.pbar.update(cur_count - self.last_count)
                self.last_count = cur_count

            # Update description with message if provided
            if message:
                self.pbar.set_description(
                    f"Cloning {self.repo_url.split('/')[-1]} - {message}"
                )

    def close(self):
        """
        Close the progress bar
        """
        if self.pbar is not None:
            self.pbar.close()
            self.pbar = None


def detect_package_manager():
    """
    Detect the current package manager being used in the environment

    This function detects which package manager is currently active in the environment
    by checking various indicators like environment variables, executable availability,
    and current Python environment characteristics.

    Returns:
        str: Package manager name ('pip', 'conda', 'uv', 'poetry', etc.)
    """
    # Check for conda environment - more comprehensive detection
    if (
        "conda" in sys.prefix
        or "CONDA_PREFIX" in os.environ
        or "CONDA_DEFAULT_ENV" in os.environ
        or "conda" in os.environ.get("VIRTUAL_ENV", "")
    ):
        return "conda"

    # Check for poetry environment
    if "POETRY_VIRTUALENVS_IN_PROJECT" in os.environ or "POETRY_ACTIVE" in os.environ:
        return "poetry"

    # Check for pipenv environment
    if "PIPENV_ACTIVE" in os.environ:
        return "pipenv"

    # Check for virtualenv/venv environment
    if "VIRTUAL_ENV" in os.environ:
        # Check if uv is available and being used in this virtual environment
        try:
            result = subprocess.run(
                ["uv", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # Additional check: see if uv.toml exists in current directory or parent directories
                current_dir = Path.cwd()
                for parent in [current_dir] + list(current_dir.parents):
                    if (parent / "uv.toml").exists() or (
                        parent / "pyproject.toml"
                    ).exists():
                        # Check if pyproject.toml has uv as build system
                        try:
                            with open(parent / "pyproject.toml", "r") as f:
                                content = f.read()
                                if "uv" in content and "build-system" in content:
                                    return "uv"
                        except (FileNotFoundError, IOError):
                            pass
                # If uv is available but no project config, still prefer it over pip
                return "uv"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Check if uv is available globally (even without project config)
    try:
        result = subprocess.run(
            ["uv", "--version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return "uv"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check if pip is available and working
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return "pip"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Default to pip as fallback
    return "pip"


def install_dependencies_with_manager(
    package_manager: str,
    requirements_file: Optional[Path] = None,
    dependencies: Optional[list] = None,
):
    """
    Install dependencies using the specified package manager

    This function installs Python packages using the detected package manager.
    It supports multiple package managers including pip, conda, uv, poetry, and pipenv.

    Args:
        package_manager (str): Package manager to use ('pip', 'conda', 'uv', 'poetry', 'pipenv')
        requirements_file (Path): Path to requirements.txt file
        dependencies (list): List of package names to install

    Returns:
        bool: True if installation was successful, False otherwise
    """
    try:
        click.echo(f"Installing dependencies using {package_manager}...")

        if package_manager == "conda":
            if requirements_file and requirements_file.exists():
                # For conda, we need to handle requirements.txt differently
                # Read the file and install packages one by one
                with open(requirements_file, "r") as f:
                    deps = [
                        line.strip()
                        for line in f
                        if line.strip() and not line.startswith("#")
                    ]
                for dep in deps:
                    # Extract package name (remove version specifiers)
                    package_name = (
                        dep.split("==")[0]
                        .split(">=")[0]
                        .split("<=")[0]
                        .split("~=")[0]
                        .split("!=")[0]
                    )
                    click.echo(f"Installing {package_name} via conda...")
                    subprocess.run(
                        ["conda", "install", "-y", package_name.strip()],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    click.echo(f"✓ Installed {package_name} via conda")
            elif dependencies:
                for dep in dependencies:
                    click.echo(f"Installing {dep} via conda...")
                    subprocess.run(
                        ["conda", "install", "-y", dep],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    click.echo(f"✓ Installed {dep} via conda")

        elif package_manager == "uv":
            if requirements_file and requirements_file.exists():
                click.echo("Installing from requirements.txt via uv...")
                subprocess.run(
                    ["uv", "pip", "install", "-r", str(requirements_file)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                click.echo("✓ Dependencies installed successfully via uv")
            elif dependencies:
                for dep in dependencies:
                    click.echo(f"Installing {dep} via uv...")
                    subprocess.run(
                        ["uv", "pip", "install", dep],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    click.echo(f"✓ Installed {dep} via uv")

        elif package_manager == "poetry":
            if requirements_file and requirements_file.exists():
                # Poetry doesn't directly support requirements.txt, so we read and add packages
                with open(requirements_file, "r") as f:
                    deps = [
                        line.strip()
                        for line in f
                        if line.strip() and not line.startswith("#")
                    ]
                for dep in deps:
                    click.echo(f"Adding {dep} via poetry...")
                    subprocess.run(
                        ["poetry", "add", dep],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    click.echo(f"✓ Added {dep} via poetry")
            elif dependencies:
                for dep in dependencies:
                    click.echo(f"Adding {dep} via poetry...")
                    subprocess.run(
                        ["poetry", "add", dep],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    click.echo(f"✓ Added {dep} via poetry")

        elif package_manager == "pipenv":
            if requirements_file and requirements_file.exists():
                click.echo("Installing from requirements.txt via pipenv...")
                subprocess.run(
                    ["pipenv", "install", "-r", str(requirements_file)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                click.echo("✓ Dependencies installed successfully via pipenv")
            elif dependencies:
                for dep in dependencies:
                    click.echo(f"Installing {dep} via pipenv...")
                    subprocess.run(
                        ["pipenv", "install", dep],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    click.echo(f"✓ Installed {dep} via pipenv")

        else:  # pip (default)
            if requirements_file and requirements_file.exists():
                click.echo("Installing from requirements.txt via pip...")
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "-r",
                        str(requirements_file),
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                click.echo("✓ Dependencies installed successfully via pip")
            elif dependencies:
                for dep in dependencies:
                    click.echo(f"Installing {dep} via pip...")
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", dep],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    click.echo(f"✓ Installed {dep} via pip")

        click.echo("✓ All dependencies installed successfully!")
        return True

    except subprocess.CalledProcessError as e:
        click.echo(f"✗ Failed to install dependencies via {package_manager}")
        click.echo(f"Error: {e}")
        if e.stdout:
            click.echo(f"stdout: {e.stdout}")
        if e.stderr:
            click.echo(f"stderr: {e.stderr}")
        return False
    except Exception as e:
        click.echo(f"✗ Error installing dependencies via {package_manager}: {e}")
        return False


def resolve_dataset_url(dataset_repo_url: str) -> str:
    """
    Resolve dataset repository URL with environment variable substitution

    Args:
        dataset_repo_url (str): Original dataset repository URL

    Returns:
        str: Resolved URL with environment variable substitution
    """
    if not dataset_repo_url:
        return dataset_repo_url

    hf_endpoint = os.environ.get("HF_ENDPOINT")
    if not hf_endpoint:
        return dataset_repo_url

    parsed = urlparse(dataset_repo_url)
    if parsed.hostname != "huggingface.co":
        return dataset_repo_url

    endpoint = hf_endpoint if "://" in hf_endpoint else f"https://{hf_endpoint}"
    endpoint_parsed = urlparse(endpoint)
    if not endpoint_parsed.netloc:
        return dataset_repo_url

    resolved_url = urlunparse(
        parsed._replace(
            scheme=endpoint_parsed.scheme or "https",
            netloc=endpoint_parsed.netloc,
        )
    )
    click.echo(f"Using custom HF endpoint: {hf_endpoint}")
    click.echo(f"Resolved URL: {resolved_url}")
    return resolved_url


def get_available_tasks() -> dict:
    """
    Get available tasks from the benchmarks module

    Returns:
        dict: Dictionary mapping task names to their metadata
    """
    try:
        from agentsociety_benchmark.benchmarks import get_all_task_configs  # type: ignore

        task_configs = get_all_task_configs()
        available_tasks = {}

        for task_name, task_config in task_configs.items():
            # Get original dataset URL
            original_dataset_url = task_config.get("dataset_repo_url", "")

            # Resolve URL with environment variable substitution
            resolved_dataset_url = resolve_dataset_url(original_dataset_url)

            # Convert to standard format
            task_info = {
                "name": task_config.get("name", task_name),
                "description": task_config.get(
                    "description", f"Benchmark task: {task_name}"
                ),
                "local_path": str(
                    Path(__file__).parent.parent.parent / "benchmarks" / task_name
                ),
                "dependencies": task_config.get("dependencies", []),
                "source": "local",
                "dataset_repo_url": resolved_dataset_url,
                "dataset_branch": task_config.get("dataset_branch", "main"),
                "version": task_config.get("version", "1.0.0"),
                "author": task_config.get("author", "Unknown"),
                "tags": task_config.get("tags", []),
                "prepare_config_func": task_config.get("prepare_config_func"),
                "evaluation_func": task_config.get("evaluation_func"),
                "template_agent": task_config.get("template_agent"),
            }

            available_tasks[task_name] = task_info

        return available_tasks

    except ImportError as e:
        click.echo(f"Warning: Could not import benchmarks module: {e}")
        return {}


def download_dataset_from_repo(
    repo_url: str, output_dir: Path, branch: str = "main"
) -> bool:
    """
    Download dataset from Git repository (can be HuggingFace or GitHub) to local directory

    Args:
        repo_url (str): Git repository URL
        output_dir (Path): Local directory to save the dataset
        branch (str): Branch to clone (default: main)

    Returns:
        bool: True if download was successful, False otherwise
    """
    try:
        click.echo(f"Downloading dataset from repository: {repo_url}")
        click.echo(f"Branch: {branch}")

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize progress tracker
        progress = CloneProgress(repo_url)

        try:
            # Clone the repository with progress callback
            Repo.clone_from(
                repo_url,
                output_dir,
                branch=branch,
                depth=1,  # Shallow clone for faster download
                progress=progress,
            )
        finally:
            # Always close the progress bar
            progress.close()

        click.echo(f"Successfully downloaded dataset to {output_dir}")
        return True

    except Exception as e:
        click.echo(f"Error downloading dataset from repository: {e}")
        return False


@click.command()
@click.argument("task", type=str)
@click.option(
    "--force",
    is_flag=True,
    help="Force re-download even if dataset already exists",
)
@click.option(
    "--only-install-deps",
    is_flag=True,
    help="Only install dependencies without cloning the dataset",
)
@click.option(
    "--no-interaction",
    is_flag=True,
    help="Do not interact with the user",
)
@click.pass_context
def clone(
    ctx: click.Context,
    task: str,
    force: bool,
    only_install_deps: bool,
    no_interaction: bool = False,
):
    """
    Clone a benchmark task's datasets from Git repositories

    TASK: Name of the task to clone (e.g., BehaviorModeling, HurricaneMobility)
    """
    # Check LFS support before proceeding
    if not only_install_deps:  # Only check LFS when actually cloning datasets
        click.echo("Checking Large File Storage (LFS) support...")
        if not check_lfc_support():
            click.echo(
                click.style(
                    "Error: Large File Storage (LFS) is not supported in your environment.",
                    fg="red",
                    bold=True,
                )
            )
            click.echo(
                "LFS is required for downloading large dataset files from Git repositories."
            )
            show_lfc_installation_guide()
            return

    home_dir = ctx.obj["home_dir"]
    datasets_dir = home_dir / "datasets"
    datasets_dir.mkdir(exist_ok=True)

    # Get available tasks
    available_tasks = get_available_tasks()

    if task not in available_tasks:
        click.echo(f"Error: Task '{task}' not found.")
        click.echo("Available tasks:")
        for task_name, task_info in available_tasks.items():
            click.echo(f"  - {task_name}: {task_info['description']}")
        return

    task_info = available_tasks[task]
    task_dataset_dir = datasets_dir / task

    # Skip dataset cloning if only installing dependencies
    if not only_install_deps:
        # Check if dataset already exists
        if task_dataset_dir.exists() and not force:
            click.echo(
                f"Dataset for task '{task}' already exists at {task_dataset_dir}"
            )
            click.echo("Use --force to re-download")
            return

        # Remove existing directory if force is used
        if task_dataset_dir.exists() and force:
            shutil.rmtree(task_dataset_dir)

        # Check if task has dataset repository configured
        dataset_repo_url = task_info.get("dataset_repo_url")
        if not dataset_repo_url:
            click.echo(
                f"Error: Task '{task}' does not have a dataset repository configured."
            )
            click.echo("Please add 'dataset_repo_url' to the task's config.yaml file.")
            return

        # Download dataset from repository
        success = download_dataset_from_repo(
            dataset_repo_url, task_dataset_dir, task_info.get("dataset_branch", "main")
        )

        if not success:
            click.echo(f"Failed to download dataset for task '{task}'")
            return

    # Handle dependency installation
    if only_install_deps:
        # Only install dependencies without cloning dataset
        click.echo(
            f"Installing dependencies for task '{task}' without cloning dataset..."
        )
    else:
        # Normal clone operation - always install dependencies after cloning
        click.echo(f"Installing dependencies for task '{task}'...")

    # Always install dependencies (either standalone or after cloning)
    # Interactive package manager selection
    available_managers = ["pip", "conda", "uv", "poetry", "pipenv"]
    detected_manager = detect_package_manager()

    click.echo(f"Detected package manager: {detected_manager}")
    click.echo("Available package managers:")
    for i, manager in enumerate(available_managers, 1):
        marker = " (detected)" if manager == detected_manager else ""
        click.echo(f"  {i}. {manager}{marker}")

    if not no_interaction:
        while True:
            try:
                choice = click.prompt(
                    "Please select a package manager (1-5)",
                    type=click.IntRange(1, 5),
                    default=available_managers.index(detected_manager) + 1,
                )
                package_manager = available_managers[choice - 1]
                break
            except click.Abort:
                click.echo("Installation cancelled by user")
                return
            except Exception as e:
                click.echo(f"Invalid input: {e}. Please try again.")
    else:
        package_manager = detected_manager

    click.echo(f"Selected package manager: {package_manager}")

    # Check for requirements.txt in the task directory
    task_dir = Path(task_info["local_path"])
    requirements_file = task_dir / "requirements.txt"

    # Show what will be installed
    if requirements_file.exists():
        click.echo(f"Found requirements.txt: {requirements_file}")
        try:
            with open(requirements_file, "r") as f:
                deps = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.startswith("#")
                ]
            click.echo(f"Dependencies to install: {', '.join(deps)}")
        except Exception as e:
            click.echo(f"Warning: Could not read requirements.txt: {e}")
    elif "dependencies" in task_info and task_info["dependencies"]:
        click.echo(f"Dependencies to install: {', '.join(task_info['dependencies'])}")
    else:
        click.echo("No dependencies specified for this task")
        return

    # Ask for confirmation
    if not no_interaction:
        if not click.confirm("Do you want to install these dependencies?"):
            click.echo("Dependency installation skipped")
            return

    # Install dependencies
    if requirements_file.exists():
        click.echo("Installing dependencies from requirements.txt...")
        if not install_dependencies_with_manager(
            package_manager, requirements_file=requirements_file
        ):
            click.echo(f"Failed to install dependencies for '{task}'")
    else:
        # Install dependencies from task info
        if "dependencies" in task_info and task_info["dependencies"]:
            click.echo(
                f"Installing dependencies: {', '.join(task_info['dependencies'])}"
            )
            if not install_dependencies_with_manager(
                package_manager, dependencies=task_info["dependencies"]
            ):
                click.echo(f"Failed to install dependencies for '{task}'")

    # Show next steps
    if only_install_deps:
        click.echo(f"\nDependencies for task '{task}' have been installed!")
    else:
        click.echo(f"\nDataset for task '{task}' is ready!")
        click.echo(f"Dataset location: {task_dataset_dir}")
    click.echo("To run the task, use: asbench run <task> --datasets <path>")


@click.command()
@click.pass_context
def list_tasks(ctx: click.Context):
    """
    List available benchmark tasks
    """
    available_tasks = get_available_tasks()

    click.echo("Available benchmark tasks:")
    click.echo()

    for task_name, task_info in available_tasks.items():
        click.echo(f"  {click.style(task_name, fg='green', bold=True)}")
        click.echo(f"    Description: {task_info['description']}")
        click.echo(f"    Version: {task_info.get('version', '1.0.0')}")
        click.echo(f"    Author: {task_info.get('author', 'Unknown')}")
        click.echo(f"    Source: Local ({task_info['local_path']})")

        # Show dataset source
        if task_info.get("dataset_repo_url"):
            click.echo(f"    Dataset: Git Repository ({task_info['dataset_repo_url']})")
            if (
                task_info.get("dataset_branch")
                and task_info["dataset_branch"] != "main"
            ):
                click.echo(f"    Branch: {task_info['dataset_branch']}")
        else:
            click.echo(f"    Dataset: {click.style('Not configured', fg='red')}")

        # Show tags
        if task_info.get("tags"):
            click.echo(f"    Tags: {', '.join(task_info['tags'])}")

        # Show dependencies
        if task_info.get("dependencies"):
            deps_count = len(task_info["dependencies"])
            click.echo(f"    Dependencies: {deps_count} package(s)")
            if deps_count <= 5:  # Show all if <= 5
                click.echo(f"      {', '.join(task_info['dependencies'])}")
            else:  # Show first 3 and count
                click.echo(
                    f"      {', '.join(task_info['dependencies'][:3])}... (+{deps_count-3} more)"
                )

        # Show available functions
        functions = []
        if task_info.get("prepare_config_func"):
            functions.append("prepare_config")
        if task_info.get("evaluation_func"):
            functions.append("evaluation")
        if task_info.get("template_agent"):
            functions.append("template_agent")

        if functions:
            click.echo(f"    Functions: {', '.join(functions)}")

        click.echo()


@click.command()
@click.option(
    "--force",
    is_flag=True,
    help="Force update even if local changes exist",
)
@click.option(
    "--branch",
    default="main",
    help="Branch to pull from (default: main)",
)
@click.pass_context
def update_benchmarks(ctx: click.Context, force: bool, branch: str):
    """
    Update local benchmarks from remote repository

    This command pulls the latest benchmarks from the remote repository
    to update the local benchmarks directory.
    """
    # Get the benchmarks directory path
    current_file = Path(__file__)
    benchmarks_dir = current_file.parent.parent.parent / "benchmarks"
    project_root = benchmarks_dir.parent

    click.echo("Updating benchmarks from remote repository...")

    try:
        # Initialize git repository
        repo = Repo(project_root)

        # Check if there are local changes
        if repo.is_dirty() and not force:
            click.echo("Warning: Local changes detected in the repository.")
            click.echo("Use --force to update anyway (local changes will be lost)")
            return

        # Fetch latest changes
        click.echo("Fetching latest changes...")
        origin = repo.remotes.origin
        origin.fetch()

        # Checkout the specified branch
        if branch != repo.active_branch.name:
            click.echo(f"Switching to branch '{branch}'...")
            repo.git.checkout(branch)

        # Pull latest changes
        click.echo("Pulling latest changes...")
        origin.pull()

        click.echo("Benchmarks updated successfully!")

    except Exception as e:
        click.echo(f"Error updating benchmarks: {e}")
        return
