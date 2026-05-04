import multiprocessing
import os

port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

# Dynamic worker count: (2 × CPU) + 1, capped at 4 for free tier
cpu_count = multiprocessing.cpu_count()
workers = min((2 * cpu_count) + 1, 4)

# Threaded workers — essential for I/O-heavy app (Groq, Supabase, Photon calls)
worker_class = "gthread"
threads = 2

timeout = 120
max_requests = 1000
max_requests_jitter = 100
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = "info"
proc_name = "celestial_arc"


def post_worker_init(worker):
    import logging
    logging.getLogger(__name__).info(f"Worker spawned: {worker.pid}")


def worker_exit(server, worker):
    import logging
    logging.getLogger(__name__).info(f"Worker exited: {worker.pid}")
