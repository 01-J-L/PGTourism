from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail # Make sure this is imported
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
import os

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail() # Initialize Flask-Mail

def create_app():
    load_dotenv()

    app = Flask(__name__)

    # Config
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or "dev_key_123"
    
    # Database Config
    db_url = os.getenv("SQLALCHEMY_DATABASE_URI") or "sqlite:///dev.db"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # --- EMAIL CONFIGURATION ---
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true' # Ensure boolean
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    sender_email = os.getenv('MAIL_USERNAME')
    app.config['MAIL_DEFAULT_SENDER'] = ("Padre Garcia Tourism", sender_email)
    # ---------------------------

    # --- FILE UPLOAD CONFIG ---
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    # -------------------------------

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app) # Initialize mail with the app
    
    login_manager.login_view = "auth.login"

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
   
    from .views import views
    from .auth import auth
    app.register_blueprint(views)
    app.register_blueprint(auth)

    # Initialize DB and Create Super Admin
    with app.app_context():
        db.create_all()
        
        # Auto-create Super Admin
        admin = User.query.filter_by(email="super-admin").first()
        if not admin:
            new_admin = User(
                email="super-admin",
                first_name="Super Administrator",
                password=generate_password_hash("admin123@", method='pbkdf2:sha256'),
                is_admin=True,
                is_super_admin=True 
            )
            db.session.add(new_admin)
            db.session.commit()
            

    return app