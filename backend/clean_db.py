import os
import sqlite3

db_path = "backend/app.db"
if not os.path.exists(db_path):
    db_path = "app.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for table in ["comments", "social_posts", "submissions", "course_members", "exercises", "courses"]:
        try:
            cur.execute(f"DELETE FROM {table}")
        except Exception as e:
            print(f"Error {table}: {e}")
    
    # Chỉ giữ lại 2 tài khoản sạch
    cur.execute("DELETE FROM users WHERE username NOT IN ('coach_hoang', 'student_nam')")
    conn.commit()

    print("SQLite Cleaned Successfully:")
    print("Users:", cur.execute("SELECT id, username, role FROM users").fetchall())
    print("Exercises:", cur.execute("SELECT count(*) FROM exercises").fetchone()[0])
    print("Courses:", cur.execute("SELECT count(*) FROM courses").fetchone()[0])
    conn.close()
