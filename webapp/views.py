from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, abort
from flask_login import login_required, current_user
from flask_mail import Message
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from flask import jsonify

import os
import uuid
import io
import datetime 
import tempfile
import re # Added for ordinance sorting

from docx2pdf import convert
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import Color
import math
from reportlab.lib.utils import ImageReader
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from sqlalchemy import or_
from . import db, mail

# Update this line to include all your models
from .models import User, SiteContent, TouristSpot, Ordinance, SocialLink, FooterLink, EmergencyHotline, Mayor, Barangay, FestivalEvent, CommercialEstablishment, Accommodation, FinancialInstitution, MajorAttraction, FoodDish, SweetTreat, FestivalGalleryImage, AttractionMedia, HistoryMedia

views = Blueprint("views", __name__)

# =========================================
#               TEMPLATE FILTERS
# =========================================

@views.app_template_filter('get_file_icon')
def get_file_icon(filename):
    """Returns a Remix Icon class based on the file extension."""
    if not filename:
        return 'ri-file-list-3-line'
        
    ext = filename.split('.')[-1].lower()
    
    if ext == 'pdf':
        return 'ri-file-pdf-line'
    elif ext in ['doc', 'docx']:
        return 'ri-file-word-line'
    elif ext in ['xls', 'xlsx', 'csv']:
        return 'ri-file-excel-line'
    elif ext in ['ppt', 'pptx']:
        return 'ri-file-ppt-line'
    elif ext in ['zip', 'rar', '7z', 'tar']:
        return 'ri-file-zip-line'
    elif ext in ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp']:
        return 'ri-image-line'
    elif ext in ['mp4', 'mov', 'avi', 'webm', 'mkv']:
        return 'ri-film-line'
    else:
        return 'ri-file-list-3-line'

# =========================================
#               HELPER FUNCTIONS
# ==========================================

def get_ord_sort_key(ord_obj):
    """
    Parses ordinance numbers to sort Year Latest to Oldest (Desc), 
    then Sequence Number Ascending.
    """
    text = str(ord_obj.number).strip()
    nums = re.findall(r'\d+', text)
    if len(nums) >= 2:
        # Check which one is the 4 digit year
        if len(nums[0]) == 4:
            return (-int(nums[0]), int(nums[1]), text)
        elif len(nums[1]) == 4:
            return (-int(nums[1]), int(nums[0]), text)
        else:
            return (-int(nums[0]), int(nums[1]), text)
    elif len(nums) == 1:
        return (-int(nums[0]), 0, text)
    else:
        return (0, 0, text)

def get_font(font_size):
    """Tries to load a system scalable font. Fallbacks if running on bare Linux."""
    for font_name in ["arial.ttf", "FreeSans.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"]:
        try:
            return ImageFont.truetype(font_name, font_size)
        except:
            continue
    return ImageFont.load_default()

