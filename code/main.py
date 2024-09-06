import os
from google.cloud import storage, secretmanager, bigquery
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
import yaml
import functions_framework

    # initialize clients
storage_client = storage.Client()
bigquery_client = bigquery.Client()
secret_client = secretmanager.SecretManagerServiceClient()

# Get OpenAI API key from Secret Manager
project_id = os.environ.get("GCP_PROJECT")
secret_name = f"projects/{project_id}/secrets/openai_api_key/versions/latest"
response = secret_client.access_secret_version(request={"name": secret_name})
openai_api_key = response.payload.data.decode("UTF-8")

# Initialize OpenAI embeddings
embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=openai_api_key)

# Initialize text splitter
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

def process_yaml_file(bucket_name, file_name):
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(file_name)
    content = blob.download_as_text()
    semantic_model = yaml.safe_load(content)
    entity_name = semantic_model['semantic_model']['name']
    return entity_name, yaml.dump(semantic_model)

@functions_framework.http
def process_knowledge_base(request):
    # Get bucket and file information from the request
    if request.method == 'POST':
        data = request.get_json()
        if data and 'message' in data:
            message = data['message']
            attributes = message.get('attributes', {})
            bucket_name = attributes.get('bucketId')
            file_name = attributes.get('objectId')
        else:
            return "Invalid request: missing message data", 400
    else:
        return "Invalid request method", 405

    # Process only YAML files
    if not file_name.endswith('.yaml'):
        return f"Skipping non-YAML file: {file_name}", 200

    # Process the YAML file
    entity_name, yaml_content = process_yaml_file(bucket_name, file_name)
    
    # Split the content into chunks
    texts = text_splitter.split_text(yaml_content)
    
    # Generate embeddings
    embedded_texts = embeddings.embed_documents(texts)

    # Prepare rows for insertion
    rows_to_insert = [
        {
            "entity": entity_name,
            "chunk_id": f"{entity_name}_{i}",
            "text_chunk": chunk,
            "embedding": embedding
        }
        for i, (chunk, embedding) in enumerate(zip(texts, embedded_texts))
    ]

    # Get BigQuery dataset and table information from environment variables
    dataset_id = os.environ.get('BIGQUERY_DATASET', 'knowledge_base')
    table_id = os.environ.get('BIGQUERY_TABLE', 'semantic_model_vector')
    table_ref = f"{bigquery_client.project}.{dataset_id}.{table_id}"

    # Delete existing rows for the processed entity
    delete_query = f"""
    DELETE FROM `{table_ref}`
    WHERE entity = @entity
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("entity", "STRING", entity_name)
        ]
    )
    bigquery_client.query(delete_query, job_config=job_config).result()

    # Insert new rows
    errors = bigquery_client.insert_rows_json(table_ref, rows_to_insert)

    if errors == []:
        return f"Successfully uploaded embeddings for {entity_name} to BigQuery", 200
    else:
        return f"Errors occurred while uploading embeddings for {entity_name}: {errors}", 500

if __name__ == "__main__":
    # This is used when running locally only. When deploying to Cloud Run,
    # a webserver will serve the app.
    app.run(host='localhost', port=8080, debug=True)