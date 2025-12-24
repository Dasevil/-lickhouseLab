# Лабораторная работа №2: Система e-commerce мониторинга на ClickHouse + Prometheus + Grafana

## Цель работы

Развернуть полноценную аналитическую систему для интернет-магазина, включающую:
- **ClickHouse** как высокопроизводительную колончатую СУБД для хранения каталога товаров и пользовательских событий
- **Prometheus** для сбора технических метрик производительности
- **Grafana** для визуализации бизнес-аналитики и мониторинга системы

## Предварительные требования

### Программное обеспечение
- **Docker** и **Docker Compose** (Docker Desktop или Docker Engine 20.10+)
- **Python 3.10+** с установленным pip
- **Git** для клонирования репозитория

### Аппаратные требования
- Минимум **4 ГБ ОЗУ**
- **10 ГБ свободного места** на диске
- Процессор с поддержкой **AVX2** (для ClickHouse)

### Данные для работы
Файлы данных доступны по ссылке:  
`https://disk.yandex.ru/d/8XvFIqyIc7hSGw`  
(Для получения пароля обратитесь в Telegram: @Sergpoly78)

Необходимо скачать:
- `10ozon.csv` - каталог товаров интернет-магазина
- `RawEvent.parquet` - журнал пользовательских событий

## Быстрый старт

### Шаг 1: Подготовка рабочего пространства

```bash
# Клонируем репозиторий
git clone <https://github.com/Dasevil/-lickhouseLab.git>


# Помещаем скачанные файлы данных
# data/10ozon.csv
# data/RawEvent.parquet
```

### Шаг 2: Конфигурация Docker-сервисов

**`docker-compose.yml`** - основной файл оркестрации:
```yaml
version: "3.8"

services:
  clickhouse:
    image: clickhouse/clickhouse-server:latest
    container_name: clickhouse
    ports:
      - "8123:8123"  # HTTP-интерфейс
      - "9000:9000"  # Нативный протокол
      - "9363:9363"  # Prometheus метрики
    volumes:
      - ./clickhouse/init.sql:/docker-entrypoint-initdb.d/init.sql
      - ./clickhouse/conf.d:/etc/clickhouse-server/conf.d
      - ./data:/var/lib/clickhouse/user_files
      - clickhouse-data:/var/lib/clickhouse
      - clickhouse-logs:/var/log/clickhouse-server
    ulimits:
      nofile:
        soft: 262144
        hard: 262144

  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    depends_on:
      - clickhouse

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on:
      - prometheus

volumes:
  clickhouse-data:
  clickhouse-logs:
  grafana-data:
```

### Шаг 3: Запуск инфраструктуры

```bash
# Запуск всех сервисов в фоновом режиме
docker compose up -d

# Проверка состояния контейнеров
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Ожидаемый вывод:
# NAMES        STATUS        PORTS
# clickhouse   Up 2 minutes  0.0.0.0:8123->8123/tcp, 0.0.0.0:9000->9000/tcp, 0.0.0.0:9363->9363/tcp
# prometheus   Up 2 minutes  0.0.0.0:9090->9090/tcp
# grafana      Up 1 minute   0.0.0.0:3000->3000/tcp
```

## Структура данных

### Каталог товаров (`10ozon.csv`)

| Столбец CSV | Поле в БД    | Тип данных | Описание                |
|-------------|--------------|------------|-------------------------|
| c1          | —            | Игнорируется | Служебная колонка       |
| c2          | offer_id     | UInt64     | Уникальный ID товара    |
| c3          | price        | Float64    | Цена товара            |
| c4          | seller_id    | UInt64     | ID продавца            |
| c5          | category_id  | UInt32     | ID категории товара    |
| c6          | vendor       | String     | Производитель/бренд    |

**Важно**: Первая строка содержит заголовки и должна быть проигнорирована при загрузке.

### Журнал событий (`RawEvent.parquet`)

| Поле             | Тип данных       | Описание                     |
|------------------|------------------|------------------------------|
| Hour             | DateTime         | Временная метка события      |
| DeviceTypeName   | LowCardinality(String) | Тип устройства пользователя |
| ApplicationName  | LowCardinality(String) | Название приложения          |
| OSName           | LowCardinality(String) | Операционная система         |
| ProvinceName     | LowCardinality(String) | Регион пользователя          |
| ContentUnitID    | UInt64           | ID товара (ссылка на каталог)|

## Инициализация ClickHouse

