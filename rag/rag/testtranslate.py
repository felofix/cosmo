import requests
import pprint
import sys

if len(sys.argv) > 1:
   question = ' '.join(sys.argv[1:])
else:
   question = "What is the capital of France?"

documents = [
   "La France a pour capitale Paris.",
   "Le pays est connu pour sa culture et sa cuisine.",
   "Parijs is niet in Spanje",
   "Paris is teh capital."
]

body = {"question": question, "documents": documents}
endpoint = "http://localhost:8888/translate"
print("Query:", body, "to", endpoint)

response = requests.post(endpoint, json=body)
assert response.status_code == 200

data = response.json()
print("Response: ", end="")
pprint.pprint(data)

assert "translations" in data
assert len(data["translations"]) == len(documents)

for translation in data["translations"]:
   assert "translation" in translation
   assert "from_lang" in translation
   assert "to_lang" in translation

