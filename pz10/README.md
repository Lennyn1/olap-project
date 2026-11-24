# З10 — Дашборд Metabase над ClickHouse

**Дисциплина:** Оперативный анализ данных (OLAP)  
**Студент:** Лежень А.В. · **Группа:** 233  
**Проект:** Анализ розничных продаж (D1 — Розница)

## Цель

Создать в Metabase дашборд **«Розница — анализ выручки»** с четырьмя SQL-виджетами и единым фильтром периода. Источник — ClickHouse `retail_pz7`, не DuckDB. Сводка З09 используется только для графика по дням и магазинам.

| SQL | Виджет | Источник | Вопрос паспорта |
|---|---|---|---|
| `dashboards/01_total_revenue.sql` | Карточка Number: общая выручка | `fact_sales` | Каноническая мера |
| `dashboards/02_revenue_by_region.sql` | Столбцы: выручка по регионам | `fact_sales`, `dim_store` | Выручка по регионам |
| `dashboards/03_revenue_by_category.sql` | Столбцы: выручка по категориям | `fact_sales`, `dim_product` | Рейтинг категорий |
| `dashboards/04_daily_store_revenue.sql` | Линии: выручка по дням и магазинам | `agg_daily_store_sales` + `dim_store` | Динамика выручки |

**Канон:** `dashboards/canonical_metric.sql`, `SUM(amount)` по детальному `retail_pz7.fact_sales`. Без фильтров = **264.00**. При фильтре периода метрика на карточке рассчитывает тот же `SUM(f.amount)`, ограниченный датой через справочник `dim_date`; это *фильтрованная версия*, а не изменение определения меры.

## Шаг 0. Проверить исходные таблицы

Открыть Docker Desktop. В PowerShell:

```powershell
cd E:\OLAP
py -3.11 pz10/scripts/check_data.py
```

Ожидается `PASS`, 15 детальных строк и **264.00** в `fact_sales` и агрегате. Скрипт создаёт `pz10/checks/results.md`. Если отсутствует агрегат, запустить `py -3.11 pz9/scripts/build_aggregate.py`. Если отсутствует `retail_pz7`, сначала З07, затем З09.

## Шаг 1. Подключить Metabase к ClickHouse

Открыть <http://localhost:3000>. Metabase работает в Docker под именем `olap_metabase`, ClickHouse — `olap_clickhouse`.

