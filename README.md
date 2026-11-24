# Remote IT Vacancies ETL

Пет-проект: ETL-пайплайн для сбора IT-вакансий, пересчёта зарплат в BYN по курсу Нацбанка РБ и загрузки данных в PostgreSQL.

## Что делает скрипт

1. **Extract**
   - Тянет свежие вакансии из API [Remote OK](https://remoteok.com) (используется `curl_cffi`, так как обычный `requests` режется по TLS-отпечатку).
   - Забирает актуальные курсы валют с API Нацбанка РБ.
   - Пишет логи работы и сетевые ошибки в консоль и в `etl.log`.

2. **Transform**
   - Отбирает профильные IT-вакансии (`data`, `python`, `sql`, `engineer`, `analyst`).
   - Убирает нулевые зарплаты (`0` -> `NaN`), считает среднюю вилку в долларах и переводит её в BYN.
   - Приводит даты к нормальному формату, склеивает теги в строку и чистит дубли по `id`.

3. **Load**
   - Заливает очищенную таблицу в `remote_vacancies` (PostgreSQL).
   - Пересобирает два представления (`VIEW`) для быстрой аналитики:
     - `company_stats_v` — статистика по количеству вакансий и средней зарплате в разрезе компаний.
     - `stack_demand_v` — разбивка вакансий и зарплат по основному стеку (`Python`, `SQL`, `DevOps`, `AI/ML`).

## Стек

- Python 3 (`pandas`, `curl_cffi`, `python-dotenv`)
- PostgreSQL (`SQLAlchemy`, `psycopg2`)

## Как запустить

1. Установить зависимости:
   ```bash
   pip install -r requirements.txt
   ```

2. Создать в PostgreSQL пустую базу `vacancies_etl`.

3. Переименовать `config.env.example` в `config.env` и прописать свои креды для подключения к БД:
   ```env
   DB_URL=postgresql+psycopg2://postgres:password@localhost:5432/vacancies_etl
   ```

4. Запустить пайплайн:
   ```bash
   python main.py
   ```

---
Данные о вакансиях получены с [Remote OK](https://remoteok.com).
