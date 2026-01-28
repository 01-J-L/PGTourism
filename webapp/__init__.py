from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
import os

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    load_dotenv()

    app = Flask(__name__)

    # Config
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or "dev_key_123"
    
    # Database Config
    db_url = os.getenv("SQLALCHEMY_DATABASE_URI") or "sqlite:///dev.db"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # --- NEW: FILE UPLOAD CONFIG ---
    # Define where to save images: /webapp/static/uploads
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    
    # Create the folder if it doesn't exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    # -------------------------------

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
   
    from .views import views
    from .auth import auth
    app.register_blueprint(views)
    app.register_blueprint(auth)

    with app.app_context():
        db.create_all()
        
        # Auto-create Admin
        admin = User.query.filter_by(email="admin").first()
        if not admin:
            new_admin = User(
                email="admin",
                first_name="Administrator",
                password=generate_password_hash("admin123", method='pbkdf2:sha256'),
                is_admin=True
            )
            db.session.add(new_admin)
            db.session.commit()

    return app