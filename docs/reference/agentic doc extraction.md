# Lab 4: Document Understanding with Agentic Document Extraction

In this lab, you will use LandingAI's Agentic Document Extraction (ADE) framework to parse documents and extract key-value pairs using a single API. Note that Lab 4 has two parts. Here in the first part, we cover Exercise 1: Extract Key-Value Pairs from a Utility Bill and Exercise 2: ADE on Difficult Documents. In the second part, we cover Exercise 3: Automated Pipeline for Loan Applications.   

**Learning Objectives:**
- Use the Parse API to convert documents into structured markdown with visual grounding
- Define JSON schemas to extract specific fields from documents
- Use the Extract API to pull key-value pairs with source location references

## Background

ADE is built on three approaches:
- Vision-First: Documents are visual objects where meaning is encoded in layout, structure, and spatial relationships
- Data-Centric: Models are trained on large, diverse, and curated datasets
- Agentic: The system plans, decides, acts, and verifies until responses meet quality thresholds

The foundation is the **Document Pre-trained Transformer (DPT)** family of models that combine text parsing, layout detection, reading order, and multimodal reasoning capabilities.

## Outline

- [1. Setup and Authentication](#1)
- [2. Helper Functions](#2)
- [3. Exercise 1: Extract Key-Value Pairs from a Utility Bill](#3)
  - [3.1 Preview the Document](#3-1)
  - [3.2 Parse the Document](#3-2)
  - [3.3 Explore the Output from Parse](#3-3)
  - [3.4 Extract Key-Value Pairs](#3-4)
  - [3.5 Explore the Output from Extract](#3-5)
- [4. Exercise 2: ADE on Difficult Documents](#4)
  - [4.1 Charts and Flowcharts](#4-1)
  - [4.2 Tables with Missing Gridlines](#4-2)
  - [4.3 Handwritten Forms](#4-3)
  - [4.4 Handwritten Calculus](#4-4)
  - [4.5 Illustrations and Infographics](#4-5)
  - [4.6 Stamps and Signatures](#4-6)
- [5. Summary](#5)

<a id="1"></a>

## 1. Setup and Authentication

Import the required libraries. Key imports from LandingAI:
- `LandingAIADE`: Client for making API calls
- `ParseResponse`: Type for document parsing results
- `ExtractResponse`: Type for field extraction results

```python
# General imports

import os
import json
import pymupdf
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from IPython.display import display, IFrame, Markdown, HTML
from IPython.display import Image as DisplayImage
from PIL import Image as PILImage, ImageDraw
```

```python
# Imports specific to Agentic Document Extraction

from landingai_ade import LandingAIADE
from landingai_ade.types import ParseResponse, ExtractResponse
```

```python
# Load environment variables from .env
_ = load_dotenv(override=True)
```

Initialize the ADE client. The API key is loaded automatically from the environment variable `VISION_AGENT_API_KEY`.

To use ADE outside this course, you can generate a free API key at [va.landing.ai](https://va.landing.ai).

```python
# Initialize the client
client = LandingAIADE()
print("Authenticated client initialized")
```

<a id="2"></a>

## 2. Helper Functions

Import visualization functions from `helper.py` to display documents and draw bounding boxes around detected chunks.

```python
from helper import print_document, draw_bounding_boxes, draw_bounding_boxes_2
from helper import create_cropped_chunk_images
```

<a id="3"></a>

## 3. Exercise 1: Extract Key-Value Pairs from a Utility Bill

Parse a utility bill and extract specific fields like current charges, gas usage, and electric usage. The workflow:
1. Preview the document
2. Parse with DPT-2 to get structured markdown and chunks
3. Extract key-value pairs using a JSON schema

<p style="background-color:#f7fff8; padding:15px; border-width:3px; border-color:#e0f0e0; border-style:solid; border-radius:6px"> 🚨
&nbsp; <b>Different Run Results:</b> LandingAI continues to innovate with DPT-2. Considering updates to the model, your results might differ slightly from those shown in the video.</p>

<a id="3-1"></a>

### 3.1 Preview the Document

A combined gas and electric bill from a San Diego utility with monthly billing period, separate charges, and usage history charts.

```python
print_document("utility_example/utility_bill.pdf")
```

<a id="3-2"></a>

### 3.2 Parse the Document

The Parse API converts the document into structured markdown with:
- Chunks: Semantic regions (text, tables, figures, logos, marginalia)
- Bounding boxes: Coordinates for each chunk
- Markdown: Text representation with embedded chunk IDs

Using `dpt-2-latest` provides the most current version of the DPT-2 model.

```python
# Specify the file path to the document
document_path = Path("utility_example/utility_bill.pdf")

print("⚡ Calling API to parse document...")

# Parse the document using the Parse() API
parse_result: ParseResponse = client.parse(
    document=document_path,
    model="dpt-2-latest"
)

print(f"Parsing completed.")
print(f"job_id: {parse_result.metadata.job_id}")
print(f"Filename: {parse_result.metadata.filename}")
print(f"Total time (ms): {parse_result.metadata.duration_ms}")
print(f"Total pages: {len(parse_result.splits)}")
print(f"Total markdown characters: {len(parse_result.markdown)}")
print(f"Total chunks: {len(parse_result.chunks)}")
```

<a id="3-3"></a>

### 3.3 Explore the Output from Parse

The parse result contains the document structure. Visualize the detected chunks with bounding boxes.

```python
# Create and view an annotated version
draw_bounding_boxes(parse_result, document_path)
```

Each chunk has a unique ID, type, page number, and bounding box coordinates. Chunk types include: `logo`, `text`, `table`, `figure`, and `marginalia`.

```python
# Inspect the first 5 chunks
parse_result.chunks[0:5]
```

```python
print(f"The first chunk has an id: {parse_result.chunks[0].id}")
print(f"The first chunk is type: {parse_result.chunks[0].type}")
print(f"The first chunk is on page: {parse_result.chunks[0].grounding.page}")
print(f"The first chunk is at box coordinates: {parse_result.chunks[0].grounding.box}")
```

```python
# How many chunks of each type?
counts = {}

for chunk in parse_result.model_dump()["chunks"]:
    t = chunk["type"]
    counts[t] = counts.get(t, 0) + 1

print(counts)
```

The top-level markdown contains the full document content with embedded chunk IDs. These IDs enable visual grounding namely tracing extracted values to their source location.

```python
print("TOP-LEVEL MARKDOWN CONTENTS")
print(f"{parse_result.markdown[0:500]}")
```

Tables are rendered as HTML with unique IDs for each cell. This enables extraction to reference specific table cells.

```python
# Chunk-level markdown rendered
display(HTML(parse_result.chunks[9].markdown))
```

```python
print(" ")
print("CHUNK-LEVEL MARKDOWN CONTENTS")
print(f"{parse_result.chunks[9].markdown}")
```

<a id="3-4"></a>

### 3.4 Extract Key-Value Pairs from the Document

Define a JSON schema specifying the fields to extract. The schema supports:
- Nested objects: (e.g., `account_summary` with sub-fields)
- Multiple types: `number`, `string`, `boolean`
- Rich descriptions: Guide the extraction model

More descriptive field definitions improve extraction accuracy.

```python
schema_dict = {
    "type": "object",
    "title": "Utility Bill Field Extraction Schema",
    "properties": {
    "account_summary": {
      "type": "object",
      "title": "Account Summary",
      "properties": {
        "current_charges": {
          "type": "number",
          "description": "The charges incurred during the current billing "
            "period."
        },
        "total_amount_due": {
          "type": "number",
          "description": "The total amount currently due."
        }
      }
    },
    "gas_summary": {
      "type": "object",
      "title": "Gas Usage Summary",
      "properties": {
        "total_therms_used": {
          "type": "number",
          "description": "Total therms of gas used in the billing period."
        },
        "gas_current_charges": {
          "type": "number",
          "description": "The gas charges incurred during the current "
            "billing period."
        },
        "gas_usage_chart": {
          "type": "boolean",
          "description": "Does the document contain a chart of historical "
            "gas usage?"
        },
        "gas_max_month": {
          "type": "string",
          "description": "Which month has the highest historical gas usage? "
            "Return month name only."
        }
      }
    },
    "electric_summary": {
      "type": "object",
      "title": "Electric Usage Summary",
      "properties": {
        "total_kwh_used": {
          "type": "number",
          "description": "Total kilowatt hours of electricity used in the "
            "billing period."
        },
        "electric_current_charges": {
          "type": "number",
          "description": "The gas charges incurred during the current "
            "billing period."
        },
        "electric_usage_chart": {
          "type": "boolean",
          "description": "Does the document contain a chart of historical "
            "electric usage?"
        },
        "electric_max_month": {
          "type": "string",
          "description": "Which month has the highest historical electric "
            "usage? Return month name only."
        }
      }
    }
  }
}

# Convert the dictionary into a JSON-formatted string
schema_json = json.dumps(schema_dict)
```

Call the Extract API with the schema and markdown from the parse step. The Extract API uses the structured markdown from the Parse API to find the requested fields in the text. 

```python
print("⚡ Calling API to extract from the document...")

# Using the Extract() API to extract structured data using the schema
extraction_result: ExtractResponse = client.extract(
            schema=schema_json,
            markdown=parse_result.markdown, # Notice that the input used is the top-level markdown from the parse step
            model="extract-latest"
)

print(f"Extraction completed.")
```

<a id="3-5"></a>

### 3.5 Explore the Output from Extract

The extraction result contains:
- extraction: The extracted values matching your schema
- extraction_metadata: References to source chunk/cell IDs for each value

```python
# View all extracted values
extraction_result.extraction
```

The metadata provides visual grounding. Short IDs like `0-a` refer to table cells, while longer UUIDs refer to figure or text chunks. This enables verification UIs that highlight the exact source of each extracted value.

```python
# View all metadata for extracted values
extraction_result.extraction_metadata
```

<a id="4"></a>

## 4. Exercise 2: ADE Performance on Difficult-to-Parse Documents

See how ADE handles document types that are challenging for traditional OCR and VLM approaches:
- Charts and flowcharts with complex spatial relationships
- Tables with missing gridlines and merged cells
- Handwritten forms with checkboxes and circles
- Illustrations without text
- Official stamps and signatures

The same API and DPT model handles all of these without additional configuration.

```python
def parse_document(parse_filename: str, model = "dpt-2-latest", 
                   display_option = "HTML") -> ParseResponse:
    """
    Parse a document with ADE and display the result in the desired format.

    Args:
        parse_filename: Path to the document to parse.
        display_option: One of:
            - "Raw Markdown" : print the markdown as plain text
            - "HTML"         : render the markdown as HTML in the notebook

    Returns:
        ParseResponse: The full parse response object.
    """

    document_path = Path(parse_filename)
    
    print("⚡ Calling API to parse document...")
    
    full_parse_result: ParseResponse = client.parse(  
        #send document to Parse API
        document=document_path, 
        model=model
    )

    _ = draw_bounding_boxes(full_parse_result, document_path=document_path)

    print(f"Parsing completed.")
    print(f"job_id: {full_parse_result.metadata.job_id}")
    print(f"Total pages: {len(full_parse_result.splits)}")
    print(f"Total time (ms): {full_parse_result.metadata.duration_ms}")
    print(f"Total markdown characters: {len(full_parse_result.markdown)}")
    print(f"Number of chunks: {len(full_parse_result.chunks)}")
    print(f" ")
    print("Complete Markdown:")

    if display_option == "Raw Markdown":
        print("Complete Markdown (raw):")
        print(full_parse_result.markdown)

    elif display_option == "HTML":
        print("Rendering markdown as HTML...")
        display(HTML(full_parse_result.markdown))

    else:
        print(
            f"[Unknown display_option '{display_option}'; "
            "valid options are 'Raw Markdown' or 'HTML'. "
            "Defaulting to HTML.]"
        )
        display(HTML(full_parse_result.markdown))
```

<a id="4-1"></a>

### 4.1 Charts and Flowcharts

Charts encode meaning through bars, lines, and spatial relationships. Flowcharts use arrows to show connections that don't follow standard reading order.

```python
print_document("difficult_examples/Investor_Presentation_pg7.png")
```

```python
parse_document("difficult_examples/Investor_Presentation_pg7.png", 
               display_option = "Raw Markdown")
```

This HR flowchart has arrows pointing in multiple directions. Traditional OCR would fail because "Select candidate" appears *above* "Good reference" on the page, but logically follows it in the workflow.

```python
print_document("difficult_examples/hr_process_flowchart.png")
```

```python
parse_document("difficult_examples/hr_process_flowchart.png", 
               display_option = "HTML")
```

<a id="4-2"></a>

### 4.2 Tables with Many Cells, Missing Gridlines, and Merged Cells

Real-world tables often lack clear gridlines, have merged header cells, or contain blank cells. ADE handles these by understanding the visual structure.

```python
print_document("difficult_examples/virology_pg2.pdf")
```

```python
parse_document("difficult_examples/virology_pg2.pdf", 
               display_option = "HTML")
```

This "mega table" has over 1,000 cells with merged rows and columns. LLMs typically hallucinate on large tables because they can't hold all the numbers in context. The agentic approach processes tables visually, avoiding this limitation.

```python
print_document("difficult_examples/sales_volume.png")
```

```python
parse_document("difficult_examples/sales_volume.png", 
               display_option = "HTML")
```

<a id="4-3"></a>

### 4.3 Handwritten Form with Checkboxes and Circles

This patient intake form combines handwriting, checkboxes, and circled selections. ADE detects these interaction patterns and converts them to structured markdown.

```python
print_document("difficult_examples/patient_intake.pdf")
```

```python
parse_document("difficult_examples/patient_intake.pdf", 
               display_option = "Raw Markdown")
```

<a id="4-4"></a>

### 4.4 Handwritten Calculus Answer Sheet

Mathematical notation like integrals, square roots, and fractions requires understanding visual symbols. ADE can parse handwritten math into structured representations.

```python
print_document("difficult_examples/calculus_BC_answer_sheet.jpg")
```

```python
parse_document("difficult_examples/calculus_BC_answer_sheet.jpg", display_option = "HTML")
```

<a id="4-5"></a>

### 4.5 Illustrations and Infographics

Some documents contain no text - only illustrations. For these, use `dpt-1-latest` which provides more detailed figure descriptions.

```python
print_document("difficult_examples/ikea-assembly.pdf")
```

```python
parse_document("difficult_examples/ikea-assembly.pdf", 
               model = "dpt-1-latest", 
               display_option = "Raw Markdown")
```

```python
print_document("difficult_examples/ikea_infographic.jpg")
```

```python
parse_document("difficult_examples/ikea_infographic.jpg", 
               display_option = "Raw Markdown")
```

<a id="4-6"></a>

### 4.6 Certificate of Origin with Stamps and Signatures

Official documents often contain stamps with curved text and handwritten signatures. ADE detects these as `attestation` chunk types and extracts their content.

```python
print_document("difficult_examples/certificate_of_origin.pdf")
```

```python
parse_document("difficult_examples/certificate_of_origin.pdf", 
               display_option = "HTML")
```

<a id="5"></a>

## 5. Summary

Here's what we learned about LandingAI's ADE framework:

| Concept | Description |
|---------|-------------|
| **Parse API** | Converts documents to structured markdown with chunks, bounding boxes, and unique IDs |
| **Extract API** | Pulls key-value pairs using JSON schemas with references for visual grounding |
| **DPT Models** | Document Pre-trained Transformers (DPT-2) that understand documents visually |
| **Chunk Types** | `logo`, `text`, `table`, `figure`, `marginalia`, `attestation` |
| **Visual Grounding** | Each extracted value references its source chunk |

In the next lab, you will build a complete document processing pipeline for loan automation using document categorization and extraction schemas.


# Lab 4: Document Understanding with Agentic Document Extraction II

In this lab, you will process multiple documents, categorize their types, and extract specific fields according to their respective schemas.

**Learning Objectives:**
- Specify extraction schemas with Pydantic 
- Implement categorization of documents by type
- Build validation logic into extracted information

## Background

Banks receive loan application documents with arbitrary filenames (eg "uploadA.pdf", "image456.jpg"). The workflow must:
1. Identify each document type (pay stub, W2, bank statement, etc.)
2. Extract relevant fields based on a schema pertaining to that document type
3. Validate that all documents belong to the same applicant

## Outline

- [1. Setup and Authentication](#1)
- [2. Helper Functions](#2)
- [3. Full Document Processing Pipeline](#3)
  - [3.1 Preview User-Supplied Documents](#3-1)
  - [3.2 Document Categorization Schema](#3-2)
  - [3.3 Document-Specific Extraction Schemas](#3-3)
  - [3.4 Parse and Categorize Documents](#3-4)
  - [3.5 Extract Financial Data](#3-5)
  - [3.6 Visualize Parsing Results](#3-6)
  - [3.7 Visualize Extracted Fields Only](#3-7)
  - [3.8 Create a Final Dataframe](#3-8)
  - [3.9 Validation Logic](#3-9)
- [4. Summary](#4)

<a id="1"></a>

## 1. Setup and Authentication

Import the required libraries and initialize the ADE client. This setup is identical to the previous lab.

```python
# General imports
import os
import json
import pymupdf
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from IPython.display import display, IFrame, Markdown, HTML
from IPython.display import Image as DisplayImage
from PIL import Image as PILImage, ImageDraw
```

```python
# Imports specific to Agentic Document Extraction
from landingai_ade import LandingAIADE
from landingai_ade.types import ParseResponse, ExtractResponse
```

```python
# Load environment variables from .env
_ = load_dotenv(override=True)
```

```python
# Initialize the client
client = LandingAIADE()
print("Authenticated client initialized")
```

<a id="2"></a>

## 2. Helper Functions

Import visualization helpers for displaying documents and bounding boxes.

```python
from helper import print_document, draw_bounding_boxes, draw_bounding_boxes_2
from helper import create_cropped_chunk_images
```

<a id="3"></a>

## 3. Full Document Processing Pipeline: Loan Automation

Imagine you work at a bank reviewing loan applications. Applicants upload various financial documents with arbitrary names. Your pipeline needs to:

1. **Parse** all documents to understand their content
2. **Categorize** each document (Is it a pay stub? Bank statement? ID?)
3. **Extract** the relevant fields based on document type
4. **Validate** that all documents belong to the same person

<a id="3-1"></a>

### 3.1 Preview the User-Supplied Documents

Preview all documents in the input folder. These are sample documents from different people (for demonstration purposes).

```python
def display_directory(directory_path: str):
    """
    Displays all supported documents (PDFs and images) in a directory.

    Args:
        directory_path: Path to the directory containing the documents.
    """
    directory = Path(directory_path)

    if not directory.exists() or not directory.is_dir():
        print(f"Directory not found: {directory_path}")
        return

    # Supported extensions
    supported = {".png", ".jpg", ".jpeg", ".pdf"}

    # Get all matching files
    files = sorted([f for f in directory.iterdir()
                    if f.suffix.lower() in supported])

    if not files:
        print("No supported documents found.")
        return

    # Display each document using your existing helper
    for f in files:
        print(f"\n--- Displaying: {f.name} ---\n")
        print_document(str(f))
```

```python
display_directory("input_folder")
```

<a id="3-2"></a>

### 3.2 Document Categorization Schema

This lab uses **Pydantic** instead of JSON to define schemas. Pydantic provides type validation, rich descriptions via `Field()`, and enum support for constrained values.

ADE accepts both JSON and Pydantic schemas, converting Pydantic to JSON before sending to the API.

```python
# Import Pydantic for schema definition
# ADE accepts pydantic and JSON schemas.
# Exercise 1 used JSON. Exercise 3 uses pydantic.

from enum import Enum
from pydantic import BaseModel, Field
from landingai_ade.lib import pydantic_to_json_schema

class DocumentType(str, Enum):
    ID = "ID"
    W2 = "W2"
    pay_stub = "pay_stub"
    bank_statement = "bank_statement"
    investment_statement = "investment_statement"

    # Descriptions for each value
    def describe(self) -> str:
        descriptions = {
            "ID": "An official government identification such as a "
            "passport or driver's license.",
            "W2": "A year-end W-2 form reporting annual taxable wages "
            "and withholdings.",
            "pay_stub": "A periodic employee earnings statement.",
            "bank_statement": "A checking or savings account statement "
            "with balances and transactions.",
            "investment_statement": "A brokerage or investment account "
            "statement showing holdings, value, and transactions.",
        }
        return descriptions[self.value]

class DocType(BaseModel):
    type: DocumentType = Field(
        description="The type of document being analyzed.",
        title="Document Type",
    )
```

<a id="3-3"></a>

### 3.3 Define Document-Specific Extraction Schemas

Each document type has different fields of interest. Define separate Pydantic schemas for:
- **ID**: Name, issuer, issue date, identifier
- **W2**: Employee/employer names, year, wages (Box 1)
- **Pay Stub**: Employee/employer names, pay period, gross/net pay
- **Bank Statement**: Account owner, bank name, account number, balance
- **Investment Statement**: Account owner, institution, year, total value

```python
# ---------------------------------------------------------
# Schema for ID
# ---------------------------------------------------------
class IDSchema(BaseModel):
    name: str = Field(description="Full name of the person", 
                      title="Full Name")
    issuer: str = Field(description="The state or country issuing the "
                        "identification.", title="Issuer")
    issue_date: str = Field(description="The issue date for the "
                            "identification.", title="Issue Date")
    identifier: str = Field(description="The unique identifier such as a "
                            "drivers license number or passport number", 
                            title="Identifier")

# ---------------------------------------------------------
# Schema for W2
# ---------------------------------------------------------
class W2Schema(BaseModel):
    employee_name: str = Field(description="The name of the employee.", 
                               title="Employee Name")
    employer_name: str = Field(description="The name of the employer "
                               "organization issuing the W2.", 
                               title="Employer Name")
    w2_year: int = Field(description="The year of the W2 form.", 
                         title="W2 Year")
    wages_box_1: float = Field(description="The total wages shown in box 1 "
                               "of the form", title="Box 1")

# ---------------------------------------------------------
# Schema for Pay Stubs
# ---------------------------------------------------------
class PaymentStubSchema(BaseModel):
    employee_name: str = Field(description="The name of the employee.", 
                               title="Employee Name")
    employer_name: str = Field(description="The name of the employer "
                               "organization.", title="Employer Name")
    pay_period: str = Field(description="The pay period for the stub.",
                            title="Pay Period")
    gross_pay: float = Field(description="The gross pay amount.",
                             title="Gross Pay")
    net_pay: float = Field(description="The net pay amount after "
                           "deductions.", title="Net Pay")
    
# ---------------------------------------------------------
# Schema for Bank Statements
# ---------------------------------------------------------
class BankStatementSchema(BaseModel):
    account_owner: str = Field(description="The name of the account "
                               "owner(s).", title="Account Owner")
    bank_name: str = Field(description="The name of the bank.", 
                           title="Bank Name")
    account_number: str = Field(description="The bank account number.", 
                                title="Account Number")
    end_date: str = Field(description="The ending date for the statement.", 
                          title="End Date")
    balance: float = Field(description="The current balance of the bank "
                           "account.", title="Bank Balance")

# ---------------------------------------------------------
# Schema for Investment Statements
# ---------------------------------------------------------
class InvestmentStatementSchema(BaseModel):
    account_owner: str = Field(description="The name of the account owner(s)."
                               , title="Account Owner")
    institution_name: str = Field(description="The name of the financial "
                                  "institution.", title="Institution Name")
    investment_year: int = Field(description="The year of the investment "
                                 "statement.", title="Investment Year")
    investment_value: float = Field(description="The total value of the "
                                    "account as of the statement end date.", 
                                    title="Investment Balance")

# ---------------------------------------------------------
# Map document types to their corresponding schemas
# ---------------------------------------------------------
schema_per_doc_type = {
    "bank_statement": BankStatementSchema,
    "investment_statement": InvestmentStatementSchema,
    "pay_stub": PaymentStubSchema,
    "ID": IDSchema,
    "W2": W2Schema,
}
```

```python
# Convert the document type schema to JSON format for API calls
doc_type_json_schema = pydantic_to_json_schema(DocType)
```

<a id="3-4"></a>

### 3.4 Parse and Categorize Documents

For each document:
1. **Parse** to extract content (using `split="page"` for per-page markdown)
2. **Categorize** using only the first page (sufficient for identification)

```python
input_folder = Path("input_folder")

# Dictionary to store document types and parse results
document_types = {}

# Process each document in the folder
for document in input_folder.iterdir():

    # 🔥 Skip directories so ADE doesn't try to parse them
    if document.is_dir():
        continue
        
    print(f"Processing document: {document.name}")

    # Step 1: Parse the document to extract layout and content
    parse_result: ParseResponse = client.parse(
        document=document,
        split="page",  #Notice that each document is being split by page.
        model="dpt-2-latest"
    )
    print("Parsing completed.")
    print(" ")
    
    # Notice that we only use the first page to determine the document type
    first_page_markdown = parse_result.splits[0].markdown  
    
    # Step 2: Extract document type using the categorization schema
    print("Extracting Document Type...")
    extraction_result: ExtractResponse = client.extract(
        schema=doc_type_json_schema,
        markdown=first_page_markdown
    )
    doc_type = extraction_result.extraction["type"]
    print(f"Document Type Extraction: {doc_type}\n")
    print("       ----------         ")
    print(" ")
    
    # Store results for later use
    document_types[document] = {
        "document_type": doc_type,
        "parse_result": parse_result
    }
```

<a id="3-5"></a>

### 3.5 Extract Financial Data Based on Document Type

Now that we know each document's type, we apply the appropriate schema to extract the relevant fields. The schema mapping (`schema_per_doc_type`) ensures each document gets the correct extraction template.

```python
# Dictionary to store extraction results
document_extractions = {}

# Extract financial data from each document using its specific schema
for document, extraction in document_types.items():
    print(f"Processing document: {document.name}")

    # Get the appropriate schema for this document type
    json_schema = pydantic_to_json_schema(
        schema_per_doc_type[extraction["document_type"]]
    )

    # Extract structured data using the schema
    extraction_result: ExtractResponse = client.extract(
        schema=json_schema,
        markdown=extraction["parse_result"].markdown
    )
    print("Detailed Extraction:", extraction_result.extraction)

    # Store extraction results
    document_extractions[document] = {
        "extraction": extraction_result.extraction,
        "extraction_metadata": extraction_result.extraction_metadata,
    }

print(document_extractions)
```

<a id="3-6"></a>

### 3.6 Visualize Parsing Results with Bounding Boxes

Visualize all detected chunks for each document to verify parsing quality.

```python
from helper import draw_bounding_boxes_2

# Combine all extraction data
final_extractions = {}

for document, extraction in document_extractions.items():
    final_extractions[document] = {
        **extraction,
        **document_types[document],
    }

# Visualize all parsed chunks for each document
for document, extraction in final_extractions.items():
    print(f"Visualizing document: {document.name}")
    base_path = f"results/{document.stem}"
    os.makedirs(base_path, exist_ok=True)
    draw_bounding_boxes_2(
        extraction["parse_result"].grounding,
        document,
        base_path=base_path
    )
```

```python
PILImage.open(f"results/uploadC/page_1_annotated.png")
```

```python
PILImage.open(f"results/uploadE/page_1_annotated.png")
```

<a id="3-7"></a>

### 3.7 Visualize Extracted Fields Only

For human-in-the-loop systems, highlight only the extracted fields to show reviewers where values originated.

```python
for document, extraction in final_extractions.items():
    print(f"Visualizing extracted fields for: {document.name}")
    base_path = f"results_extracted/{document.stem}"

    parse_result = extraction["parse_result"]
    document_grounds = {}

    for label, metadata_value in extraction["extraction_metadata"].items():
        chunk_id = metadata_value["references"][0]
        grounding = parse_result.grounding[chunk_id]
        document_grounds[chunk_id] = grounding

    draw_bounding_boxes_2(
        document_grounds,  # dict of chunk_id -> grounding
        document,
        base_path=base_path
    )
```

```python
PILImage.open(f"results_extracted/uploadC/page_1_annotated.png")
```

<a id="3-8"></a>

### 3.8 Create a Final Dataframe

Consolidate all extracted fields into a summary dataframe for a complete view of applicant information.

```python
import pandas as pd

# Collect all the fields into a summary dataframe
rows = []

for document, info in document_extractions.items():
    extraction = info["extraction"]
    doc_type = document_types[document]["document_type"]  # from your classification step

    input_folder = document.parent.name
    document_name = document.name

    for field, value in extraction.items():
        rows.append({
            "applicant_folder": input_folder,
            "document_name": document_name,
            "document_type": doc_type,
            "field": field,
            "value": value,
        })

df = pd.DataFrame(rows)

df
```

<a id="3-9"></a>

### 3.9 Validation Logic

Apply business logic to validate the submission:
- **Name matching**: Verify all documents belong to the same person
- **Year verification**: Check all documents are from recent years
- **Asset totals**: Calculate the applicant's total net worth

**Check 1: Name Matching**

Verify that all name fields across documents match to catch mismatched submissions.

```python
# Logic check to determine whether the five name fields extracted 
# from five documents match each other.

name_fields = {"account_owner", "employee_name", "name"}
df_names = df[df["field"].isin(name_fields)].copy()
all_names_match = df_names["value"].nunique() == 1

if all_names_match:
    print("✅ All 5 name fields match!")
else:
    print("❌ The name fields do NOT match.")
    print("Values found:")
    print(df_names[["document_name", "field", "value"]])
```

**Check 2: Document Year**

Loan applications require recent documents. Extract and verify the year from each document.

```python
# Logic to extract and check the year associated with each document

import re

# 1. Fields that may contain a year
year_fields = {
    "w2_year",
    "investment_year",
    "issue_date",
    "end_date",
    "pay_period",
}

# 2. Helper to pull a 4-digit year out of a string/number
def extract_year(value):
    """
    Return a 4-digit year (1900–2099) from a value, or None if none found.
    """
    if value is None:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", str(value))
    return int(match.group(0)) if match else None


# 3. Build a table of years per document
year_rows = []

for doc_name in df["document_name"].unique():
    doc_df = df[df["document_name"] == doc_name]

    # Only rows whose field is one of our year-related fields
    doc_year_fields = doc_df[doc_df["field"].isin(year_fields)]

    for _, row in doc_year_fields.iterrows():
        year_value = extract_year(row["value"])
        year_rows.append({
            "document_name": doc_name,
            "field": row["field"],
            "value": row["value"],
            "year_extracted": year_value,
        })

df_years = pd.DataFrame(year_rows)

print("Per-document year info:")
print(df_years)
```

**Check 3: Total Assets**

Sum all bank and investment balances to determine loan eligibility.

```python
# Logic to sum all bank balances and all investment balances from your extraction

# Define fields
bank_balance_field = "balance"
investment_balance_field = "investment_value"

# Filter rows
df_bank = df[df["field"] == bank_balance_field].copy()
df_invest = df[df["field"] == investment_balance_field].copy()

# Ensure numeric
df_bank["value"] = pd.to_numeric(df_bank["value"], errors="coerce")
df_invest["value"] = pd.to_numeric(df_invest["value"], errors="coerce")

# Compute totals
total_bank = df_bank["value"].sum()
total_investments = df_invest["value"].sum()
total_assets = total_bank + total_investments

# Print
print(f"Total Bank Balances: ${total_bank:,.2f}")
print(f"Total Investment Balances: ${total_investments:,.2f}")
print(f"Total Assets: ${total_assets:,.2f}")
```

<a id="4"></a>

## 4. Summary

In this lab, you built a document processing pipeline for loan automation:

| Step | Description |
|------|-------------|
| **Parse** | Convert documents to structured markdown with chunks and grounding |
| **Categorize** | Identify document types from the first page according to a categorization schema |
| **Extract** | Apply Pydantic schemas specific to document type |
| **Visualize** | Display bounding boxes for all chunks  |
| **Validate** | Apply data validation to fields (eg name matching, year checks, asset totals) |

Our approach applies to other scenarios such as insurance claims, healthcare records, legal briefings, and payroll processing.

In the next lesson, you'll use ADE for RAG (Retrieval-Augmented Generation) applications.
