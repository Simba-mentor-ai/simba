FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

# Install build dependencies for Alpine
RUN apk add --no-cache build-base musl-dev libffi-dev rust cargo gettext

COPY requirements.txt /code/
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . /code/
COPY entrypoint.sh /code/
RUN chmod +x /code/entrypoint.sh

# Add this line to create the logs directory
RUN mkdir -p /code/logs

RUN python manage.py compilemessages

RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["sh", "/code/entrypoint.sh"]
