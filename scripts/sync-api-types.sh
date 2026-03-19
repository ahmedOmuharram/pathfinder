#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for API..."
until curl -sf http://api:8000/api/v1/health > /dev/null 2>&1; do
  sleep 1
done

echo "Fetching OpenAPI spec..."
node -e "
const http = require('http');
const fs = require('fs');
http.get('http://api:8000/openapi.json', res => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => { fs.writeFileSync('packages/spec/openapi.json', data); console.log('Wrote openapi.json'); });
}).on('error', e => { console.error(e); process.exit(1); });
"

echo "Generating TypeScript types..."
cd packages/shared-ts && yarn generate:openapi

echo "Types synced successfully."
