
report: https://yunikeil.ru/cdx_homework/

## Установка зависимостей

```
pip install -r requirements.txt -r requirements-dev.txt
```

## Генерация SBOM файлов

```
cyclonedx-py requirements -i requirements.txt -o sbom-prod.json
cyclonedx-py requirements -i requirements-dev.txt -o sbom-dev.json
```

## Запуск Dependency-Check

Разовая команда для загрузки данных уязвимостей

```bash
docker run --rm -it \
  -v "$PWD/dc-data:/usr/share/dependency-check/data" \
  owasp/dependency-check:latest \
  --nvdApiKey keyhere \
  --updateonly
```

Сканирование без обновления

```bash
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
```


## Поднимаем Dependency-Check

```bash
docker compose -f docker-compose.yml -f docker-compose.deptrack.yml up -d
```


## Загружаем SBOM

```bash
curl -X POST "http://localhost:8081/api/v1/bom" \
  -H "X-Api-Key: odt_v7RyelJ7_PTsvago5imCgW45iF9zDJuOkypXyPRTT" \
  -F "project=840c65d1-fa84-40c7-b103-c0503f1671a0" \
  -F "bom=@sbom-prod.json"

{"token":"0cad9ea3-ba0d-486f-8c31-7e2787f73878"}
```

Результат: https://yunikeil.ru/cdx_homework/reports/dependency-track/report.html

## Автоматизация actions

[reports](.github/workflows/publish-deptrack-report-pages.yml)

[sbom](.github/workflows/supplychain-security.yml)

