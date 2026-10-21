from app.database import engine
from sqlalchemy import text

def add_live_image_url_column():
    """Add live_image_url column to users table if it doesn't exist"""
    with engine.connect() as connection:
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='live_image_url'
        """)
        result = connection.execute(check_query)
        
        if result.fetchone():
            print("[OK] Column 'live_image_url' already exists in users table")
            return
        
        alter_query = text("""
            ALTER TABLE users 
            ADD COLUMN live_image_url TEXT
        """)
        connection.execute(alter_query)
        connection.commit()
        print("[OK] Successfully added 'live_image_url' column to users table")

if __name__ == "__main__":
    try:
        add_live_image_url_column()
    except Exception as e:
        print(f"[ERROR] {e}")
        print("\nYou can also run this SQL command directly in your PostgreSQL database:")
        print("ALTER TABLE users ADD COLUMN live_image_url TEXT;")
