#!/usr/bin/env python3

import asyncio
import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll, Vertical
from textual.widgets import Header, Footer, DataTable, RichLog, Static, TextArea
from textual.worker import Worker, WorkerState
from textual.binding import Binding


logging.basicConfig(
  filename='lazymanager_debug.log',
  level=logging.DEBUG,
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('lazymanager')


@dataclass
class Repository:
  path: Path
  name: str
  last_accessed: datetime | None = None
  last_commit: datetime | None = None
  branch: str | None = None
  status: str | None = None
  ahead: int | None = None
  behind: int | None = None
  is_loading: bool = False
  has_error: bool = False
  has_upstream: bool | None = None

  @property
  def sort_key_name(self):
    return self.name.lower()

  @property
  def sort_key_accessed(self):
    if self.last_accessed:
      return self.last_accessed.timestamp()
    return 0

  @property
  def sort_key_commit(self):
    if self.last_commit:
      return self.last_commit.timestamp()
    return 0

  @property
  def ahead_behind_display(self):
    if self.has_upstream is False:
      return '-'
    if self.ahead is None and self.behind is None:
      return '...'
    if self.ahead == 0 and self.behind == 0:
      return '='
    parts = []
    if self.ahead and self.ahead > 0:
      parts.append(f'↑{self.ahead}')
    if self.behind and self.behind > 0:
      parts.append(f'↓{self.behind}')
    return ' '.join(parts) if parts else '='


def get_config_dir():
  config_dir = Path.home() / '.config' / 'lazymanager'
  config_dir.mkdir(parents=True, exist_ok=True)
  return config_dir


def get_access_history_path():
  return get_config_dir() / 'access_history.json'


def get_metadata_cache_path():
  return get_config_dir() / 'metadata_cache.json'


def load_access_history():
  config_path = get_access_history_path()
  if not config_path.exists():
    return {}

  try:
    with open(config_path, 'r') as f:
      data = json.load(f)
      return {k: datetime.fromisoformat(v) for k, v in data.items()}
  except:
    return {}


def save_access_history(history):
  config_path = get_access_history_path()
  data = {k: v.isoformat() for k, v in history.items()}
  with open(config_path, 'w') as f:
    json.dump(data, f, indent=2)


def load_metadata_cache():
  cache_path = get_metadata_cache_path()
  if not cache_path.exists():
    return {}

  try:
    with open(cache_path, 'r') as f:
      data = json.load(f)
      result = {}
      for repo_path, metadata in data.items():
        result[repo_path] = {
          'branch': metadata.get('branch'),
          'status': metadata.get('status'),
          'ahead': metadata.get('ahead'),
          'behind': metadata.get('behind'),
          'last_commit': datetime.fromisoformat(metadata['last_commit']) if metadata.get('last_commit') else None
        }
      return result
  except:
    return {}


def save_metadata_cache(cache):
  cache_path = get_metadata_cache_path()
  data = {}
  for repo_path, metadata in cache.items():
    data[repo_path] = {
      'branch': metadata.get('branch'),
      'status': metadata.get('status'),
      'ahead': metadata.get('ahead'),
      'behind': metadata.get('behind'),
      'last_commit': metadata['last_commit'].isoformat() if metadata.get('last_commit') else None
    }
  with open(cache_path, 'w') as f:
    json.dump(data, f, indent=2)


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


class ErrorConsole(Container):
  DEFAULT_CSS = '''
  ErrorConsole {
    display: none;
    height: 0;
    width: 100%;
    background: $panel;
    border-top: solid $primary;
    dock: bottom;
  }

  ErrorConsole.visible {
    display: block;
    height: 33%;
    width: 100%;
  }

  ErrorConsole.fullscreen {
    display: block;
    height: 100%;
    width: 100%;
  }

  ErrorConsole > Static {
    width: 100%;
    height: auto;
    background: $primary;
    color: $text;
    padding: 0 1;
  }

  ErrorConsole > TextArea {
    width: 100%;
    height: 1fr;
    background: $panel;
    color: $text;
    border: none;
  }
  '''

  def compose(self) -> ComposeResult:
    yield Static('[2] Error Console')
    text_area = TextArea(read_only=True)
    text_area.show_line_numbers = False
    yield text_area

  def log_error(self, message: str) -> None:
    try:
      text_area = self.query_one(TextArea)
      timestamp = datetime.now().strftime('%H:%M:%S')
      current_text = text_area.text
      new_line = f'{timestamp} {message}\n'

      cursor_location = text_area.cursor_location
      scroll_y = text_area.scroll_offset.y

      text_area.load_text(current_text + new_line)

      text_area.move_cursor(cursor_location)
      text_area.scroll_to(y=scroll_y, animate=False)
    except Exception as e:
      logger.error(f'Failed to update error console: {str(e)}')

  def clear_errors(self) -> None:
    text_area = self.query_one(TextArea)
    text_area.load_text('')

  def get_error_count(self) -> int:
    text_area = self.query_one(TextArea)
    return len(text_area.text.splitlines())


class RepositoryPane(Vertical):
  DEFAULT_CSS = '''
  RepositoryPane {
    height: 1fr;
  }

  RepositoryPane > Static {
    width: 100%;
    height: auto;
    background: $primary;
    color: $text;
    padding: 0 1;
  }

  RepositoryPane > DataTable {
    height: 1fr;
  }
  '''

  BINDINGS = [
    Binding('j', 'navigate_down', '', show=False),
    Binding('k', 'navigate_up', '', show=False),
  ]

  def compose(self) -> ComposeResult:
    yield Static('[1] Repositories')
    table = DataTable()
    table.cursor_type = 'row'
    table.zebra_stripes = True
    yield table

  def action_navigate_down(self) -> None:
    table = self.query_one(DataTable)
    table.action_cursor_down()

  def action_navigate_up(self) -> None:
    table = self.query_one(DataTable)
    table.action_cursor_up()


class LazyManagerApp(App):
  CSS = '''
  Screen {
    layout: vertical;
  }
  '''

  BINDINGS = [
    ('q', 'quit', 'Quit'),
    ('n', 'sort_name', 'Name'),
    ('a', 'sort_accessed', 'Accessed'),
    ('c', 'sort_commit', 'Commit'),
    ('e,E', 'toggle_errors', 'e/E Errors'),
    ('1', 'focus_table', ''),
    ('2', 'focus_errors', ''),
  ]

  def __init__(self, base_path='C:\\Work\\source'):
    super().__init__()
    self.base_path = base_path
    self.repos = []
    self.sort_method = 'accessed'

  def get_sorted_repos(self):
    if self.sort_method == 'name':
      return sorted(self.repos, key=lambda r: r.sort_key_name)
    elif self.sort_method == 'accessed':
      return sorted(self.repos, key=lambda r: r.sort_key_accessed, reverse=True)
    elif self.sort_method == 'commit':
      return sorted(self.repos, key=lambda r: r.sort_key_commit, reverse=True)
    return self.repos

  def refresh_list(self):
    table = self.query_one(DataTable)
    cursor_row = table.cursor_row
    table.clear()

    sorted_repos = self.get_sorted_repos()
    if sorted_repos:
      for repo in sorted_repos:
        last_accessed = repo.last_accessed.strftime('%Y-%m-%d %H:%M') if repo.last_accessed else 'Never'
        last_commit = repo.last_commit.strftime('%Y-%m-%d') if repo.last_commit else ('!' if repo.has_error else 'N/A')
        branch = repo.branch if repo.branch else ('!' if repo.has_error else '...')
        status = repo.status if repo.status else ('!' if repo.has_error else '...')
        ahead_behind = repo.ahead_behind_display if not repo.has_error else '!'
        loading = '⟳' if repo.is_loading else ''
        table.add_row(repo.name, branch, status, ahead_behind, last_accessed, last_commit, loading)

      if cursor_row < len(sorted_repos):
        table.move_cursor(row=cursor_row)
    else:
      table.add_row(f'No git repositories found in {self.base_path}', '', '', '', '', '', '')

  def compose(self) -> ComposeResult:
    yield Header()
    yield RepositoryPane()
    yield ErrorConsole()
    yield Footer()

  def on_mount(self) -> None:
    try:
      logger.info('App mounted, initializing UI')
      self.title = 'LazyManager'
      self.sub_title = 'Select a repository (sorted by last accessed)'

      table = self.query_one(DataTable)
      table.add_columns('Repository', 'Branch', 'Status', '↑↓', 'Last Accessed', 'Last Commit', '')

      self.repos = find_git_repos(self.base_path)
      logger.info(f'Found {len(self.repos)} repositories')
      self.refresh_list()

      self.load_metadata_async()
    except Exception as e:
      logger.exception('Error during mount')

  def action_sort_name(self) -> None:
    self.sort_method = 'name'
    self.sub_title = 'Select a repository (sorted by name)'
    self.refresh_list()

  def action_sort_accessed(self) -> None:
    self.sort_method = 'accessed'
    self.sub_title = 'Select a repository (sorted by last accessed)'
    self.refresh_list()

  def action_sort_commit(self) -> None:
    self.sort_method = 'commit'
    self.sub_title = 'Select a repository (sorted by last commit)'
    self.refresh_list()

  def action_toggle_errors(self, shift: bool = False) -> None:
    logger.debug(f'Toggling error console (shift={shift})')
    error_console = self.query_one(ErrorConsole)

    if shift:
      if error_console.has_class('visible'):
        error_console.remove_class('visible')
      if error_console.has_class('fullscreen'):
        error_console.remove_class('fullscreen')
      else:
        error_console.add_class('fullscreen')
    else:
      if error_console.has_class('fullscreen'):
        error_console.remove_class('fullscreen')
      if error_console.has_class('visible'):
        error_console.remove_class('visible')
      else:
        error_console.add_class('visible')

  def action_focus_table(self) -> None:
    table = self.query_one(DataTable)
    table.focus()

  def action_focus_errors(self) -> None:
    error_console = self.query_one(ErrorConsole)
    if not error_console.has_class('visible') and not error_console.has_class('fullscreen'):
      error_console.add_class('visible')
    text_area = error_console.query_one(TextArea)
    text_area.focus()

  def log_error(self, message: str) -> None:
    try:
      error_console = self.query_one(ErrorConsole)
      error_console.log_error(message)
    except Exception as e:
      logger.error(f'Failed to log error to console: {str(e)}')

  def fetch_repo_metadata(self, repo: Repository) -> Repository:
    repo.has_error = False

    commit_date, has_error = get_last_commit_date(repo.path, self.log_error)
    repo.last_commit = commit_date
    repo.has_error = repo.has_error or has_error

    branch, has_error = get_git_branch(repo.path, self.log_error)
    repo.branch = branch
    repo.has_error = repo.has_error or has_error

    status, has_error = get_git_status(repo.path, self.log_error)
    repo.status = status
    repo.has_error = repo.has_error or has_error

    ahead, behind, has_upstream, has_error = get_git_ahead_behind(repo.path, self.log_error)
    repo.ahead = ahead
    repo.behind = behind
    repo.has_upstream = has_upstream
    repo.has_error = repo.has_error or has_error

    repo.is_loading = False
    return repo

  def save_repo_to_cache(self, repo: Repository) -> None:
    metadata_cache = load_metadata_cache()
    metadata_cache[str(repo.path)] = {
      'branch': repo.branch,
      'status': repo.status,
      'ahead': repo.ahead,
      'behind': repo.behind,
      'last_commit': repo.last_commit
    }
    save_metadata_cache(metadata_cache)

  def load_metadata_async(self) -> None:
    self.run_worker(self.load_all_metadata(), exclusive=False)

  async def load_all_metadata(self) -> None:
    try:
      for repo in self.repos:
        try:
          repo.is_loading = True
          self.refresh_list()
          await asyncio.to_thread(self.fetch_repo_metadata, repo)
          self.save_repo_to_cache(repo)
          self.refresh_list()
        except Exception as e:
          logger.exception(f'Error loading metadata for {repo.name}')
          repo.is_loading = False
          self.refresh_list()
    except Exception as e:
      logger.exception('Error in load_all_metadata')

  def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
    sorted_repos = self.get_sorted_repos()
    if event.cursor_row < len(sorted_repos):
      repo = sorted_repos[event.cursor_row]
      self.run_lazygit(repo)

  def run_lazygit(self, repo: Repository) -> None:
    access_history = load_access_history()
    access_history[str(repo.path)] = datetime.now()
    save_access_history(access_history)

    repo.last_accessed = access_history[str(repo.path)]

    with self.suspend():
      try:
        subprocess.run(['lazygit.exe'], cwd=str(repo.path))
      except FileNotFoundError:
        print('Error: lazygit not found. Please install lazygit first.')
        input('Press Enter to continue...')
      except Exception as e:
        print(f'Error running lazygit: {e}')
        input('Press Enter to continue...')

    self.refresh_list()


def main():
  try:
    logger.info('Starting LazyManager')
    app = LazyManagerApp()
    app.run()
  except Exception as e:
    logger.exception('Fatal error starting application')
    raise


if __name__ == '__main__':
  main()
