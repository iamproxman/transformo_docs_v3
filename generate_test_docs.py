import os
from PIL import Image, ImageDraw, ImageFont

os.makedirs("sample_docs", exist_ok=True)

def get_font(size=28):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()

def create_sample_invoice_image():
    """Generates a realistic scanned invoice image with table, logo, amounts, and dates."""
    width, height = 1200, 1600
    img = Image.new('RGB', (width, height), color='#f9fafb')
    draw = ImageDraw.Draw(img)

    # Header & Banner
    draw.rectangle([(0, 0), (1200, 120)], fill='#1e293b')
    draw.text((60, 40), "TRANSFORMO TECH SOLUTIONS INC.", fill='#ffffff')
    draw.text((850, 45), "TAX INVOICE", fill='#38bdf8')

    # Invoice Details Box
    draw.rectangle([(60, 160), (1140, 320)], outline='#cbd5e1', width=2)
    draw.text((80, 180), "Invoice No: INV-2026-8892", fill='#0f172a')
    draw.text((80, 220), "Invoice Date: 2026-10-05", fill='#0f172a')
    draw.text((80, 260), "Due Date: 2026-11-05", fill='#0f172a')

    draw.text((650, 180), "Billed To: Apex Global Enterprises", fill='#0f172a')
    draw.text((650, 220), "Contact: billing@apexglobal.com", fill='#0f172a')
    draw.text((650, 260), "Tax ID: US-998822114", fill='#0f172a')

    # Table Header
    table_y = 380
    draw.rectangle([(60, table_y), (1140, table_y + 50)], fill='#e2e8f0')
    draw.text((80, table_y + 15), "Item Description", fill='#0f172a')
    draw.text((600, table_y + 15), "Qty", fill='#0f172a')
    draw.text((750, table_y + 15), "Unit Price", fill='#0f172a')
    draw.text((950, table_y + 15), "Total Amount", fill='#0f172a')

    items = [
        ("Cloud Server Infrastructure Hosting (Oct 2026)", "1", "$850.00", "$850.00"),
        ("AI Intelligent Document Processing API Usage", "25000", "$0.02", "$500.00"),
        ("Custom Python System Integration & Support", "10 hrs", "$120.00", "$1,200.00"),
        ("Enterprise Storage & Backup Quota (500GB)", "1", "$150.00", "$150.00")
    ]

    curr_y = table_y + 70
    for desc, qty, price, total in items:
        draw.text((80, curr_y), desc, fill='#334155')
        draw.text((600, curr_y), qty, fill='#334155')
        draw.text((750, curr_y), price, fill='#334155')
        draw.text((950, curr_y), total, fill='#334155')
        draw.line([(60, curr_y + 35), (1140, curr_y + 35)], fill='#cbd5e1', width=1)
        curr_y += 50

    summary_y = curr_y + 40
    draw.rectangle([(650, summary_y), (1140, summary_y + 180)], fill='#f8fafc', outline='#cbd5e1', width=2)
    draw.text((680, summary_y + 20), "Subtotal:", fill='#475569')
    draw.text((950, summary_y + 20), "$2,700.00", fill='#475569')

    draw.text((680, summary_y + 60), "Tax / VAT (10%):", fill='#475569')
    draw.text((950, summary_y + 60), "$270.00", fill='#475569')

    draw.text((680, summary_y + 110), "Grand Total Due:", fill='#0f172a')
    draw.text((950, summary_y + 110), "$2,970.00", fill='#16a34a')

    draw.text((60, 1450), "Payment Terms: Net 30. Wire transfer to Account # 9876543210", fill='#64748b')
    draw.text((60, 1490), "Thank you for doing business with Transformo Tech Solutions!", fill='#64748b')

    img_path = "sample_docs/sample_invoice_scanned.png"
    img.save(img_path)
    print(f"✅ Generated sample invoice image: {img_path}")

