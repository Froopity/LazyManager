import logging
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger('lazymanager')


def get_last_commit_date(repo_path, error_callback=None):
  try:
    result = subprocess.run(
      ['git', 'log', '-1', '--format=%cI'],
      cwd=str(repo_path),
      capture_output=True,
      text=True,
      timeout=2
    )
    if result.returncode == 0 and result.stdout.strip():
      return datetime.fromisoformat(result.stdout.strip()), False
    elif result.returncode != 0:
      if error_callback:
        error_callback(f'git log failed in {Path(repo_path).name}: {result.stderr.strip()}')
      return None, True
  except subprocess.TimeoutExpired:
    logger.warning(f'git log timeout in {Path(repo_path).name}')
    return None, True
  except Exception as e:
    logger.error(f'git log exception in {Path(repo_path).name}: {str(e)}')
    return None, True
  return None, False


def get_git_branch(repo_path, error_callback=None):
  try:
    result = subprocess.run(
      ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
      cwd=str(repo_path),
      capture_output=True,
      text=True,
      timeout=1
    )
    if result.returncode == 0 and result.stdout.strip():
      return result.stdout.strip(), False
    elif result.returncode != 0:
      if error_callback:
        error_callback(f'git rev-parse failed in {Path(repo_path).name}: {result.stderr.strip()}')
      return None, True
  except subprocess.TimeoutExpired:
    logger.warning(f'git rev-parse timeout in {Path(repo_path).name}')
    return None, True
  except Exception as e:
    logger.error(f'git rev-parse exception in {Path(repo_path).name}: {str(e)}')
    return None, True
  return None, False


def get_git_status(repo_path, error_callback=None):
  try:
    result = subprocess.run(
      ['git', 'status', '--porcelain'],
      cwd=str(repo_path),
      capture_output=True,
      text=True,
      timeout=1
    )
    if result.returncode == 0:
      if not result.stdout.strip():
        return 'clean', False
      return 'modified', False
    elif result.returncode != 0:
      if error_callback:
        error_callback(f'git status failed in {Path(repo_path).name}: {result.stderr.strip()}')
      return None, True
  except subprocess.TimeoutExpired:
    logger.warning(f'git status timeout in {Path(repo_path).name}')
    return None, True
  except Exception as e:
    logger.error(f'git status exception in {Path(repo_path).name}: {str(e)}')
    return None, True
  return None, False


def get_git_ahead_behind(repo_path, error_callback=None):
  try:
    branch_result = subprocess.run(
      ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
      cwd=str(repo_path),
      capture_output=True,
      text=True,
      timeout=1
    )
    if branch_result.returncode != 0 or not branch_result.stdout.strip():
      return None, None, None, False

    branch = branch_result.stdout.strip()

    remote_result = subprocess.run(
      ['git', 'config', f'branch.{branch}.remote'],
      cwd=str(repo_path),
      capture_output=True,
      text=True,
      timeout=1
    )
    merge_result = subprocess.run(
      ['git', 'config', f'branch.{branch}.merge'],
      cwd=str(repo_path),
      capture_output=True,
      text=True,
      timeout=1
    )

    if remote_result.returncode != 0 or merge_result.returncode != 0:
      return None, None, False, False

    remote = remote_result.stdout.strip()
    merge = merge_result.stdout.strip()

    if merge.startswith('refs/heads/'):
      merge = merge[11:]

    upstream = f'{remote}/{merge}'

    verify_result = subprocess.run(
      ['git', 'rev-parse', '--verify', upstream],
      cwd=str(repo_path),
      capture_output=True,
      text=True,
      timeout=1
    )
    if verify_result.returncode != 0:
      return None, None, False, False

    result = subprocess.run(
      ['git', 'rev-list', '--left-right', '--count', f'HEAD...{upstream}'],
      cwd=str(repo_path),
      capture_output=True,
      text=True,
      timeout=1
    )
    if result.returncode == 0 and result.stdout.strip():
      parts = result.stdout.strip().split()
      if len(parts) == 2:
        return int(parts[0]), int(parts[1]), True, False
    elif result.returncode != 0:
      return None, None, None, False
  except subprocess.TimeoutExpired:
    logger.warning(f'git rev-list timeout in {Path(repo_path).name}')
    return None, None, None, False
  except Exception as e:
    logger.error(f'git rev-list exception in {Path(repo_path).name}: {str(e)}')
    return None, None, None, False
  return None, None, None, False
