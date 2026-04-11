import multiprocessing
import os

# Render sets PORT, default to 10000 if not found
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

# Use a static small number of workers on free tier, or calculate based on CPUs
workers = 2

# Worker class - gthread is highly recommended for Render to avoid blocking
worker_class = "gthread"
threads = 4

# Worker timeout (seconds)
timeout = 120

# Max requests before worker restart (prevents memory leaks)
max_requests = 1000

# Randomize max_requests to avoid all workers restarting at once
max_requests_jitter = 100

# Keep-alive timeout
keepalive = 5

# Access log - output to stdout for Render
accesslog = "-"

# Error log - output to stderr for Render
errorlog = "-"

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