def create_sample_hospital_bill_image():
    """Generates a realistic Hospital Medical Bill image."""
    width, height = 1200, 1600
    img = Image.new('RGB', (width, height), color='#ffffff')
    draw = ImageDraw.Draw(img)

    # Hospital Header
    draw.rectangle([(0, 0), (1200, 140)], fill='#0284c7')
    draw.text((60, 30), "METROPOLITAN CARE HOSPITAL & MEDICAL CENTER", fill='#ffffff')
    draw.text((60, 75), "100 Healthcare Parkway, Medical District, NY 10001 | Phone: (212) 555-0199", fill='#e0f2fe')
    draw.text((920, 45), "PATIENT INVOICE", fill='#ffffff')

    # Patient & Admission Info Box
    draw.rectangle([(60, 170), (1140, 350)], outline='#0284c7', width=2)
    draw.text((80, 190), "Hospital Name: Metropolitan Care Hospital", fill='#0f172a')
    draw.text((80, 230), "Patient Name: Eleanor Vance", fill='#0f172a')
    draw.text((80, 270), "Patient ID / MRN: MRN-884920", fill='#0f172a')
    draw.text((80, 310), "Attending Physician: Dr. Robert S. Thorne, MD", fill='#0f172a')

    draw.text((650, 190), "Bill No: HOSP-2026-9041", fill='#0f172a')
    draw.text((650, 230), "Admission Date: 2026-09-28", fill='#0f172a')
    draw.text((650, 270), "Discharge Date: 2026-10-02", fill='#0f172a')
    draw.text((650, 310), "Department: Cardiology / Intensive Care", fill='#0f172a')

    # Medical Itemized Charges
    table_y = 400
    draw.rectangle([(60, table_y), (1140, table_y + 45)], fill='#f0f9ff')
    draw.text((80, table_y + 12), "Medical Service / Treatment Description", fill='#0369a1')
    draw.text((700, table_y + 12), "Dept", fill='#0369a1')
    draw.text((950, table_y + 12), "Charge (USD)", fill='#0369a1')

    charges = [
        ("ICU Private Room Charges (4 Days @ $1,200/day)", "Inpatient Room", "$4,800.00"),
        ("Diagnostic Cardiac Angiography & ECG Monitoring", "Cardiology Lab", "$2,450.00"),
        ("Comprehensive Blood Panel & Lipid Profile", "Pathology Lab", "$380.00"),
        ("Intravenous Medications & Prescription Drugs", "Pharmacy", "$620.00"),
        ("Attending Physician Specialist Consultation Fee", "Medical Staff", "$950.00")
    ]

    curr_y = table_y + 60
    for desc, dept, chg in charges:
        draw.text((80, curr_y), desc, fill='#334155')
        draw.text((700, curr_y), dept, fill='#334155')
        draw.text((950, curr_y), chg, fill='#334155')
        draw.line([(60, curr_y + 35), (1140, curr_y + 35)], fill='#e2e8f0', width=1)
        curr_y += 50

    summary_y = curr_y + 40
    draw.rectangle([(650, summary_y), (1140, summary_y + 170)], fill='#f8fafc', outline='#cbd5e1', width=2)
    draw.text((680, summary_y + 20), "Total Gross Hospital Charges:", fill='#475569')
    draw.text((950, summary_y + 20), "$9,200.00", fill='#475569')

    draw.text((680, summary_y + 60), "Insurance Coverage (80%):", fill='#0284c7')
    draw.text((950, summary_y + 60), "-$7,360.00", fill='#0284c7')

    draw.text((680, summary_y + 110), "Net Amount Due by Patient:", fill='#0f172a')
    draw.text((950, summary_y + 110), "$1,840.00", fill='#dc2626')

    draw.text((60, 1450), "Please remit payment to Metropolitan Care Hospital Billing Dept.", fill='#64748b')
    draw.text((60, 1490), "For billing inquiries, contact patient.billing@metrocarehospital.org", fill='#64748b')

    img_path = "sample_docs/sample_hospital_medical_bill.png"
    img.save(img_path)
    print(f"✅ Generated sample hospital medical bill image: {img_path}")

def create_sample_hospital_discharge_pdf():
    """Generates a text PDF Hospital Discharge Summary."""
    import pymupdf as fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    text = """
ST. JUDE GENERAL HOSPITAL & MEDICAL CENTER
Department of Clinical Internal Medicine
150 Medical Center Boulevard, Suite 400
Emergency & Discharge Hotline: +1 (555) 019-4820

PATIENT DISCHARGE SUMMARY & MEDICAL REPORT

PATIENT DEMOGRAPHICS:
• Patient Name: Arthur Pendelton
• Medical Record Number (MRN): STJ-2026-77310
• Date of Admission: 2026-09-25
• Date of Discharge: 2026-10-01
• Hospital Name: St. Jude General Hospital & Medical Center
• Attending Physician: Dr. Marcus Vance, MD (Cardiology)

CLINICAL DIAGNOSIS:
1. Acute Coronary Syndrome (Stabilized)
2. Essential Hypertension (Controlled)
3. Type 2 Diabetes Mellitus

SUMMARY OF HOSPITALIZATION & TREATMENT:
The patient, Mr. Arthur Pendelton, was admitted to St. Jude General Hospital following acute onset retrosternal chest discomfort. Emergency ECG revealed ST-segment elevation. Coronary angiography was performed on Day 1 showing 85% stenosis in the left anterior descending artery. Successful drug-eluting stent placement was executed without complication.

POST-DISCHARGE MEDICATIONS:
• Aspirin 81 mg oral daily
• Clopidogrel 75 mg oral daily
• Atorvastatin 40 mg oral at bedtime
• Metoprolol Succinate 50 mg oral daily

FOLLOW-UP INSTRUCTIONS:
Patient is advised to follow up at St. Jude General Hospital Outpatient Clinic in 2 weeks. Total hospitalization charges were billed to BlueCross Insurance under Group ID # BC-9941.

Authorized Physician Signature: Dr. Marcus Vance, MD
St. Jude General Hospital Discharge Office
"""
    rect = fitz.Rect(50, 50, 545, 792)
    page.insert_textbox(rect, text, fontsize=10, fontname="helv")

    pdf_path = "sample_docs/sample_hospital_discharge_summary.pdf"
    doc.save(pdf_path)
    print(f"✅ Generated sample hospital discharge PDF: {pdf_path}")

