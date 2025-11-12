import logging
import subprocess
from datetime import datetime
from pathlib import Path

from .models import AheadBehindInfo, GitResult

logger = logging.getLogger('lazymanager')


def get_last_commit_date(repo_path, error_callback=None) -> GitResult[datetime]:
  try:
    result = subprocess.run(
      ['git', 'log', '-1', '--format=%cI'],
      cwd=str(repo_path),
      capture_output=True,
      text=True,
      timeout=2
    )
    if result.returncode == 0 and result.stdout.strip():
      return GitResult(value=datetime.fromisoformat(result.stdout.strip()), has_error=False)
    elif result.returncode != 0:
      if error_callback:
        error_callback(f'git log failed in {Path(repo_path).name}: {result.stderr.strip()}')
      return GitResult(value=None, has_error=True)
  except subprocess.TimeoutExpired:
    logger.warning(f'git log timeout in {Path(repo_path).name}')
    return GitResult(value=None, has_error=True)
  except Exception as e:
    logger.error(f'git log exception in {Path(repo_path).name}: {str(e)}')
    return GitResult(value=None, has_error=True)
  return GitResult(value=None, has_error=False)


def get_git_branch(repo_path, error_callback=None) -> GitResult[str]:
  try:
    result = subprocess.run(
      ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
      cwd=str(repo_path),
      capture_output=True,
      text=True,
      timeout=1
    )
    if result.returncode == 0 and result.stdout.strip():
      return GitResult(value=result.stdout.strip(), has_error=False)
    elif result.returncode != 0:
      if error_callback:
        error_callback(f'git rev-parse failed in {Path(repo_path).name}: {result.stderr.strip()}')
      return GitResult(value=None, has_error=True)
  except subprocess.TimeoutExpired:
    logger.warning(f'git rev-parse timeout in {Path(repo_path).name}')
    return GitResult(value=None, has_error=True)
  except Exception as e:
    logger.error(f'git rev-parse exception in {Path(repo_path).name}: {str(e)}')
    return GitResult(value=None, has_error=True)
  return GitResult(value=None, has_error=False)


def get_git_status(repo_path, error_callback=None) -> GitResult[str]:
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
        return GitResult(value='clean', has_error=False)
      return GitResult(value='modified', has_error=False)
    elif result.returncode != 0:
      if error_callback:
        error_callback(f'git status failed in {Path(repo_path).name}: {result.stderr.strip()}')
      return GitResult(value=None, has_error=True)
  except subprocess.TimeoutExpired:
    logger.warning(f'git status timeout in {Path(repo_path).name}')
    return GitResult(value=None, has_error=True)
  except Exception as e:
    logger.error(f'git status exception in {Path(repo_path).name}: {str(e)}')
    return GitResult(value=None, has_error=True)
  return GitResult(value=None, has_error=False)


def get_git_ahead_behind(repo_path, error_callback=None) -> GitResult[AheadBehindInfo]:
  try:
    branch_result = get_git_branch(repo_path, error_callback)
    if branch_result.has_error or not branch_result.value:
      return GitResult(value=AheadBehindInfo(ahead=None, behind=None, has_upstream=False), has_error=False)

    branch = branch_result.value

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
      if error_callback:
        error_callback(f'No upstream branch configured for {branch} in {Path(repo_path).name}')
      return GitResult(value=AheadBehindInfo(ahead=None, behind=None, has_upstream=False), has_error=False)

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
      if error_callback:
        error_callback(f'Upstream branch {upstream} not found in {Path(repo_path).name}: {verify_result.stderr.strip()}')
      return GitResult(value=AheadBehindInfo(ahead=None, behind=None, has_upstream=False), has_error=False)

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
        return GitResult(
          value=AheadBehindInfo(ahead=int(parts[0]), behind=int(parts[1]), has_upstream=True),
          has_error=False
        )
    elif result.returncode != 0:
      if error_callback:
        error_callback(f'git rev-list failed in {Path(repo_path).name}: {result.stderr.strip()}')
      return GitResult(value=None, has_error=True)
  except subprocess.TimeoutExpired:
    logger.warning(f'git ahead/behind timeout in {Path(repo_path).name}')
    if error_callback:
      error_callback(f'git ahead/behind timeout in {Path(repo_path).name}')
    return GitResult(value=None, has_error=True)
  except Exception as e:
    logger.error(f'git ahead/behind exception in {Path(repo_path).name}: {str(e)}')
    if error_callback:
      error_callback(f'git ahead/behind exception in {Path(repo_path).name}: {str(e)}')
    return GitResult(value=None, has_error=True)
  return GitResult(value=None, has_error=True)
