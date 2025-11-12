from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


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
