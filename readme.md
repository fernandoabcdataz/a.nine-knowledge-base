# AI Knowledge Base Processor

This project processes YAML files containing semantic models for an AI knowledge base. It extracts information from the YAML files, generates embeddings using OpenAI's API, and stores the results in Google BigQuery.

## Project Structure

```
A.NINE-KNOWLEDGE-BASE/
│
├── code/
│   ├── __pycache__/
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
│
├── knowledge-base/
│   ├── xero_invoices.yaml
│   └── xero_payments.yaml
│
├── myenv/
├── .env
├── .gitignore
├── readme.md
└── service-account.json
```

## Dockerfile

The Dockerfile sets up a Python 3.9 environment and installs the necessary dependencies to run the application.

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

ENV PORT=8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "main:app"]
```

## Main Application (main.py)

The main.py file contains a Flask application that:

1. Initializes Google Cloud clients (Storage, BigQuery, Secret Manager)
2. Retrieves the OpenAI API key from Secret Manager
3. Processes YAML files from a specified Google Cloud Storage bucket
4. Generates embeddings for the content using OpenAI's API
5. Stores the embeddings and related information in BigQuery

## Requirements

The application requires the following Python packages:

- Flask
- google-cloud-storage
- google-cloud-secret-manager
- google-cloud-bigquery
- langchain
- langchain-openai
- pyyaml
- gunicorn
- openai

## Usage

1. Build the Docker image:
   ```
   docker build -t ai-knowledge-base-processor .
   ```

2. Run the container:
   ```
   docker run -p 8080:8080 -e GCP_PROJECT=your-project-id ai-knowledge-base-processor
   ```

3. The application will process YAML files in the specified Google Cloud Storage bucket when triggered via the `/run` endpoint.

## Environment Variables

- `GCP_PROJECT`: Your Google Cloud Project ID
- `BIGQUERY_DATASET`: The BigQuery dataset to use (default: 'knowledge_base')
- `BIGQUERY_TABLE`: The BigQuery table to use (default: 'semantic_model_vector')
- `STORAGE_BUCKET`: The Google Cloud Storage bucket containing the YAML files (default: 'ai-assistant-knowledge-base')

## YAML File Structure

The YAML files in the knowledge-base directory should follow a specific structure defining semantic models. Here's a simplified example:

```yaml
semantic_model:
  name: invoices
  description: "Description of the invoices model"
  grain: invoice_id
  business_keys:
    - name: invoice_id
      column: invoice_id
  entities:
    - name: invoice
      description: "A unique invoice for sales or purchase"
      type: primary
      exp: invoice_id
  # ... (dimensions, measures, relationships, filters)
```

## Notes

- Ensure that the necessary Google Cloud APIs are enabled for your project.
- The application uses a service account for authentication. Make sure the service account has the required permissions.
- The OpenAI API key is stored in Google Secret Manager for security.