from curl_cffi import requests
import logging
import pandas as pd
from numpy import nan
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv("config.env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("etl.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)


def extract_vacancies():
    url = "https://remoteok.com/api"
    try:
        response = requests.get(url, impersonate="chrome", timeout=20)
        response.raise_for_status()
        if not response.text.strip():
            raise ValueError("RemoteOK вернул пустой ответ (возможен rate limit)")
        items = response.json()[1:]
        logging.info(f"Загружено вакансий с RemoteOK: {len(items)}")
        return items
    except Exception as e:
        logging.error(f"Ошибка при получении вакансий с RemoteOK: {e}")
        raise


def extract_rates():
    url = "https://api.nbrb.by/exrates/rates"
    params = {"periodicity": 0}
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        rates = {"BYN": 1.0}
        for item in response.json():
            rates[item["Cur_Abbreviation"]] = item["Cur_OfficialRate"] / item["Cur_Scale"]
        logging.info(f"Загружено {len(rates)} курсов валют. Курс USD: {rates.get('USD')}")
        return rates
    except Exception as e:
        logging.error(f"Ошибка при получении курсов валют НБ РБ: {e}")
        raise


def transform_vacancies(raw_vacancies, rates):
    df = pd.DataFrame(raw_vacancies)
    cols = ["id", "position", "company", "tags", "salary_min", "salary_max", "date"]
    df = df[cols].copy()

    keywords = ("data", "python", "sql", "engineer", "analyst")
    df = df[df["position"].str.lower().str.contains("|".join(keywords), na=False)]

    df["salary_min"] = df["salary_min"].replace(0, nan)
    df["salary_max"] = df["salary_max"].replace(0, nan)

    df["salary_avg_usd"] = ((df["salary_min"] + df["salary_max"]) / 2).round(2)
    df["salary_avg_byn"] = (df["salary_avg_usd"] * rates["USD"]).round(2)

    df["published_at"] = pd.to_datetime(df["date"]).dt.date
    df["tags"] = df["tags"].apply(lambda x: ", ".join(x) if isinstance(x, list) else "")

    final_cols = ["id", "position", "company", "tags", "salary_avg_byn", "published_at"]
    df = df[final_cols].drop_duplicates(subset=["id"])

    logging.info(f"После очистки осталось {len(df)} профильных вакансий.")
    return df


def load_to_db(df):
    engine = create_engine(os.getenv("DB_URL"))
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS remote_vacancies CASCADE;"))

    df.to_sql("remote_vacancies", con=engine, if_exists="replace", index=False)
    logging.info(f"Загружено {len(df)} строк в таблицу 'remote_vacancies'")
    
    with engine.begin() as conn:
        conn.execute(text(
        """
        CREATE OR REPLACE VIEW company_stats_v AS 
        SELECT company, COUNT(*) AS vacancies_count,
        ROUND(CAST(AVG(salary_avg_byn) AS numeric), 2) AS company_avg_salary
        FROM remote_vacancies
        GROUP BY company
        ORDER BY vacancies_count DESC;
        """))
        conn.execute(text(
        """
        CREATE OR REPLACE VIEW stack_demand_v AS
        SELECT
            CASE
                WHEN LOWER(tags) LIKE '%python%' THEN 'Python'
                WHEN LOWER(tags) LIKE '%sql%' THEN 'SQL'
                WHEN LOWER(tags) LIKE '%devops%' THEN 'DevOps'
                WHEN LOWER(tags) LIKE '%ai%' OR LOWER(tags) LIKE '%ml%' THEN 'AI / ML'
                ELSE 'Other IT'
            END AS tech_stack,
            COUNT(*) AS vacancies_count,
            ROUND(CAST(AVG(salary_avg_byn) AS numeric), 2) AS stack_avg_salary
        FROM remote_vacancies
        GROUP BY tech_stack
        ORDER BY vacancies_count DESC;
        """))

if __name__ == "__main__":
    raw_vacancies = extract_vacancies()
    rates = extract_rates()
    clean_df = transform_vacancies(raw_vacancies, rates)
    load_to_db(clean_df)