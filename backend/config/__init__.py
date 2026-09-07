from config.celery import app as celery_app

# Importing here is what makes `shared_task` bind to this application when
# Django starts, whether the process is a web server, a worker or a shell.
__all__ = ("celery_app",)
