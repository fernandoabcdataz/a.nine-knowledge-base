import json
from main import upload_knowledge_base

class MockRequest:
    def __init__(self, json_data):
        self.json_data = json_data

    def get_json(self):
        return self.json_data

# Simulate the HTTP request
test_request = MockRequest({
    "bucket": "abcdataz-kb",
    "name": "xero_payments.yaml"
})

# Call the function
result, status_code = upload_knowledge_base(test_request)

# Print the result
print(f"Status Code: {status_code}")
print(json.dumps(result, indent=2))