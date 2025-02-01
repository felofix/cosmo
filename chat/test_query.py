import requests
import json
import re

def format_response(response_text, docs):
    # Split into sentences (looking for [DOC: pattern)
    parts = re.split(r'(\[DOC:[^\]]+\])', response_text)
    formatted_text = ""
    
    for i in range(0, len(parts)-1, 2):
        sentence = parts[i]
        doc_refs = parts[i+1] if i+1 < len(parts) else ""
        
        # Get the doc numbers
        doc_ids = re.findall(r'DOC:\d+', doc_refs)
        
        # Format sources
        sources = "\nSources:"
        for doc_id in doc_ids:
            if doc_id in docs:
                doc = docs[doc_id]
                sources += f"\n{doc_id}:"
                sources += f"\n  Content: {doc['content']}"
                sources += f"\n  URL: {doc['url']}"
        
        # Add formatted sentence
        formatted_text += f"\033[96m{sentence}\033[0m{sources}\n\n"
    
    # Add any remaining text without sources
    if len(parts) % 2 == 1:
        formatted_text += parts[-1]
    
    return formatted_text

def query_endpoint(message):
    try:
        response = requests.post(
            'http://localhost:8888/query/',
            json={'query': message, 'k': 10, 'rerank': True}
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'response' in data and 'docs' in data:
                print("\nFormatted Response:")
                print("=" * 80)
                print(format_response(data['response'], data['docs']))
                print("=" * 80)
            else:
                print("Error: Invalid response format")
        else:
            print(f"Error: Status code {response.status_code}")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    while True:
        message = input("\nEnter your message (or 'q' to quit): ")
        if message.lower() == 'q':
            break
        query_endpoint(message)
