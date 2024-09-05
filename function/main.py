import os
from google.cloud import storage, bigquery
from langchain.llms import Anthropic
from langchain.embeddings import AnthropicEmbeddings  # Add this import
from langchain.text_splitter import RecursiveCharacterTextSplitter
import functions_framework
import yaml

# initialize clients
storage_client = storage.Client()
bigquery_client = bigquery.Client()

# initialize anthropic api key
anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")

# initialize anthropic llm
llm = Anthropic(model="claude-2.1", api_key=anthropic_api_key)  # specify the model

# initialize anthropic embeddings
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

@functions_framework.cloud_event
def upload_knowledge_base(cloud_event):
    # get bucket and file information from the event
    bucket_name = cloud_event.data["bucket"]
    file_name = cloud_event.data["name"]

    # process only yaml files
    if not file_name.endswith('.yaml'):
        print(f"Skipping non-YAML file: {file_name}")
        return

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
        print(f"Successfully uploaded embeddings for {entity_name} to BigQuery")
    else:
        print(f"Errors occurred while uploading embeddings for {entity_name}: {errors}")

if __name__ == "__main__":
    # for local testing
    class MockCloudEvent:
        def __init__(self, bucket, name):
            self.data = {"bucket": bucket, "name": name}

    mock_event = MockCloudEvent("abcdataz_knowledge_base", "example.yaml")
    upload_knowledge_base(mock_event)