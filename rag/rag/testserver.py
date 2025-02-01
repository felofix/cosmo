import requests, pprint
import sys

if len(sys.argv) > 1:
   query = ' '.join(sys.argv[1:]) 
else:
   query = "hoe vraag ik asiel aan"

body = {"query": query}
endpoint = "http://localhost:8888/query/"
print("Query:", body, "to", endpoint)
response = requests.post(endpoint, json=body)
rjson = response.json()
assert response.status_code == 200

print("Response: ",end="")
pprint.pprint(rjson)
