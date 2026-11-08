
from werkzeug.security import generate_password_hash
from db import get_db_connection


# Development-only demo accounts
users = [
    ("john@gmail.com", "John@123"),
    ("emily@gmail.com", "Emily@123"),
    ("james@gmail.com", "James@123"),
    ("daniel@gmail.com", "Daniel@123"),
    ("sarah@gmail.com", "Sarah@123")
]


def update_passwords():
    connection = get_db_connection()

    try:
        with connection.cursor() as cursor:
            for email, password in users:

                # Convert the plain password into a secure hash
                password_hash = generate_password_hash(password)

                # Save the hash in PostgreSQL
                cursor.execute(
                    """
                    UPDATE users
                    SET password_hash = %s
                    WHERE email = %s
                    """,
                    (password_hash, email)
                )

                if cursor.rowcount == 1:
                    print(f"Password updated for {email}")
                else:
                    print(f"User not found: {email}")

        connection.commit()
        print("\nAll password updates completed.")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    update_passwords()
