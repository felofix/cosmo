from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
from chatbot import NorwegianImmigrationAssistant
import re

app = Flask(__name__)
CORS(app)

# Initialize immigration assistant
assistant = NorwegianImmigrationAssistant()

@app.after_request
def add_header(response):
    """Add headers to prevent caching."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.route('/')
def home():
    return render_template('index.html')

def format_response_with_sources(response_text, docs):
    # Split into sentences (looking for [DOC: pattern)
    parts = re.split(r'(\[DOC:[^\]]+\])', response_text)
    formatted_text = ""
    
    # Track unique content/URL combinations
    seen_content = {}  # (content, url) -> first doc_id mapping
    unique_doc_ids = []  # preserve order of first appearance
    doc_id_mapping = {}  # mapping to find first doc_id for deduplication
    
    # First pass: collect unique docs by content and URL
    for i in range(0, len(parts)-1, 2):
        doc_refs = parts[i+1] if i+1 < len(parts) else ""
        doc_ids = re.findall(r'DOC:\d+', doc_refs)
        for doc_id in doc_ids:
            if doc_id in docs:
                doc = docs[doc_id]
                content = doc.get('content', '').strip()
                url = doc.get('url', '').strip()
                content_key = (content, url)
                
                if content_key not in seen_content:
                    seen_content[content_key] = doc_id
                    unique_doc_ids.append(doc_id)
                doc_id_mapping[doc_id] = seen_content[content_key]
    
    # Create citation mapping (DOC:X -> sequential number)
    citation_map = {doc_id: idx + 1 for idx, doc_id in enumerate(unique_doc_ids)}
    
    # Second pass: format text with sequential citations
    for i in range(0, len(parts)-1, 2):
        sentence = parts[i].strip()
        doc_refs = parts[i+1] if i+1 < len(parts) else ""
        
        # Get doc numbers and map to deduplicated citations
        doc_ids = list(dict.fromkeys(re.findall(r'DOC:\d+', doc_refs)))
        citations = set()  # use set to remove duplicates within the same citation block
        
        for doc_id in doc_ids:
            if doc_id in docs:
                # Use the first doc_id that had this content/URL combination
                deduplicated_doc_id = doc_id_mapping.get(doc_id)
                if deduplicated_doc_id in citation_map:
                    citations.add(str(citation_map[deduplicated_doc_id]))
        
        if citations:
            formatted_text += sentence + f" [{','.join(sorted(citations))}] "
        else:
            formatted_text += sentence + " "
    
    # Add any remaining text without sources
    if len(parts) % 2 == 1:
        formatted_text += parts[-1].strip()
    
    # Create final sources dict with sequential citation numbers
    final_sources = {}
    for doc_id in unique_doc_ids:
        citation_num = citation_map[doc_id]
        final_sources[f"DOC:{citation_num-1}"] = docs[doc_id]
    
    return formatted_text.strip(), final_sources

@app.route('/api/translate', methods=['POST'])
def translate():
    try:
        data = request.json
        response = requests.post('http://localhost:8888/translate', json=data)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        message = request.json.get('message', '')

        # Query the endpoint directly
        response = requests.post(
            'http://localhost:8888/query/',
            json={'query': message, 'k': 10, 'rerank': True}
        )
        
        if response.status_code == 200:
            data = response.json()
            # Make sure we have the expected fields
            if 'response' in data:
                # Format the response to remove [DOC:X] references and collect sources
                formatted_response, sources = format_response_with_sources(data['response'], data.get('docs', {}))
                return jsonify({
                    'success': True,
                    'response': formatted_response,
                    'docs': sources
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Invalid response format from query endpoint'
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to get response from query endpoint'
            }), 500
            
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/get-actions', methods=['POST'])
def get_actions():
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        # Create a new chatbot instance
        chatbot = NorwegianImmigrationAssistant()
        
        # Add user message and get response
        chatbot.add_message("user", message)
        chat_response = chatbot.get_response()
        chatbot.add_message("assistant", chat_response)
        
        # Generate roadmap based on conversation
        roadmap = chatbot.generate_roadmap()
        
        # Return both chat response and roadmap
        return jsonify({
            'response': chat_response,
            'roadmap': roadmap
        })
        
    except Exception as e:
        print(f"Error in get_actions: {str(e)}")
        return jsonify({
            'error': 'Failed to process request',
            'response': 'I apologize, but I encountered an error. Please try again.',
            'roadmap': """IMMEDIATE ACTIONS:
1. Contact Forbrukerrådet (Norwegian Consumer Authority)
   - Call 23 400 500 for urgent guidance
   - Opening hours: Mon-Fri, 9:00-15:00

REQUIRED DOCUMENTS:
• Lease Agreement
• Any communication with landlord

HELPFUL RESOURCES:
• Forbrukerrådet
  Website: forbrukerradet.no/housing
  Phone: 23 400 500"""
        }), 500

@app.route('/api/mark-substep-done', methods=['POST'])
def mark_substep_done():
    try:
        data = request.json
        step_id = data.get('stepId')
        substep_id = data.get('substepId')
        if step_id is None or substep_id is None:
            return jsonify({'error': 'Step ID and Substep ID are required'}), 400

        # Create new assistant instance
        assistant = NorwegianImmigrationAssistant()
        assistant.mark_substep_done(step_id, substep_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-source', methods=['POST'])
def get_source():
    try:
        data = request.get_json()
        doc_ids = data.get('docIds', [])

        # Get response data from the query endpoint
        response = requests.post(
            'http://localhost:8888/query/',
            json={'query': ' '.join(doc_ids)}  # Use doc IDs as query to get their content
        )

        if response.status_code == 200:
            query_data = response.json()
            return jsonify({
                'success': True,
                'sources': query_data.get('docs', {})
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch source content'
            })

    except Exception as e:
        print(f"Error getting source content: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    app.run(debug=True)
