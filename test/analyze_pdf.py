import fitz # PyMuPDF
import sys
import json

def analyze_pdf(pdf_path, out_path):
    try:
        doc = fitz.open(pdf_path)
        metadata = doc.metadata
        
        text_content = ""
        for i, page in enumerate(doc):
            text_content += f"\n--- Page {i+1} ---\n"
            text_content += page.get_text()
            
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("=== METADATA ===\n")
            f.write(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
            f.write("\n=== TEXT CONTENT ===\n")
            f.write(text_content + "\n")
            
            # Check for images or suspicious overlay objects
            f.write("\n=== IMAGES / OBJECTS ===\n")
            for i, page in enumerate(doc):
                images = page.get_images(full=True)
                f.write(f"Page {i+1} has {len(images)} images.\n")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_pdf(sys.argv[1], sys.argv[2])
