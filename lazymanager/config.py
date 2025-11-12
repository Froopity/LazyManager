import json
from datetime import datetime
from pathlib import Path


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