def save_file(file):
    """
    Saves the uploaded file.
    CRITICAL: If the file is an image, it immediately bakes a "Padre Garcia Tourism"
    watermark into the bottom right corner.
    """
    if not file or file.filename == '':
        return None
        
    filename = secure_filename(file.filename)
    unique_filename = str(uuid.uuid4()) + "_" + filename
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
    
    ext = filename.split('.')[-1].lower()
    
    # Apply baked-in watermark for Images
    if ext in ['jpg', 'jpeg', 'png']:
        try:
            img = Image.open(file.stream).convert("RGBA")
            watermark = Image.new("RGBA", img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(watermark)
            
            text = "Padre Garcia Tourism"
            font_size = max(int(img.width * 0.035), 14) # ~3.5% of image width
            font = get_font(font_size)
            
            try:
                bbox = draw.textbbox((0,0), text, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
            except AttributeError:
                tw, th = draw.textsize(text, font=font)
                
            x = img.width - tw - 15
            y = img.height - th - 15
            if x < 0: x = 0
            if y < 0: y = 0
            
            shadow_color = (0, 0, 0, 180)
            draw.text((x-1, y-1), text, font=font, fill=shadow_color)
            draw.text((x+1, y+1), text, font=font, fill=shadow_color)
            
            draw.text((x, y), text, font=font, fill=(255, 255, 255, 240))
            
            out = Image.alpha_composite(img, watermark)
            
            if ext in ['jpg', 'jpeg']:
                out = out.convert("RGB")
                out.save(file_path, "JPEG", quality=90)
            else:
                out.save(file_path, "PNG")
        except Exception as e:
            print(f"Upload watermark error: {e}")
            file.seek(0)
            file.save(file_path)
    else:
        file.save(file_path)
        
    return f"static/uploads/{unique_filename}"

def get_content(key, default=""):
    content = SiteContent.query.filter_by(key=key).first()
    return content.value if content else default

def get_common_content():
    social_links = SocialLink.query.all()
    footer_links = FooterLink.query.all()
    hotlines = EmergencyHotline.query.all()

    return {
        'site_logo': get_content('site_logo', ''), 
        'footer_brand_title': get_content('footer_brand_title', 'Tourism Padre Garcia'),
        'footer_brand_desc': get_content('footer_brand_desc', 'Promoting the culture and heritage of the Cattle Trading Capital.'),
        'footer_links_title': get_content('footer_links_title', 'Quick Links'),
        'footer_contact_title': get_content('footer_contact_title', 'Contact Us'),
        'footer_em_title': get_content('footer_em_title', 'Emergency Hotlines'),
        'contact_addr': get_content('contact_addr', '2nd Flr. LAM Bldg, Poblacion, Padre Garcia, Batangas 4224'),
        'contact_phone': get_content('contact_phone', '(043) 515-9209'),
        'contact_email': get_content('contact_email', 'tourism@padregarcia.gov.ph'),
        'footer_copyright': get_content('footer_copyright', '© 2025 Tourism Padre Garcia. All Rights Reserved.'),
        'social_links': social_links,
        'footer_links_list': footer_links,
        'hotlines_list': hotlines
    }

# ==========================================
#               PUBLIC ROUTES
# ==========================================

@views.route("/")
def home():
    content = get_common_content()
    content.update({
        'hero_title_1': get_content('hero_title_1', 'Padre'),
        'hero_title_2': get_content('hero_title_2', 'Garcia'),
        'hero_subtitle': get_content('hero_subtitle', 'Discover the rich heritage and vibrant culture of the Cattle Trading Capital.'),
        'hero_image': get_content('hero_image_path', url_for('static', filename='images/municipal.jpg')),
        'about_title': get_content('about_title', 'Where Tradition Meets Progress'),
        'about_text': get_content('about_text', 'Known as the Cattle Trading Capital of the Philippines, Padre Garcia is a thriving municipality in Batangas.'),
        'about_image': get_content('about_image_path', url_for('static', filename='images/municipal2.jpg')),
        'travel_title_1': get_content('travel_title_1', 'Best Time to Visit'),
        'travel_text_1': get_content('travel_text_1', 'December 1st marks our annual Kabakahan Festival.'),
        'travel_title_2': get_content('travel_title_2', 'Getting Here'),
        'travel_text_2': get_content('travel_text_2', 'Accessible via STAR Tollway (Lipa Exit) and major bus lines.'),
        'travel_title_3': get_content('travel_title_3', 'Where to Stay'),
        'travel_text_3': get_content('travel_text_3', 'We have local inns and resorts within the town proper.'),
    })
    page = request.args.get('page', 1, type=int)
    spots = TouristSpot.query.order_by(TouristSpot.order).paginate(page=page, per_page=8, error_out=False)
    return render_template("home.html", content=content, spots=spots)

@views.route("/search")
def global_search():
    q = request.args.get('q', '').strip()
    content = get_common_content()
    
    results = {
        'spots': [],
        'ordinances': [],
        'events': [],
        'pages': [],
        'attractions': [], 
        'history': [],     
        'commerce': [],    
        'food': [],        
        'total': 0
    }
    
    if q:
        search_term = f"%{q}%"
        
        # 1. Tourist Spots
        results['spots'] = TouristSpot.query.filter(or_(TouristSpot.name.ilike(search_term), TouristSpot.description.ilike(search_term))).all()
        
        # 2. Ordinances (With new sort logic)
        results['ordinances'] = Ordinance.query.filter(or_(Ordinance.title.ilike(search_term), Ordinance.number.ilike(search_term), Ordinance.description.ilike(search_term))).all()
        results['ordinances'] = sorted(results['ordinances'], key=get_ord_sort_key)

        # 3. Festival Events
        results['events'] = FestivalEvent.query.filter(or_(FestivalEvent.title.ilike(search_term), FestivalEvent.description.ilike(search_term), FestivalEvent.location.ilike(search_term))).all()
        
        # 4. Major Attractions
        results['attractions'] = MajorAttraction.query.filter(or_(MajorAttraction.name.ilike(search_term), MajorAttraction.description.ilike(search_term), MajorAttraction.location.ilike(search_term))).all()

        # 5. History & Heritage (Mayors + Barangays)
        mayors = Mayor.query.filter(or_(Mayor.name.ilike(search_term), Mayor.role.ilike(search_term), Mayor.years.ilike(search_term))).all()
        brgys = Barangay.query.filter(or_(Barangay.name.ilike(search_term), Barangay.captain_name.ilike(search_term))).all()
        for m in mayors:
            results['history'].append({'title': m.name, 'desc': f"Role: {m.role or 'N/A'} | Years: {m.years or 'N/A'}", 'type': 'Leader/Mayor'})
        for b in brgys:
            results['history'].append({'title': f"Barangay {b.name}", 'desc': f"Barangay Captain: {b.captain_name or 'N/A'}", 'type': 'Barangay'})

        # 6. Commerce & Lifestyle (Establishments + Accommodations + Banks)
        ests = CommercialEstablishment.query.filter(or_(CommercialEstablishment.name.ilike(search_term), CommercialEstablishment.description.ilike(search_term))).all()
        accs = Accommodation.query.filter(or_(Accommodation.name.ilike(search_term), Accommodation.description.ilike(search_term))).all()
        banks = FinancialInstitution.query.filter(FinancialInstitution.name.ilike(search_term)).all()
        for e in ests:
            results['commerce'].append({'title': e.name, 'desc': e.description, 'type': 'Dining/Shopping', 'url_anchor': '#establishments'})
        for a in accs:
            results['commerce'].append({'title': a.name, 'desc': a.description, 'type': 'Accommodation', 'url_anchor': '#accommodations'})
        for b in banks:
            results['commerce'].append({'title': b.name, 'desc': 'Financial Institution / Bank', 'type': 'Bank', 'url_anchor': ''})

        # 7. Food & Delicacies (Dishes + Sweets)
        dishes = FoodDish.query.filter(or_(FoodDish.name.ilike(search_term), FoodDish.description.ilike(search_term), FoodDish.tagline.ilike(search_term))).all()
        sweets = SweetTreat.query.filter(or_(SweetTreat.name.ilike(search_term), SweetTreat.description.ilike(search_term))).all()
        for d in dishes:
            results['food'].append({'title': d.name, 'desc': d.description, 'type': 'Local Dish'})
        for s in sweets:
            results['food'].append({'title': s.name, 'desc': s.description, 'type': 'Sweet/Pasalubong'})

        # 8. Static Pages Map (Keywords)
        pages_map = {
            'About Us': {'url': url_for('views.about'), 'icon': 'ri-information-line', 'desc': 'Discover the history, culture, and vision behind the municipality.', 'keywords': ['about', 'history', 'mission', 'vision', 'heritage', 'lumang bayan', 'mayor', 'town']},
            'History & Heritage': {'url': url_for('views.history'), 'icon': 'ri-hourglass-line', 'desc': 'Learn about Padre Vicente Garcia and the generations of Mayors.', 'keywords': ['history', 'mayor', 'vicente garcia', 'barangay', 'origin', 'heritage']},
            'Commerce & Economy': {'url': url_for('views.commercial'), 'icon': 'ri-store-2-line', 'desc': 'Explore local businesses, markets, and accommodations.', 'keywords': ['commerce', 'business', 'shopping', 'market', 'bank', 'hotel', 'stay', 'economy', 'trade']},
            'Major Attractions': {'url': url_for('views.attractions'), 'icon': 'ri-map-pin-line', 'desc': 'Major destinations including the Livestock Auction Market.', 'keywords': ['attraction', 'spot', 'tourism', 'livestock', 'market', 'park', 'bawi', 'trail', 'destination']},
            'Cultural Inventory': {'url': url_for('views.culture'), 'icon': 'ri-bank-line', 'desc': 'Sacred sites, historical monuments, and architecture.', 'keywords': ['culture', 'church', 'monument', 'parish', 'rosary', 'heritage', 'sacred', 'architecture']},
            'Kabakahan Festival': {'url': url_for('views.festival'), 'icon': 'ri-flag-line', 'desc': 'Annual cultural celebration of the Cattle Trading Capital.', 'keywords': ['festival', 'kabakahan', 'event', 'december', 'rodeo', 'celebration']},
            'Food & Delicacies': {'url': url_for('views.food'), 'icon': 'ri-restaurant-line', 'desc': 'Taste Batangas Goto, Halo-Halo, and sweet pasalubongs.', 'keywords': ['food', 'goto', 'halo-halo', 'sweet', 'pasalubong', 'delicacy', 'eat', 'taste', 'gastronomic']},
            'Contact Us': {'url': url_for('views.contacts'), 'icon': 'ri-contacts-book-line', 'desc': 'Get in touch with the Tourism Department.', 'keywords': ['contact', 'email', 'phone', 'location', 'address', 'map', 'message']},
            'Legislative Records': {'url': url_for('views.ordinances'), 'icon': 'ri-file-list-3-line', 'desc': 'Official repository of Municipal Ordinances.', 'keywords': ['ordinance', 'law', 'legal', 'resolution', 'record', 'document']}
        }
        
        q_lower = q.lower()
        q_words = q_lower.split()

        for page_name, info in pages_map.items():
            match = False
            if q_lower in page_name.lower() or q_lower in info['desc'].lower():
                match = True
            else:
                for kw in info['keywords']:
                    if any(word in kw for word in q_words) or kw in q_lower:
                        match = True
                        break
            
            if match:
                results['pages'].append({'name': page_name, 'url': info['url'], 'icon': info['icon'], 'desc': info['desc']})

        # Calculate Total Results found
        results['total'] = (len(results['spots']) + len(results['ordinances']) + len(results['events']) + 
                            len(results['pages']) + len(results['attractions']) + len(results['history']) + 
                            len(results['commerce']) + len(results['food']))

    return render_template("search_results.html", content=content, query=q, results=results)

@views.route("/about")
def about():
    content = get_common_content()
    content.update({
        'about_hero_badge': get_content('about_hero_badge', 'Welcome to Our Town'),
        'about_hero_h1': get_content('about_hero_h1', 'Our Story & Heritage'),
        'about_hero_sub': get_content('about_hero_sub', 'Discover the history, culture, and vision behind the Cattle Trading Capital.'),
        'about_intro_badge': get_content('about_intro_badge', 'About Padre Garcia'),
        'about_title': get_content('about_title', 'Where Tradition Meets Progress'),
        'about_text': get_content('about_text', 'Known as the Cattle Trading Capital of the Philippines...'),
        'about_image': get_content('about_image_path', url_for('static', filename='images/municipal2.jpg')),
        'about_img_caption': get_content('about_img_caption', '"A community bound by faith, hard work, and unity."'),
        'about_feat1_title': get_content('about_feat1_title', 'Rich History'),
        'about_feat1_desc': get_content('about_feat1_desc', 'Established 1949'),
        'about_feat2_title': get_content('about_feat2_title', 'Trading Hub'),
        'about_feat2_desc': get_content('about_feat2_desc', 'Economic Center'),
        'about_dir_title': get_content('about_dir_title', 'Our Direction'),
        'about_dir_sub': get_content('about_dir_sub', 'Guiding principles for a better municipality'),
        'mission_text': get_content('mission_text', 'To provide high-quality public service...'),
        'vision_text': get_content('vision_text', 'Padre Garcia shall be the premier agro-industrial center...'),
        'fact_year': get_content('fact_year', '1949'),
        'fact_barangays': get_content('fact_barangays', '18'),
        'fact_population': get_content('fact_population', '50k+'),
        'fact_festival': get_content('fact_festival', 'Dec 1'),
        'about_cta_title': get_content('about_cta_title', 'Experience the Warmth of Padre Garcia'),
        'about_cta_text': get_content('about_cta_text', 'Whether you are here for business, cattle trading, or leisure, our town welcomes you with open arms.'),
    })
    return render_template("about.html", content=content)

@views.route("/download/<path:filename>")
def download_watermarked(filename):
    clean_filename = filename.replace('static/uploads/', '').replace('static/images/', '').replace('static/', '')
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Resolve File Path
    full_file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], clean_filename)
    if not os.path.exists(full_file_path):
        full_file_path = os.path.join(base_dir, 'static', 'images', clean_filename)
    if not os.path.exists(full_file_path):
        full_file_path = os.path.join(base_dir, 'static', clean_filename)
    
    if not os.path.exists(full_file_path):
        current_app.logger.warning(f"File not found for download: {filename}")
        abort(404)

    ext = full_file_path.split('.')[-1].lower()
    new_filename_prefix = "PG_Tourism_" 
    new_download_name = f"{new_filename_prefix}{os.path.basename(clean_filename)}"
    dl = request.args.get('dl', '0') == '1'
    temp_pdf_path = None

    # ==========================================
    # INTERCEPT: CONVERT DOCX/DOC TO PDF
    # ==========================================
    if ext in ['doc', 'docx']:
        try:
            # Create a temporary PDF file to hold the conversion
            temp_fd, temp_pdf_path = tempfile.mkstemp(suffix='.pdf')
            os.close(temp_fd) 
            
            # Convert the Word Doc to PDF
            convert(full_file_path, temp_pdf_path)
            
            # Now treat this file as a PDF for the rest of the script
            full_file_path = temp_pdf_path
            ext = 'pdf'
            
            # Change the download filename extension to .pdf
            new_download_name = new_download_name.rsplit('.', 1)[0] + '.pdf'
            
        except Exception as e:
            current_app.logger.error(f"Error converting DOCX to PDF: {e}")
            # If conversion fails, it falls back to the original docx later in the script

    # 2. Fetch the "Site Logo" from the database or use default
    logo_setting = SiteContent.query.filter_by(key='site_logo').first()
    has_logo = False
    
    if logo_setting and logo_setting.value:
        logo_path = os.path.join(current_app.root_path, logo_setting.value)
        if os.path.exists(logo_path):
            has_logo = True
            
    if not has_logo:
        logo_path = os.path.join(base_dir, 'static', 'images', 'logo_watermark.png')
        has_logo = os.path.exists(logo_path)

    def get_transparent_logo(target_width, opacity=0.50):
        if not has_logo: return None
        try:
            img = Image.open(logo_path).convert("RGBA")
            aspect_ratio = img.height / img.width
            new_width = int(target_width)
            new_height = int(new_width * aspect_ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            alpha = img.split()[3]
            alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
            img.putalpha(alpha)
            return img
        except Exception as e:
            current_app.logger.error(f"Error loading watermark logo: {e}")
            return None

    # ==========================================
    # WATERMARK IMAGES (TILED REPEAT)
    # ==========================================
    if ext in ['jpg', 'jpeg', 'png']:
        try:
            base_image = Image.open(full_file_path).convert("RGBA")
            width, height = base_image.size
            watermark_layer = Image.new("RGBA", (width, height), (0,0,0,0))
            
            if has_logo:
                logo_w = int(width * 0.15)
                if logo_w < 80: logo_w = 80 
                logo_img = get_transparent_logo(logo_w, opacity=0.25) 
                
                if logo_img:
                    logo_h = logo_img.height
                    gap_x, gap_y = int(logo_w * 0.5), int(logo_h * 0.5)
                    
                    for y in range(0, height, logo_h + gap_y):
                        for x in range(0, width, logo_w + gap_x):
                            offset_x = int((logo_w + gap_x) / 2) if (y // (logo_h + gap_y)) % 2 == 1 else 0
                            draw_x = x + offset_x
                            if draw_x < width and y < height:
                                watermark_layer.paste(logo_img, (draw_x, y), logo_img)
            else:
                draw = ImageDraw.Draw(watermark_layer)
                text = "PADRE GARCIA TOURISM"
                font_size = max(int(width * 0.04), 14)
                font = get_font(font_size)
                
                try: bbox = draw.textbbox((0,0), text, font=font); text_w, text_h = bbox[2]-bbox[0], bbox[3]-bbox[1]
                except AttributeError: text_w, text_h = draw.textsize(text, font=font)
                
                gap_x, gap_y = int(text_w * 0.3), int(text_h * 3)
                for y in range(0, height, text_h + gap_y):
                    for x in range(0, width, text_w + gap_x):
                        offset_x = int((text_w + gap_x) / 2) if (y // (text_h + gap_y)) % 2 == 1 else 0
                        draw_x = x + offset_x
                        if draw_x < width and y < height:
                            draw.text((draw_x, y), text, font=font, fill=(255, 255, 255, 90))
            
            out = Image.alpha_composite(base_image, watermark_layer)
            if ext in ['jpg', 'jpeg']:
                out = out.convert("RGB")
                save_format = 'JPEG'
            else:
                save_format = 'PNG'

            img_io = io.BytesIO()
            out.save(img_io, save_format, quality=95)
            img_io.seek(0)
            return send_file(img_io, mimetype=f'image/{save_format.lower()}', as_attachment=dl, download_name=new_download_name)
        except Exception as e:
            current_app.logger.error(f"Error watermarking image: {e}")
            return send_file(full_file_path, as_attachment=dl, download_name=new_download_name)

    # ==========================================
    # WATERMARK PDFs (TILED REPEAT)
    # ==========================================
    elif ext == 'pdf':
        try:
            # 1. READ ENTIRE PDF INTO MEMORY TO RELEASE WINDOWS FILE LOCK
            with open(full_file_path, "rb") as f:
                original_pdf_stream = io.BytesIO(f.read())
                
            # 2. DELETE THE TEMPORARY FILE IMMEDIATELY NOW THAT WE HAVE IT IN MEMORY
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
                temp_pdf_path = None # Mark as handled
                
            packet = io.BytesIO()
            c = canvas.Canvas(packet, pagesize=letter)
            pg_w, pg_h = letter

            if has_logo:
                logo_pil = get_transparent_logo(150, opacity=0.15)
                if logo_pil:
                    img_byte_arr = io.BytesIO()
                    logo_pil.save(img_byte_arr, format='PNG')
                    img_byte_arr.seek(0)
                    rl_logo = ImageReader(img_byte_arr)
                    logo_w = 150
                    logo_h = 150 * (logo_pil.height / logo_pil.width)
                    
                    gap_x, gap_y = 100, 100
                    for y in range(-int(logo_h), int(pg_h) + int(logo_h), int(logo_h + gap_y)):
                        for x in range(-int(logo_w), int(pg_w) + int(logo_w), int(logo_w + gap_x)):
                            offset_x = int((logo_w + gap_x) / 2) if (y // (logo_h + gap_y)) % 2 == 1 else 0
                            c.drawImage(rl_logo, x + offset_x, y, width=logo_w, height=logo_h, mask='auto')
            else:
                c.setFillColor(Color(0.5, 0.5, 0.5, alpha=0.15))
                c.setFont("Helvetica-Bold", 35)
                text = "PADRE GARCIA TOURISM"
                for y in range(0, int(pg_h), 200):
                    for x in range(0, int(pg_w), 300):
                        c.saveState()
                        offset = 150 if (y // 200) % 2 == 1 else 0
                        c.translate(x + offset, y)
                        c.rotate(30)
                        c.drawCentredString(0, 0, text)
                        c.restoreState()
            
            c.save()
            packet.seek(0)
            
            watermark_pdf = PdfReader(packet)
            original_pdf = PdfReader(original_pdf_stream)
            output = PdfWriter()
            
            for page in original_pdf.pages:
                page.merge_page(watermark_pdf.pages[0]) 
                output.add_page(page)
            
            out_stream = io.BytesIO()
            output.write(out_stream)
            out_stream.seek(0)
            
            return send_file(out_stream, mimetype='application/pdf', as_attachment=dl, download_name=new_download_name)
            
        except Exception as e:
            current_app.logger.error(f"Error watermarking PDF: {e}")
            
            # If an error happens, we still want to give them the unwatermarked file and clean up
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                # Read unwatermarked into memory, delete disk file, then send memory stream
                with open(temp_pdf_path, "rb") as f:
                    fallback_stream = io.BytesIO(f.read())
                os.remove(temp_pdf_path)
                return send_file(fallback_stream, mimetype='application/pdf', as_attachment=dl, download_name=new_download_name)
                
            return send_file(full_file_path, as_attachment=dl, download_name=new_download_name)

    # ==========================================
    # SERVE OTHER FILES (.xls, .ppt, failed docs) NORMALLY
    # ==========================================
    else:
        mimetype_map = {
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'ppt': 'application/vnd.ms-powerpoint',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'zip': 'application/zip',
        }
        detected_mimetype = mimetype_map.get(ext, 'application/octet-stream')
        return send_file(full_file_path, mimetype=detected_mimetype, as_attachment=dl, download_name=new_download_name)
    
@views.route("/manage-users", methods=["GET", "POST"])
@login_required
def manage_users():
    if not current_user.is_admin or not current_user.is_super_admin:
        flash("Unauthorized access.", "error")
        return redirect(url_for("views.dashboard"))

    if request.method == "POST":
        if "delete_user" in request.form:
            user_id = request.form.get("user_id")
            user_to_delete = User.query.get(user_id)
            if user_to_delete:
                if user_to_delete.id == current_user.id:
                    flash("You cannot delete your own account.", "error")
                else:
                    db.session.delete(user_to_delete)
                    db.session.commit()
                    flash("User account deleted.", "success")
            return redirect(url_for("views.manage_users"))

        if "change_password" in request.form:
            user_id = request.form.get("user_id")
            new_pass = request.form.get("new_password")
            user_to_edit = User.query.get(user_id)
            if user_to_edit and new_pass:
                hashed_password = generate_password_hash(new_pass, method='pbkdf2:sha256')
                user_to_edit.password = hashed_password
                db.session.commit()
                flash(f"Password for {user_to_edit.email} updated!", "success")
            else:
                flash("Error updating password.", "error")
            return redirect(url_for("views.manage_users"))

        if "edit_user" in request.form:
            user_id = request.form.get("user_id")
            fname = request.form.get("edit_fname")
            email = request.form.get("edit_email")
            role_type = request.form.get("edit_role") 
            user_to_edit = User.query.get(user_id)
            if user_to_edit:
                existing_email = User.query.filter_by(email=email).first()
                if existing_email and existing_email.id != int(user_id):
                    flash("That username/email is already taken.", "error")
                else:
                    user_to_edit.first_name = fname
                    user_to_edit.email = email
                    if user_to_edit.id == current_user.id and role_type != 'super':
                        flash("You cannot demote your own account.", "error")
                    else:
                        if role_type == 'super':
                            user_to_edit.is_super_admin = True
                            user_to_edit.is_admin = True
                        else:
                            user_to_edit.is_super_admin = False
                            user_to_edit.is_admin = True
                        db.session.commit()
                        flash("User details updated successfully!", "success")
            return redirect(url_for("views.manage_users"))

        if "add_sub_admin" in request.form:
            email = request.form.get("new_email")
            fname = request.form.get("new_fname")
            password = request.form.get("new_password")
            user_exists = User.query.filter_by(email=email).first()
            if user_exists:
                flash("Email already exists.", "error")
            else:
                new_user = User(
                    email=email,
                    first_name=fname,
                    password=generate_password_hash(password, method='pbkdf2:sha256'),
                    is_admin=True,
                    is_super_admin=False
                )
                db.session.add(new_user)
                db.session.commit()
                flash("New Sub-Admin created!", "success")
            return redirect(url_for("views.manage_users"))

    users = User.query.all()
    return render_template("manage_users.html", users=users)

@views.route("/history")
def history():
    content = get_common_content()
    mayors = Mayor.query.order_by(Mayor.id).all()
    barangays = Barangay.query.order_by(Barangay.name).all() 
    
    # Fetch media specifically for the Padre Garcia section
    pg_media = HistoryMedia.query.filter_by(section_key='padre_garcia').order_by(HistoryMedia.order).all()

    # --- NEW: Fetch media for the 'Extra Information Section' ---
    extra_info_media = HistoryMedia.query.filter_by(section_key='history_extra_info').order_by(HistoryMedia.order).all()

    biography_text = """An eminent Filipino Batangueño Priest – Hero, Padre Vicente Teodoro Garcia was named after St. Vincent Ferrer by his beloved parents Don Jose Garcia and Doña Andrea Teodora of barrio Maugat, then Old Rosario (1687) now this Municipality of Padre V. Garcia (1949), Province of Batangas, Philippines.

HIS EDUCATION, DISCIPLINE AND PROFESSION:
He studied at Universidad de Sto. Tomas (Bachiller en Artes 1839; Bachiller en Teologia 1847; Doctor en Teologia 1848; Licenciado en Sagrado Teologia 1885). He also attended Real Colegio de San Jose where he earned his Bachelor of Canon and Civil Law and Doctor of Divine Theology (1849). He was ordained Priest in June 1849.

HIS NOTABLE POSITIONS, DUTIES AND APOSTOLIC WORKS:
• Rector of the Royal College of San Jose, Manila
• Chaplain of the Artillery Regiment in the Peninsular Army
• Ecclesiastical Governor at the Diocese of Nueva Caceres
• Canonigo Penetenciario and Private Consultant under Prelate of Manila Cathedral
• Founder, Hospital of the Lepers in Camarines, Bicol
• Wise Counsel (from the aged) of Philippine National Hero Dr. Jose P. Rizal

HIS WRITINGS AND AUTHORSHIP:
He authored numerous works including "Oracion Funebre" (1861), "Vida de San Eustaquio" (1875), "Aves de los Almas" (1875), "Pagtulad kay Kristo" (1880), "Pagsisiyam sa Mahal na Birhen" (1881), and "Casaysayan ng mga Cababalaghan" (1881).

HIS DEFENSE OF RIZAL:
Most notably, he wrote the Brave Defense Counter Attack Letter defending "Noli Me Tangere" (Touch Me Not) or "Huwag mo Akong Salangin" published in La Solidaridad, Vol.11, 79-80 under the pen name V. Caraig (1895).

LEGACY:
On August 7, 2017, the Sangguniang Bayan passed Ordinance No. 25-2017 declaring April 5 of every year as Padre Vicente Garcia Day to commemorate the birthdate of Padre Vicente T. Garcia."""

    defaults = {
        'hist_hero_title': 'History & Heritage', 'hist_hero_sub': 'From Lumang Bayan to Today',
        'hist_hero_img': url_for('static', filename='images/municipal.jpg'),
        'hist_org_title': 'Our Origins', 'hist_org_text': 'Originally known as Lumang Bayan...',
        'hist_build_title': 'Transformation Of Municipal Buildings', 'hist_build_sub': 'Witnessing the structural evolution...',
        'hist_b1_img': url_for('static', filename='images/firstm.jpg.jpg'), 'hist_b1_lbl': 'First Municipal Hall', 'hist_b1_desc': 'The original municipal hall of Padre Garcia.',
        'hist_b2_img': url_for('static', filename='images/firstmm.jpg.jpg'), 'hist_b2_lbl': 'After the Fire', 'hist_b2_desc': 'The rebuilt structure following the tragic fire.',
        'hist_b3_img': url_for('static', filename='images/first.jpg.jpg'), 'hist_b3_lbl': 'First Renovation', 'hist_b3_desc': 'The first major architectural renovation of the hall.',
        'hist_b4_img': url_for('static', filename='images/municipal.jpg'), 'hist_b4_lbl': 'Modern Structure', 'hist_b4_desc': 'The contemporary and modern municipal building standing today.',
        
        'hist_pg_title': 'Padre Vicente Teodoro Garcia', 
        'hist_pg_sub': 'April 05, 1817 – July 12, 1899',
        'hist_pg_sect_title': 'Life & Works', 
        'hist_pg_text': biography_text, 
        'hist_pg_img': url_for('static', filename='images/pgv.jpg.jpg'),
        'hist_pg_wiki': 'https://en.wikipedia.org/wiki/Vicente_Garc%C3%ADa',
        'hist_pg_file': '', 

        'hist_mayor_title': "Mayor's Generation", 'hist_mayor_sub': "Leaders who shaped our history",
        'hist_brgy_title': 'The 18 Barangays', 'hist_brgy_sub': 'Click on a barangay to view details',

        # --- NEW EXTRA INFO DEFAULTS ---
        'hist_extra_title': 'A Legacy of Strength',
        'hist_extra_sub': 'Cultural Resilience',
        'hist_extra_desc': 'Padre Garcia has weathered many storms and emerged stronger, a testament to the enduring spirit of its people. From colonial struggles to modern challenges, the municipality has always found its way to progress while preserving its unique identity.',
        # 'hist_extra_img': url_for('static', filename='images/municipal.jpg') # REMOVED: Now handled by HistoryMedia
    }
    for k, v in defaults.items(): content[k] = get_content(k, v)
    
    return render_template("history.html", 
                           content=content, 
                           mayors=mayors, 
                           barangays=barangays, 
                           pg_media=pg_media,
                           extra_info_media=extra_info_media)

@views.route("/commercial")
def commercial():
    content = get_common_content()
    
    page = request.args.get('page', 1, type=int)
    establishments = CommercialEstablishment.query.order_by(CommercialEstablishment.id.desc()).paginate(page=page, per_page=6, error_out=False)
    
    page_stay = request.args.get('page_stay', 1, type=int)
    accommodations = Accommodation.query.order_by(Accommodation.id.desc()).paginate(page=page_stay, per_page=6, error_out=False)
    
    banks = FinancialInstitution.query.all()
    
    defaults = {
        'comm_hero_title': 'Commerce & Lifestyle', 
        'comm_hero_sub': 'Business & Leisure', 
        'comm_hero_desc': 'A growing agro-industrial hub teeming with opportunities and vibrant local life.', 
        'comm_hero_bg': url_for('static', filename='images/commerce_hero.jpg'),
        'comm_intro_title': 'A Thriving Economy', 
        'comm_intro_text': 'Beyond the cattle market...',
        'comm_shop_title': 'Shopping & Markets', 
        'comm_shop_head': 'Padre Garcia Public Market', 
        'comm_shop_text': 'The daily heartbeat of the town...', 
        'comm_shop_img': url_for('static', filename='images/public_market.jpg'),
        'comm_shop_li1': 'Fresh Fruits & Vegetables',
        'comm_shop_li2': 'Clothing & Dry Goods',
        'comm_shop_li3': 'Agricultural Supplies',
        'comm_dine_title': 'Featured Establishments', 
        'comm_stay_title': 'Stay & Relax', 
        'comm_stay_head': 'Resorts & Inns', 'comm_stay_text': 'Padre Garcia offers various accommodations...', 
        'comm_fin_title': 'Financial Infrastructure', 
        'comm_fin_text': 'To support the high volume of trade, we have a robust banking system.'
    }
    for k, v in defaults.items(): content[k] = get_content(k, v)
    return render_template("commercial.html", content=content, establishments=establishments, accommodations=accommodations, banks=banks)


@views.route("/attractions")
def attractions():
    content = get_common_content()
    attractions_list = MajorAttraction.query.order_by(MajorAttraction.id).all()
    
    defaults = {
        'attr_hero_title': 'Major Attractions', 
        'attr_hero_sub': 'Pride of the Town', 
        'attr_hero_desc': 'From our economic heart to our natural wonders.', 
        'attr_hero_bg': url_for('static', filename='images/cattle_market.jpg')
    }
    for k, v in defaults.items(): content[k] = get_content(k, v)
    
    return render_template("attractions.html", content=content, attractions=attractions_list)

@views.route('/api/attraction/<int:id>/media')
@login_required
def get_attraction_media(id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
        
    attraction = MajorAttraction.query.get_or_404(id)
    media_list = [
        {
            'id': item.id,
            'url': item.media_url,
            'type': item.media_type,
            'caption': item.caption
        } 
        for item in attraction.media_items
    ]
    return jsonify({'media': media_list})

@views.route("/attraction/<int:id>")
def attraction_detail(id):
    attraction = MajorAttraction.query.get_or_404(id)
    content = get_common_content()
    return render_template("attraction_detail.html", attraction=attraction, content=content)

@views.route("/culture")
def culture():
    content = get_common_content()
    defaults = {
        'cult_hero_title': 'Cultural Inventory', 
        'cult_hero_sub': 'The sacred sites...', 
        'cult_hero_tag': 'Preserving Heritage', 
        'cult_hero_bg': url_for('static', filename='images/municipal.jpg'),
        'cult_church_title': 'Most Holy Rosary Parish', 
        'cult_old_img': url_for('static', filename='images/church_old.jpg'), 
        'cult_old_lbl': 'The Old Church', 
        'cult_new_img': url_for('static', filename='images/church_new.jpg'), 
        'cult_new_lbl': 'The Modern Structure',
        'cult_hist_title': 'Historical Significance', 
        'cult_hist_text': 'The Parish stands as...', 
        'cult_arch_title': 'Architecture', 
        'cult_arch_text': 'Exterior details...',
        'cult_patron_img': url_for('static', filename='images/mama_mary.jpg'), 
        'cult_patron_title': 'Our Lady of the Most Holy Rosary', 
        'cult_patron_sub': '"The beloved patroness..."', 
        'cult_patron_text': 'The image...',
        'cult_mon_title': 'Historical Monuments', 
        'cult_mon_sub': 'Honoring Pillars',
        'cult_m1_name': 'Padre Vicente Garcia', 'cult_m1_desc': '...', 'cult_m1_img': '...', 
        'cult_m1_pos': '50', # <--- ADD THIS (Default to Center)
        'cult_m2_name': 'Hon. Graciano R. Recto', 'cult_m2_desc': '...', 'cult_m2_img': '...', 
        'cult_m2_pos': '50', # <--- ADD THIS
        'cult_m3_name': 'Father Antonio', 'cult_m3_desc': '...', 'cult_m3_img': '...', 
        'cult_m3_pos': '50'  # <--- ADD THIS
    }
    
    # This loop actually fetches the saved values from the database
    for k, v in defaults.items(): 
        content[k] = get_content(k, v)
        
    return render_template("culture.html", content=content)

@views.route("/festival")
def festival():
    content = get_common_content()
    events = FestivalEvent.query.all() 
    page = request.args.get('page', 1, type=int)
    gallery = FestivalGalleryImage.query.order_by(FestivalGalleryImage.id.desc()).paginate(page=page, per_page=4, error_out=False)
    
    defaults = {
        'fest_hero_bg': url_for('static', filename='images/festival_hero.jpg'), 
        'fest_date_badge': 'Every Dec 1', 
        'fest_hero_title': 'Kabakahan Festival', 
        'fest_hero_sub': 'Celebrating the Cattle Trading Capital',
        'fest_intro_title': 'The Spirit of the Festival', 
        'fest_intro_text': 'Annual cultural celebration...',
        'fest_c1_title': 'Culture', 'fest_c1_desc': 'Showcasing talent', 
        'fest_c2_title': 'Trade', 'fest_c2_desc': 'Boosting economy', 
        'fest_c3_title': 'Faith', 'fest_c3_desc': 'Thanksgiving',
        'fest_legal_title': 'Legal Basis', 
        'fest_legal_desc': 'Institutionalized by law...', 'fest_legal_img': url_for('static', filename='images/festival_parade.jpg'), 'fest_ord_text': 'WHEREAS...',
        'fest_prog_title': 'Program & Activities', 'fest_prog_sub': 'Highlights',
        'fest_gal_title': 'Captured Moments'
    }
    for k, v in defaults.items(): content[k] = get_content(k, v)
    return render_template("festival.html", content=content, events=events, gallery=gallery)

@views.route("/food")
def food():
    content = get_common_content()
    dishes = FoodDish.query.all()
    sweets = SweetTreat.query.all()
    
    defaults = {
        'food_hero_title': 'Gastronomic Delights', 
        'food_hero_sub': 'Taste of Padre Garcia', 
        'food_hero_desc': 'Discover the rich, savory flavors and sweet delicacies that define our culture.', 
        'food_hero_bg': url_for('static', filename='images/food_hero.jpg'),
        'food_s3_title': 'Sweets & Pasalubong', 
        'food_s3_desc': 'Take home a piece of Padre Garcia with our local treats.'
    }
    for k, v in defaults.items(): content[k] = get_content(k, v)
    return render_template("food.html", content=content, dishes=dishes, sweets=sweets)

@views.route("/ordinances")
def ordinances():
    content = get_common_content()
    ordinances_list = Ordinance.query.all()
    ordinances_list = sorted(ordinances_list, key=get_ord_sort_key)
    return render_template("ordinances.html", content=content, ordinances=ordinances_list)

@views.route("/contacts", methods=["GET", "POST"])
def contacts():
    content = get_common_content()
    defaults = {
        'contact_hero_title': 'Get in Touch', 'contact_hero_sub': "We'd love to hear from you", 'contact_hero_bg': url_for('static', filename='images/municipal.jpg'),
        'contact_card_addr_title': 'Visit Us', 'contact_card_addr_text': '2nd Flr. LAM Bldg, Poblacion...',
        'contact_card_phone_title': 'Call Us', 'contact_phone_main': '(043) 515-9209', 'contact_phone_alt': '(043) 515-7424',
        'contact_card_email_title': 'Email Us', 'contact_email_main': 'tourism@padregarcia.gov.ph', 'contact_email_alt': 'info@padregarcia.gov.ph',
        'contact_form_title': 'Send us a Message', 'contact_map_url': 'https://www.google.com/maps/embed?pb=...'
    }
    for k, v in defaults.items(): content[k] = get_content(k, v)

    if request.method == "POST":
        # Handle Form Submission Data
        name = request.form.get("sender_name")
        email = request.form.get("sender_email")
        subject = request.form.get("subject")
        message = request.form.get("message")
        
        receiver = get_content('contact_receiver_email', '')

        if not receiver:
            flash("Message could not be sent. The administrator has not configured a receiving email address yet.", "error")
        else:
            try:
                # 1. Format the sender nicely
                sender_email = current_app.config['MAIL_USERNAME']
                
                # Create the email message
                msg = Message(
                    subject=f"Website Inquiry: {subject}", # Removed brackets [] as they sometimes trigger automated filters
                    sender=("Padre Garcia Tourism", sender_email), # Formats as: "Padre Garcia Tourism" <your@email.com>
                    recipients=[receiver],
                    reply_to=(name, email) # Formats as: "User Name" <user@email.com>
                )
                
                # Render the HTML email template
                msg.html = render_template(
                    "email/contact_form_email.html",
                    name=name,
                    email=email,
                    subject=subject,
                    message=message,
                    current_year=datetime.datetime.now().year # Pass current year for footer
                )

                # Provide a plain text alternative for clients that don't render HTML
                msg.body = f"""
New message from the Padre Garcia Tourism website:

Name: {name}
Email: {email}
Subject: {subject}

Message:
{message}

---
This message was sent via your website's contact form.
Visit Padre Garcia Tourism: {url_for('views.home', _external=True)}
"""
                
                mail.send(msg)
                flash("Your message has been sent successfully!", "success")
                
            except Exception as e:
                current_app.logger.error(f"Failed to send contact form email: {e}") 
                flash("An error occurred while sending your message. Please try again later or contact us directly.", "error")
        
        return redirect(url_for('views.contacts'))

    return render_template("contact.html", content=content)

@views.route("/spot/<int:id>")
def spot_detail(id):
    spot = TouristSpot.query.get_or_404(id)
    content = get_common_content()
    return render_template("spot_detail.html", spot=spot, content=content)

@views.route("/dashboard")
@login_required
def dashboard():
    if not current_user.is_admin:
        return redirect(url_for("views.home"))
    return render_template("admin_dashboard.html", user=current_user)

@views.route("/edit-home-hero", methods=["GET", "POST"])
@login_required
def edit_home_hero():
    if not current_user.is_admin: return redirect(url_for("views.home"))
    if request.method == "POST":
        fields = ['hero_title_1', 'hero_title_2', 'hero_subtitle']
        for field in fields:
            val = request.form.get(field)
            if val is not None:
                existing = SiteContent.query.filter_by(key=field).first()
                if existing: existing.value = val
                else: db.session.add(SiteContent(key=field, value=val))
        file = request.files.get("hero_image_file")
        if file and file.filename != '':
            path = save_file(file)
            existing = SiteContent.query.filter_by(key='hero_image_path').first()
            if existing: existing.value = path
            else: db.session.add(SiteContent(key='hero_image_path', value=path))
        db.session.commit()
        flash("Home Hero updated!", "success")
        return redirect(url_for("views.edit_home_hero"))
    content = {
        'hero_title_1': get_content('hero_title_1', 'Padre'),
        'hero_title_2': get_content('hero_title_2', 'Garcia'),
        'hero_subtitle': get_content('hero_subtitle', 'Discover the rich heritage...'),
        'hero_image_path': get_content('hero_image_path', url_for('static', filename='images/municipal.jpg'))
    }
    return render_template("edit_home_hero.html", content=content)

@views.route("/edit-header", methods=["GET", "POST"])
@login_required
def edit_header():
    if not current_user.is_admin: return redirect(url_for("views.home"))
    
    if request.method == "POST":
        file = request.files.get("site_logo_file")
        if file and file.filename != '':
            path = save_file(file)
            existing = SiteContent.query.filter_by(key='site_logo').first()
            if existing: 
                existing.value = path
            else: 
                db.session.add(SiteContent(key='site_logo', value=path))
            
            db.session.commit()
            flash("Website Logo updated successfully!", "success")
            return redirect(url_for("views.edit_header"))
            
    content = {
        'site_logo': get_content('site_logo', '')
    }
    return render_template("edit_header.html", content=content)

@views.route("/edit-about-teaser", methods=["GET", "POST"])
@login_required
def edit_about_teaser():
    if not current_user.is_admin: return redirect(url_for("views.home"))
    if request.method == "POST":
        fields = ['about_title', 'about_text'] 
        for field in fields:
            val = request.form.get(field)
            if val is not None:
                existing = SiteContent.query.filter_by(key=field).first()
                if existing: existing.value = val
                else: db.session.add(SiteContent(key=field, value=val))
        file = request.files.get("about_image_file")
        if file and file.filename != '':
            path = save_file(file)
            existing = SiteContent.query.filter_by(key='about_image_path').first()
            if existing: existing.value = path
            else: db.session.add(SiteContent(key='about_image_path', value=path))
        db.session.commit()
        flash("About Teaser updated!", "success")
        return redirect(url_for("views.edit_about_teaser"))
    content = {
        'about_title': get_content('about_title', 'Where Tradition Meets Progress'),
        'about_text': get_content('about_text', 'Known as the Cattle Trading Capital...'),
        'about_image_path': get_content('about_image_path', url_for('static', filename='images/municipal2.jpg'))
    }
    return render_template("edit_about_teaser.html", content=content)

@views.route("/manage-spots", methods=["GET", "POST"])
@login_required
def manage_spots():
    if not current_user.is_admin: return redirect(url_for("views.home"))
    if request.method == "POST":
        if "add_spot" in request.form:
            name = request.form.get("spot_name")
            desc = request.form.get("spot_desc")
            link = request.form.get("spot_link")
            file = request.files.get("spot_image_file")
            final_path = None
            if file and file.filename != '': final_path = save_file(file)
            if name and final_path:
                db.session.add(TouristSpot(name=name, image_url=final_path, description=desc, link_url=link))
                flash("Spot added successfully!", "success")
            else:
                flash("Name and Image are required.", "error")
        elif "edit_spot" in request.form:
            spot_id = request.form.get("spot_id")
            spot = TouristSpot.query.get(spot_id)
            if spot:
                spot.name = request.form.get("spot_name")
                spot.description = request.form.get("spot_desc")
                spot.link_url = request.form.get("spot_link")
                file = request.files.get("spot_image_file")
                if file and file.filename != '':
                    new_path = save_file(file)
                    spot.image_url = new_path
                db.session.commit()
                flash(f"{spot.name} updated successfully!", "success")
            else:
                flash("Spot not found.", "error")
        elif "delete_spot" in request.form:
            spot_id = request.form.get("spot_id")
            spot = TouristSpot.query.get(spot_id)
            if spot:
                db.session.delete(spot)
                flash("Spot deleted.", "success")
        db.session.commit()
        return redirect(url_for("views.manage_spots"))
    spots = TouristSpot.query.order_by(TouristSpot.id.desc()).all()
    return render_template("manage_spots.html", spots=spots)

@views.route("/manage-ordinances", methods=["GET", "POST"])
@login_required
def manage_ordinances():
    if not current_user.is_admin: return redirect(url_for("views.home"))
    if request.method == "POST":
        if "add_ordinance" in request.form:
            num = request.form.get("ord_number")
            title = request.form.get("ord_title")
            desc = request.form.get("ord_desc")
            files = request.files.getlist("ord_file")
            
            paths = []
            for f in files:
                if f and f.filename != '':
                    path = save_file(f)
                    if path: paths.append(path)
                    
            file_url = "|".join(paths) if paths else None
            
            if num and title:
                db.session.add(Ordinance(number=num, title=title, description=desc, file_url=file_url))
                flash("Ordinance added successfully!", "success")
            else:
                flash("Number and Title are required.", "error")
                
        elif "edit_ordinance" in request.form:
            ord_id = request.form.get("ord_id")
            ordinance = Ordinance.query.get(ord_id)
            if ordinance:
                ordinance.number = request.form.get("ord_number")
                ordinance.title = request.form.get("ord_title")
                ordinance.description = request.form.get("ord_desc")
                
                files = request.files.getlist("ord_file")
                new_paths = []
                for f in files:
                    if f and f.filename != '':
                        path = save_file(f)
                        if path: new_paths.append(path)
                        
                if new_paths:
                    existing = ordinance.file_url.split('|') if ordinance.file_url else []
                    existing.extend(new_paths)
                    ordinance.file_url = "|".join(existing)
                    
                db.session.commit()
                flash("Ordinance updated successfully!", "success")
                
        elif "delete_ord_file" in request.form:
            ord_id = request.form.get("ord_id")
            file_path = request.form.get("file_path")
            ordinance = Ordinance.query.get(ord_id)
            if ordinance and ordinance.file_url:
                paths = ordinance.file_url.split('|')
                if file_path in paths:
                    paths.remove(file_path)
                    ordinance.file_url = "|".join(paths) if paths else None
                    db.session.commit()
                    flash("File removed.", "success")
                    
        elif "delete_ordinance" in request.form:
            ord_id = request.form.get("ord_id")
            ordinance = Ordinance.query.get(ord_id)
            if ordinance:
                db.session.delete(ordinance)
                flash("Ordinance deleted.", "success")
                
        db.session.commit()
        return redirect(url_for("views.manage_ordinances"))
        
    ordinances = Ordinance.query.all()
    ordinances = sorted(ordinances, key=get_ord_sort_key)
    return render_template("manage_ordinances.html", ordinances=ordinances)

@views.before_app_request
def check_maintenance():
    try:
        setting = SiteContent.query.filter_by(key='site_maintenance_mode').first()
        is_maintenance = (setting.value == 'true') if setting else False
    except:
        is_maintenance = False
    if not is_maintenance:
        return None
    if (request.endpoint and 'static' in request.endpoint) or \
       (request.endpoint == 'views.maintenance') or \
       (request.endpoint and 'auth.' in request.endpoint):
        return None
    if current_user.is_authenticated and current_user.is_super_admin:
        return None
    return redirect(url_for('views.maintenance'))

@views.route("/maintenance")
def maintenance():
    if get_content('site_maintenance_mode', 'false') != 'true':
        return redirect(url_for('views.home'))
    if current_user.is_authenticated and current_user.is_super_admin:
        flash("Maintenance Mode is active, but you have Super Admin access.", "warning")
        return redirect(url_for('views.dashboard'))
    return render_template("maintenance.html")

@views.route("/site-settings", methods=["GET", "POST"])
@login_required
def site_settings():
    if not current_user.is_super_admin:
        flash("Unauthorized. Only Super Admins can access Global Settings.", "error")
        return redirect(url_for("views.dashboard"))
    
    if request.method == "POST":
        # HANDLE MAINTENANCE MODE TOGGLE
        if "toggle_maintenance" in request.form:
            mode = request.form.get("maintenance_mode")
            status = 'true' if mode else 'false'
            content = SiteContent.query.filter_by(key='site_maintenance_mode').first()
            if content:
                content.value = status
            else:
                db.session.add(SiteContent(key='site_maintenance_mode', value=status))
            db.session.commit()
            if status == 'true':
                flash("Maintenance Mode ENABLED. The public site is now locked.", "warning")
            else:
                flash("Maintenance Mode DISABLED. The site is now live.", "success")
            return redirect(url_for("views.site_settings"))

        # HANDLE CONTACT EMAIL RECEIVER UPDATE
        if "update_receiver_email" in request.form:
            email = request.form.get("receiver_email")
            # Basic email validation (you might want more robust validation)
            if "@" not in email or "." not in email:
                flash("Please enter a valid email address.", "error")
            else:
                content = SiteContent.query.filter_by(key='contact_receiver_email').first()
                if content:
                    content.value = email
                else:
                    db.session.add(SiteContent(key='contact_receiver_email', value=email))
                db.session.commit()
                flash("Contact form receiver email updated successfully.", "success")
            return redirect(url_for("views.site_settings"))

    current_status = get_content('site_maintenance_mode', 'false')
    receiver_email = get_content('contact_receiver_email', '')
    return render_template("site_settings.html", maintenance_mode=current_status, receiver_email=receiver_email)

@views.route("/edit-footer", methods=["GET", "POST"])
@login_required
def edit_footer():
    if not current_user.is_admin: return redirect(url_for("views.home"))
    if request.method == "POST":
        if "add_social" in request.form:
            platform = request.form.get("platform_name")
            url = request.form.get("platform_url")
            icon = request.form.get("platform_icon")
            if platform and url:
                new_link = SocialLink(platform=platform, url=url, icon=icon)
                db.session.add(new_link)
                db.session.commit()
                flash("Social link added!", "success")
            else:
                flash("Platform Name and URL are required.", "error")
            return redirect(url_for("views.edit_footer"))
        if "delete_social" in request.form:
            link_id = request.form.get("link_id")
            link = SocialLink.query.get(link_id)
            if link:
                db.session.delete(link)
                db.session.commit()
                flash("Social link deleted.", "success")
            return redirect(url_for("views.edit_footer"))
        if "add_quick_link" in request.form:
            label = request.form.get("link_label")
            url = request.form.get("link_url")
            if label and url:
                new_fl = FooterLink(label=label, url=url)
                db.session.add(new_fl)
                db.session.commit()
                flash("Footer link added!", "success")
            return redirect(url_for("views.edit_footer"))
        if "delete_quick_link" in request.form:
            fl_id = request.form.get("fl_id")
            link = FooterLink.query.get(fl_id)
            if link:
                db.session.delete(link)
                db.session.commit()
                flash("Footer link deleted.", "success")
            return redirect(url_for("views.edit_footer"))
        elif "edit_quick_link" in request.form:
            fl_id = request.form.get("link_id")
            link = FooterLink.query.get(fl_id)
            if link:
                link.label = request.form.get("link_label")
                link.url = request.form.get("link_url")
                db.session.commit()
                flash("Link updated successfully!", "success")
            return redirect(url_for("views.edit_footer"))
        if "add_hotline" in request.form:
            name = request.form.get("hotline_name")
            num = request.form.get("hotline_num")
            if name and num:
                new_hl = EmergencyHotline(name=name, number=num)
                db.session.add(new_hl)
                db.session.commit()
                flash("Hotline added!", "success")
            return redirect(url_for("views.edit_footer"))
        if "delete_hotline" in request.form:
            hl_id = request.form.get("hl_id")
            hotline = EmergencyHotline.query.get(hl_id)
            if hotline:
                db.session.delete(hotline)
                db.session.commit()
                flash("Hotline deleted.", "success")
            return redirect(url_for("views.edit_footer"))
        elif "edit_hotline" in request.form:
            hl_id = request.form.get("hotline_id")
            hotline = EmergencyHotline.query.get(hl_id)
            if hotline:
                hotline.name = request.form.get("hotline_name")
                hotline.number = request.form.get("hotline_num")
                db.session.commit()
                flash("Hotline updated successfully!", "success")
            return redirect(url_for("views.edit_footer"))
        else:
            fields = [
                'footer_brand_title', 'footer_brand_desc',
                'footer_links_title', 'footer_contact_title', 
                'contact_addr', 'contact_phone', 'contact_email',
                'footer_em_title', 'footer_copyright'
            ]
            for field in fields:
                val = request.form.get(field)
                if val is not None:
                    existing = SiteContent.query.filter_by(key=field).first()
                    if existing: existing.value = val
                    else: db.session.add(SiteContent(key=field, value=val))
            db.session.commit()
            flash("Footer settings updated!", "success")
            return redirect(url_for("views.edit_footer"))
    content = get_common_content() 
    return render_template("edit_footer.html", content=content)

@views.route("/edit-travel", methods=["GET", "POST"])
@login_required
def edit_travel():
    if not current_user.is_admin: return redirect(url_for("views.home"))
    if request.method == "POST":
        fields = ['travel_title_1', 'travel_text_1', 'travel_title_2', 'travel_text_2', 'travel_title_3', 'travel_text_3']
        for field in fields:
            val = request.form.get(field)
            if val is not None:
                existing = SiteContent.query.filter_by(key=field).first()
                if existing: existing.value = val
                else: db.session.add(SiteContent(key=field, value=val))
        db.session.commit()
        flash("Travel Info updated!", "success")
        return redirect(url_for("views.edit_travel"))
    content = {
        'travel_title_1': get_content('travel_title_1', 'Best Time to Visit'),
        'travel_text_1': get_content('travel_text_1', 'December 1st marks our Kabakahan Festival...'),
        'travel_title_2': get_content('travel_title_2', 'Getting Here'),
        'travel_text_2': get_content('travel_text_2', 'Accessible via STAR Tollway (Lipa Exit)...'),
        'travel_title_3': get_content('travel_title_3', 'Where to Stay'),
        'travel_text_3': get_content('travel_text_3', 'We have local inns within the town proper...'),
    }
    return render_template("edit_travel.html", content=content)

@views.route("/edit-about", methods=["GET", "POST"])
@login_required
def edit_about():
    if not current_user.is_admin: return redirect(url_for("views.home"))
    if request.method == "POST":
        fields = [
            'about_hero_badge', 'about_hero_h1', 'about_hero_sub',
            'about_intro_badge', 'about_title', 'about_text', 'about_img_caption',
            'about_feat1_title', 'about_feat1_desc', 
            'about_feat2_title', 'about_feat2_desc',
            'about_dir_title', 'about_dir_sub',
            'mission_text', 'vision_text',
            'fact_year', 'fact_barangays', 'fact_population', 'fact_festival',
            'about_cta_title', 'about_cta_text'
        ]
        for field in fields:
            val = request.form.get(field)
            if val is not None:
                existing = SiteContent.query.filter_by(key=field).first()
                if existing: existing.value = val
                else: db.session.add(SiteContent(key=field, value=val))
        file = request.files.get("about_image_file")
        if file and file.filename != '':
            path = save_file(file)
            existing = SiteContent.query.filter_by(key='about_image_path').first()
            if existing: existing.value = path
            else: db.session.add(SiteContent(key='about_image_path', value=path))
        db.session.commit()
        flash("About Page updated!", "success")
        return redirect(url_for("views.edit_about"))
    content = {
        'about_hero_badge': get_content('about_hero_badge', 'Welcome to Our Town'),
        'about_hero_h1': get_content('about_hero_h1', 'Our Story & Heritage'),
        'about_hero_sub': get_content('about_hero_sub', 'Discover the history, culture, and vision behind the Cattle Trading Capital.'),
        'about_intro_badge': get_content('about_intro_badge', 'About Padre Garcia'),
        'about_title': get_content('about_title', 'Where Tradition Meets Progress'),
        'about_text': get_content('about_text', 'Known as the Cattle Trading Capital...'),
        'about_image_path': get_content('about_image_path', url_for('static', filename='images/municipal2.jpg')),
        'about_img_caption': get_content('about_img_caption', '"A community bound by faith, hard work, and unity."'),
        'about_feat1_title': get_content('about_feat1_title', 'Rich History'),
        'about_feat1_desc': get_content('about_feat1_desc', 'Established 1949'),
        'about_feat2_title': get_content('about_feat2_title', 'Trading Hub'),
        'about_feat2_desc': get_content('about_feat2_desc', 'Economic Center'),
        'about_dir_title': get_content('about_dir_title', 'Our Direction'),
        'about_dir_sub': get_content('about_dir_sub', 'Guiding principles for a better municipality'),
        'mission_text': get_content('mission_text', 'To provide high-quality public service...'),
        'vision_text': get_content('vision_text', 'Padre Garcia shall be the premier agro-industrial...'),
        'fact_year': get_content('fact_year', '1949'),
        'fact_barangays': get_content('fact_barangays', '18'),
        'fact_population': get_content('fact_population', '50k+'),
        'fact_festival': get_content('fact_festival', 'Dec 1'),
        'about_cta_title': get_content('about_cta_title', 'Experience the Warmth of Padre Garcia'),
        'about_cta_text': get_content('about_cta_text', 'Whether you are here for business, cattle trading, or leisure...'),
    }
    return render_template("about_us_edit.html", content=content)

# ==========================================
#               ADMIN ROUTES
# ==========================================

@views.route("/edit-history", methods=["GET", "POST"])
@login_required
def edit_history():
    if not current_user.is_admin: return redirect(url_for("views.home"))

    biography_text = """An eminent Filipino Batangueño Priest – Hero, Padre Vicente Teodoro Garcia was named after St. Vincent Ferrer by his beloved parents Don Jose Garcia and Doña Andrea Teodora of barrio Maugat, then Old Rosario (1687) now this Municipality of Padre V. Garcia (1949), Province of Batangas, Philippines.

HIS EDUCATION, DISCIPLINE AND PROFESSION:
He studied at Universidad de Sto. Tomas (Bachiller en Artes 1839; Bachiller en Teologia 1847; Doctor en Teologia 1848; Licenciado en Sagrado Teologia 1885). He also attended Real Colegio de San Jose where he earned his Bachelor of Canon and Civil Law and Doctor of Divine Theology (1849). He was ordained Priest in June 1849.

HIS NOTABLE POSITIONS, DUTIES AND APOSTOLIC WORKS:
• Rector of the Royal College of San Jose, Manila
• Chaplain of the Artillery Regiment in the Peninsular Army
• Ecclesiastical Governor at the Diocese of Nueva Caceres
• Canonigo Penetenciario and Private Consultant under Prelate of Manila Cathedral
• Founder, Hospital of the Lepers in Camarines, Bicol
• Wise Counsel (from the aged) of Philippine National Hero Dr. Jose P. Rizal

HIS WRITINGS AND AUTHORSHIP:
He authored numerous works including "Oracion Funebre" (1861), "Vida de San Eustaquio" (1875), "Aves de los Almas" (1875), "Pagtulad kay Kristo" (1880), "Pagsisiyam sa Mahal na Birhen" (1881), and "Casaysayan ng mga Cababalaghan" (1881).

HIS DEFENSE OF RIZAL:
Most notably, he wrote the Brave Defense Counter Attack Letter defending "Noli Me Tangere" (Touch Me Not) or "Huwag mo Akong Salangin" published in La Solidaridad, Vol.11, 79-80 under the pen name V. Caraig (1895).

LEGACY:
On August 7, 2017, the Sangguniang Bayan passed Ordinance No. 25-2017 declaring April 5 of every year as Padre Vicente Garcia Day to commemorate the birthdate of Padre Vicente T. Garcia."""

    if request.method == "POST":
        # --- Handle Mayor Forms ---
        if "add_mayor" in request.form:
            name = request.form.get("mayor_name")
            role = request.form.get("mayor_role")
            years = request.form.get("mayor_years")
            description = request.form.get("mayor_desc")
            file = request.files.get("mayor_img")
            final_path = save_file(file) if file and file.filename != '' else url_for('static', filename='images/placeholder_mayor.jpg')
            if name:
                db.session.add(Mayor(name=name, role=role, years=years, description=description, image_url=final_path))
                db.session.commit()
                flash("New Mayor added!", "success")
            return redirect(url_for("views.edit_history"))

        if "edit_mayor" in request.form:
            mayor = Mayor.query.get_or_404(request.form.get("mayor_id"))
            mayor.name = request.form.get("mayor_name")
            mayor.role = request.form.get("mayor_role")
            mayor.years = request.form.get("mayor_years")
            mayor.description = request.form.get("mayor_desc")
            file = request.files.get("mayor_img")
            if file and file.filename != '':
                mayor.image_url = save_file(file)
            db.session.commit()
            flash("Mayor details updated!", "success")
            return redirect(url_for("views.edit_history"))

        if "delete_mayor" in request.form:
            mayor = Mayor.query.get_or_404(request.form.get("mayor_id"))
            db.session.delete(mayor)
            db.session.commit()
            flash("Mayor deleted.", "success")
            return redirect(url_for("views.edit_history"))

        # --- Handle Barangay Forms ---
        if "add_barangay" in request.form:
            name = request.form.get("brgy_name")
            new_brgy = Barangay(
                name=name,
                captain_name=request.form.get("brgy_captain"),
                map_url=request.form.get("brgy_map"),
                captain_image=save_file(request.files.get("brgy_img")) if request.files.get("brgy_img") else None
            )
            db.session.add(new_brgy)
            db.session.commit()
            flash(f"Added {name}!", "success")
            return redirect(url_for("views.edit_history"))

        if "edit_barangay" in request.form:
            brgy = Barangay.query.get_or_404(request.form.get("brgy_id"))
            brgy.name = request.form.get("brgy_name")
            brgy.captain_name = request.form.get("brgy_captain")
            brgy.map_url = request.form.get("brgy_map")
            file = request.files.get("brgy_img")
            if file and file.filename != '':
                brgy.captain_image = save_file(file)
            db.session.commit()
            flash(f"Updated {brgy.name}!", "success")
            return redirect(url_for("views.edit_history"))

        if "delete_barangay" in request.form:
            brgy = Barangay.query.get_or_404(request.form.get("brgy_id"))
            db.session.delete(brgy)
            db.session.commit()
            flash("Barangay deleted.", "success")
            return redirect(url_for("views.edit_history"))
        
        # --- Handle History Media Upload (Gallery) ---
        if "add_history_media" in request.form:
            files = request.files.getlist("media_files")
            caption = request.form.get("media_caption")
            section_key = request.form.get("section_key") 
            for file in files:
                if file and file.filename != '':
                    path = save_file(file)
                    ext = file.filename.split('.')[-1].lower()
                    media_type = 'video' if ext in ['mp4', 'mov', 'webm'] else 'image'
                    new_media = HistoryMedia(section_key=section_key, media_url=path, media_type=media_type, caption=caption)
                    db.session.add(new_media)
            db.session.commit()
            flash(f"Added new media item(s).", "success")
            return redirect(url_for("views.edit_history"))

        if "update_history_media_caption" in request.form:
            media_item = HistoryMedia.query.get_or_404(request.form.get("media_id"))
            media_item.caption = request.form.get("media_caption")
            db.session.commit()
            flash("Image description updated!", "success")
            return redirect(url_for("views.edit_history"))

        if "delete_history_media" in request.form:
            media_item = HistoryMedia.query.get_or_404(request.form.get("media_id"))
            db.session.delete(media_item)
            db.session.commit()
            flash("Media item deleted.", "success")
            return redirect(url_for("views.edit_history"))

        # --- Handle Main Static Content (Save All Changes Button) ---
        if "update_main_content" in request.form:
            pdf_file = request.files.get("hist_pg_pdf")
            if pdf_file and pdf_file.filename != '':
                path = save_file(pdf_file)
                existing = SiteContent.query.filter_by(key='hist_pg_file').first()
                if existing: existing.value = path
                else: db.session.add(SiteContent(key='hist_pg_file', value=path))

            fields = [
                'hist_hero_title', 'hist_hero_sub', 'hist_org_title', 'hist_org_text',
                'hist_build_title', 'hist_build_sub', 'hist_b1_lbl', 'hist_b2_lbl', 'hist_b3_lbl', 'hist_b4_lbl',
                'hist_b1_desc', 'hist_b2_desc', 'hist_b3_desc', 'hist_b4_desc',
                'hist_pg_title', 'hist_pg_sub', 'hist_pg_sect_title', 'hist_pg_text', 'hist_pg_wiki',
                'hist_mayor_title', 'hist_mayor_sub', 'hist_brgy_title', 'hist_brgy_sub',
                'hist_extra_title', 'hist_extra_sub', 'hist_extra_desc'
            ]
            for field in fields:
                val = request.form.get(field)
                if val is not None:
                    existing = SiteContent.query.filter_by(key=field).first()
                    if existing: existing.value = val
                    else: db.session.add(SiteContent(key=field, value=val))

            img_fields = ['hist_hero_img', 'hist_pg_img', 'hist_b1_img', 'hist_b2_img', 'hist_b3_img', 'hist_b4_img']
            for field in img_fields:
                file = request.files.get(field + "_file")
                if file and file.filename != '':
                    path = save_file(file)
                    existing = SiteContent.query.filter_by(key=field).first()
                    if existing: existing.value = path
                    else: db.session.add(SiteContent(key=field, value=path))

            db.session.commit()
            flash("History Page updated successfully!", "success")
            return redirect(url_for("views.edit_history"))

    # GET Request
    mayors_list = Mayor.query.order_by(Mayor.id).all()
    barangays_list = Barangay.query.order_by(Barangay.name).all()
    pg_media = HistoryMedia.query.filter_by(section_key='padre_garcia').order_by(HistoryMedia.id.desc()).all()
    extra_info_media = HistoryMedia.query.filter_by(section_key='history_extra_info').order_by(HistoryMedia.id.desc()).all()

    defaults = {
        'hist_hero_title': 'History & Heritage', 'hist_hero_sub': 'From Lumang Bayan to Today',
        'hist_hero_img': url_for('static', filename='images/municipal.jpg'),
        'hist_org_title': 'Our Origins', 'hist_org_text': 'Originally known as Lumang Bayan...',
        'hist_build_title': 'Transformation Of Municipal Buildings', 'hist_build_sub': 'Witnessing the structural evolution...',
        'hist_b1_img': url_for('static', filename='images/firstm.jpg.jpg'), 'hist_b1_lbl': 'First Municipal Hall', 'hist_b1_desc': 'The original municipal hall of Padre Garcia.',
        'hist_b2_img': url_for('static', filename='images/firstmm.jpg.jpg'), 'hist_b2_lbl': 'After the Fire', 'hist_b2_desc': 'The rebuilt structure following the tragic fire.',
        'hist_b3_img': url_for('static', filename='images/first.jpg.jpg'), 'hist_b3_lbl': 'First Renovation', 'hist_b3_desc': 'The first major architectural renovation of the hall.',
        'hist_b4_img': url_for('static', filename='images/municipal.jpg'), 'hist_b4_lbl': 'Modern Structure', 'hist_b4_desc': 'The contemporary and modern municipal building standing today.',
        'hist_pg_title': 'Padre Vicente Teodoro Garcia', 'hist_pg_sub': 'April 05, 1817 – July 12, 1899',
        'hist_pg_sect_title': 'Life & Works', 'hist_pg_text': biography_text, 
        'hist_pg_img': url_for('static', filename='images/pgv.jpg.jpg'), 'hist_pg_wiki': 'https://en.wikipedia.org/wiki/Vicente_Garc%C3%ADa',
        'hist_pg_file': '', 'hist_mayor_title': "Mayor's Generation", 'hist_mayor_sub': "Leaders who shaped our history",
        'hist_brgy_title': 'The 18 Barangays', 'hist_brgy_sub': 'Click on a barangay to view details',
        'hist_extra_title': 'A Legacy of Strength', 'hist_extra_sub': 'Cultural Resilience', 'hist_extra_desc': 'Padre Garcia has weathered many storms...',
    }
    
    content = {}
    for k, v in defaults.items(): content[k] = get_content(k, v)
    
    return render_template("edit_history.html", content=content, mayors=mayors_list, barangays=barangays_list, pg_media=pg_media, extra_info_media=extra_info_media)

@views.route("/edit-commerce", methods=["GET", "POST"])
@login_required
def edit_commerce():
    if not current_user.is_admin: return redirect(url_for("views.home"))
    
    if request.method == "POST":
        
        if "add_est" in request.form:
            new_est = CommercialEstablishment(name=request.form.get("est_name"), description=request.form.get("est_desc"), map_url=request.form.get("est_map"), image_url=save_file(request.files.get("est_img")) if request.files.get("est_img") else None)
            db.session.add(new_est)
            db.session.commit()
            flash("Establishment added successfully!", "success")
            return redirect(url_for("views.edit_commerce"))

        if "edit_est" in request.form:
            est = CommercialEstablishment.query.get(request.form.get("est_id"))
            if est:
                est.name, est.description, est.map_url = request.form.get("est_name"), request.form.get("est_desc"), request.form.get("est_map")
                if request.files.get("est_img") and request.files.get("est_img").filename != '': est.image_url = save_file(request.files.get("est_img"))
                db.session.commit()
                flash("Establishment updated!", "success")
            return redirect(url_for("views.edit_commerce"))

        if "delete_est" in request.form:
            est = CommercialEstablishment.query.get(request.form.get("est_id"))
            if est:
                db.session.delete(est)
                db.session.commit()
            return redirect(url_for("views.edit_commerce"))

        if "add_acc" in request.form:
            new_acc = Accommodation(name=request.form.get("acc_name"), description=request.form.get("acc_desc"), map_url=request.form.get("acc_map"), image_url=save_file(request.files.get("acc_img")) if request.files.get("acc_img") else None)
            db.session.add(new_acc)
            db.session.commit()
            flash("Accommodation added successfully!", "success")
            return redirect(url_for("views.edit_commerce"))

        if "edit_acc" in request.form:
            acc = Accommodation.query.get(request.form.get("acc_id"))
            if acc:
                acc.name, acc.description, acc.map_url = request.form.get("acc_name"), request.form.get("acc_desc"), request.form.get("acc_map")
                if request.files.get("acc_img") and request.files.get("acc_img").filename != '': acc.image_url = save_file(request.files.get("acc_img"))
                db.session.commit()
                flash("Accommodation updated!", "success")
            return redirect(url_for("views.edit_commerce"))

        if "delete_acc" in request.form:
            acc = Accommodation.query.get(request.form.get("acc_id"))
            if acc:
                db.session.delete(acc)
                db.session.commit()
            return redirect(url_for("views.edit_commerce"))

        if "add_bank" in request.form:
            new_bank = FinancialInstitution(name=request.form.get("bank_name"), url=request.form.get("bank_url"))
            db.session.add(new_bank)
            db.session.commit()
            flash("Financial Institution added!", "success")
            return redirect(url_for("views.edit_commerce"))

        if "edit_bank" in request.form:
            bank = FinancialInstitution.query.get(request.form.get("bank_id"))
            if bank:
                bank.name, bank.url = request.form.get("bank_name"), request.form.get("bank_url")
                db.session.commit()
                flash("Institution updated!", "success")
            return redirect(url_for("views.edit_commerce"))

        if "delete_bank" in request.form:
            bank = FinancialInstitution.query.get(request.form.get("bank_id"))
            if bank:
                db.session.delete(bank)
                db.session.commit()
            return redirect(url_for("views.edit_commerce"))

        fields = [
            'comm_hero_title', 'comm_hero_sub', 'comm_hero_desc',
            'comm_intro_title', 'comm_intro_text',
            'comm_shop_title', 'comm_shop_head', 'comm_shop_text',
            'comm_shop_li1', 'comm_shop_li2', 'comm_shop_li3',
            'comm_dine_title',
            'comm_stay_title', 'comm_stay_head', 'comm_stay_text',
            'comm_fin_title', 'comm_fin_text'
        ]
        for field in fields:
            val = request.form.get(field)
            if val is not None:
                existing = SiteContent.query.filter_by(key=field).first()
                if existing: existing.value = val
                else: db.session.add(SiteContent(key=field, value=val))
                
        img_fields = ['comm_hero_bg', 'comm_shop_img']
        for field in img_fields:
            file = request.files.get(field + "_file")
            if file and file.filename != '':
                path = save_file(file)
                existing = SiteContent.query.filter_by(key=field).first()
                if existing: existing.value = path
                else: db.session.add(SiteContent(key=field, value=path))
                
        db.session.commit()
        flash("Commerce Page static content updated!", "success")
        return redirect(url_for("views.edit_commerce"))

    defaults = {
        'comm_hero_title': 'Commerce & Lifestyle', 'comm_hero_sub': 'Business & Leisure', 'comm_hero_desc': 'A growing agro-industrial hub...', 
        'comm_hero_bg': url_for('static', filename='images/commerce_hero.jpg'),
        'comm_intro_title': 'A Thriving Economy', 'comm_intro_text': 'Beyond the cattle market...',
        'comm_shop_title': 'Shopping & Markets', 'comm_shop_head': 'Padre Garcia Public Market', 'comm_shop_text': 'The daily heartbeat of the town...', 'comm_shop_img': url_for('static', filename='images/public_market.jpg'),
        'comm_shop_li1': 'Fresh Fruits & Vegetables', 'comm_shop_li2': 'Clothing & Dry Goods', 'comm_shop_li3': 'Agricultural Supplies',
        'comm_dine_title': 'Featured Establishments',
        'comm_stay_title': 'Stay & Relax', 'comm_stay_head': 'Resorts & Inns', 'comm_stay_text': 'Padre Garcia offers various accommodations...',
        'comm_fin_title': 'Financial Infrastructure', 'comm_fin_text': 'To support the high volume of trade...'
    }
    content = {}
    for k, v in defaults.items(): content[k] = get_content(k, v)
    
    establishments = CommercialEstablishment.query.order_by(CommercialEstablishment.id.desc()).all()
    accommodations = Accommodation.query.order_by(Accommodation.id.desc()).all()
    banks = FinancialInstitution.query.order_by(FinancialInstitution.id.desc()).all()
    
    return render_template("edit_commerce.html", content=content, establishments=establishments, accommodations=accommodations, banks=banks)


@views.route("/edit-attractions", methods=["GET", "POST"])
@login_required
def edit_attractions():
    if not current_user.is_admin: return redirect(url_for("views.home"))
    
    if request.method == "POST":
        
        # --- Handle Main Attraction Edits ---
        if "add_attr" in request.form:
            new_attr = MajorAttraction(
                name=request.form.get("attr_name"), 
                tag=request.form.get("attr_tag"),
                description=request.form.get("attr_desc"), 
                location=request.form.get("attr_loc"),
                map_url=request.form.get("attr_map"), 
                full_content=request.form.get("attr_full_content"),
                media_url=save_file(request.files.get("attr_media")) if request.files.get("attr_media") else None
            )
            db.session.add(new_attr)
            db.session.commit()
            flash("Attraction added successfully!", "success")
            return redirect(url_for("views.edit_attractions"))

        if "edit_attr" in request.form:
            attr = MajorAttraction.query.get_or_404(request.form.get("attr_id"))
            attr.name = request.form.get("attr_name")
            attr.tag = request.form.get("attr_tag")
            attr.description = request.form.get("attr_desc")
            attr.location = request.form.get("attr_loc")
            attr.map_url = request.form.get("attr_map")
            attr.full_content = request.form.get("attr_full_content")
            
            file = request.files.get("attr_media")
            if file and file.filename != '': 
                attr.media_url = save_file(file)
            db.session.commit()
            flash("Attraction details updated!", "success")
            return redirect(url_for("views.edit_attractions"))

        if "delete_attr" in request.form:
            attr = MajorAttraction.query.get_or_404(request.form.get("attr_id"))
            db.session.delete(attr)
            db.session.commit()
            flash("Attraction deleted.", "success")
            return redirect(url_for("views.edit_attractions"))

        # --- Handle Gallery Media Upload (Images/Videos) ---
        if "add_gallery_media" in request.form:
            attraction_id = request.form.get("attraction_id")
            attraction = MajorAttraction.query.get_or_404(attraction_id)
            files = request.files.getlist("gallery_files")
            caption = request.form.get("media_caption")

            for file in files:
                if file and file.filename != '':
                    path = save_file(file)
                    ext = file.filename.split('.')[-1].lower()
                    media_type = 'video' if ext in ['mp4', 'mov', 'webm'] else 'image'

                    new_media = AttractionMedia(
                        attraction_id=attraction_id,
                        media_url=path,
                        media_type=media_type,
                        caption=caption
                    )
                    db.session.add(new_media)
            db.session.commit()
            flash(f"Added new gallery media to {attraction.name}.", "success")
            return redirect(url_for("views.edit_attractions"))
        
        # --- Handle Downloadable Files Upload (PDFs, Docs, etc.) ---
        if "add_download_file" in request.form:
            attraction_id = request.form.get("attraction_id")
            attraction = MajorAttraction.query.get_or_404(attraction_id)
            files = request.files.getlist("download_files")
            caption = request.form.get("file_caption")

            for file in files:
                if file and file.filename != '':
                    path = save_file(file)
                    
                    new_media = AttractionMedia(
                        attraction_id=attraction_id,
                        media_url=path,
                        media_type='file',
                        caption=caption
                    )
                    db.session.add(new_media)
            db.session.commit()
            flash(f"Added downloadable file(s) to {attraction.name}.", "success")
            return redirect(url_for("views.edit_attractions"))
        
        # --- Handle Media Deletion (For both visual media and files) ---
        if "delete_media" in request.form:
            media_id = request.form.get("media_id")
            media_item = AttractionMedia.query.get_or_404(media_id)
            
            # Optional: Delete the actual file from the server
            try:
                if media_item.media_url:
                    file_path = os.path.join(current_app.root_path, media_item.media_url)
                    if os.path.exists(file_path):
                        os.remove(file_path)
            except Exception as e:
                current_app.logger.error(f"Error deleting file {media_item.media_url}: {e}")

            db.session.delete(media_item)
            db.session.commit()
            flash("Media/File item deleted.", "success")
            return redirect(url_for("views.edit_attractions"))

        # --- Static Content Handler ---
        fields = ['attr_hero_title', 'attr_hero_sub', 'attr_hero_desc']
        for field in fields:
            val = request.form.get(field)
            if val is not None:
                existing = SiteContent.query.filter_by(key=field).first()
                if existing: 
                    existing.value = val
                else: 
                    db.session.add(SiteContent(key=field, value=val))
                
        # Handle file upload for static content
        file = request.files.get("attr_hero_bg_file")
        if file and file.filename != '':
            path = save_file(file)
            existing = SiteContent.query.filter_by(key="attr_hero_bg").first()
            if existing: 
                existing.value = path
            else: 
                db.session.add(SiteContent(key="attr_hero_bg", value=path))
                
        db.session.commit()
        flash("Attractions Page static content updated!", "success")
        return redirect(url_for("views.edit_attractions"))

    # --- GET Request Logic ---
    defaults = {
        'attr_hero_title': 'Major Attractions', 
        'attr_hero_sub': 'Pride of the Town', 
        'attr_hero_desc': 'From our economic heart to our natural wonders.', 
        'attr_hero_bg': url_for('static', filename='images/cattle_market.jpg')
    }
    content = {}
    for k, v in defaults.items(): content[k] = get_content(k, v)
    
    attractions_list = MajorAttraction.query.order_by(MajorAttraction.id.desc()).all()
    
    return render_template("edit_attractions.html", content=content, attractions=attractions_list)

@views.route("/edit-culture", methods=["GET", "POST"])
@login_required
def edit_culture():
    if not current_user.is_admin: 
        return redirect(url_for("views.home"))

    if request.method == "POST":
        # 1. List ALL text-based fields including the NEW repositioning (pos) fields
        fields = [
            'cult_hero_title', 'cult_hero_sub', 'cult_hero_tag',
            'cult_church_title', 'cult_old_lbl', 'cult_new_lbl',
            'cult_hist_title', 'cult_hist_text', 'cult_arch_title', 'cult_arch_text',
            'cult_patron_title', 'cult_patron_sub', 'cult_patron_text',
            'cult_mon_title', 'cult_mon_sub',
            'cult_m1_name', 'cult_m1_desc', 'cult_m1_pos', # Added pos
            'cult_m2_name', 'cult_m2_desc', 'cult_m2_pos', # Added pos
            'cult_m3_name', 'cult_m3_desc', 'cult_m3_pos'  # Added pos
        ]

        # 2. Loop through and save each field to the SiteContent table
        for field in fields:
            val = request.form.get(field)
            if val is not None:
                existing = SiteContent.query.filter_by(key=field).first()
                if existing: 
                    existing.value = val
                else: 
                    db.session.add(SiteContent(key=field, value=val))

        # 3. Handle Image Uploads
        img_fields = [
            'cult_hero_bg', 'cult_old_img', 'cult_new_img', 'cult_patron_img',
            'cult_m1_img', 'cult_m2_img', 'cult_m3_img'
        ]
        for field in img_fields:
            file = request.files.get(field + "_file")
            if file and file.filename != '':
                path = save_file(file)
                existing = SiteContent.query.filter_by(key=field).first()
                if existing: 
                    existing.value = path
                else: 
                    db.session.add(SiteContent(key=field, value=path))

        db.session.commit()
        flash("Culture Page updated successfully!", "success")
        return redirect(url_for("views.edit_culture"))

    # --- GET REQUEST (Retrieving data for the editor) ---
    defaults = {
        'cult_hero_title': 'Cultural Inventory', 
        'cult_hero_sub': 'The sacred sites...', 
        'cult_hero_tag': 'Preserving Heritage', 
        'cult_hero_bg': url_for('static', filename='images/municipal.jpg'),
        'cult_church_title': 'Most Holy Rosary Parish', 
        'cult_old_img': url_for('static', filename='images/church_old.jpg'), 
        'cult_old_lbl': 'The Old Church', 
        'cult_new_img': url_for('static', filename='images/church_new.jpg'), 
        'cult_new_lbl': 'The Modern Structure',
        'cult_hist_title': 'Historical Significance', 
        'cult_hist_text': 'The Parish stands as...', 
        'cult_arch_title': 'Architecture', 
        'cult_arch_text': 'Exterior details...',
        'cult_patron_img': url_for('static', filename='images/mama_mary.jpg'), 
        'cult_patron_title': 'Our Lady of the Most Holy Rosary', 
        'cult_patron_sub': '"The beloved patroness..."', 
        'cult_patron_text': 'The image...',
        'cult_mon_title': 'Historical Monuments', 
        'cult_mon_sub': 'Honoring Pillars',
        'cult_m1_name': 'Padre Vicente Garcia', 'cult_m1_desc': 'A Filipino priest...', 'cult_m1_img': url_for('static', filename='images/monument_vicente.jpg'), 'cult_m1_pos': '50',
        'cult_m2_name': 'Hon. Graciano R. Recto', 'cult_m2_desc': 'First Mayor...', 'cult_m2_img': url_for('static', filename='images/monument_recto.jpg'), 'cult_m2_pos': '50',
        'cult_m3_name': 'Father Antonio', 'cult_m3_desc': 'Religious figure...', 'cult_m3_img': url_for('static', filename='images/monument_antonio.jpg'), 'cult_m3_pos': '50'
    }
    
    content = {}
    for k, v in defaults.items(): 
        content[k] = get_content(k, v)
        
    return render_template("edit_cultural_inventory.html", content=content)

@views.route("/edit-festival", methods=["GET", "POST"])
@login_required
def edit_festival():
    if not current_user.is_admin: return redirect(url_for("views.home"))
    
    if request.method == "POST":
        
        if "add_event" in request.form:
            new_event = FestivalEvent(
                month=request.form.get("ev_month"), day=request.form.get("ev_day"), 
                title=request.form.get("ev_title"), location=request.form.get("ev_loc"), 
                description=request.form.get("ev_desc")
            )
            db.session.add(new_event)
            db.session.commit()
            flash("Event added successfully!", "success")
            return redirect(url_for("views.edit_festival"))
            
        if "edit_event" in request.form:
            ev = FestivalEvent.query.get(request.form.get("event_id"))
            if ev:
                ev.month, ev.day, ev.title = request.form.get("ev_month"), request.form.get("ev_day"), request.form.get("ev_title")
                ev.location, ev.description = request.form.get("ev_loc"), request.form.get("ev_desc")
                db.session.commit()
                flash("Event updated!", "success")
            return redirect(url_for("views.edit_festival"))
            
        if "delete_event" in request.form:
            event = FestivalEvent.query.get(request.form.get("event_id"))
            if event:
                db.session.delete(event)
                db.session.commit()
            return redirect(url_for("views.edit_festival"))

        if "add_gal" in request.form:
            files = request.files.getlist("gal_img")
            caption = request.form.get("gal_cap")
            link_url = request.form.get("gal_link")
            
            image_added = False
            for file in files:
                if file and file.filename != '':
                    path = save_file(file)
                    if path:
                        new_gal = FestivalGalleryImage(
                            caption=caption,
                            link_url=link_url,
                            image_url=path
                        )
                        db.session.add(new_gal)
                        image_added = True
            
            if image_added:
                db.session.commit()
                flash("New gallery image(s) added successfully!", "success")
            else:
                flash("No images were selected for upload.", "error")
                
            return redirect(url_for("views.edit_festival"))

        if "edit_gal" in request.form:
            gal = FestivalGalleryImage.query.get(request.form.get("gal_id"))
            if gal:
                gal.caption = request.form.get("gal_cap")
                gal.link_url = request.form.get("gal_link")
                file = request.files.get("gal_img")
                if file and file.filename != '': gal.image_url = save_file(file)
                db.session.commit()
                flash("Gallery image updated!", "success")
            return redirect(url_for("views.edit_festival"))

        if "delete_gal" in request.form:
            gal = FestivalGalleryImage.query.get(request.form.get("gal_id"))
            if gal:
                db.session.delete(gal)
                db.session.commit()
            return redirect(url_for("views.edit_festival"))

        fields = [
            'fest_date_badge', 'fest_hero_title', 'fest_hero_sub',
            'fest_intro_title', 'fest_intro_text',
            'fest_c1_title', 'fest_c1_desc', 'fest_c2_title', 'fest_c2_desc', 'fest_c3_title', 'fest_c3_desc',
            'fest_legal_title', 'fest_legal_desc', 'fest_ord_text',
            'fest_prog_title', 'fest_prog_sub', 'fest_gal_title'
        ]
        for field in fields:
            val = request.form.get(field)
            if val is not None:
                existing = SiteContent.query.filter_by(key=field).first()
                if existing: existing.value = val
                else: db.session.add(SiteContent(key=field, value=val))
                
        img_fields = ['fest_hero_bg', 'fest_legal_img']
        for field in img_fields:
            file = request.files.get(field + "_file")
            if file and file.filename != '':
                path = save_file(file)
                existing = SiteContent.query.filter_by(key=field).first()
                if existing: existing.value = path
                else: db.session.add(SiteContent(key=field, value=path))
                
        db.session.commit()
        flash("Festival Page static content updated!", "success")
        return redirect(url_for("views.edit_festival"))

    events_list = FestivalEvent.query.all()
    gallery_list = FestivalGalleryImage.query.order_by(FestivalGalleryImage.id.desc()).all()
    
    defaults = {
        'fest_hero_bg': url_for('static', filename='images/festival_hero.jpg'), 'fest_date_badge': 'Every Dec 1', 'fest_hero_title': 'Kabakahan Festival', 'fest_hero_sub': 'Celebrating the Cattle Trading Capital',
        'fest_intro_title': 'The Spirit of the Festival', 'fest_intro_text': 'Annual cultural celebration...',
        'fest_c1_title': 'Culture', 'fest_c1_desc': 'Showcasing talent', 'fest_c2_title': 'Trade', 'fest_c2_desc': 'Boosting economy', 'fest_c3_title': 'Faith', 'fest_c3_desc': 'Thanksgiving',
        'fest_legal_title': 'Legal Basis', 'fest_legal_desc': 'Institutionalized by law...', 'fest_legal_img': url_for('static', filename='images/festival_parade.jpg'), 'fest_ord_text': 'WHEREAS...',
        'fest_prog_title': 'Program & Activities', 'fest_prog_sub': 'Highlights', 'fest_gal_title': 'Captured Moments'
    }
    content = {}
    for k, v in defaults.items(): content[k] = get_content(k, v)
    
    return render_template("edit_festival.html", content=content, events=events_list, gallery=gallery_list)

@views.route("/edit-food", methods=["GET", "POST"])
@login_required
def edit_food():
    if not current_user.is_admin: return redirect(url_for("views.home"))
    
    if request.method == "POST":
        
        if "add_dish" in request.form:
            new_dish = FoodDish(
                name=request.form.get("dish_name"),
                tagline=request.form.get("dish_tagline"),
                description=request.form.get("dish_desc"),
                link_url=request.form.get("dish_link"),
                image_url=save_file(request.files.get("dish_img")) if request.files.get("dish_img") else None
            )
            db.session.add(new_dish)
            db.session.commit()
            flash("Dish added successfully!", "success")
            return redirect(url_for("views.edit_food"))

        if "edit_dish" in request.form:
            dish = FoodDish.query.get(request.form.get("dish_id"))
            if dish:
                dish.name = request.form.get("dish_name")
                dish.tagline = request.form.get("dish_tagline")
                dish.description = request.form.get("dish_desc")
                dish.link_url = request.form.get("dish_link")
                file = request.files.get("dish_img")
                if file and file.filename != '': dish.image_url = save_file(file)
                db.session.commit()
                flash("Dish updated!", "success")
            return redirect(url_for("views.edit_food"))

        if "delete_dish" in request.form:
            dish = FoodDish.query.get(request.form.get("dish_id"))
            if dish:
                db.session.delete(dish)
                db.session.commit()
            return redirect(url_for("views.edit_food"))

        if "add_sweet" in request.form:
            new_sweet = SweetTreat(
                name=request.form.get("sweet_name"),
                description=request.form.get("sweet_desc"),
                link_url=request.form.get("sweet_link"),
                image_url=save_file(request.files.get("sweet_img")) if request.files.get("sweet_img") else None
            )
            db.session.add(new_sweet)
            db.session.commit()
            flash("Sweet Treat added!", "success")
            return redirect(url_for("views.edit_food"))

        if "edit_sweet" in request.form:
            sweet = SweetTreat.query.get(request.form.get("sweet_id"))
            if sweet:
                sweet.name = request.form.get("sweet_name")
                sweet.description = request.form.get("sweet_desc")
                sweet.link_url = request.form.get("sweet_link")
                file = request.files.get("sweet_img")
                if file and file.filename != '': sweet.image_url = save_file(file)
                db.session.commit()
                flash("Sweet Treat updated!", "success")
            return redirect(url_for("views.edit_food"))

        if "delete_sweet" in request.form:
            sweet = SweetTreat.query.get(request.form.get("sweet_id"))
            if sweet:
                db.session.delete(sweet)
                db.session.commit()
            return redirect(url_for("views.edit_food"))

        fields = ['food_hero_title', 'food_hero_sub', 'food_hero_desc', 'food_s3_title', 'food_s3_desc']
        for field in fields:
            val = request.form.get(field)
            if val is not None:
                existing = SiteContent.query.filter_by(key=field).first()
                if existing: existing.value = val
                else: db.session.add(SiteContent(key=field, value=val))
                
        file = request.files.get("food_hero_bg_file")
        if file and file.filename != '':
            path = save_file(file)
            existing = SiteContent.query.filter_by(key='food_hero_bg').first()
            if existing: existing.value = path
            else: db.session.add(SiteContent(key='food_hero_bg', value=path))
                
        db.session.commit()
        flash("Food Page static content updated!", "success")
        return redirect(url_for("views.edit_food"))

    defaults = {
        'food_hero_title': 'Gastronomic Delights', 
        'food_hero_sub': 'Taste of Padre Garcia', 
        'food_hero_desc': 'Discover the rich, savory flavors...', 
        'food_hero_bg': url_for('static', filename='images/food_hero.jpg'),
        'food_s3_title': 'Sweets & Pasalubong', 
        'food_s3_desc': 'Take home a piece of Padre Garcia...'
    }
    content = {}
    for k, v in defaults.items(): content[k] = get_content(k, v)
    
    dishes = FoodDish.query.order_by(FoodDish.id.desc()).all()
    sweets = SweetTreat.query.order_by(SweetTreat.id.desc()).all()
    
    return render_template("edit_food.html", content=content, dishes=dishes, sweets=sweets)

@views.route("/edit-contact", methods=["GET", "POST"])
@login_required
def edit_contact():
    if not current_user.is_admin: return redirect(url_for("views.home"))
    if request.method == "POST":
        fields = [
            'contact_hero_title', 'contact_hero_sub',
            'contact_card_addr_title', 'contact_card_addr_text',
            'contact_card_phone_title', 'contact_phone_main', 'contact_phone_alt',
            'contact_card_email_title', 'contact_email_main', 'contact_email_alt',
            'contact_form_title', 'contact_map_url'
        ]
        for field in fields:
            val = request.form.get(field)
            if val is not None:
                existing = SiteContent.query.filter_by(key=field).first()
                if existing: existing.value = val
                else: db.session.add(SiteContent(key=field, value=val))
        img_fields = ['contact_hero_bg']
        for field in img_fields:
            file = request.files.get(field + "_file")
            if file and file.filename != '':
                path = save_file(file)
                existing = SiteContent.query.filter_by(key=field).first()
                if existing: existing.value = path
                else: db.session.add(SiteContent(key=field, value=path))
        db.session.commit()
        flash("Contact Page updated!", "success")
        return redirect(url_for("views.edit_contact"))
    defaults = {
        'contact_hero_title': 'Get in Touch', 'contact_hero_sub': "We'd love to hear from you", 'contact_hero_bg': url_for('static', filename='images/municipal.jpg'),
        'contact_card_addr_title': 'Visit Us', 'contact_card_addr_text': '2nd Flr. LAM Bldg, Poblacion...',
        'contact_card_phone_title': 'Call Us', 'contact_phone_main': '(043) 515-9209', 'contact_phone_alt': '(043) 515-7424',
        'contact_card_email_title': 'Email Us', 'contact_email_main': 'tourism@padregarcia.gov.ph', 'contact_email_alt': 'info@padregarcia.gov.ph',
        'contact_form_title': 'Send us a Message', 'contact_map_url': 'https://www.google.com/maps/embed?pb=...'
    }
    content = {}
    for k, v in defaults.items(): content[k] = get_content(k, v)
    return render_template("edit_contact.html", content=content)