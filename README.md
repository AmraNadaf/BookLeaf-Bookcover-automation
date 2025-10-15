# 📚 Automated Book Cover Quality Checker

Smart automation that validates book covers for print quality in seconds.

#What It Does

Monitors Google Drive → Detects new covers → Runs 4 quality checks → Logs to Airtable → Emails feedback

#Quality Checks

DPI Analysis - Validates 300 DPI print standard
Pixelation Detection - Catches low-quality/compressed images  
Badge Overlap - Ensures award badges aren't covered
Safe Margins - Verifies 3mm print-safe zones

#Automation Features

1. Real-time Google Drive monitoring (60s polling)  
2. Persistent tracking (no duplicate processing)  
3. Auto-logging to Airtable with 15+ metrics  
4. Contextual email feedback to authors  
5. Supports PNG, JPG, PDF formats

#Tech Stack

Python • OpenCV • EasyOCR • PyDrive • Airtable API • SMTP

#Results

**Pass** → "Ready for publishing!" ✉️  
**Review Needed** → Specific fix instructions ✉️

Built for print-on-demand workflows. To reduce manual labour
