#!/usr/bin/env python3

import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Header, Footer, Label, ListItem, ListView


def find_git_repos(base_path):
  repos = []
  base = Path(base_path)

  if not base.exists():
    return repos

  for item in base.iterdir():
    if item.is_dir():
      git_dir = item / '.git'
      if git_dir.exists():
        repos.append(item)

  return sorted(repos, key=lambda p: p.name.lower())


class LazyManagerApp(App):
  CSS = '''
  ListView {
    height: 100%;
  }
  '''

  BINDINGS = [
    ('q', 'quit', 'Quit'),
    ('j', 'navigate_down', 'Down'),
    ('k', 'navigate_up', 'Up'),
  ]

  def __init__(self, base_path='C:\\Work\\source'):
    super().__init__()
    self.base_path = base_path
    self.repos = []

  def compose(self) -> ComposeResult:
    yield Header()
    yield ListView()
    yield Footer()

  def on_mount(self) -> None:
    self.title = 'LazyManager'
    self.sub_title = 'Select a repository'

    self.repos = find_git_repos(self.base_path)
    list_view = self.query_one(ListView)

    for repo in self.repos:
      list_view.append(ListItem(Label(repo.name)))

    if not self.repos:
      list_view.append(ListItem(Label(f'No git repositories found in {self.base_path}')))

  def action_navigate_down(self) -> None:
    list_view = self.query_one(ListView)
    list_view.action_cursor_down()

  def action_navigate_up(self) -> None:
    list_view = self.query_one(ListView)
    list_view.action_cursor_up()

  def on_list_view_selected(self, event: ListView.Selected) -> None:
    if event.list_view.index is not None and event.list_view.index < len(self.repos):
      repo = self.repos[event.list_view.index]
      self.run_lazygit(repo)

  def run_lazygit(self, repo_path: Path) -> None:
    with self.suspend():
      try:
        subprocess.run(['lazygit.exe'], cwd=str(repo_path))
      except FileNotFoundError:
        print('Error: lazygit not found. Please install lazygit first.')
        input('Press Enter to continue...')
      except Exception as e:
        print(f'Error running lazygit: {e}')
        input('Press Enter to continue...')


def main():
  app = LazyManagerApp()
  app.run()


if __name__ == '__main__':
  main()
