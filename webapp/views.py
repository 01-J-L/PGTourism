from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from . import db
from .models import SiteContent, TouristSpot
import os
import uuid

views = Blueprint("views", __name__)

# --- HELPER: SAVE IMAGE ---
def save_image(file):
    if not file or file.filename == '':
        return None
    
    filename = secure_filename(file.filename)
    unique_filename = str(uuid.uuid4()) + "_" + filename
    
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(file_path)
    
    return f"static/uploads/{unique_filename}"

def get_content(key, default=""):
    content = SiteContent.query.filter_by(key=key).first()
    return content.value if content else default

# --- ROUTE: HOME PAGE ---
@views.route("/")
def home():
    # Fetch Content
    content = {
        # Hero
        'hero_title_1': get_content('hero_title_1', 'Padre'),
        'hero_title_2': get_content('hero_title_2', 'Garcia'),
        'hero_subtitle': get_content('hero_subtitle', 'Discover the rich heritage...'),
        'hero_image': get_content('hero_image_path', url_for('static', filename='images/municipal.jpg')),
        
        # About
        'about_title': get_content('about_title', 'Where Tradition Meets Progress'),
        'about_text': get_content('about_text', 'Known as the Cattle Trading Capital...'),
        'about_image': get_content('about_image_path', url_for('static', filename='images/municipal2.jpg')),

        # Travel Essentials
        'travel_title_1': get_content('travel_title_1', 'Best Time to Visit'),
        'travel_text_1': get_content('travel_text_1', 'December 1st marks our Kabakahan Festival...'),
        'travel_title_2': get_content('travel_title_2', 'Getting Here'),
        'travel_text_2': get_content('travel_text_2', 'Accessible via STAR Tollway (Lipa Exit)...'),
        'travel_title_3': get_content('travel_title_3', 'Where to Stay'),
        'travel_text_3': get_content('travel_text_3', 'We have local inns within the town proper...'),

        # Footer
        'footer_brand_title': get_content('footer_brand_title', 'Tourism Padre Garcia'),
        'footer_brand_desc': get_content('footer_brand_desc', 'Promoting the culture...'),
        'footer_links_title': get_content('footer_links_title', 'Quick Links'),
        'footer_link1_text': get_content('footer_link1_text', 'About Us'),
        'footer_link1_url': get_content('footer_link1_url', '#'),
        'footer_link2_text': get_content('footer_link2_text', 'Tourist Spots'),
        'footer_link2_url': get_content('footer_link2_url', '#'),
        'footer_link3_text': get_content('footer_link3_text', 'Events Calendar'),
        'footer_link3_url': get_content('footer_link3_url', '#'),
        'footer_contact_title': get_content('footer_contact_title', 'Contact Us'),
        'contact_addr': get_content('contact_addr', '2nd Flr. LAM Bldg...'),
        'contact_phone': get_content('contact_phone', '(043) 515-9209'),
        'contact_email': get_content('contact_email', 'tourism@padregarcia.gov.ph'),
        'footer_em_title': get_content('footer_em_title', 'Emergency Hotlines'),
        'footer_em1_name': get_content('footer_em1_name', 'PNP Station'),
        'footer_em1_num': get_content('footer_em1_num', '116'),
        'footer_em2_name': get_content('footer_em2_name', 'Fire Station'),
        'footer_em2_num': get_content('footer_em2_num', '177'),
        'social_fb': get_content('social_fb', ''),
        'social_x': get_content('social_x', ''),
        'social_ig': get_content('social_ig', ''),
        'footer_copyright': get_content('footer_copyright', '© 2025 Tourism...'),
    }
    
    spots = TouristSpot.query.order_by(TouristSpot.order).all()
    return render_template("home.html", content=content, spots=spots)

# --- ROUTE: SPOT DETAIL (NEW) ---
@views.route("/spot/<int:id>")
def spot_detail(id):
    spot = TouristSpot.query.get_or_404(id)
    
    # Pass limited content for footer consistency
    content = {
        'contact_addr': get_content('contact_addr', ''),
        'contact_phone': get_content('contact_phone', ''),
        'contact_email': get_content('contact_email', ''),
        'footer_copyright': get_content('footer_copyright', ''),
    }
    
    return render_template("spot_detail.html", spot=spot, content=content)

@views.route("/contacts")
def contacts():
    return render_template("contact.html")

