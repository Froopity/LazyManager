import logging
from pathlib import Path

from .models import Repository

logger = logging.getLogger('lazymanager')


def find_git_repos(base_path, access_history, metadata_cache):
  repos = []
  base = Path(base_path)

  if not base.exists():
    logger.warning(f'Base path does not exist: {base_path}')
    return repos

  try:
    for item in base.iterdir():
      try:
        if not item.is_dir():
          continue

        git_dir = item / '.git'
        if not git_dir.exists():
          continue

        if not git_dir.is_dir():
          logger.debug(f'Skipping {item.name}: .git is not a directory (likely submodule or worktree)')
          continue

        cached = metadata_cache.get(str(item), {})
        repo = Repository(
          path=item,
          name=item.name,
          last_accessed=access_history.get(str(item)),
          last_commit=cached.get('last_commit'),
          branch=cached.get('branch'),
          status=cached.get('status'),
          ahead=cached.get('ahead'),
          behind=cached.get('behind'),
          has_upstream=cached.get('has_upstream')
        )
        repos.append(repo)
      except PermissionError:
        logger.warning(f'Permission denied accessing: {item}')
      except Exception as e:
        logger.error(f'Error processing {item}: {str(e)}')
  except PermissionError:
    logger.error(f'Permission denied reading directory: {base_path}')
  except Exception as e:
    logger.error(f'Error iterating directory {base_path}: {str(e)}')

  return repos
