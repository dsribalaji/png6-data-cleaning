#!/bin/sh
# gen-local-tls.sh - generate throwaway LOCAL-ONLY TLS/key material for the
# hardening overlay. Run once per host. Never commit the output.
set -eu
cd "$(dirname "$0")"
mkdir -p pg-tls
if [ ! -f pg-tls/server.key ]; then
  openssl req -x509 -newkey rsa:2048 -keyout pg-tls/server.key -out pg-tls/server.crt \
    -days 365 -nodes -subj "/CN=postgres" 2>/dev/null
  # postgres runs as uid 999 in the container; the key must be 0600 and his.
  docker run --rm -v "$PWD/pg-tls:/tls" postgres:16 \
    sh -c 'chown 999:999 /tls/server.key && chmod 600 /tls/server.key && chmod 644 /tls/server.crt'
  echo "pg-tls/server.{crt,key} created"
else
  echo "pg-tls/server.key exists, skipping"
fi
if ! grep -q "^MINIO_KMS_SECRET_KEY=" ../.env 2>/dev/null; then
  KEY=$(openssl rand -base64 32)
  printf "MINIO_KMS_SECRET_KEY=png6-local:%s\n" "$KEY" >> ../.env
  echo "MINIO_KMS_SECRET_KEY added to .env"
else
  echo "MINIO_KMS_SECRET_KEY already in .env"
fi
echo OK
