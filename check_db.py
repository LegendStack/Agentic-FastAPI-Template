import sqlite3


def check_db():
    conn = sqlite3.connect("checkpoints.db")
    cursor = conn.cursor()

    print("--- Tables in checkpoints.db ---")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for table in tables:
        print(f"Table: {table[0]}")

    print("\n--- Searching for 'coffee' or 'Jira Sync' in checkpoints ---")
    cursor.execute("SELECT thread_id, checkpoint FROM checkpoints")
    rows = cursor.fetchall()
    found = False
    for thread_id, checkpoint_blob in rows:
        # Checkpoint is usually a binary blob (pickled or JSON)
        try:
            # Try to decode as string first to see if text exists
            text = str(checkpoint_blob).lower()
            if "coffee" in text or "jira sync" in text:
                print(f"Found match in Thread: {thread_id}")
                found = True
        except:
            pass

    if not found:
        print("No matches found in checkpoints.")

    conn.close()


if __name__ == "__main__":
    check_db()
