from pathlib import Path
import os

import pandas as pd
import psycopg2

from dotenv import load_dotenv
from psycopg2.extras import execute_values


# ============================================================
# CONFIG
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

NLP_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "complaint_nlp_features.csv"
)

load_dotenv(
    PROJECT_ROOT / ".env"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_env(*names, default=None):
    """
    Return first available environment variable.
    Supports common naming conventions.
    """

    for name in names:
        value = os.getenv(name)

        if value:
            return value

    return default


def get_connection():

    host = get_env(
        "DB_HOST",
        "POSTGRES_HOST",
        "PGHOST",
        default="localhost",
    )

    port = get_env(
        "DB_PORT",
        "POSTGRES_PORT",
        "PGPORT",
        default="5432",
    )

    database = get_env(
        "DB_NAME",
        "POSTGRES_DB",
        "PGDATABASE",
    )

    user = get_env(
        "DB_USER",
        "POSTGRES_USER",
        "PGUSER",
    )

    password = get_env(
        "DB_PASSWORD",
        "POSTGRES_PASSWORD",
        "PGPASSWORD",
    )

    if not database:
        raise ValueError(
            "Database name not found in .env."
        )

    if not user:
        raise ValueError(
            "Database user not found in .env."
        )

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=database,
        user=user,
        password=password,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "\n========================================"
    )
    print(
        "NLP POSTGRESQL LOADER"
    )
    print(
        "========================================"
    )

    if not NLP_FILE.exists():
        raise FileNotFoundError(
            f"NLP feature file not found:\n"
            f"{NLP_FILE}"
        )

    print(
        f"\nReading:\n{NLP_FILE}"
    )

    df = pd.read_csv(
        NLP_FILE,
        dtype={
            "complaint_id": str,
            "company": str,
            "product": str,
            "state": str,
            "sentiment_label": str,
            "topic_name": str,
            "topic_keywords": str,
            "urgency_reason": str,
        },
    )

    print(
        f"\nRows read: {len(df):,}"
    )


    # ========================================================
    # TYPE CLEANUP
    # ========================================================

    df["date_received"] = pd.to_datetime(
        df["date_received"],
        errors="coerce",
    ).dt.date

    df["month_start_date"] = pd.to_datetime(
        df["month_start_date"],
        errors="coerce",
    ).dt.date

    df["sentiment_score"] = pd.to_numeric(
        df["sentiment_score"],
        errors="coerce",
    )

    df["topic_id"] = pd.to_numeric(
        df["topic_id"],
        errors="coerce",
    ).astype("Int64")

    df["urgency_flag"] = pd.to_numeric(
        df["urgency_flag"],
        errors="coerce",
    ).fillna(0).astype(int)

    df["narrative_word_count"] = pd.to_numeric(
        df["narrative_word_count"],
        errors="coerce",
    ).astype("Int64")


    # ========================================================
    # QUALITY CHECK
    # ========================================================

    print(
        "\n========================================"
    )
    print(
        "PRE-LOAD QUALITY CHECK"
    )
    print(
        "========================================"
    )

    print(
        f"Rows: {len(df):,}"
    )

    print(
        f"Unique complaint IDs: "
        f"{df['complaint_id'].nunique():,}"
    )

    print(
        f"Duplicate complaint IDs: "
        f"{df['complaint_id'].duplicated().sum():,}"
    )

    print(
        f"Missing complaint IDs: "
        f"{df['complaint_id'].isna().sum():,}"
    )

    print(
        f"Distinct topics: "
        f"{df['topic_id'].nunique():,}"
    )

    print(
        "\nTopic distribution:"
    )

    print(
        df["topic_name"]
        .value_counts()
        .to_string()
    )


    if df["complaint_id"].duplicated().any():
        raise ValueError(
            "Duplicate complaint IDs found. "
            "Load stopped."
        )


    # ========================================================
    # CONNECT
    # ========================================================

    conn = get_connection()

    try:

        cursor = conn.cursor()

        print(
            "\nConnected to PostgreSQL."
        )


        # ====================================================
        # CREATE RAW SCHEMA
        # ====================================================

        cursor.execute(
            """
            create schema if not exists raw;
            """
        )


        # ====================================================
        # CREATE TABLE
        # ====================================================

        cursor.execute(
            """
            create table if not exists
            raw.complaint_nlp_features (

                complaint_id text primary key,

                date_received date,

                month_start_date date,

                company text,

                product text,

                state text,

                sentiment_score numeric,

                sentiment_label text,

                topic_id integer,

                topic_name text,

                topic_keywords text,

                urgency_flag integer,

                urgency_reason text,

                narrative_word_count integer,

                loaded_at timestamp
                    default current_timestamp
            );
            """
        )


        # ====================================================
        # REPLACE DEVELOPMENT DATASET
        # ====================================================

        cursor.execute(
            """
            select count(*)
            from raw.complaint_nlp_features;
            """
        )

        existing_rows = cursor.fetchone()[0]

        print(
            f"\nExisting NLP rows: "
            f"{existing_rows:,}"
        )

        print(
            "Clearing existing NLP table..."
        )

        cursor.execute(
            """
            truncate table
            raw.complaint_nlp_features;
            """
        )


        # ====================================================
        # PREPARE LOAD
        # ====================================================

        columns = [
            "complaint_id",
            "date_received",
            "month_start_date",
            "company",
            "product",
            "state",
            "sentiment_score",
            "sentiment_label",
            "topic_id",
            "topic_name",
            "topic_keywords",
            "urgency_flag",
            "urgency_reason",
            "narrative_word_count",
        ]

        load_df = df[columns].copy()

        load_df = load_df.astype(
            object
        ).where(
            pd.notnull(load_df),
            None,
        )

        records = list(
            load_df.itertuples(
                index=False,
                name=None,
            )
        )


        # ====================================================
        # INSERT
        # ====================================================

        print(
            f"Loading {len(records):,} "
            f"NLP records into PostgreSQL..."
        )

        insert_sql = """
            insert into raw.complaint_nlp_features (

                complaint_id,
                date_received,
                month_start_date,
                company,
                product,
                state,
                sentiment_score,
                sentiment_label,
                topic_id,
                topic_name,
                topic_keywords,
                urgency_flag,
                urgency_reason,
                narrative_word_count

            )
            values %s
        """

        execute_values(
            cursor,
            insert_sql,
            records,
            page_size=1000,
        )


        # ====================================================
        # VALIDATION
        # ====================================================

        cursor.execute(
            """
            select

                count(*) as total_rows,

                count(
                    distinct complaint_id
                ) as unique_complaints,

                count(
                    distinct topic_id
                ) as distinct_topics

            from raw.complaint_nlp_features;
            """
        )

        (
            total_rows,
            unique_complaints,
            distinct_topics,
        ) = cursor.fetchone()


        print(
            "\n========================================"
        )
        print(
            "POSTGRESQL NLP VALIDATION"
        )
        print(
            "========================================"
        )

        print(
            f"Total rows: "
            f"{total_rows:,}"
        )

        print(
            f"Unique complaint IDs: "
            f"{unique_complaints:,}"
        )

        print(
            f"Distinct topics: "
            f"{distinct_topics:,}"
        )


        cursor.execute(
            """
            select

                topic_name,

                count(*) as complaint_count,

                round(
                    avg(sentiment_score),
                    4
                ) as avg_sentiment,

                sum(urgency_flag)
                    as urgent_complaints

            from raw.complaint_nlp_features

            group by topic_name

            order by complaint_count desc;
            """
        )

        print(
            "\nTopic validation:"
        )

        for row in cursor.fetchall():

            print(
                f"{row[0]} | "
                f"{row[1]:,} complaints | "
                f"sentiment={row[2]} | "
                f"urgent={row[3]}"
            )


        # ====================================================
        # COMMIT
        # ====================================================

        conn.commit()

        print(
            "\nLoad completed successfully."
        )

        print(
            "Transaction committed."
        )


    except Exception:

        conn.rollback()

        print(
            "\nLoad failed. "
            "Transaction rolled back."
        )

        raise


    finally:

        conn.close()

        print(
            "Database connection closed."
        )


if __name__ == "__main__":
    main()