import os
import time
import shutil
import threading
import pathlib

from utils import app as utils_app

lock = threading.Lock()


def get_cache_path():
    return pathlib.Path(utils_app.static_folder) / "tmp"


def get_cache_relpath(full_path):
    return str(full_path)[len(utils_app.static_folder):]


def invalidate_cache(viz_ids):
    if not viz_ids:
        shutil.rmtree(get_cache_path())
        os.makedirs(get_cache_path())
    else:
        for v in viz_ids:
            shutil.rmtree(get_cache_path() / v)


def set_last_access(path):
    with open(os.path.join(path, "last_access.txt"), "w") as f:
        f.write(str(time.time()))


def scan_tmp_directory():
    oldest_accessed_dir = {"dir": None, "access_time": None}
    total_size = sum(f.stat().st_size for f in get_cache_path().glob('**/*') if f.is_file())
    # this will be some visualization IDs
    for p in get_cache_path().glob('*'):
        if not (p / 'last_access.txt').exists():
            oldest_accessed_dir = {"dir": p, "access_time": 0}
        elif oldest_accessed_dir["dir"] is None:
            with open(p / 'last_access.txt') as f:
                timestamp = f.read()
                if timestamp == '':
                    continue
                oldest_accessed_dir = {"dir": p, "access_time": float(timestamp)}
        else:
            with open(p / 'last_access.txt') as f:
                if float(f.read()) < oldest_accessed_dir["access_time"]:
                    timestamp = f.read()
                    if timestamp == '':
                        continue
                    oldest_accessed_dir = {"dir": p, "access_time": float(timestamp)}
    return total_size, oldest_accessed_dir["dir"]


def cleanup():
    with lock:
        print("Checking visualization cache...")
        # Max tmp size is 500MB
        max_size = 500000000
        folder_size, oldest_dir = scan_tmp_directory()
        while folder_size > max_size:
            print(f"Maximum cache size reached. Deleting {os.path.basename(oldest_dir)}.")
            shutil.rmtree(oldest_dir)
            folder_size, oldest_dir = scan_tmp_directory()
