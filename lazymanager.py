#!/usr/bin/env python3

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Header, Footer, DataTable


@dataclass
class Repository:
  path: Path
  name: str
  last_accessed: datetime | None = None
  last_commit: datetime | None = None

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


def get_config_path():
  config_dir = Path.home() / '.config' / 'lazymanager'
  config_dir.mkdir(parents=True, exist_ok=True)
  return config_dir / 'access_history.json'


def load_access_history():
  config_path = get_config_path()
  if not config_path.exists():
    return {}

  try:
    with open(config_path, 'r') as f:
      data = json.load(f)
      return {k: datetime.fromisoformat(v) for k, v in data.items()}
  except:
    return {}


def save_access_history(history):
  config_path = get_config_path()
  data = {k: v.isoformat() for k, v in history.items()}
  with open(config_path, 'w') as f:
    json.dump(data, f, indent=2)


def get_last_commit_date(repo_path):
  try:
    result = subprocess.run(
      ['git', 'log', '-1', '--format=%cI'],
      cwd=str(repo_path),
      capture_output=True,
      text=True,
      timeout=2
    )
    if result.returncode == 0 and result.stdout.strip():
      return datetime.fromisoformat(result.stdout.strip())
  except:
    pass
  return None


def find_git_repos(base_path):
  repos = []
  base = Path(base_path)

  if not base.exists():
    return repos

  access_history = load_access_history()

  for item in base.iterdir():
    if item.is_dir():
      git_dir = item / '.git'
      if git_dir.exists():
        repo = Repository(
          path=item,
          name=item.name,
          last_accessed=access_history.get(str(item)),
          last_commit=get_last_commit_date(item)
        )
        repos.append(repo)

  return repos


class LazyManagerApp(App):
  CSS = '''
  DataTable {
    height: 100%;
  }
  '''

  BINDINGS = [
    ('q', 'quit', 'Quit'),
    ('j', 'navigate_down', 'Down'),
    ('k', 'navigate_up', 'Up'),
    ('n', 'sort_name', 'Name'),
    ('a', 'sort_accessed', 'Accessed'),
    ('c', 'sort_commit', 'Commit'),
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
    table.clear()

    sorted_repos = self.get_sorted_repos()
    if sorted_repos:
      for repo in sorted_repos:
        last_accessed = repo.last_accessed.strftime('%Y-%m-%d %H:%M') if repo.last_accessed else 'Never'
        last_commit = repo.last_commit.strftime('%Y-%m-%d') if repo.last_commit else 'N/A'
        table.add_row(repo.name, last_accessed, last_commit)
    else:
      table.add_row(f'No git repositories found in {self.base_path}', '', '')

  def compose(self) -> ComposeResult:
    yield Header()
    table = DataTable()
    table.cursor_type = 'row'
    table.zebra_stripes = True
    yield table
    yield Footer()

  def on_mount(self) -> None:
    self.title = 'LazyManager'
    self.sub_title = 'Select a repository (sorted by last accessed)'

    table = self.query_one(DataTable)
    table.add_columns('Repository', 'Last Accessed', 'Last Commit')

    self.repos = find_git_repos(self.base_path)
    self.refresh_list()

  def action_navigate_down(self) -> None:
    table = self.query_one(DataTable)
    table.action_cursor_down()

  def action_navigate_up(self) -> None:
    table = self.query_one(DataTable)
    table.action_cursor_up()

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
  app = LazyManagerApp()
  app.run()


if __name__ == '__main__':
  main()
