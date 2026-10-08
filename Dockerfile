FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

# gettext est necessaire pour `manage.py compilemessages` (i18n Django).
# build-essential reste en filet de securite au cas ou un paquet n'aurait
# exceptionnellement pas de roue precompilee pour cette plateforme -- mais,
# contrairement a l'image alpine precedente, la tres grande majorite des
# paquets (cryptography, pydantic_core, numpy, pandas, scipy, tiktoken...)
# ont des roues manylinux precompilees pour une base glibc comme celle-ci,
# donc aucune compilation lourde ne devrait plus avoir lieu ici.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gettext \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /code/
# --no-cache-dir : evite que pip garde en cache les paquets deja telecharges
# a l'interieur de l'image -- c'est precisement ce cache qui a rempli le
# disque de la VM et fait echouer le build precedent ("no space left on
# device" en ecrivant dans .cache/pip/http-v2/...).
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . /code/
# settings.py writes to logs/django_errors.log, but git doesn't track the empty
# logs/ folder, so create it before any manage.py command runs
RUN mkdir -p /code/logs
COPY entrypoint.sh /code/
# A Windows checkout (git core.autocrlf=true) gives entrypoint.sh CRLF line endings,
# and sh then fails with "set: illegal option -". dos2unix makes it LF; it's a no-op
# on files that are already LF (Linux/macOS checkouts).
# Installed explicitly (not relying on busybox) and kept on its own line so changing it
# doesn't invalidate the slow pip install cache. On a Debian-based image (e.g.
# python:3.13-slim) use: apt-get update && apt-get install -y dos2unix
RUN apt-get update && apt-get install -y --no-install-recommends dos2unix && rm -rf /var/lib/apt/lists/*
RUN dos2unix /code/entrypoint.sh && chmod +x /code/entrypoint.sh

# Add this line to create the logs directory
RUN mkdir -p /code/logs

RUN python manage.py compilemessages

RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["sh", "/code/entrypoint.sh"]
