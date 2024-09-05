# AI Assistant Knowledge Base

This project sets up a knowledge base for an AI assistant using Google Cloud Platform (GCP) services. It includes a Cloud Function that processes YAML files stored in Cloud Storage, generates embeddings using the Anthropic API, and stores the results in BigQuery.

## Project Structure

```
A.NINE-KNOWLEDGE-BASE/
├── function/
│   ├── main.py
│   └── requirements.txt
├── knowledge-base/
│   └── xero_payments.yaml
├── terraform/
│   ├── main.tf
│   ├── terraform.tfvars
│   └── variables.tf
└── .gitignore
```

## Setup

1. Ensure you have the following prerequisites:
   - Google Cloud Platform account
   - Terraform installed
   - gcloud CLI installed and configured

2. Clone this repository and navigate to the project directory.

3. Set up your GCP project and enable the necessary APIs:
   - Cloud Functions API
   - Cloud Build API
   - Secret Manager API
   - BigQuery API
   - Cloud Storage API

4. Create a service account with the necessary permissions and download the JSON key.

5. Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to the path of your service account key:
   ```
   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
   ```

6. Update the `terraform.tfvars` file with your project-specific values.

7. Initialize Terraform and apply the configuration:
   ```
   cd terraform
   terraform init
   terraform apply
   ```

8. After the Terraform apply completes successfully, the Cloud Function will be deployed and ready to use.

## Usage

The Cloud Function is triggered by HTTP requests. To process a YAML file:

1. Upload a YAML file to the created Cloud Storage bucket.
2. Send an HTTP POST request to the Cloud Function URL with the following JSON payload:
   ```json
   {
     "bucket": "your-bucket-name",
     "name": "your-file-name.yaml"
   }
   ```

The function will process the YAML file, generate embeddings, and store the results in BigQuery.

## Maintenance

- To update the Cloud Function code, modify the files in the `function/` directory and re-run `terraform apply`.
- To add new YAML files to the knowledge base, upload them to the Cloud Storage bucket and trigger the Cloud Function.
- Monitor the Cloud Function logs and BigQuery table for any issues or unexpected results.

## Security Considerations

- The Anthropic API key is stored in Secret Manager. Ensure that access to this secret is tightly controlled.
- The Cloud Function is publicly accessible. Consider implementing authentication if needed.
- Review and adjust the IAM permissions regularly to ensure least privilege access.