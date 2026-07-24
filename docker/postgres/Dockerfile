FROM postgres:17

RUN apt-get update && \
    apt-get install -y \
        postgresql-17-partman \
        git \
        build-essential \
        postgresql-server-dev-17 && \
    rm -rf /var/lib/apt/lists/*

# pgTAP from source (no PGDG deb for pg17 pgtap)
RUN cd /tmp && \
    git clone --depth 1 https://github.com/theory/pgtap.git && \
    cd pgtap && \
    make PG_CONFIG=/usr/lib/postgresql/17/bin/pg_config && \
    make install PG_CONFIG=/usr/lib/postgresql/17/bin/pg_config && \
    cd / && rm -rf /tmp/pgtap /var/lib/apt/lists/*