def create_sample_resume_pdf():
    """Generates a text PDF resume for testing PDF text probing."""
    import pymupdf as fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    text = """
DR. ALEX R. CHEN
Senior AI Research Scientist & Lead Engineer
Email: alex.chen@example.com | Phone: +1 (555) 382-9102 | Location: San Francisco, CA

SUMMARY
Passionate Machine Learning Engineer with 8+ years of experience building scalable Intelligent Document Processing (IDP), Vision-Language Models (LayoutLM, Donut), and Retrieval-Augmented Generation (RAG) pipelines.

WORK EXPERIENCE

Lead AI Engineer — NeuralDoc Systems (2023 – Present)
• Architected enterprise RAG pipelines indexing 5M+ technical PDFs and contract documents.
• Reduced document extraction error rates by 42% using hybrid BM25 + dense vector retrieval.
• Integrated multi-modal LLMs for automated invoice key-value field extraction.

Senior ML Engineer — VisionTech Labs (2020 – 2023)
• Fine-tuned LayoutLMv3 and Tesseract OCR models for multi-lingual scanned receipts.
• Engineered high-throughput Python FastAPI microservices handling 1,000 requests/second.

EDUCATION
Ph.D. in Computer Science — Stanford University (2016 – 2020)
Specialization: Deep Learning for Visual Layout & Natural Language Processing.

TECHNICAL SKILLS
• Languages: Python, C++, SQL, JavaScript (ES6+)
• AI/ML: PyTorch, Hugging Face Transformers, OpenCV, PyMuPDF, PyTesseract, Gemini API
• Infrastructure: Docker, FastAPI, PostgreSQL, Redis, RabbitMQ
"""
    rect = fitz.Rect(50, 50, 545, 792)
    page.insert_textbox(rect, text, fontsize=11, fontname="helv")

    pdf_path = "sample_docs/sample_resume_alex_chen.pdf"
    doc.save(pdf_path)
    print(f"✅ Generated sample resume PDF: {pdf_path}")

def create_sample_algorithm_pdf():
    """Generates a technical document on Graph Search Algorithms."""
    import pymupdf as fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    text = """
TECHNICAL SPECIFICATION: GRAPH SEARCH & DIJKSTRA ROUTING ALGORITHMS
Document Type: Technical Architecture Specification
Author: Systems Engineering Team
Version: 3.2.0 | Status: APPROVED

1. OVERVIEW
This technical document specifies the shortest path graph traversal algorithms used in network packet routing and spatial graph optimization algorithms.

2. DIJKSTRA'S ALGORITHM PSEUDOCODE
Function Dijkstra(Graph, source):
    create vertex set Q
    for each vertex v in Graph:
        dist[v] ← INFINITY
        prev[v] ← UNDEFINED
        add v to Q
    dist[source] ← 0
    
    while Q is not empty:
        u ← vertex in Q with min dist[u]
        remove u from Q
        for each neighbor v of u still in Q:
            alt ← dist[u] + Graph.Edges(u, v)
            if alt < dist[v]:
                dist[v] ← alt
                prev[v] ← u
    return dist, prev

3. COMPLEXITY ANALYSIS
Time Complexity with Priority Queue / Binary Heap: O((V + E) log V)
Space Complexity: O(V) memory allocation for priority queues.
"""
    rect = fitz.Rect(50, 50, 545, 792)
    page.insert_textbox(rect, text, fontsize=11, fontname="helv")

    pdf_path = "sample_docs/sample_algorithm_spec.pdf"
    doc.save(pdf_path)
    print(f"✅ Generated sample algorithm PDF: {pdf_path}")

if __name__ == "__main__":
    create_sample_invoice_image()
    create_sample_hospital_bill_image()
    create_sample_hospital_discharge_pdf()
    create_sample_resume_pdf()
    create_sample_algorithm_pdf()

