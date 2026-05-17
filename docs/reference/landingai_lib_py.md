> ## Documentation Index
> Fetch the complete documentation index at: https://docs.landing.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Python Library

export const section = 'ADE Section';

export const classify = 'ADE Classify';

export const adePythonLibrary = 'ade-python';

export const dpt2 = 'DPT-2';

export const dpt1 = 'DPT-1';

export const dpt = 'Document Pre-Trained Transformer';

export const companyName = 'LandingAI';

export const extract = 'ADE Extract';

export const parse = 'ADE Parse';

export const ade = 'Agentic Document Extraction';

The [{adePythonLibrary}](https://github.com/landing-ai/ade-python) library is a lightweight Python library you can use for parsing documents, classifying pages, extracting data, generating tables of contents, and splitting documents into sub-documents.

The library is automatically generated from our API specification, ensuring you have access to the latest endpoints and parameters.

## Install the Library

```bash theme={null}
pip install landingai-ade
```

## Set the API Key as an Environment Variable

To use the library, first [generate an API key](https://va.landing.ai/my/settings/api-key). Save the key to a `.zshrc` file or another secure location on your computer. Then export the key as an environment variable.

```bash theme={null}
export VISION_AGENT_API_KEY=<your-api-key>
```

<Info>For more information about API keys and alternate methods for setting the API key, go to [API Key](./agentic-api-key).</Info>

## Use with EU Endpoints

By default, the library uses the US endpoints. If your API key is from the EU endpoint, set the `environment` parameter to `eu` when initializing the client.

```python theme={null}
from pathlib import Path
from landingai_ade import LandingAIADE

client = LandingAIADE(
    environment="eu",
)

# ... rest of your code
```

<Info>For more information about using {ade} in the EU, go to [European Union (EU)](./ade-eu).</Info>

## Parse: Getting Started

The `parse` function converts documents into structured markdown with chunk and grounding metadata. Use these examples as guides to get started with parsing with the library.

### Parse Local Files

Use the `document` parameter to parse files from your filesystem. Pass the file path as a `Path` object.

```python theme={null}
from pathlib import Path
from landingai_ade import LandingAIADE

client = LandingAIADE()

# Replace with your file path
response = client.parse(
    document=Path("/path/to/file/document"),
    model="dpt-2-latest",
    save_to="./output"
)
print(response.chunks)
```

### Parse Remote URLs

Use the `document_url` parameter to parse files from remote URLs (http, https, ftp, ftps).

```python theme={null}
from landingai_ade import LandingAIADE

client = LandingAIADE()

# Parse a remote file
response = client.parse(
    document_url="https://example.com/document.pdf",
    model="dpt-2-latest",
    save_to="./output"
)
print(response.chunks)
```

### Set Parameters

The `parse` function accepts optional parameters to customize parsing behavior. To see all available parameters, go to [ADE Parse API](https://docs.landing.ai/api-reference/tools/ade-parse).

Pass these parameters directly to the `parse()` function.

```python theme={null}
from pathlib import Path
from landingai_ade import LandingAIADE

client = LandingAIADE()

response = client.parse(
    document=Path("/path/to/document.pdf"),
    model="dpt-2-latest",
    split="page"
)
```

### Parse Jobs

The `parse_jobs` function enables you to asynchronously parse documents that are up to 1,000 pages or 1 GB.
For more information about parse jobs, go to [Parse Large Files (Parse Jobs)](./ade-parse-async).

Here is the basic workflow for working with parse jobs:

1. Start a parse job.
2. Copy the `job_id` in the response.
3. Get the results from the parsing job with the `job_id`.

This script contains the full workflow:

```python [expandable] theme={null}
import time
from pathlib import Path
from landingai_ade import LandingAIADE

client = LandingAIADE()

## Step 1: Create a parse job
job = client.parse_jobs.create(
    document=Path("/path/to/file/document"),
    model="dpt-2-latest"
)

job_id = job.job_id
print(f"Job {job_id} created.")

 # Step 2: Get the parsing results
while True: 
  response = client.parse_jobs.get(job_id)
  if response.status == "completed":
    print(f"Job {job_id} completed.")
    break
  print(f"Job {job_id}: {response.status} ({response.progress * 100:.0f}% complete)")
  time.sleep(5)

# Step 3: Access the parsed data
print("Global markdown:", response.data.markdown[:200] + "...")
print(f"Number of chunks: {len(response.data.chunks)}")

# Save Markdown output (useful if you plan to run extract on the Markdown)
with open("output.md", "w", encoding="utf-8") as f:
    f.write(response.data.markdown)
```

#### List Parse Jobs

To list all async parse jobs associated with your API key, run this code:

```python theme={null}
from pathlib import Path
from landingai_ade import LandingAIADE

client = LandingAIADE()

# List all jobs
response = client.parse_jobs.list()
for job in response.jobs:
    print(f"Job {job.job_id}: {job.status}")
```

### Parse Output

The `parse` function returns a `ParseResponse` object with the following fields:

* **`chunks`**: List of `Chunk` objects, one for each parsed region
* **`markdown`**: Complete Markdown representation of the document
* **`metadata`**: Processing information (credit usage, duration, filename, job ID, page count, version)
* **`splits`**: List of `Split` objects organizing chunks by page or section
* **`grounding`**: Dictionary mapping chunk IDs to detailed grounding information

For detailed information about the response structure, chunks, grounding, and bounding box coordinates, go to [JSON Response](./ade-json-response).

#### Common Use Cases for ParseResponse Fields

**Access all text chunks:**

```python theme={null}
for chunk in response.chunks:
    if chunk.type == 'text':
        print(f"Chunk {chunk.id}: {chunk.markdown}")
```

**Filter chunks by page:**

```python theme={null}
page_0_chunks = [chunk for chunk in response.chunks if chunk.grounding.page == 0]
```

**Get chunk locations:**

```python theme={null}
for chunk in response.chunks:
    box = chunk.grounding.box
    print(f"Chunk at page {chunk.grounding.page}: ({box.left}, {box.top}, {box.right}, {box.bottom})")
```

**Access detailed chunk types from grounding dictionary:**

```python theme={null}
for chunk_id, grounding in response.grounding.items():
    print(f"Chunk {chunk_id} has type: {grounding.type}")
```

## Extract: Getting Started

The `extract` function extracts structured data from Markdown content using extraction schemas. Use these examples as guides to get started with extracting with the library.

**Pass Markdown Content**

The library supports a few methods for passing the Markdown content for extraction:

* Extract data directly from the [parse response](#extract-from-parse-response)
* Extract data from a local [Markdown file](#extract-from-markdown-files)
* Extract data from a Markdown file at a remote URL: `markdown_url="https://example.com/file.md"`

**Pass the Extraction Schema**

The library supports a few methods for passing the extraction schema:

* [Pydantic models](#extraction-with-pydantic)
* [JSON schema (inline)](#extraction-with-json-schema-inline)
* [JSON schema file](#extraction-with-json-schema-file)

### Extract from Parse Response

After parsing a document, you can pass the markdown string directly from the `ParseResponse` to the extract function without saving it to a file.

```python theme={null}
import json
from pathlib import Path
from landingai_ade import LandingAIADE

# Define your extraction schema
schema_dict = {
    "type": "object",
    "properties": {
        "employee_name": {
            "type": "string",
            "description": "The employee's full name"
        }
    }
}

client = LandingAIADE()
schema_json = json.dumps(schema_dict)

# Parse the document
parse_response = client.parse(
    document=Path("/path/to/document.pdf"),
    model="dpt-2-latest"
)

# Extract data using the markdown string from parse response
extract_response = client.extract(
    schema=schema_json,
    markdown=parse_response.markdown,  # Pass markdown string directly
    model="extract-latest"
)

# Access the extracted data
print(extract_response.extraction)
```

### Extract from Markdown Files

If you already have a Markdown file (from a previous parsing operation), you can extract data directly from it. Use the `markdown` parameter for local markdown files or `markdown_url` for remote markdown files.

```python [expandable] theme={null}
import json
from pathlib import Path
from landingai_ade import LandingAIADE

# Define your extraction schema
schema_dict = {
    "type": "object",
    "properties": {
        "employee_name": {
            "type": "string",
            "description": "The employee's full name"
        },
        "employee_ssn": {
            "type": "string",
            "description": "The employee's Social Security Number"
        },
        "gross_pay": {
            "type": "number",
            "description": "The gross pay amount"
        }
    }
}

client = LandingAIADE()
schema_json = json.dumps(schema_dict)

# Extract from a local markdown file
extract_response = client.extract(
    schema=schema_json,
    markdown=Path("/path/to/output.md"),
    model="extract-latest"
)

# Or extract from a remote markdown file
extract_response = client.extract(
    schema=schema_json,
    markdown_url="https://example.com/document.md",
    model="extract-latest"
)

# Access the extracted data
print(extract_response.extraction)
```

### Extraction with Pydantic

Use Pydantic models to define your extraction schema in a type-safe way. The library provides a helper function to convert Pydantic models to JSON schemas.

```python [expandable] theme={null}
from pathlib import Path
from landingai_ade import LandingAIADE
from landingai_ade.lib import pydantic_to_json_schema
from pydantic import BaseModel, Field

# Define your extraction schema as a Pydantic model
class PayStubData(BaseModel):
    employee_name: str = Field(description="The employee's full name")
    employee_ssn: str = Field(description="The employee's Social Security Number")
    gross_pay: float = Field(description="The gross pay amount")

# Initialize the client
client = LandingAIADE()

# First, parse the document to get markdown
parse_response = client.parse(
    document=Path("/path/to/pay-stub.pdf"),
    model="dpt-2-latest"
)

# Convert Pydantic model to JSON schema
schema = pydantic_to_json_schema(PayStubData)

# Extract structured data using the schema
extract_response = client.extract(
    schema=schema,
    markdown=parse_response.markdown,
    model="extract-latest"
)

# Access the extracted data
print(extract_response.extraction)

# Access extraction metadata to see which chunks were referenced
print(extract_response.extraction_metadata)
```

### Extraction with JSON Schema (Inline)

Define your extraction schema directly as a JSON string in your script.

```python [expandable] theme={null}
import json
from pathlib import Path
from landingai_ade import LandingAIADE

# Define your extraction schema as a dictionary
schema_dict = {
    "type": "object",
    "properties": {
        "employee_name": {
            "type": "string",
            "description": "The employee's full name"
        },
        "employee_ssn": {
            "type": "string",
            "description": "The employee's Social Security Number"
        },
        "gross_pay": {
            "type": "number",
            "description": "The gross pay amount"
        }
    }
}

# Initialize the client
client = LandingAIADE()

# First, parse the document to get markdown
parse_response = client.parse(
    document=Path("/path/to/pay-stub.pdf"),
    model="dpt-2-latest"
)

# Convert schema dictionary to JSON string
schema_json = json.dumps(schema_dict)

# Extract structured data using the schema
extract_response = client.extract(
    schema=schema_json,
    markdown=parse_response.markdown,
    model="extract-latest"
)

# Access the extracted data
print(extract_response.extraction)

# Access extraction metadata to see which chunks were referenced
print(extract_response.extraction_metadata)
```

### Extraction with JSON Schema File

Load your extraction schema from a separate JSON file for better organization and reusability.

For example, here is the `pay_stub_schema.json` file:

```json theme={null}
{
  "type": "object",
  "properties": {
    "employee_name": {
      "type": "string",
      "description": "The employee's full name"
    },
    "employee_ssn": {
      "type": "string",
      "description": "The employee's Social Security Number"
    },
    "gross_pay": {
      "type": "number",
      "description": "The gross pay amount"
    }
  }
}
```

You can pass the JSON file defined above in the following script:

```python [expandable] theme={null}
import json
from pathlib import Path
from landingai_ade import LandingAIADE

# Initialize the client
client = LandingAIADE()

# First, parse the document to get markdown
parse_response = client.parse(
    document=Path("/path/to/pay-stub.pdf"),
    model="dpt-2-latest"
)

# Load schema from JSON file
with open("pay_stub_schema.json", "r") as f:
    schema_json = f.read()

# Extract structured data using the schema
extract_response = client.extract(
    schema=schema_json,
    markdown=parse_response.markdown,
    model="extract-latest"
)

# Access the extracted data
print(extract_response.extraction)

# Access extraction metadata to see which chunks were referenced
print(extract_response.extraction_metadata)
```

### Extract Nested Subfields

Define nested Pydantic models to extract hierarchical data from documents. This approach organizes related information under meaningful section names.

Define nested models before the main extraction schema. Otherwise, the nested model classes will not be defined when referenced.

For example, to extract data from the **Patient Details** and **Emergency Contact Information** sections in this <a href="/examples/medical-form.pdf" download="medical-form.pdf">Medical Form</a>, define separate models for each section, then combine them in a main model.

```python [expandable] theme={null}
from pathlib import Path
from pydantic import BaseModel, Field
from landingai_ade import LandingAIADE
from landingai_ade.lib import pydantic_to_json_schema


# Define a nested model for patient-specific information
class PatientDetails(BaseModel):

    patient_name: str = Field(
        ...,
        description='Full name of the patient.',
        title='Patient Name'
    )
    date: str = Field(
        ...,
        description='Date the patient information form was filled out.',
        title='Date',
    )


# Define a nested model for emergency contact details
class EmergencyContactInformation(BaseModel):

    emergency_contact_name: str = Field(
        ...,
        description='Full name of the emergency contact person.',
        title='Emergency Contact Name',
    )
    relationship_to_patient: str = Field(
        ...,
        description='Relationship of the emergency contact to the patient.',
        title='Relationship to Patient',
    )
    primary_phone_number: str = Field(
        ...,
        description='Primary phone number of the emergency contact.',
        title='Primary Phone Number',
    )
    secondary_phone_number: str = Field(
        ...,
        description='Secondary phone number of the emergency contact.',
        title='Secondary Phone Number',
    )
    address: str = Field(
        ...,
        description='Full address of the emergency contact.',
        title='Address'
    )


# Define the main extraction schema that combines all the nested models
class PatientAndEmergencyContactInformationExtractionSchema(BaseModel):

    # Nested field containing patient details
    patient_details: PatientDetails = Field(
        ...,
        description='Information about the patient as provided in the form.',
        title='Patient Details',
    )

    # Nested field containing emergency contact information
    emergency_contact_information: EmergencyContactInformation = Field(
        ...,
        description='Details of the emergency contact person for the patient.',
        title='Emergency Contact Information',
    )


# Initialize the client
client = LandingAIADE()

# Parse the document to get markdown
parse_response = client.parse(
    document=Path("/path/to/medical-form.pdf"),
    model="dpt-2-latest"
)

# Convert Pydantic model to JSON schema
schema = pydantic_to_json_schema(PatientAndEmergencyContactInformationExtractionSchema)

# Extract structured data using the schema
extract_response = client.extract(
    schema=schema,
    markdown=parse_response.markdown,
    model="extract-latest"
)

# Display the extracted structured data
print(extract_response.extraction)
```

### Extract Variable-Length Data with List Objects

Use python `List` type inside of a Pydantic BaseModel to extract repeatable data structures when you don't know how many items will appear. Common examples include line items in invoices, transaction records, or contact information for multiple people.

For example, to extract variable-length wire instructions and line items from this <a href="/examples/wire-transfer.pdf" download="wire-transfer.pdf">Wire Transfer Form</a>, use `List[DescriptionItem]` for line items and `List[WireInstruction]` for wire transfer details.

```python [expandable] theme={null}
from typing import List
from pathlib import Path
from pydantic import BaseModel, Field
from landingai_ade import LandingAIADE
from landingai_ade.lib import pydantic_to_json_schema

# Nested models for list fields
class DescriptionItem(BaseModel):
    description: str = Field(description="Invoice or Bill Description")
    amount: float = Field(description="Invoice or Bill Amount")

class WireInstruction(BaseModel):
    bank_name: str = Field(description="Bank name")
    bank_address: str = Field(description="Bank address")
    bank_account_no: str = Field(description="Bank account number")
    swift_code: str = Field(description="SWIFT code")
    aba_routing: str = Field(description="ABA routing number")
    ach_routing: str = Field(description="ACH routing number")

# Invoice model containing list object fields
class Invoice(BaseModel):
    description_or_particular: List[DescriptionItem] = Field(
        description="List of invoice line items (description and amount)"
    )
    wire_instructions: List[WireInstruction] = Field(
        description="Wire transfer instructions"
    )

# Main extraction model
class ExtractedInvoiceFields(BaseModel):
    invoice: Invoice = Field(description="Invoice list-type fields")

# Initialize the client
client = LandingAIADE()

# Parse the document to get markdown
parse_response = client.parse(
    document=Path("/path/to/wire-transfer.pdf"),
    model="dpt-2-latest"
)

# Convert Pydantic model to JSON schema
schema = pydantic_to_json_schema(ExtractedInvoiceFields)

# Extract structured data using the schema
extract_response = client.extract(
    schema=schema,
    markdown=parse_response.markdown,
    model="extract-latest"
)

# Display the extracted data
print(extract_response.extraction)
```

### Extraction Output

The `extract` function returns an `ExtractResponse` object with the following fields:

* **`extraction`**: The extracted key-value pairs as defined by your schema
* **`extraction_metadata`**: Metadata showing which chunks were referenced for each extracted field
* **`metadata`**: Processing information including credit usage, duration, filename, job ID, version, and schema validation errors

For detailed information about the response structure, extraction metadata, and chunk references, go to [Extract JSON Response](./ade-extract-response).

## Classify: Getting Started

The `classify` function classifies each page in a document by type. Provide your document and a list of classes, and the API assigns a class to each page. Use these examples as guides to get started with classifying with the library.

### Classify Local Files

Use the `document` parameter to classify files from your filesystem. Pass the file path as a `Path` object.

```python theme={null}
import json
from pathlib import Path
from landingai_ade import LandingAIADE

client = LandingAIADE()

classes = [
    {"class": "invoice", "description": "A commercial bill with line items, totals, and payment terms"},
    {"class": "bank_statement", "description": "A monthly summary of account transactions"},
    {"class": "pay_stub"}
]

response = client.classify(
    classes=json.dumps(classes),
    document=Path("/path/to/document.pdf"),
    model="classify-latest"
)

for result in response.classification:
    print(f"Page {result.page}: {result.class_}")
```

### Classify Remote URLs

Use the `document_url` parameter to classify files from remote URLs (http, https, ftp, ftps).

```python theme={null}
import json
from landingai_ade import LandingAIADE

client = LandingAIADE()

classes = [
    {"class": "invoice", "description": "A commercial bill with line items, totals, and payment terms"},
    {"class": "bank_statement", "description": "A monthly summary of account transactions"}
]

response = client.classify(
    classes=json.dumps(classes),
    document_url="https://example.com/document.pdf",
    model="classify-latest"
)

for result in response.classification:
    print(f"Page {result.page}: {result.class_}")
```

### Set Parameters

The `classify` function accepts optional parameters to customize classification behavior. To see all available parameters, go to [{classify} API](https://docs.landing.ai/api-reference/tools/ade-classify).

```python theme={null}
import json
from pathlib import Path
from landingai_ade import LandingAIADE

client = LandingAIADE()

classes = [
    {"class": "invoice"},
    {"class": "bank_statement"}
]

response = client.classify(
    classes=json.dumps(classes),
    document=Path("/path/to/document.pdf"),
    model="classify-latest"
)
```

### Classify Output

The `classify` function returns a `ClassifyResponse` object with the following fields:

* **`classification`**: List of `Classification` objects, one per page, each containing:
  * **`class_`**: The predicted class label, or `'unknown'` if the page could not be classified. Note: `class_` is used instead of `class` because `class` is a reserved keyword in Python.
  * **`page`**: The zero-indexed page number
  * **`reason`**: A brief explanation of the classification (for debugging)
  * **`suggested_class`**: A proposed class when the prediction is `'unknown'`
* **`metadata`**: Processing information (credit usage, duration, filename, job ID, page count, version)

For detailed information about the response structure, see [JSON Response for Classification](./ade-classify-response).

#### Common Use Cases for ClassifyResponse Fields

**Get classification for each page:**

```python theme={null}
for result in response.classification:
    print(f"Page {result.page}: {result.class_}")
```

**Filter pages by class:**

```python theme={null}
invoices = [r for r in response.classification if r.class_ == "invoice"]
print(f"Found {len(invoices)} invoice pages")
```

**Handle pages that could not be classified:**

```python theme={null}
unknown = [r for r in response.classification if r.class_ == "unknown"]
for r in unknown:
    print(f"Page {r.page}: suggested class is {r.suggested_class}")
```

## Section: Getting Started

The `section` function analyzes a parsed document and generates a hierarchical table of contents. Use these examples as guides to get started with sectioning with the library.

**Pass Markdown Content**

The library supports a few methods for passing the Markdown content for sectioning:

* Section data directly from the [parse response](#section-from-parse-response)
* Section data from a local [Markdown file](#section-from-markdown-files)
* Section data from a Markdown file at a remote URL: `markdown_url="https://example.com/file.md"`

### Section from Parse Response

After parsing a document, you can pass the Markdown string directly from the `ParseResponse` to the section function without saving it to a file.

```python theme={null}
from pathlib import Path
from landingai_ade import LandingAIADE

client = LandingAIADE()

# Parse the document
parse_response = client.parse(
    document=Path("/path/to/document.pdf"),
    model="dpt-2-latest"
)

# Section using the Markdown string from parse response
section_response = client.section(
    markdown=parse_response.markdown,  # Pass Markdown string directly
    model="section-latest"
)

# Access the table of contents
for entry in section_response.table_of_contents:
    indent = "  " * (entry.level - 1)
    print(f"{indent}{entry.section_number}. {entry.title}")
```

### Section from Markdown Files

If you already have a Markdown file (from a previous parsing operation), you can section it directly. Use the `markdown` parameter for local Markdown files or `markdown_url` for remote Markdown files.

```python theme={null}
from pathlib import Path
from landingai_ade import LandingAIADE

client = LandingAIADE()

# Section from a local Markdown file
section_response = client.section(
    markdown=Path("/path/to/parsed_output.md"),
    model="section-latest"
)

# Or section from a remote Markdown file
section_response = client.section(
    markdown_url="https://example.com/document.md",
    model="section-latest"
)

# Access the table of contents
for entry in section_response.table_of_contents:
    indent = "  " * (entry.level - 1)
    print(f"{indent}{entry.section_number}. {entry.title}")
```

### Set Parameters

The `section` function accepts optional parameters to customize sectioning behavior. To see all available parameters, go to [{section} API](https://docs.landing.ai/api-reference/tools/ade-section).

```python theme={null}
from pathlib import Path
from landingai_ade import LandingAIADE

client = LandingAIADE()

section_response = client.section(
    markdown=Path("/path/to/parsed_output.md"),
    guidelines="Treat each numbered article as a top-level section",
    model="section-latest"
)
```

### Section Output

The `section` function returns a `SectionResponse` object with the following fields:

* **`table_of_contents`**: List of `SectionTOCEntry` objects, each containing:
  * **`title`**: The generated section heading text
  * **`level`**: The hierarchy depth (1 = top-level, 2 = subsection, 3 = sub-subsection, and so on)
  * **`section_number`**: The hierarchical number (for example, `"1"`, `"1.2"`, `"1.2.3"`)
  * **`start_reference`**: The chunk ID where this section begins, corresponding to a `chunks[].id` value from the parse response
* **`table_of_contents_md`**: Markdown-formatted TOC string with anchor links
* **`metadata`**: Processing information (credit usage, duration, filename, job ID, version)

For detailed information about the response structure, see [JSON Response for Sectioning](./ade-section-response).

## Split: Getting Started

The `split` function classifies and separates a parsed document into multiple sub-documents based on Split Rules you define. Use these examples as guides to get started with splitting with the library.

**Pass Markdown Content**

The library supports a few methods for passing the Markdown content for splitting:

* Split data directly from the [parse response](#split-from-parse-response)
* Split data from a local [Markdown file](#split-from-markdown-files)
* Split data from a Markdown file at a remote URL: `markdown_url="https://example.com/file.md"`

**Define Split Rules**

Split Rules define how the API classifies and separates your document. Each Split Rule consists of:

* `name`: The Split Type name (required)
* `description`: Additional context about what this Split Type represents (optional)
* `identifier`: A field that makes each instance unique, used to create separate splits (optional)

For more information about Split Rules, see [Split Rules](./ade-split#split-rules).

### Split from Parse Response

After parsing a document, you can pass the Markdown string directly from the `ParseResponse` to the split function without saving it to a file.

```python theme={null}
import json
from pathlib import Path
from landingai_ade import LandingAIADE

client = LandingAIADE()

# Parse the document
parse_response = client.parse(
    document=Path("/path/to/document.pdf"),
    model="dpt-2-latest"
)

# Define Split Rules
split_class = [
    {
        "name": "Bank Statement",
        "description": "Document from a bank that summarizes all account activity over a period of time."
    },
    {
        "name": "Pay Stub",
        "description": "Document that details an employee's earnings, deductions, and net pay for a specific pay period.",
        "identifier": "Pay Stub Date"
    }
]

# Split using the Markdown string from parse response
split_response = client.split(
    split_class=json.dumps(split_class),
    markdown=parse_response.markdown,  # Pass Markdown string directly
    model="split-latest"
)

# Access the splits
for split in split_response.splits:
    print(f"Classification: {split.classification}")
    print(f"Identifier: {split.identifier}")
    print(f"Pages: {split.pages}")
```

### Split from Markdown Files

If you already have a Markdown file (from a previous parsing operation), you can split it directly. Use the `markdown` parameter for local Markdown files or `markdown_url` for remote Markdown files.

```python theme={null}
import json
from pathlib import Path
from landingai_ade import LandingAIADE

client = LandingAIADE()

# Define Split Rules
split_class = [
    {
        "name": "Invoice",
        "description": "A document requesting payment for goods or services.",
        "identifier": "Invoice Number"
    },
    {
        "name": "Receipt",
        "description": "A document acknowledging that payment has been received."
    }
]

# Split from a local Markdown file
split_response = client.split(
    split_class=json.dumps(split_class),
    markdown=Path("/path/to/parsed_output.md"),
    model="split-latest"
)

# Or split from a remote Markdown file
split_response = client.split(
    split_class=json.dumps(split_class),
    markdown_url="https://example.com/document.md",
    model="split-latest"
)

# Access the splits
for split in split_response.splits:
    print(f"Classification: {split.classification}")
    if split.identifier:
        print(f"Identifier: {split.identifier}")
    print(f"Number of pages: {len(split.pages)}")
    print(f"Markdown content: {split.markdowns[0][:100]}...")
```

### Set Parameters

The `split` function accepts optional parameters to customize split behavior. To see all available parameters, go to [ADE Split API](https://docs.landing.ai/api-reference/tools/ade-split).

```python theme={null}
import json
from pathlib import Path
from landingai_ade import LandingAIADE

client = LandingAIADE()

split_response = client.split(
    split_class=json.dumps([
        {"name": "Section A", "description": "Introduction section"},
        {"name": "Section B", "description": "Main content section"}
    ]),
    markdown=Path("/path/to/parsed_output.md"),
    model="split-latest"
)
```

### Split Output

The `split` function returns a `SplitResponse` object with the following fields:

* **`splits`**: List of `Split` objects, each containing:
  * **`classification`**: The Split Type name assigned to this sub-document
  * **`identifier`**: The unique identifier value (or `None` if no identifier was specified)
  * **`pages`**: List of zero-indexed page numbers that belong to this split
  * **`markdowns`**: List of Markdown content strings, one for each page
* **`metadata`**: Processing information (credit usage, duration, filename, job ID, page count, version)

For detailed information about the response structure, see [JSON Response for Splitting](./ade-split-response).

#### Common Use Cases for SplitResponse Fields

**Access all splits by classification:**

```python theme={null}
for split in split_response.splits:
    print(f"Split Type: {split.classification}")
    print(f"Pages included: {split.pages}")
```

**Filter splits by classification:**

```python theme={null}
invoices = [split for split in split_response.splits if split.classification == "Invoice"]
print(f"Found {len(invoices)} invoices")
```

**Access Markdown content for each split:**

```python theme={null}
for split in split_response.splits:
    print(f"Classification: {split.classification}")
    for i, markdown in enumerate(split.markdowns):
        print(f"  Page {split.pages[i]} Markdown: {markdown[:100]}...")
```

**Group splits by identifier:**

```python theme={null}
from collections import defaultdict

splits_by_id = defaultdict(list)
for split in split_response.splits:
    if split.identifier:
        splits_by_id[split.identifier].append(split)

for identifier, splits in splits_by_id.items():
    print(f"Identifier '{identifier}': {len(splits)} split(s)")
```

## Save Output

Use the optional `save_to` parameter to save the full API response as a JSON file. The parameter is available on `parse`, `extract`, and `split`.

### Use the Default File Name

Pass a directory path. The library names the file using the input document's filename and the function called (for example, `document_parse_output.json`).

<CodeGroup>
  ```python Parse theme={null}
  # Saves as: ./output/document_parse_output.json
  response = client.parse(
      document=Path("/path/to/document.pdf"),
      model="dpt-2-latest",
      save_to="./output"
  )
  ```

  ```python Extract theme={null}
  # Saves as: ./output/document_extract_output.json
  extract_response = client.extract(
      schema=schema_json,
      markdown=Path("/path/to/document.md"),
      model="extract-latest",
      save_to="./output"
  )
  ```

  ```python Split theme={null}
  # Saves as: ./output/document_split_output.json
  split_response = client.split(
      split_class=json.dumps(split_class),
      markdown=Path("/path/to/document.md"),
      model="split-latest",
      save_to="./output"
  )
  ```
</CodeGroup>

<Info>When passing Markdown content as a string (`markdown=parse_response.markdown`), the library cannot derive a filename from the content. In this situation, use [Set the File Name](#set-the-file-name) instead.</Info>

### Set the File Name

Pass a path ending in `.json` to choose the exact location and filename.

<CodeGroup>
  ```python Parse theme={null}
  response = client.parse(
      document=Path("/path/to/document.pdf"),
      model="dpt-2-latest",
      save_to="./output/my_parse_results.json"
  )
  ```

  ```python Extract theme={null}
  extract_response = client.extract(
      schema=schema_json,
      markdown=parse_response.markdown,
      model="extract-latest",
      save_to="./output/document_extract_output.json"
  )
  ```

  ```python Split theme={null}
  split_response = client.split(
      split_class=json.dumps(split_class),
      markdown=parse_response.markdown,
      model="split-latest",
      save_to="./output/document_split_output.json"
  )
  ```
</CodeGroup>

### Save the Markdown Field

The `parse` response includes a `markdown` field that you can pass directly to other functions in the same script. To save the Markdown for downstream tasks, write it to a file:

```python theme={null}
with open("output.md", "w", encoding="utf-8") as f:
    f.write(response.markdown)
```