1. Администрирование (**Admin settings**) → **Databases** → **Add database** → **ClickHouse**.
2. Если ClickHouse отсутствует в списке, установить **совместимый с Metabase v0.52.16 драйвер ClickHouse** в `E:\OLAP\Стенд\metabase\plugins\`, затем перезапустить контейнер `docker restart olap_metabase`. Файлы драйвера не нужно коммитить в Git.
3. Указать `Display name: OLAP retail_pz7`, `Host: clickhouse`, `Port: 8123`, `Database: retail_pz7`. **`localhost` здесь неправильный хост**: внутри Metabase это сам Metabase-контейнер.
4. Указать действительные учётные данные ClickHouse. **Не рассчитывать на `default` с пустым паролем**: он уже не прошёл HTTP-проверку на стенде (`Code: 516`). Сначала проверить сетевой доступ и права пользователя; диагностические команды приведены ниже.
5. Нажать **Save / Test connection** и убедиться, что Metabase видит `fact_sales`, `dim_date`, `dim_store`, `dim_product`, `agg_daily_store_sales`.

### Если ClickHouse отклоняет логин по HTTP (важно!)

Проверка с хоста (не меняет состояние ClickHouse):

```powershell
curl.exe "http://localhost:8123/?query=SELECT%201"
docker exec olap_clickhouse clickhouse-client --query "SELECT currentUser(), version()"
docker exec olap_clickhouse clickhouse-client --query "SHOW USERS"
```

Если `curl` сообщает `AUTHENTICATION_FAILED`, это подтверждает проблему сетевой авторизации, а не отсутствие данных. **Не удалять Docker volumes и не сбрасывать пароль `default`.** Рекомендуется создать отдельного пользователя Metabase только с `SELECT` на `retail_pz7.*`, используя учетную запись ClickHouse с правом управления пользователями. Например, если `CREATE USER` поддерживается текущей конфигурацией, в интерактивном клиенте (`docker exec -it olap_clickhouse clickhouse-client`) администратор выполняет SQL:

```sql
CREATE USER IF NOT EXISTS metabase_reader IDENTIFIED WITH sha256_password BY 'REPLACE_WITH_A_STRONG_PASSWORD';
GRANT SELECT ON retail_pz7.* TO metabase_reader;
```

Заменить пароль своим уникальным значением; **не сохранять его в GitHub**. При `ACCESS_DENIED` / отсутствии права `CREATE USER` остановиться и проверить конфигурацию пользователей Docker; не изменять рабочий `default` наугад. Проверьте учётные данные по HTTP, затем используйте их в Metabase. Если `default` локально входит без пароля, это не доказывает, что он имеет сетевой доступ. При необходимости отдельного пользователя можно задать через `users.d` конфигурации ClickHouse и перезапуск контейнера; это отдельная настройка сервера.

## Шаг 2. Создать четыре вопроса (Native SQL)

В Metabase: **New → SQL query**, выбрать подключение `OLAP retail_pz7`, вставить содержимое каждого файла из `dashboards/` (кроме `canonical_metric.sql`), нажать **Run**, выбрать визуализацию и **Save**. Имена вопросов:

1. `Z10 · Общая выручка` → **Number**.
2. `Z10 · Выручка по регионам` → **Bar**: X = `region`, Y = `total_revenue`.
3. `Z10 · Выручка по категориям` → **Bar**: X = `category`, Y = `total_revenue`.
4. `Z10 · Выручка по дням и магазинам` → **Line**: X = `sale_date`, Y = `total_revenue`, series / breakout = `store_name` (если доступен в визуализации).

**Даты:** в каждом SQL есть опциональный параметр `[[WHERE {{date_filter}}]]`. При первом создании вопроса Metabase попросит задать тип переменной `date_filter`. Выбрать **Field Filter**, привязать к `dim_date.full_date` и указать SQL alias `d` (в настройках переменной, если интерфейс предлагает `Table and field alias`). Для этого во всех четырёх запросах намеренно использован `INNER JOIN retail_pz7.dim_date AS d`. При варианте Field Filter нельзя вручную писать `d.full_date = {{date_filter}}`: Metabase сам вставляет условие. SQL-запросы можно выполнять и без даты: необязательный блок `[[...]]` пропускается.

## Шаг 3. Создать дашборд и фильтр

1. **New → Dashboard** → название **«Розница — анализ выручки»** → **Save**.
2. В режиме редактирования добавить все четыре сохранённых вопроса.
3. **Add a filter → Time / Date** (фильтр периода) → название «Период».
4. Связать фильтр с переменной `date_filter` **каждого** из четырёх Native SQL вопросов. Проверьте, что на каждой карточке связь активна, затем сохраните дашборд.
5. Без фильтра: KPI **264.00**. Выбрать январь 2024: KPI и диаграммы должны измениться согласованно. Проверить снятие фильтра и возврат к **264.00**.

Если Metabase не позволяет связать SQL-вопрос с фильтром: откройте сохранённый вопрос, проверьте тип `date_filter = Field Filter`, привязку к `dim_date.full_date` и alias `d`, затем повторно добавьте вопрос на дашборд. Не выдавайте фильтр за рабочий, пока изменение периода не меняет данные.

## Шаг 4. Сохранить доказательства

SQL всех виджетов уже находится в `pz10/dashboards/`. Результаты проверки ClickHouse — `pz10/checks/results.md`. По возможности сохранить скрин дашборда `pz10/checks/dashboard.png` и/или локальную ссылку `http://localhost:3000/dashboard/...` в `pz10/checks/dashboard_check.md` (локальный URL доступен только на вашем ПК). Отметить выполненные пункты из `pz10/checks/README.md`.

```powershell
git add pz10
git commit -m "Z10: Metabase ClickHouse revenue dashboard"
git push
```

## Что говорить на зачёте

- Metabase строит графики из ClickHouse, не из DuckDB.
- Каноническая метрика — `SUM(amount)` по факту; график по дням и магазинам использует пересчитанную сводку З09.
- Зерно факта — строка продажи; зерно сводки — день × магазин.
- Период — срез, применяемый к каждому вопросу; фильтр должен действовать одинаково.

**Важно:** наличие файлов в GitHub не заменяет реально созданный дашборд в Metabase. На зачёте показываем работающую страницу в `localhost:3000`.