### База данных и таблицы

**`clickhouse/init.sql`**:
```sql
-- Создание базы данных ecom
CREATE DATABASE IF NOT EXISTS ecom;

USE ecom;

-- Таблица каталога товаров
CREATE TABLE IF NOT EXISTS ecom_offers
(
    snapshot_date Date DEFAULT today(),
    offer_id      UInt64,
    price         Float64,
    seller_id     UInt64,
    category_id   UInt32,
    vendor        String
)
ENGINE = ReplacingMergeTree(snapshot_date)
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (category_id, offer_id);

-- Таблица сырых событий
CREATE TABLE IF NOT EXISTS raw_events
(
    Hour            DateTime,
    DeviceTypeName  LowCardinality(String),
    ApplicationName LowCardinality(String),
    OSName          LowCardinality(String),
    ProvinceName    LowCardinality(String),
    ContentUnitID   UInt64
)
ENGINE = MergeTree
PARTITION BY toDate(Hour)
ORDER BY (Hour, ContentUnitID);
```

### Материализованные представления

```sql
-- Агрегация по категориям
CREATE MATERIALIZED VIEW IF NOT EXISTS catalog_by_category_mv
ENGINE = SummingMergeTree
PARTITION BY category_id
ORDER BY category_id
AS
SELECT
    category_id,
    count() AS offers_cnt
FROM ecom_offers
GROUP BY category_id;

-- Агрегация по брендам и категориям
CREATE MATERIALIZED VIEW IF NOT EXISTS catalog_by_brand_mv
ENGINE = SummingMergeTree
PARTITION BY vendor
ORDER BY (vendor, category_id)
AS
SELECT
    vendor,
    category_id,
    count() AS offers_cnt
FROM ecom_offers
GROUP BY vendor, category_id;

-- Сводка событий по товарам
CREATE MATERIALIZED VIEW IF NOT EXISTS offer_events_mv
ENGINE = SummingMergeTree
PARTITION BY toDate(Hour)
ORDER BY (offer_id)
AS
SELECT
    toDate(r.Hour) AS event_date,
    e.offer_id     AS offer_id,
    e.category_id  AS category_id,
    e.vendor       AS vendor,
    count()        AS events_cnt
FROM raw_events AS r
INNER JOIN ecom_offers AS e
    ON r.ContentUnitID = e.offer_id
GROUP BY event_date, offer_id, category_id, vendor;
```

## Загрузка данных в ClickHouse

### Подключение к ClickHouse

```bash
# Вход в интерактивную консоль ClickHouse
docker exec -it clickhouse clickhouse-client
```

### Импорт каталога товаров

```sql
-- Переключаемся в базу ecom
USE ecom;

-- Отключаем обработку заголовков для CSV
SET input_format_with_names_use_header = 0;

-- Загрузка данных из CSV файла
INSERT INTO ecom_offers (offer_id, price, seller_id, category_id, vendor)
SELECT
    toUInt64(c2)  AS offer_id,    -- Преобразуем строку в число
    toFloat64(c3) AS price,
    toUInt64(c4)  AS seller_id,
    toUInt32(c5)  AS category_id,
    c6            AS vendor       -- Строковое поле без преобразования
FROM file('10ozon.csv', 'CSV')
WHERE c2 != 'offer_id';          -- Пропускаем строку заголовков
```

### Импорт журнала событий

```sql
-- Загрузка данных из Parquet файла
INSERT INTO raw_events
SELECT
    Hour,
    DeviceTypeName,
    ApplicationName,
    OSName,
    ProvinceName,
    ContentUnitID
FROM file('RawEvent.parquet', 'Parquet');
```

### Проверка загруженных данных

```sql
-- Количество записей в каталоге
SELECT count() AS total_offers FROM ecom_offers;

-- Количество событий
SELECT count() AS total_events FROM raw_events;

-- Просмотр первых 5 записей
SELECT * FROM ecom_offers LIMIT 5;
SELECT * FROM raw_events LIMIT 5;
```

## Аналитические запросы

### Сравнение производительности: сырые данные vs материализованные представления

**Запрос 1: Топ-20 категорий по количеству товаров**

```sql
-- Через материализованное представление (быстро)
SELECT
    category_id,
    offers_cnt
FROM catalog_by_category_mv
FINAL
ORDER BY offers_cnt DESC
LIMIT 20;

-- По сырым данным (медленнее)
SELECT
    category_id,
    count() AS offers_cnt
FROM ecom_offers
GROUP BY category_id
ORDER BY offers_cnt DESC
LIMIT 20;
```

