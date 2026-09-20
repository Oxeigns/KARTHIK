FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -m bot
COPY . .
RUN mkdir -p /app/data && chown -R bot:bot /app
USER bot
EXPOSE 8080
CMD ["python", "bot.py"]
