# З08 — Запросы и ключи ClickHouse

**Студент:** Лежень А.В.  
**Группа:** 233  
**Домен:** D1 — Розница  
**Главная метрика:** `SUM(amount)`, контрольное значение на sample: `264.00`.

## Цель

Выполнить один и тот же набор аналитических SQL-запросов в DuckDB и ClickHouse, проверить равенство ответов и объяснить `ORDER BY` и решение по `PARTITION BY`.

## Входные данные

- DuckDB: `pz3/retail_local.duckdb` — таблицы З03/З05.
- ClickHouse: база `retail_pz7` из З07 (четыре таблицы MergeTree).
- SQL DuckDB: `pz4/sql/analytics.sql` и `pz4/sql/canonical_metric.sql`.
- Аналогичные SQL для ClickHouse: `pz8/sql/analytics_clickhouse.sql` и `pz8/sql/canonical_metric_clickhouse.sql`.
- Docker Desktop, контейнер `olap_clickhouse`; Python 3.11 с установленным `duckdb`.

**Важно:** наш ClickHouse допускает `clickhouse-client` внутри контейнера, но внешнее HTTP-подключение пользователя `default` требует другой авторизации. Скрипт использует `docker exec` и не требует пароля в репозитории.

## Запуск в PowerShell (Windows 10)

```powershell
cd E:\OLAP
py -3.11 pz8/scripts/compare_engines.py
```

Скрипт последовательно запускает **эталон метрики и 6 запросов З04** (slice, roll-up по месяцу и году, dice, оконную долю/ранг, топ-5 магазинов). Для каждого сравниваются колонки и значения результата между DuckDB и ClickHouse (денежные числа сравниваются с точностью 2 знака). Отдельно сравнивается фильтр `date_id = 20240101` как эксперимент с ведущей колонкой `ORDER BY` и, по возможности, сохраняется результат `EXPLAIN indexes = 1`.

Результат выполнения сохраняется в `pz8/checks/results.md` и выводится кратко в терминале. **Если есть расхождение, скрипт завершится с кодом 1 и не сформирует итоговый отчёт.** Скрипт только читает данные и не пересоздаёт ни одну базу.

## Ручной запуск эталонного запроса на ClickHouse

```powershell
docker exec olap_clickhouse clickhouse-client --query "SELECT SUM(amount) AS total_revenue FROM retail_pz7.fact_sales"
```

Ожидаемый контрольный результат на исходном sample — `264.00` (в консоли формат вывода может быть `264`).

## Пояснение ORDER BY и PARTITION BY

См. [`notes/partition_decision.md`](notes/partition_decision.md). В fact применяется `ORDER BY (date_id, store_id, product_id)` — порядок и первичный разреженный индекс, **не уникальный ключ**. Месячная партиция на 15 записях не нужна. Это осознанное ограничение с ценой отказа, которую следует добавить в `pz2/cut.md` из [`notes/cut_addition.md`](notes/cut_addition.md).

## Что сдать

- `sql/analytics_clickhouse.sql` — шесть запросов для ClickHouse.
- `sql/canonical_metric_clickhouse.sql` — эталон ClickHouse, соответствующий эталону DuckDB.
- `scripts/compare_engines.py` — воспроизводимый прогон обоих движков.
- `checks/results.md` — фактическая сверка, появится после успешного запуска.
- `notes/partition_decision.md` — обоснование `ORDER BY` и отказа от партиции.
- Обновлённый `pz2/cut.md` — пункт о цене отказа от партиционирования.

## Отличие от З06

В З06 SCD2 был реализован как отдельная учебная демонстрация. Здесь сравнивается **основная невeрсионированная витрина** З03 и З07, поэтому метрика и зерно остаются прежними.
