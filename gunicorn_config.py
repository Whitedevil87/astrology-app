import multiprocessing
import os

# Bind to localhost and a port (Nginx will proxy to this)
bind = "127.0.0.1:8000"

# Number of worker processes
# General formula: (2 x CPU cores) + 1
workers = max(multiprocessing.cpu_count() * 2 + 1, 4)

# Worker class
worker_class = "sync"

# Worker timeout (seconds)
timeout = 30

# Max requests before worker restart (prevents memory leaks)
max_requests = 1000

# Randomize max_requests to avoid all workers restarting at once
max_requests_jitter = 100

# Keep-alive timeout
keepalive = 2

# Access log
accesslog = "/var/log/gunicorn_access.log" if os.path.exists("/var/log") else "-"

# Error log
errorlog = "/var/log/gunicorn_error.log" if os.path.exists("/var/log") else "-"

# Log level
loglevel = "info"

# Proc name (for identification in ps)
proc_name = "astrology_app"

# Server hooks for graceful handling
def post_worker_init(worker):
    """Called after a worker has initialized."""
    import logging
    logging.getLogger(__name__).info(f"Worker spawned: {worker.pid}")

def worker_exit(server, worker):
    """Called after a worker has died."""
    import logging
    logging.getLogger(__name__).info(f"Worker exited: {worker.pid}")
