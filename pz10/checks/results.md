# З10 — подготовка данных для Metabase

Студент: Лежень А.В., группа 233.

Источник: ClickHouse `retail_pz7`. Проверка доступности из Metabase проводится отдельно.

## fact rows and canonical revenue

```text
15	264
```

## aggregate rows and revenue

```text
13	264
```

## revenue by region

```text
Запад	153.5
Центр	110.5
```

## revenue by category

```text
Бакалея	6
Молочка	129
Напитки	111
Хлеб	18
```

**PASS:** fact contains 15 rows, fact/aggregate revenue is 264.00.

Важно: этот скрипт НЕ создаёт виджеты в Metabase и НЕ проверяет фильтр дашборда. Проверки интерфейса — вручную по README.