**Запрос 2: Топ-30 брендов по количеству товаров**

```sql
-- Через MV
SELECT
    vendor,
    sum(offers_cnt) AS offers_cnt
FROM catalog_by_brand_mv
GROUP BY vendor
ORDER BY offers_cnt DESC
LIMIT 30;

-- По сырым данным
SELECT
    vendor,
    count() AS offers_cnt
FROM ecom_offers
GROUP BY vendor
ORDER BY offers_cnt DESC
LIMIT 30;
```

**Запрос 3: Среднее количество товаров на бренд в категории**

```sql
-- Оптимизированный вариант
SELECT
    category_id,
    avg(offers_cnt) AS avg_offers_per_brand
FROM catalog_by_brand_mv
GROUP BY category_id
ORDER BY avg_offers_per_brand DESC;

-- Базовый вариант
SELECT
    category_id,
    avg(offers_per_brand) AS avg_offers_per_brand
FROM (
    SELECT
        category_id,
        vendor,
        count() AS offers_per_brand
    FROM ecom_offers
    GROUP BY category_id, vendor
) AS brand_stats
GROUP BY category_id
ORDER BY avg_offers_per_brand DESC;
```

**Запрос 4: Товары без пользовательских событий (потери в воронке)**

```sql
-- Используя JOIN с сырыми событиями
SELECT
    o.offer_id,
    o.category_id,
    o.vendor,
    o.price,
    'no_events' AS status
FROM ecom_offers AS o
LEFT JOIN (
    SELECT DISTINCT ContentUnitID AS offer_id
    FROM raw_events
) AS e ON o.offer_id = e.offer_id
WHERE e.offer_id IS NULL;

-- Используя материализованное представление событий
SELECT
    o.offer_id,
    o.category_id,
    o.vendor,
    o.price,
    'no_tracked_events' AS status
FROM ecom_offers AS o
LEFT JOIN offer_events_mv AS ev ON o.offer_id = ev.offer_id
WHERE ev.offer_id IS NULL;
```

##  Настройка мониторинга

### Конфигурация Prometheus

**`prometheus/prometheus.yml`**:
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'clickhouse'
    static_configs:
      - targets: ['clickhouse:9363']
    scrape_interval: 10s
    metrics_path: '/metrics'
```

### Активация метрик в ClickHouse

**`clickhouse/conf.d/prometheus.xml`**:
```xml
<clickhouse>
    <prometheus>
        <endpoint>/metrics</endpoint>
        <port>9363</port>
        <metrics>true</metrics>
        <events>true</events>
        <asynchronous_metrics>true</asynchronous_metrics>
        <errors>true</errors>
        <status_info>true</status_info>
    </prometheus>
</clickhouse>
```

### Настройка Grafana

#### Подключение источников данных

1. **Prometheus**
   - URL: `http://prometheus:9090`
   - Access: `Server (default)`

2. **ClickHouse**
   - Установите плагин: `grafana-clickhouse-datasource`
   - Host: `clickhouse:9000`
   - Database: `ecom`
   - Username: `default` (или создайте специального пользователя)

#### Создание пользователя для тестирования

```sql
-- Создание пользователя benchmark
CREATE USER IF NOT EXISTS benchmark IDENTIFIED WITH no_password;
GRANT SHOW TABLES, SELECT ON ecom.* TO benchmark;

-- Проверка прав
SHOW GRANTS FOR benchmark;
```

## Нагрузочное тестирование

### Подготовка Python-окружения

```bash
# Установка необходимых библиотек
pip install clickhouse-driver python-docx pandas numpy

# Проверка установки
python -c "import clickhouse_driver; print('ClickHouse driver version:', clickhouse_driver.__version__)"
```

### Запуск тестового скрипта

```bash
# Базовый запуск
python test.py

# С дополнительными параметрами
python test.py --iterations 50 --concurrency 10 --output report.docx
```

**Структура тестового скрипта** (`test.py`):
```python
"""
Нагрузочное тестирование ClickHouse:
1. Подключение к базе ecom
2. Выполнение набора аналитических запросов
3. Измерение времени выполнения
4. Генерация отчета
5. Мониторинг метрик через Prometheus
"""
```

### Ключевые метрики для отслеживания

Во время нагрузочного тестирования отслеживайте:

1. **QPS (Queries Per Second)** - количество запросов в секунду
2. **Query Latency** - время выполнения запросов
3. **Memory Usage** - потребление оперативной памяти
4. **CPU Utilization** - загрузка процессора
5. **Disk I/O** - активность чтения/записи

## Дашборды в Grafana

### Бизнес-метрики (ClickHouse как источник)

**Панель 1: Динамика каталога**
- Количество товаров по дням
- Новые товары за период
- Изменение ценовой политики

**Панель 2: Активность пользователей**
- События по типам устройств
- Географическое распределение
- Пиковые часы активности

**Панель 3: Эффективность каталога**
- Процент товаров с событиями
- Топ-10 категорий по вовлеченности
- Конверсия просмотров

### Технические метрики (Prometheus как источник)

**Панель 4: Производительность системы**
```promql
# Запросы в секунду
rate(ClickHouseProfileEvents_Query[1m])

# Среднее время выполнения
rate(ClickHouseProfileEvents_QueryTimeMicroseconds[1m]) / 
rate(ClickHouseProfileEvents_Query[1m]) / 1e6

# Активные соединения
ClickHouseMetrics_TCPConnection
```

**Панель 5: Использование ресурсов**
```promql
# Память
ClickHouseAsynchronousMetrics_MemoryResident

# Диск
ClickHouseAsynchronousMetrics_DiskUsed
ClickHouseAsynchronousMetrics_DiskTotal

# Сеть
rate(ClickHouseProfileEvents_NetworkSendBytes[1m])
```

## Операционные задачи

### Управление сервисами

```bash
# Проверка логов
docker compose logs -f clickhouse
docker compose logs -f prometheus
docker compose logs -f grafana

# Перезапуск конкретного сервиса
docker compose restart clickhouse

# Полная остановка с сохранением данных
docker compose down

# Очистка всех данных (внимание!)
docker compose down -v
```

### Резервное копирование данных

```bash
# Экспорт структуры БД
docker exec clickhouse clickhouse-client \
  --query "SHOW CREATE DATABASE ecom" > backup/ecom_schema.sql

# Экспорт данных (выборочно)
docker exec clickhouse clickhouse-client \
  --query "SELECT * FROM ecom.ecom_offers FORMAT Parquet" \
  > backup/ecom_offers_$(date +%Y%m%d).parquet
```

## Практические задания для отчета

1. **Сравнение производительности**
   - Замерьте время выполнения аналитических запросов с MV и без
   - Определите выигрыш в производительности для каждого типа запроса

2. **Анализ эффективности каталога**
   - Найдите категории с наибольшим/наименьшим покрытием событиями
   - Определите бренды с самой высокой вовлеченностью

3. **Мониторинг под нагрузкой**
   - Запустите нагрузочный тест на 100+ параллельных запросов
   - Отследите как меняются метрики в Grafana
   - Определите "узкие места" системы

4. **Оптимизация запросов**
   - Проанализируйте медленные запросы через `system.query_log`
   - Предложите оптимизации (индексы, материализованные представления)

## Критерии успешного выполнения

Все три сервиса запущены и доступны  
Данные загружены в ClickHouse (проверка: `SELECT count() FROM ecom_offers`)  
Материализованные представления созданы и заполнены  
Настроены источники данных в Grafana  
Созданы дашборды с бизнес-метриками и тех. мониторингом  
Проведено нагрузочное тестирование, собраны метрики  
Подготовлен отчет с анализом результатов  

## Полезные ссылки

- [ClickHouse Documentation](https://clickhouse.com/docs/)
- [Prometheus Querying](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Dashboard Tutorial](https://grafana.com/tutorials/)
- [ClickHouse для e-commerce](https://clickhouse.com/use-cases/e-commerce)

---

## 💡 Советы по выполнению

1. **Поэтапное выполнение** - не пытайтесь сделать всё сразу. Начните с запуска Docker, затем загрузки данных, потом настройки мониторинга.

2. **Документируйте проблемы** - если что-то не работает, сохраняйте логи ошибок и сообщения консоли.

3. **Экспериментируйте с запросами** - попробуйте модифицировать аналитические запросы под свои гипотезы.

4. **Сравнивайте производительность** - обратите внимание на разницу между простыми запросами и запросами к материализованным представлениям.

5. **Используйте мониторинг** - Grafana даёт отличную визуализацию того, как система ведёт себя под нагрузкой.

