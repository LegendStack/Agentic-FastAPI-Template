
import sqlite3
import json

def dump_thread(thread_id):
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    
    print(f"Dumping messages for thread: {thread_id}")
    
    # Query messages
    cursor.execute("SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at", (thread_id,))
    messages = cursor.fetchall()
    
    if not messages:
        print("No messages found in messages table. Checking checkpoints table...")
        # LangGraph checkpoints are in 'checkpoints' table
        cursor.execute("SELECT thread_id, checkpoint_id, checkpoint FROM checkpoints WHERE thread_id = ?", (thread_id,))
        checkpoints = cursor.fetchall()
        for tid, cid, cp in checkpoints:
            print(f"--- Checkpoint {cid} ---")
            # The checkpoint is usually a binary blob or JSON
            try:
                # Try simple print
                print(str(cp)[:500])
            except:
                print("Could not decode checkpoint blob")
    else:
        for role, content in messages:
            print(f"\n--- {role} ---")
            print(content)

    conn.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        dump_thread(sys.argv[1])
    else:
        print("Usage: python dump_db.py <thread_id>")
