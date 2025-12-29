


pip install -r requirements.txt -r requirements-dev.txt


cyclonedx-py requirements -i requirements.txt -o sbom-prod.json


docker run --rm -it \
  -v "$PWD/dc-data:/usr/share/dependency-check/data" \
  owasp/dependency-check:latest \
  --nvdApiKey keyhere \
  --updateonly


docker run --rm -it \
  -v "$PWD:/src" \
  -v "$PWD/reports/dc:/report" \
  -v "$PWD/dc-data:/usr/share/dependency-check/data" \
  owasp/dependency-check:latest \
  --scan /src/requirements.txt \
  --scan /src/requirements-dev.txt \
  --format "HTML" --format "JSON" \
  --out /report \
  --project "fastapi-sbom-demo" \
  --log /report/dc.log \
  --prettyPrint \
  --noupdate



docker compose -f docker-compose.yml -f docker-compose.deptrack.yml up -d


curl -X POST "http://localhost:8081/api/v1/bom" \
  -H "X-Api-Key: odt_v7RyelJ7_PTsvago5imCgW45iF9zDJuOkypXyPRTT" \
  -F "project=840c65d1-fa84-40c7-b103-c0503f1671a0" \
  -F "bom=@sbom-prod.json"

{"token":"0cad9ea3-ba0d-486f-8c31-7e2787f73878"}%