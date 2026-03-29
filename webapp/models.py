from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func

# ==========================================
#               USER MODEL
# ==========================================

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(150))
    is_admin = db.Column(db.Boolean, default=False)       # Regular Admin
    is_super_admin = db.Column(db.Boolean, default=False) # Super Admin

# ==========================================
#           SITE CONTENT (TEXT/IMAGES)
# ==========================================

class SiteContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)

# ==========================================
#           TOURISM & MODULES
# ==========================================

class TouristSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, nullable=True)
    link_url = db.Column(db.String(500), nullable=True) 
    order = db.Column(db.Integer, default=0)

class Ordinance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    file_url = db.Column(db.String(500), nullable=True)
    date_added = db.Column(db.DateTime(timezone=True), server_default=func.now())

class FestivalEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(20), nullable=False)
    day = db.Column(db.String(10), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)

# ==========================================
#           HISTORY & GOVERNMENT
# ==========================================

class Mayor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(150), nullable=True)
    years = db.Column(db.String(50), nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    description = db.Column(db.Text, nullable=True)

class Barangay(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    captain_name = db.Column(db.String(150), nullable=True)
    captain_image = db.Column(db.String(500), nullable=True)
    map_url = db.Column(db.Text, nullable=True)

# ==========================================
#           FOOTER & CONTACTS
# ==========================================

class SocialLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    icon = db.Column(db.String(50), nullable=False)

class FooterLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)

class EmergencyHotline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    number = db.Column(db.String(50), nullable=False)

# ==========================================
#           COMMERCE & LIFESTYLE
# ==========================================

class CommercialEstablishment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    map_url = db.Column(db.String(500), nullable=True)

class Accommodation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    map_url = db.Column(db.String(500), nullable=True)

class FinancialInstitution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=True)

# === UPDATED MAJOR ATTRACTION AND NEW MEDIA TABLE ===
class MajorAttraction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    tag = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True) # Short description for cards
    location = db.Column(db.String(150), nullable=True)
    map_url = db.Column(db.String(500), nullable=True)
    media_url = db.Column(db.String(500), nullable=True) # Hero/Featured media
    full_content = db.Column(db.Text, nullable=True) # Main article text
    
    # Relationship to media items
    media_items = db.relationship('AttractionMedia', backref='attraction', lazy=True, cascade="all, delete-orphan")

class AttractionMedia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attraction_id = db.Column(db.Integer, db.ForeignKey('major_attraction.id'), nullable=False)
    media_url = db.Column(db.String(500), nullable=False)
    media_type = db.Column(db.String(20), nullable=False) # 'image', 'video', 'file'
    caption = db.Column(db.String(300), nullable=True)
# ====================================================

class FoodDish(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    tagline = db.Column(db.String(150), nullable=True)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    link_url = db.Column(db.String(500), nullable=True)

class SweetTreat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    link_url = db.Column(db.String(500), nullable=True)

class FestivalGalleryImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(500), nullable=False)
    link_url = db.Column(db.String(500), nullable=True)
    caption = db.Column(db.String(200), nullable=True)

class HistoryMedia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # A key to identify which history section this media belongs to (e.g., 'padre_garcia')
    section_key = db.Column(db.String(100), nullable=False, index=True)
    media_url = db.Column(db.String(500), nullable=False)
    media_type = db.Column(db.String(20), nullable=False)  # 'image' or 'video'
    caption = db.Column(db.String(300), nullable=True)
    order = db.Column(db.Integer, default=0)