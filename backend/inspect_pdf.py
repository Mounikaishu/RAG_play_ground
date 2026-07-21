import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from pdf_loader import load_pdf

text = load_pdf("data/interview_experiences/Deloitte_DataAnalyst_AllRounds.pdf")
print("="*60)
print("DELOITTE PDF TEXT CONTENT")
print("="*60)
print(text)
print("="*60)
