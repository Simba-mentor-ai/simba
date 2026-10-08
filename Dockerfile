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
COPY entrypoint.sh /code/
RUN chmod +x /code/entrypoint.sh

# Add this line to create the logs directory
RUN mkdir -p /code/logs

RUN python manage.py compilemessages

RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["sh", "/code/entrypoint.sh"]
