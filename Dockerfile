# Keystone + FalkorDB in one image, preloaded with the seed graphs (kb_falkordb, kb_pallets).
FROM falkordb/falkordb:latest
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir -r requirements.txt
COPY keystone keystone
COPY public public
COPY data/eval_result.json data/qa_eval.json data/
COPY seed/dump.rdb.gz /tmp/dump.rdb.gz
RUN mkdir -p /var/lib/falkordb/data && gunzip -c /tmp/dump.rdb.gz > /var/lib/falkordb/data/dump.rdb && rm /tmp/dump.rdb.gz
COPY docker-entrypoint.sh /entry.sh
RUN chmod +x /entry.sh
ENV PYTHONPATH=/app
EXPOSE 8000 3000
ENTRYPOINT ["/entry.sh"]