# --- ROUTE: ADMIN DASHBOARD ---
@views.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    if not current_user.is_admin:
        flash("Access Denied.", "error")
        return redirect(url_for("views.home"))

    if request.method == "POST":
        
        # A. UPDATE SITE CONTENT
        if "update_content" in request.form:
            fields = [
                'hero_title_1', 'hero_title_2', 'hero_subtitle', 
                'about_title', 'about_text',
                'travel_title_1', 'travel_text_1', 'travel_title_2', 'travel_text_2', 'travel_title_3', 'travel_text_3',
                'footer_brand_title', 'footer_brand_desc',
                'footer_links_title', 'footer_link1_text', 'footer_link1_url', 
                'footer_link2_text', 'footer_link2_url', 'footer_link3_text', 'footer_link3_url',
                'footer_contact_title', 'contact_addr', 'contact_phone', 'contact_email',
                'footer_em_title', 'footer_em1_name', 'footer_em1_num', 'footer_em2_name', 'footer_em2_num',
                'social_fb', 'social_x', 'social_ig', 'footer_copyright'
            ]
            for field in fields:
                val = request.form.get(field)
                existing = SiteContent.query.filter_by(key=field).first()
                if existing: existing.value = val
                else: db.session.add(SiteContent(key=field, value=val))
            
            # Images
            hero_file = request.files.get("hero_image_file")
            if hero_file and hero_file.filename != '':
                path = save_image(hero_file)
                existing = SiteContent.query.filter_by(key='hero_image_path').first()
                if existing: existing.value = path
                else: db.session.add(SiteContent(key='hero_image_path', value=path))

            about_file = request.files.get("about_image_file")
            if about_file and about_file.filename != '':
                path = save_image(about_file)
                existing = SiteContent.query.filter_by(key='about_image_path').first()
                if existing: existing.value = path
                else: db.session.add(SiteContent(key='about_image_path', value=path))
            
            flash("Content updated!", "success")

        # B. ADD SPOT
        elif "add_spot" in request.form:
            name = request.form.get("spot_name")
            desc = request.form.get("spot_desc")
            link = request.form.get("spot_link")
            file = request.files.get("spot_image_file")
            url_input = request.form.get("spot_image_url")
            
            final_path = None
            if file and file.filename != '': final_path = save_image(file)
            elif url_input: final_path = url_input

            if name and final_path:
                db.session.add(TouristSpot(name=name, image_url=final_path, description=desc, link_url=link))
                flash("Spot added!", "success")
            else:
                flash("Name and Image required.", "error")

        # C. EDIT SPOT
        elif "edit_spot" in request.form:
            spot_id = request.form.get("spot_id")
            spot = TouristSpot.query.get(spot_id)
            if spot:
                spot.name = request.form.get("spot_name")
                spot.description = request.form.get("spot_desc")
                spot.link_url = request.form.get("spot_link")
                
                file = request.files.get("spot_image_file")
                url_input = request.form.get("spot_image_url")
                
                if file and file.filename != '':
                    spot.image_url = save_image(file)
                elif url_input and url_input.strip() != '':
                    spot.image_url = url_input.strip()
                flash("Spot updated!", "success")

        # D. DELETE SPOT
        elif "delete_spot" in request.form:
            spot = TouristSpot.query.get(request.form.get("spot_id"))
            if spot:
                db.session.delete(spot)
                flash("Spot deleted.", "success")

        db.session.commit()
        return redirect(url_for("views.dashboard"))

    # GET: Populate form
    keys = [
        'hero_title_1', 'hero_title_2', 'hero_subtitle', 'hero_image_path',
        'about_title', 'about_text', 'about_image_path',
        'travel_title_1', 'travel_text_1', 'travel_title_2', 'travel_text_2', 'travel_title_3', 'travel_text_3',
        'footer_brand_title', 'footer_brand_desc',
        'footer_links_title', 'footer_link1_text', 'footer_link1_url', 'footer_link2_text', 'footer_link2_url', 'footer_link3_text', 'footer_link3_url',
        'footer_contact_title', 'contact_addr', 'contact_phone', 'contact_email',
        'footer_em_title', 'footer_em1_name', 'footer_em1_num', 'footer_em2_name', 'footer_em2_num',
        'social_fb', 'social_x', 'social_ig', 'footer_copyright'
    ]
    content = {k: get_content(k, '') for k in keys}
    spots = TouristSpot.query.all()
    
    return render_template("admin_dashboard.html", content=content, spots=spots, user=current_user)