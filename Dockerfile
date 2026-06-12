# leadgen — runs the Flask GUI server in a container.
#
# Scraping happens entirely at runtime against live, no-key data sources; this
# image bundles NO lead data. Generated CSV/XLSX files are written inside the
# container (gui/_output) per run — mount a volume there if you want to keep them.
FROM python:3.11-slim

# Avoid .pyc files and force unbuffered, UTF-8 stdout (progress lines use glyphs).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app

# Copy the whole repo (package + GUI) and install with the GUI extra.
COPY . /app
RUN pip install --no-cache-dir ".[gui]"

# Flask GUI listens on 5000.
EXPOSE 5000

# Default: serve the web GUI. Override CMD to run the CLI, e.g.:
#   docker run --rm leadgen python -m leadgen --vertical web_design --market austin_tx
CMD ["python", "gui/app.py"]
