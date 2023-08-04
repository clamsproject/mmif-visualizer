import os
import time
import shutil

def set_last_access(path):
    with open(os.path.join(path, "last_access.txt"), "w") as f:
        f.write(str(time.time()))

def scan_tmp_directory():
    total_size = 0
    oldest_accessed_dir = {"dir": None, "access_time": None}
    for path, dirs, files in os.walk("/app/static/tmp"):
        for f in files:
            fp = os.path.join(path, f)
            total_size += os.path.getsize(fp)

        # Get oldest accessed directory for deletion
        if os.path.dirname(path) != "/app/static/tmp":
            continue
        if not os.path.isfile(os.path.join(path, "last_access.txt")):
            oldest_accessed_dir = {"dir": path, "access_time": 0}
        elif oldest_accessed_dir["dir"] is None:
            with open(os.path.join(path, "last_access.txt")) as f:
                timestamp = f.read()
                if timestamp == '':
                    continue
                oldest_accessed_dir = {"dir": path, "access_time": float(timestamp)}
        else:
            with open(os.path.join(path, "last_access.txt")) as f:
                if float(f.read()) < oldest_accessed_dir["access_time"]:
                    timestamp = f.read()
                    if timestamp == '':
                        continue
                    oldest_accessed_dir = {"dir": path, "access_time": float(timestamp)}
    
    return total_size, oldest_accessed_dir["dir"]


def cleanup():
    print("Checking visualization cache...")
    # Max tmp size is 50MB
    max_size = 10000000
    folder_size, oldest_dir = scan_tmp_directory()
    while folder_size > max_size:
        print(f"Maximum cache size reached. Deleting {os.path.basename(oldest_dir)}.")
        shutil.rmtree(oldest_dir)
        folder_size, oldest_dir = scan_tmp_directory()
    # Cleanup again in 12 hours
    time.sleep(43200)
    cleanup()
