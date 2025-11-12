import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger('lazymanager')


def atomic_write_json(path, data):
  path = Path(path)
  temp_path = path.with_suffix('.tmp')
  try:
    with open(temp_path, 'w') as f:
      json.dump(data, f, indent=2)
      f.flush()
      os.fsync(f.fileno())
    os.replace(temp_path, path)
  except Exception as e:
    if temp_path.exists():
      temp_path.unlink()
    raise


def get_config_dir():
  config_dir = Path.home() / '.config' / 'lazymanager'
  config_dir.mkdir(parents=True, exist_ok=True)
  return config_dir


def get_access_history_path():
  return get_config_dir() / 'access_history.json'


def get_metadata_cache_path():
  return get_config_dir() / 'metadata_cache.json'


def get_config_path():
  return get_config_dir() / 'config.json'


def load_config():
  config_path = get_config_path()
  default_config = {
    'base_path': str(Path.home())
  }

  if not config_path.exists():
    return default_config

  try:
    with open(config_path, 'r') as f:
      data = json.load(f)
      return {**default_config, **data}
  except FileNotFoundError:
    return default_config
  except json.JSONDecodeError as e:
    logger.warning(f'Failed to parse config JSON: {e}')
    return default_config
  except PermissionError as e:
    logger.error(f'Permission denied reading config: {e}')
    return default_config
  except Exception as e:
    logger.error(f'Error loading config: {e}')
    return default_config


def save_config(config):
  config_path = get_config_path()
  atomic_write_json(config_path, config)


def load_access_history():
  config_path = get_access_history_path()
  if not config_path.exists():
    return {}

  try:
    with open(config_path, 'r') as f:
      data = json.load(f)
      return {k: datetime.fromisoformat(v) for k, v in data.items()}
  except FileNotFoundError:
    return {}
  except json.JSONDecodeError as e:
    logger.warning(f'Failed to parse access history JSON: {e}')
    return {}
  except PermissionError as e:
    logger.error(f'Permission denied reading access history: {e}')
    return {}
  except Exception as e:
    logger.error(f'Error loading access history: {e}')
    return {}


def save_access_history(history):
  config_path = get_access_history_path()
  data = {k: v.isoformat() for k, v in history.items()}
  atomic_write_json(config_path, data)


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
          'has_upstream': metadata.get('has_upstream'),
          'last_commit': datetime.fromisoformat(metadata['last_commit']) if metadata.get('last_commit') else None
        }
      return result
  except FileNotFoundError:
    return {}
  except json.JSONDecodeError as e:
    logger.warning(f'Failed to parse metadata cache JSON: {e}')
    return {}
  except PermissionError as e:
    logger.error(f'Permission denied reading metadata cache: {e}')
    return {}
  except Exception as e:
    logger.error(f'Error loading metadata cache: {e}')
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
      'has_upstream': metadata.get('has_upstream'),
      'last_commit': metadata['last_commit'].isoformat() if metadata.get('last_commit') else None
    }
  atomic_write_json(cache_path, data)
