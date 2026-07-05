FROM python:3.11-slim as builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim

RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
    curl ca-certificates tzdata sqlite3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    ln -fs /usr/share/zoneinfo/Asia/Kolkata /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata

RUN useradd -m -u 1000 -s /bin/bash scanner

WORKDIR /app
COPY --from=builder /root/.local /home/scanner/.local
COPY . .

RUN mkdir -p logs reports charts output/reports output/charts data && \
    chown -R scanner:scanner /app

ENV PATH="/home/scanner/.local/bin:${PATH}" \
    PYTHONPATH="/app:${PYTHONPATH}" \
    TZ="Asia/Kolkata"

USER scanner

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["python", "main.py", "--mode", "live"]
