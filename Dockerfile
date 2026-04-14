FROM python:3.11

RUN apt-get update && apt-get install -y ffmpeg

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt && \
    yt-dlp -U

CMD ["gunicorn", "app:app", "--workers", "1", "--threads", "4", "--timeout", "0"]
