from webapp import create_app, db

# This script ensures the new 'history_media' table is created
# in your database without affecting existing data.

app = create_app()

with app.app_context():
    print("Connecting to the database and creating new tables if they don't exist...")
    db.create_all()
    print("[SUCCESS] Database schema is up to date. The 'history_media' table has been created.")