import argparse
import logging
import os
import sys
from pathlib import Path

if __name__ == '__main__':
  sys.path.insert(0, str(Path(__file__).parent.parent))
  from lazymanager.app import LazyManagerApp
  from lazymanager.config import get_config_dir
else:
  from .app import LazyManagerApp
  from .config import get_config_dir

log_file = get_config_dir() / 'lazymanager_debug.log'
logging.basicConfig(
  filename=str(log_file),
  level=logging.DEBUG,
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('lazymanager')


def main():
  parser = argparse.ArgumentParser(description='LazyManager - TUI for managing git repositories')
  parser.add_argument('--base-path', help='Base directory to scan for git repositories')
  args = parser.parse_args()

  try:
    logger.info('Starting LazyManager')
    os.system('echo "\033]0;%s\007"' % 'lazymanager')
    app = LazyManagerApp(base_path=args.base_path)
    app.run()
  except Exception as e:
    logger.exception('Fatal error starting application')
    raise


if __name__ == '__main__':
  main()
