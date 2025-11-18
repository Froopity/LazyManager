import asyncio
import logging
import os
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer, Header, TextArea
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .config import (load_access_history, load_config, load_metadata_cache,
                     save_access_history, save_metadata_cache)
from .git_utils import (get_git_ahead_behind, get_git_branch, get_git_status,
                        get_last_commit_date)
from .models import Repository
from .repository import find_git_repos
from .widgets import ErrorConsole, RepositoryPane

logger = logging.getLogger('lazymanager')


class GitChangeHandler(FileSystemEventHandler):
  def __init__(self, app, repo):
    self.app = app
    self.repo = repo
    self.debounce_timer = None

  def on_any_event(self, event):
    if event.is_directory:
      return

    path = Path(event.src_path)
    if path.name in ('index.lock', 'HEAD.lock', '.git.lock'):
      return

    if self.debounce_timer:
      self.debounce_timer.cancel()

    self.debounce_timer = threading.Timer(1.0, self._flag_needs_refresh)
    self.debounce_timer.start()

  def _flag_needs_refresh(self):
    self.repo.needs_refresh = True
    self.app.call_from_thread(self.app.refresh_list)


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
    ('r', 'refresh', 'Refresh'),
    ('e', 'toggle_errors', 'e Errors'),
    ('1', 'focus_table', ''),
    ('2', 'focus_errors', ''),
  ]

  def __init__(self, base_path=None):
    super().__init__()
    config = load_config()
    self.base_path = base_path or config.get('base_path')
    self.repos = []
    self.sort_method = 'accessed'
    self.metadata_cache = {}
    self.access_history = {}
    self.observer = None

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
        refresh_indicator = '⟳' if repo.needs_refresh else ''
        table.add_row(repo.name, branch, status, ahead_behind, last_accessed, last_commit, refresh_indicator)

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

      self.metadata_cache = load_metadata_cache()
      self.access_history = load_access_history()

      self.repos = find_git_repos(self.base_path, self.access_history, self.metadata_cache)
      logger.info(f'Found {len(self.repos)} repositories')
      self.refresh_list()

      self.load_metadata_async()
      self.start_watching()
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

  def action_refresh(self) -> None:
    repos_to_refresh = [repo for repo in self.repos if repo.needs_refresh]
    if repos_to_refresh:
      self.run_worker(self.refresh_repos_metadata(repos_to_refresh), exclusive=False)

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

    commit_result = get_last_commit_date(repo.path, self.log_error)
    repo.last_commit = commit_result.value
    repo.has_error = repo.has_error or commit_result.has_error

    branch_result = get_git_branch(repo.path, self.log_error)
    repo.branch = branch_result.value
    repo.has_error = repo.has_error or branch_result.has_error

    status_result = get_git_status(repo.path, self.log_error)
    repo.status = status_result.value
    repo.has_error = repo.has_error or status_result.has_error

    ahead_behind_result = get_git_ahead_behind(repo.path, self.log_error)
    if ahead_behind_result.value:
      repo.ahead = ahead_behind_result.value.ahead
      repo.behind = ahead_behind_result.value.behind
      repo.has_upstream = ahead_behind_result.value.has_upstream
    else:
      repo.ahead = None
      repo.behind = None
      repo.has_upstream = None
    repo.has_error = repo.has_error or ahead_behind_result.has_error

    return repo

  def save_repo_to_cache(self, repo: Repository) -> None:
    self.metadata_cache[str(repo.path)] = {
      'branch': repo.branch,
      'status': repo.status,
      'ahead': repo.ahead,
      'behind': repo.behind,
      'has_upstream': repo.has_upstream,
      'last_commit': repo.last_commit
    }

  def load_metadata_async(self) -> None:
    self.run_worker(self.load_all_metadata(), exclusive=False)

  async def load_all_metadata(self) -> None:
    try:
      tasks = [asyncio.to_thread(self.fetch_repo_metadata, repo) for repo in self.repos]
      await asyncio.gather(*tasks, return_exceptions=True)

      for repo in self.repos:
        self.save_repo_to_cache(repo)

      save_metadata_cache(self.metadata_cache)
      self.refresh_list()
    except Exception as e:
      logger.exception('Error in load_all_metadata')

  async def refresh_repos_metadata(self, repos) -> None:
    try:
      tasks = [asyncio.to_thread(self.fetch_repo_metadata, repo) for repo in repos]
      await asyncio.gather(*tasks, return_exceptions=True)

      for repo in repos:
        repo.needs_refresh = False
        self.save_repo_to_cache(repo)

      save_metadata_cache(self.metadata_cache)
      self.refresh_list()
    except Exception as e:
      logger.exception('Error in refresh_repos_metadata')

  def start_watching(self):
    self.observer = Observer()

    for repo in self.repos:
      git_dir = repo.path / '.git'
      if not git_dir.exists():
        continue

      handler = GitChangeHandler(self, repo)

      watch_paths = [
        git_dir / 'HEAD',
        git_dir / 'index',
        git_dir / 'FETCH_HEAD',
        git_dir / 'refs' / 'heads'
      ]

      for watch_path in watch_paths:
        if watch_path.exists():
          self.observer.schedule(handler, str(watch_path), recursive=(watch_path.name == 'heads'))

    self.observer.start()
    logger.info(f'Started watching {len(self.repos)} repositories')

  def reload_metadata_and_refresh(self):
    self.load_metadata_async()

  def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
    sorted_repos = self.get_sorted_repos()
    if event.cursor_row < len(sorted_repos):
      repo = sorted_repos[event.cursor_row]
      if repo.needs_refresh:
        self.run_worker(self.refresh_repos_metadata([repo]), exclusive=False)

  def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
    sorted_repos = self.get_sorted_repos()
    if event.cursor_row < len(sorted_repos):
      repo = sorted_repos[event.cursor_row]
      self.run_lazygit(repo)

  def run_lazygit(self, repo: Repository) -> None:
    self.access_history[str(repo.path)] = datetime.now()
    save_access_history(self.access_history)

    repo.last_accessed = self.access_history[str(repo.path)]

    lazygit_cmd = shutil.which('lazygit') or shutil.which('lazygit.exe')
    if not lazygit_cmd:
      with self.suspend():
        print('Error: lazygit not found. Please install lazygit first.')
      return

    with self.suspend():
      try:
        subprocess.run([lazygit_cmd], cwd=str(repo.path))
      except Exception as e:
        print(f'Error running lazygit: {e}')

    os.system('echo \033]0;%s\007' % 'lazymanager')
    self.refresh_list()

  def on_unmount(self) -> None:
    if self.observer:
      self.observer.stop()
      self.observer.join()
      logger.info('Stopped file system watcher')
