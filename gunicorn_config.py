import multiprocessing

# Gunicorn configuration file

# Bind to 0.0.0.0:8000
bind = "0.0.0.0:8000"

# Number of worker processes
workers = multiprocessing.cpu_count() * 2 + 1

# Number of threads per worker
threads = 2

# Timeout for workers
timeout = 120

# Log levels
loglevel = "info"

# Log to stdout
accesslog = "-"
errorlog = "-"

# Process name
proc_name = "gunicorn_online_store"
