from dotenv import load_dotenv
import os
from google.cloud import storage, secretmanager
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
import functions_framework
import yaml

# initialize clients
storage_client = storage.Client()
# secret_client = secretmanager.SecretManagerServiceClient()

load_dotenv(dotenv_path='../.env')

# get anthropic api key from secret manager
project_id = os.environ.get("GCP_PROJECT")
# secret_name = f"projects/{project_id}/secrets/openai-api-key/versions/latest"
# response = secret_client.access_secret_version(request={"name": secret_name})
openai_api_key = os.environ.get("OPENAI_API_KEY")

# initialize anthropic llm and embeddings
embeddings = OpenAIEmbeddings(model="text-embedding-3-large", api_key=openai_api_key)

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

    # prepare rows for insertion (we'll return this instead of inserting)
    rows_to_insert = [
        {
            "entity": entity_name,
            "chunk_id": f"{entity_name}_{i}",
            "text_chunk": chunk,
            "embedding": embedding[:5]  # only return first 5 values of embedding for brevity
        }
        for i, (chunk, embedding) in enumerate(zip(texts, embedded_texts))
    ]

    return {"message": f"Processed {entity_name}", "data": rows_to_insert}, 200