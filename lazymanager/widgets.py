import logging
from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import DataTable, Static, TextArea

logger = logging.getLogger('lazymanager')


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
