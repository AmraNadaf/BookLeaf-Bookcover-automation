from pyairtable import Api

# -------------------- CONFIG --------------------
AIRTABLE_TOKEN = "#"
AIRTABLE_BASE_ID = "app4SYI2WfSXar9nP"
TABLE_ID= "tblCECcfMV07ksUxM"
# TABLE_ID = "BookCovers"
# -------------------- SETUP --------------------
api = Api(AIRTABLE_TOKEN)
table = api.table(AIRTABLE_BASE_ID, TABLE_ID)

# -------------------- DATA --------------------
data = {
    "File Name": "test_image.jpg",
    "Book ID": 523,
    "Timestamp": "2025-10-15 15:30:00",
    "Author Email": "amranadaf@gmail.com",
    "Author Name": "Amra",
    "Overlap Flag": False,
    "Overlap Text": "",
    "Safe Margin Flag": True,
    "Safe Margin Message": "All good",
    "DPI of Image": 300,
    "Pixelation Score": 0.12,
    "Pixelation Status": "Good",
    "DPI Status": "Acceptable",
    "Overall Assessment": "✅ Passed quality check",
    "Email Text": "Sample email text here"
}

# -------------------- CREATE RECORD --------------------
record = table.create(data)
print("✅ Record created:", record['id'])
