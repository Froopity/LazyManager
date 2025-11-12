from pathlib import Path

from .config import load_access_history, load_metadata_cache
from .models import Repository


def find_git_repos(base_path):
  repos = []
  base = Path(base_path)

  if not base.exists():
    return repos

  access_history = load_access_history()
  metadata_cache = load_metadata_cache()

  for item in base.iterdir():
    if item.is_dir():
      git_dir = item / '.git'
      if git_dir.exists():
        cached = metadata_cache.get(str(item), {})
        repo = Repository(
          path=item,
          name=item.name,
          last_accessed=access_history.get(str(item)),
          last_commit=cached.get('last_commit'),
          branch=cached.get('branch'),
          status=cached.get('status'),
          ahead=cached.get('ahead'),
          behind=cached.get('behind')
        )
        repos.append(repo)

  return repos
