#!/usr/bin/env python3

import logging
import sys
from pathlib import Path

if __name__ == '__main__':
  sys.path.insert(0, str(Path(__file__).parent.parent))
  from lazymanager.app import LazyManagerApp
else:
  from .app import LazyManagerApp

logging.basicConfig(
  filename='lazymanager_debug.log',
  level=logging.DEBUG,
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('lazymanager')


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
