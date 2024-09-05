import os
from google.cloud import storage, bigquery, secretmanager
from langchain.llms import Anthropic
from langchain.embeddings import AnthropicEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
import functions_framework
import yaml

# initialize clients
storage_client = storage.Client()
bigquery_client = bigquery.Client()
secret_client = secretmanager.SecretManagerServiceClient()

# get anthropic api key from secret manager
project_id = os.environ.get("GCP_PROJECT")
secret_name = "projects/{}/secrets/{}/versions/latest".format(project_id, "anthropic-api-key")
response = secret_client.access_secret_version(request={"name": secret_name})
anthropic_api_key = response.payload.data.decode("UTF-8")

# initialize anthropic llm and embeddings
llm = Anthropic(model="claude-2.1", api_key=anthropic_api_key)
embeddings = AnthropicEmbeddings(model="claude-2.1", api_key=anthropic_api_key)

# initialize text splitter
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

def process_yaml_file(bucket_name, file_name):
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(file_name)
    content = blob.download_as_text()
    semantic_model = yaml.safe_load(content)
    entity_name = semantic_model['semantic_model']['name']
    return entity_name, yaml.dump(semantic_model)

@functions_framework.http
def upload_knowledge_base(request):
    # Get bucket and file information from the request
    data = request.get_json()
    bucket_name = data["bucket"]
    file_name = data["name"]

    # process only yaml files
    if not file_name.endswith('.yaml'):
        return f"skipping non-YAML file: {file_name}", 200

    # process the yaml file
    entity_name, yaml_content = process_yaml_file(bucket_name, file_name)
    
    # split the content into chunks
    texts = text_splitter.split_text(yaml_content)
    
    # generate embeddings
    embedded_texts = embeddings.embed_documents(texts)

    # prepare rows for insertion
    rows_to_insert = [
        {
            "entity": entity_name,
            "chunk_id": f"{entity_name}_{i}",
            "text_chunk": chunk,
            "embedding": embedding
        }
        for i, (chunk, embedding) in enumerate(zip(texts, embedded_texts))
    ]

    # get BigQuery dataset and table information from environment variables
    dataset_id = os.environ.get('BIGQUERY_DATASET', 'knowledge_base')
    table_id = os.environ.get('BIGQUERY_TABLE', 'semantic_model_embeddings')
    table_ref = f"{bigquery_client.project}.{dataset_id}.{table_id}"

    # delete existing rows for the processed entity
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

    # insert new rows
    errors = bigquery_client.insert_rows_json(table_ref, rows_to_insert)

    if errors == []:
        return f"successfully uploaded embeddings for {entity_name} to BigQuery", 200
    else:
        return f"errors occurred while uploading embeddings for {entity_name}: {errors}", 500