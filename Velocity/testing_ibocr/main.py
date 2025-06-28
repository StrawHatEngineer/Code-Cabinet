import json
import os
import logging
import io
from instabase.ocr.client.libs import ibocr
from instabase.client_helpers import clients

def process_json_file(input_filepath, content):
    """
    Process JSON file and create document info dictionary
    """
    data = json.loads(content)
    document_info = {}
    
    for record in data['records']:
        class_label = record['classification_label']
        page_range = record['page_range']
        start_page = page_range['start_page']
        end_page = page_range['end_page']
        
        if class_label not in document_info:
            document_info[class_label] = []
            
        document_info[class_label].append({
            'start_page': start_page,
            'end_page': end_page
        })
        
    return document_info

def extract_page_range(clients, input_pdf_path, output_path, start_page, end_page):
    """
    Extract page range from PDF using Instabase file operations
    """
    # Read input PDF
    pdf_content = clients.ibfile.read_file(input_pdf_path)
    if not pdf_content:
        raise IOError(f"Could not read input PDF: {input_pdf_path}")
        
    # Create PDF reader/writer
    reader = PdfReader(io.BytesIO(pdf_content))
    writer = PdfWriter()
    
    # Validate page range
    if start_page < 1:
        raise ValueError("start_page must be >= 1")
        
    if end_page > len(reader.pages):
        raise ValueError(f"end_page ({end_page}) exceeds PDF length ({len(reader.pages)})")
        
    if start_page > end_page:
        raise ValueError("start_page cannot be greater than end_page")
    
    # Extract pages
    for i in range(start_page - 1, end_page):
        writer.add_page(reader.pages[i])
        
    # Write output
    output = io.BytesIO()
    writer.write(output)
    
    # Save using ibfile
    resp, err = clients.ibfile.write_file(output_path, output.getvalue())
    if err:
        raise IOError(f"Could not write output file: {output_path}")

def extract_all_documents(clients, input_pdf_path, output_dir, doc_info):
    """
    Extract all document sections based on document info
    """
    # Create output directory
    mkdir_resp, err = clients.ibfile.mkdir(output_dir)
    if err:
        raise IOError(f"Could not create output directory: {output_dir}")
        
    for doc_type, ranges in doc_info.items():
        for page_range in ranges:
            # Construct output filename
            base_name = os.path.basename(input_pdf_path)
            output_name = f"{base_name}.{doc_type}-{page_range['start_page']}-{page_range['end_page']}.pdf"
            output_path = os.path.join(output_dir, output_name)
            
            extract_page_range(
                clients,
                input_pdf_path, 
                output_path,
                page_range['start_page'],
                page_range['end_page']
            )

def process_pdf_udf(content, input_filepath, clients, **kwargs):
    """
    Main UDF function for processing PDFs
    """
    # Load and parse JSON
    json_content = clients.ibfile.read_file('./test.json')
    doc_info = process_json_file('./test.json', json_content)
    
    # Extract documents
    extract_all_documents(clients, input_filepath, "output", doc_info)
    
    # Return original content unchanged
    return content

def register(name_to_fn):
    fns = {
        'process_pdf': {
            'fn': process_pdf_udf,
            'ex': '',
            'desc': 'Extract document sections from PDF'
        }
    }
    name_to_fn.update(fns)