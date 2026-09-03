import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

connection = None

try:
    connection = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            current_database(),
            current_user,
            version();
        """
    )

    result = cursor.fetchone()

    print("\nPostgreSQL connection successful.")
    print("Database:", result[0])
    print("User:", result[1])
    print("PostgreSQL:", result[2])

    cursor.close()

except Exception as error:
    print("\nPostgreSQL connection failed.")
    print(error)

finally:
    if connection:
        connection.close()
        print("\nConnection closed.")