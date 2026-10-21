from app.database import engine
from sqlalchemy import text, inspect

def verify_column():
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    print("Columns in 'users' table:")
    for col in columns:
        marker = " <-- EXISTS" if col == "live_image_url" else ""
        print(f"  - {col}{marker}")
    
    if "live_image_url" in columns:
        print("\n[OK] live_image_url column exists!")
    else:
        print("\n[ERROR] live_image_url column NOT found!")
        print("Run: python add_live_image_url_column.py")

if __name__ == "__main__":
    verify_column()
