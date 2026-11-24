import pypdf

pdf_path = r'C:\Users\ADMIN\Downloads\20261_Mô tả tổng quan đề tài-BTL I.pptx.pdf'
reader = pypdf.PdfReader(pdf_path)

print(f"Tổng số trang: {len(reader.pages)}")

for i, page in enumerate(reader.pages):
    links = []
    if "/Annots" in page:
        for annot in page["/Annots"]:
            obj = annot.get_object()
            if "/A" in obj and "/URI" in obj["/A"]:
                links.append(obj["/A"]["/URI"])
    if links:
        print(f"\n[+] SLIDE {i+1}:")
        for l in links:
            print(f"    - {l}")
