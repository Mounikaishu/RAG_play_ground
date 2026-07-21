import sys
import os
import fitz

doc = fitz.open("data/interview_experiences/Deloitte_DataAnalyst_AllRounds.pdf")
print("="*60)
print("DELOITTE PDF TEXT VIA PYMUPDF")
print("="*60)
for page in doc:
    print(page.get_text())
print("="*60)
doc.close()
