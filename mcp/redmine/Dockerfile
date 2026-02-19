FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir redmine-mcp-server

EXPOSE 9000

CMD ["redmine-mcp-server", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "9000"]
