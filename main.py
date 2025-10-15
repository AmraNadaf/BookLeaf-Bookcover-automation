import cv2
import easyocr
#import matplotlib.pyplot as plt
import difflib
import numpy as np
import re
import os
import time
from datetime import datetime
from pdf2image import convert_from_path
from pyairtable import Api
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# ==================== CONFIGURATION ====================
FOLDER_ID = "1V_K4reMFymFRytjrtMFmOO7QkN-E5dMf"  # Your Google Drive folder ID
POLL_INTERVAL = 60  # Check every 60 seconds
DOWNLOAD_DIR = "./downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Airtable setup
AIRTABLE_API_KEY = "#"
AIRTABLE_BASE_ID = "app4SYI2WfSXar9nP"
AIRTABLE_TABLE_NAME= "tblCECcfMV07ksUxM"
# TABLE_ID = "BookCovers"
#------------------necessary api library usage-----------
api = Api(AIRTABLE_API_KEY)
table = api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)



# Expected badge text
EXPECTED_TEXT1 = "Winner of the 21st Century Emily Dickinson Award".lower()
EXPECTED_TEXT2 = "Award".lower()

# Track processed files
PROCESSED_FILES_LOG = "processed_files.txt"

def load_processed_files():
    """Load previously processed file IDs from disk"""
    if os.path.exists(PROCESSED_FILES_LOG):
        with open(PROCESSED_FILES_LOG, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_processed_file(file_id):
    """Save a processed file ID to disk"""
    with open(PROCESSED_FILES_LOG, 'a') as f:
        f.write(f"{file_id}\n")

processed_files = load_processed_files()
print(f"Loaded {len(processed_files)} previously processed files")

# Initialize OCR reader once (expensive operation)
print("Initializing OCR reader...")

reader = easyocr.Reader(['en'], gpu=True)
print("✅ OCR reader ready\n")


# ==================== HELPER FUNCTIONS ====================

def draw_bounding_boxes(image, detections, threshold=0.25):
    """Draw bounding boxes around detected text"""
    for bbox, text, score in detections:
        if score > threshold:
            cv2.rectangle(image, tuple(map(int, bbox[0])), tuple(map(int, bbox[2])), (0, 255, 0), 5)
            cv2.putText(image, text, tuple(map(int, bbox[0])), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.65, (255, 0, 0), 2)


def find_overlap_text_dual(text_detections, badge_coords, expected_text1, expected_text2, similarity_threshold=0.8,
                           tolerance=3):
    """Check if any text overlaps with badge area (except expected badge text)"""
    badge_x1, badge_y1, badge_x2, badge_y2 = badge_coords
    safe_margin_flag_foverlap = False
    overlap_flag = False
    overlap_text = ""

    for bbox, text, score in text_detections:
        xs = [pt[0] for pt in bbox]
        ys = [pt[1] for pt in bbox]

        if any((badge_x1 - tolerance) <= x <= (badge_x2 + tolerance) and
               (badge_y1 - tolerance) <= y <= (badge_y2 + tolerance) for x, y in zip(xs, ys)):

            similarity1 = difflib.SequenceMatcher(None, text.lower(), expected_text1.lower()).ratio()
            similarity2 = difflib.SequenceMatcher(None, text.lower(), expected_text2.lower()).ratio()
            print(f"  Detected: '{text}', similarity1: {similarity1:.2f}, similarity2: {similarity2:.2f}")

            if similarity1 < similarity_threshold and similarity2 < similarity_threshold:
                print(f"  ⚠️ Overlapping text found: '{text}'")
                safe_margin_flag_foverlap = True
                overlap_flag = True
                overlap_text = text

    if not overlap_flag:
        print("  ✅ No unwanted overlaps detected.")

    return safe_margin_flag_foverlap, overlap_flag, overlap_text


def comprehensive_image_quality(image_region, expected_width_inches=5, expected_height_inches=8, actual_dpi=100):
    """Complete image quality assessment including DPI and pixelation"""
    height_px, width_px = image_region.shape[:2]

    # Calculate DPI
    dpi_h = width_px / expected_width_inches
    dpi_v = height_px / expected_height_inches
    avg_dpi = (dpi_h + dpi_v) / 2

    # DPI Assessment
    if avg_dpi >= 300:
        dpi_status = "✅ EXCELLENT - Print Ready"
        dpi_score = 100
    elif avg_dpi >= 200:
        dpi_status = "⚠️ ACCEPTABLE - May show quality loss"
        dpi_score = 60
    elif avg_dpi >= 150:
        dpi_status = "⚠️ POOR - Visible pixelation expected"
        dpi_score = 30
    else:
        dpi_status = "❌ REJECTED - Not suitable for printing"
        dpi_score = 0

    # Pixelation check
    gray = cv2.cvtColor(image_region, cv2.COLOR_BGR2GRAY).astype(np.float32)
    block_size = 8

    vertical_diffs = []
    for i in range(block_size, width_px, block_size):
        vertical_diffs.append(np.mean(np.abs(gray[:, i] - gray[:, i - 1])))

    horizontal_diffs = []
    for j in range(block_size, height_px, block_size):
        horizontal_diffs.append(np.mean(np.abs(gray[j, :] - gray[j - 1, :])))

    blockiness = (np.mean(vertical_diffs) + np.mean(horizontal_diffs)) / 2

    if blockiness > 15:
        pixel_status = "Highly Pixelated"
    elif blockiness > 4:
        pixel_status = "Moderately Pixelated"
    else:
        pixel_status = "Not Pixelated"

    return {
        'dimensions': f"{width_px}x{height_px} pixels",
        'dpi': round(avg_dpi, 1),
        'dpi_status': dpi_status,
        'blockiness_score': round(blockiness, 2),
        'pixelation_status': pixel_status,
        'dpi_score': dpi_score
    }


def pdf_to_image(pdf_path, dpi=300):
    """Converts the first page of a PDF to an OpenCV image"""
    pages = convert_from_path(pdf_path, dpi=dpi)
    first_page = pages[0]
    img = np.array(first_page)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    return img


def extract_book_id(file_reference):
    """Extracts ISBN (Book ID) from filename"""
    filename = os.path.basename(file_reference)
    match = re.search(r"(\d+)_", filename)
    if match:
        return int(match.group(1))
    return None


def pick_email_template(overlap_flag, safe_margin_flagged, dpi_status):
    """Select appropriate email template based on issues"""

    email_templates = {
        "badge_only": "Hello Amra,\n\n⚠️ Your book cover has text overlapping the award badge area.\nPlease move the text above the badge to resolve the issue.\n\nThank you!",
        "margin_only": "Hello Amra,\n\n⚠️ Some text is outside the safe margin zone.\nPlease adjust your text to stay within the safe margins (3mm on sides).\n\nThank you!",
        "quality_only": "Hello Amra,\n\n❌ Your cover image quality is too low for print.\nPlease upload a higher resolution version (≥300 DPI).\n\nThank you!",
        "badge_and_margin": "Hello Amra,\n\n⚠️ Your cover has text overlapping the badge and outside safe margins.\nPlease fix both issues.\n\nThank you!",
        "badge_and_quality": "Hello Amra,\n\n⚠️ Your cover text overlaps the badge and image quality is too low.\nPlease fix both issues.\n\nThank you!",
        "margin_and_quality": "Hello Amra,\n\n⚠️ Text outside safe margins and image quality too low.\nPlease fix both issues.\n\nThank you!",
        "all_three_issues": "Hello Amra,\n\n⚠️ Your cover has three issues: badge overlap, unsafe margins, and low quality.\nPlease correct all issues.\n\nThank you!",
        "pass": "Hello Amra,\n\n✅ Your cover passed all checks and is ready for publishing!\n\nThank you!"
    }

    dpi_issue = dpi_status != "✅ EXCELLENT - Print Ready"

    if overlap_flag and safe_margin_flagged and dpi_issue:
        return email_templates["all_three_issues"]
    elif overlap_flag and safe_margin_flagged:
        return email_templates["badge_and_margin"]
    elif overlap_flag and dpi_issue:
        return email_templates["badge_and_quality"]
    elif safe_margin_flagged and dpi_issue:
        return email_templates["margin_and_quality"]
    elif overlap_flag:
        return email_templates["badge_only"]
    elif safe_margin_flagged:
        return email_templates["margin_only"]
    elif dpi_issue:
        return email_templates["quality_only"]
    else:
        return email_templates["pass"]


# ==================== MAIN PROCESSING FUNCTION ====================

def process_book_cover(image_path):
    """Process a single book cover image and return results"""

    print(f"\n{'=' * 70}")
    print(f"PROCESSING: {os.path.basename(image_path)}")
    print(f"{'=' * 70}")

    # Load image (PDF or image file)
    file_ext = os.path.splitext(image_path)[1].lower()

    if file_ext == ".pdf":
        img = pdf_to_image(image_path)
    elif file_ext in [".png", ".jpg", ".jpeg"]:
        img = cv2.imread(image_path)
    else:
        print(f"❌ Unsupported file format: {file_ext}")
        return None

    if img is None:
        print(f"❌ Error loading image: {image_path}")
        return None

    height, width = img.shape[:2]
    print(f"Image dimensions: {width}x{height} pixels")

    # -------------------- OCR Detection --------------------
    print("\n[1/4] Running OCR detection...")
    text_detections = reader.readtext(img)
    print(f"  Detected {len(text_detections)} text regions")

    # -------------------- Badge Area Detection --------------------
    print("\n[2/4] Checking badge area overlap...")
    bottom_strip_height = 106

    badge_x1 = width // 2
    badge_x2 = width
    badge_y1 = height - bottom_strip_height
    badge_y2 = height
    badge_coords = badge_x1, badge_y1, badge_x2, badge_y2

    safe_margin_flag_foverlap, overlap_flag, overlap_text = find_overlap_text_dual(
        text_detections, badge_coords, EXPECTED_TEXT1, EXPECTED_TEXT2
    )

    # -------------------- Extract Right Half --------------------
    print("\n[3/4] Analyzing image quality (right half)...")
    right_half = img[0:height, width // 2:width]

    quality_results = comprehensive_image_quality(right_half, actual_dpi=100)

    print(f"  Dimensions: {quality_results['dimensions']}")
    print(f"  Estimated DPI: {quality_results['dpi']}")
    print(f"  DPI Status: {quality_results['dpi_status']}")
    print(f"  Pixelation Score: {quality_results['blockiness_score']}")
    print(f"  Pixelation Status: {quality_results['pixelation_status']}")

    # -------------------- Safe Margin Check --------------------
    print("\n[4/4] Checking safe margins (3mm)...")
    text_detections_right = reader.readtext(right_half)

    actual_dpi = 100
    safe_margin_px = (3 / 25.4) * actual_dpi
    height_px, width_px = right_half.shape[:2]

    safe_margin_flagged = False
    unsafe_texts = []

    for bbox, text, score in text_detections_right:
        xs = [pt[0] for pt in bbox]
        if any(x < safe_margin_px or x > width_px - safe_margin_px for x in xs):
            print(f"  ⚠️ Text '{text}' is in unsafe margin")
            safe_margin_flagged = True
            unsafe_texts.append(text)

    if not safe_margin_flagged:
        print("  ✅ All text within safe margins")

    safe_margin_message = "✅ All text within safe margins" if not safe_margin_flagged else f"⚠️ Unsafe margins: {', '.join(unsafe_texts)}"

    # Apply overlap flag to margin status
    if safe_margin_flag_foverlap:
        safe_margin_flagged = True

    # -------------------- Overall Assessment --------------------
    if overlap_flag:
        overall_assessment = "Review Needed"
    elif quality_results['dpi_status'] != "✅ EXCELLENT - Print Ready":
        overall_assessment = "Review Needed"
    elif safe_margin_flagged:
        overall_assessment = "Review Needed"
    else:
        overall_assessment = "Pass"

    # -------------------- Email Template --------------------
    email_text = pick_email_template(overlap_flag, safe_margin_flagged, quality_results['dpi_status'])

    # -------------------- Prepare Data --------------------
    file_name = os.path.basename(image_path)
    book_id = extract_book_id(image_path)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    result = {
        "File Name": file_name,
        "Book ID": book_id,
        "Timestamp": timestamp,
        "Author Email": "amranadaf@gmail.com",  # TODO: Extract from filename or metadata
        "Author Name": "Amra",  # TODO: Extract from filename or metadata
        "Overlap Flag": overlap_flag,
        "Overlap Text": overlap_text if overlap_flag else "",
        "Safe Margin Flag": safe_margin_flagged,
        "Safe Margin Message": safe_margin_message,
        "DPI of Image": quality_results['dpi'],
        "Pixelation Score": quality_results['blockiness_score'],
        "Pixelation Status": quality_results['pixelation_status'],
        "DPI Status": quality_results['dpi_status'],
        "Overall Assessment": overall_assessment,
        "Email Text": email_text
    }

    # -------------------- Final Report --------------------
    print(f"\n{'=' * 70}")
    print("FINAL ASSESSMENT")
    print(f"{'=' * 70}")
    print(f"Status: {overall_assessment}")
    print(f"DPI: {quality_results['dpi']}")
    print(f"Pixelation: {quality_results['pixelation_status']}")
    print(f"Badge Overlap: {'Yes' if overlap_flag else 'No'}")
    print(f"Safe Margins: {'No' if safe_margin_flagged else 'Yes'}")
    print(f"{'=' * 70}\n")

    return result





def insert_to_airtable(result: dict):
    """Insert record into Airtable"""
    try:
        record = table.create(result)
        print("✅ Record created:", record['id'])
        return record['id']
    except Exception as e:
        print("❌ Error uploading to Airtable:", e)
        return None

#-----------------------------function for sending mail---------------------
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
EMAIL_ADDRESS = "amranadaf@gmail.com"
EMAIL_PASSWORD = "#"  # Use app password if using Gmail

def send_email(email_text, recipient_email= 'amraspacestars@gmail.com', subject="Book Cover Feedback"):
    """Send email to author"""
    try:
        # Compose email
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(email_text, 'plain'))

        # Connect to Gmail SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()

        print(f"✅ Email sent to {recipient_email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email to {recipient_email}: {e}")
        return False







def authenticate_google_drive():
    """Authenticate with Google Drive"""
    print("Authenticating with Google Drive...")

    gauth = GoogleAuth()
    gauth.LoadCredentialsFile("mycreds.txt")

    if gauth.credentials is None:
        print("First time authentication - browser will open...")
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        print("Refreshing expired credentials...")
        gauth.Refresh()
    else:
        print("Using saved credentials...")
        gauth.Authorize()

    gauth.SaveCredentialsFile("mycreds.txt")
    drive = GoogleDrive(gauth)
    print("✅ Authenticated successfully\n")

    return drive


# ==================== MAIN MONITORING LOOP ====================

def main():
    """Main function to monitor Google Drive and process new files"""

    # Authenticate with Google Drive
    drive = authenticate_google_drive()

    print(f"Monitoring folder ID: {FOLDER_ID}")
    print(f"Checking every {POLL_INTERVAL} seconds")
    print(f"Press Ctrl+C to stop\n")
    print("=" * 70)

    while True:
        try:
            # List all files in the folder
            file_list = drive.ListFile({
                'q': f"'{FOLDER_ID}' in parents and trashed=false"
            }).GetList()

            for file in file_list:
                file_id = file['id']
                file_title = file['title']

                # Check if it's a new image/PDF file
                if file_id not in processed_files and file_title.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf')):
                    print(f"\n🔔 NEW FILE DETECTED: {file_title}")

                    # Download file
                    local_path = os.path.join(DOWNLOAD_DIR, file_title)
                    file.GetContentFile(local_path)
                    print(f"📥 Downloaded to: {local_path}")

                    # Process the image
                    result = process_book_cover(local_path)

                    if result:
                        # Insert into Airtable
                        insert_to_airtable(result)  # Uncomment when ready

                        # TODO: Send email notification
                        send_email(result['Email Text'], result['Author Email'])

                        print(f"✅ Completed processing: {file_title}")

                    # Mark as processed
                    processed_files.add(file_id)
                    save_processed_file(file_id)

            # Wait before next poll
            print(f"\n⏳ Waiting {POLL_INTERVAL} seconds before next check...")
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\n\n⚠️ Stopping monitor...")
            break
        except Exception as e:
            print(f"⚠️ Error: {e}")
            time.sleep(POLL_INTERVAL)


# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    # For testing a single image locally:
    # result = process_book_cover("test_image.png")
    # print(result)

    # For automated Google Drive monitoring:
    main()