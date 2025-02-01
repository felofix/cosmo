import os
from openai import OpenAI
import re
import json

SYSTEM_PROMPT = """
You are an expert assistant tasked with answering questions accurately using only the provided context.
Your answers must clearly indicate which sources from the context support each part of the response. Follow these guidelines:

1. Use only the information from the provided context with their corresponding IDs. Do not rely on prior knowledge.
2. After each sentence in your answer that uses information from the context, append the relevant source ID(s) in square brackets, e.g., [DOC:1], [DOC:2,DOC:3].
3. Always answer in the language of the query, translating content from context where required.
4. NEVER cite all sources to show information is not present in any source, any cited sources should DIRECTLY help answer the user's question.
5. NEVER refer to your "context" or "sources", or to the original language of documents. Directly provide the relevant information only.
6. If the context contains no relevant information, output [FAILED] followed by a message to the user in their language, without sources.
"""

SYSTEM_PROMPT = """
You are an expert assistant tasked with answering questions accurately using only the provided context. Follow these guidelines:

1. Context-Only Responses: Use only the information from the provided context with their corresponding IDs. Do not use any prior knowledge or make assumptions.
2. Source Citation: After each sentence that uses information from the context, append the relevant source ID(s) in square brackets, e.g., [DOC:1], [DOC:2, DOC:3].
3. Language Consistency: Always answer in the language of the query, translating content from context where required.
4. Selective Citation: Cite only the specific source IDs that directly support your answer. Do not cite sources that do not contribute to the response. If no relevant information is found, do not cite any sources.
5. No Irrelevant Sources: NEVER cite all provided sources to indicate missing information. If no relevant information is found, respond with [FAILED] followed by a brief message in the user's language indicating that the requested information is not available.
6. Professional Tone: Provide clear, accurate, and concise responses without referring to the context, sources, or their original language.
"""


def create_client():
    return OpenAI(
        base_url="https://api.studio.nebius.ai/v1/",
        api_key=os.environ.get("NEBIUS_KEY"),
    )

def translate_query(question, document):
    client = create_client()
    translation_prompt = (
        f"Translate the following document to the language of the question and return the result in JSON format.\n\n"
        f"Question: {question}\n\n"
        f"Document: {document}\n\n"
        f"Output format: {{\"translation\": <translated_text>, \"from_lang\": <source_language>, \"to_lang\": <target_language>}}\n"
        "Do not output anything other than the JSON. If the document is already in the right language, do not change it, and return 'to_lang' equal to 'from_lang'."
    )
    
    completion = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct",
        messages=[{"role": "user", "content": translation_prompt}],
    )
    
    response = completion.choices[0].message.content
    try:
        result = json.loads(response)  # Assuming the response is a valid JSON string
    except Exception as e:
        print(f"Could not parse json {response!r}: {e}")
        result =  {"from_lang": "?", "to_lang": "?", "translation": "<translation failed>"}
    result['document'] = document
    return result

def query_with_context(question, sources, temperature=0.3):
    client = create_client()
    user_prompt = "# Context:\n"

    docs_by_tag = {}
    for i, (doc, chunk) in enumerate(sources):
        content = chunk.replace("\n", " ")
        tag = f"DOC:{i}"
        user_prompt += f"- [{tag}] {content}\n"
        docs_by_tag[tag] = dict(url=doc.url, content=content)
    user_prompt += f"\nUser Question: {question}"

    print(f"Sending prompt with question {question!r} and {len(sources)} sources")
    completion = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
        temperature=temperature,
    )
    response = completion.choices[0].message.content
    print(f"Response: {response!r}")

    parsed_response = parse_response(response)
    parsed_response['docs'] = {k: v for k,v in docs_by_tag.items() if k in parsed_response['tags']}
    return parsed_response


def parse_response(response):
    tags = []
    success = True

    if "[FAILED]" in response:
        success = False
        response = response.replace("[FAILED]", "").strip()

    tags = set(extract_tags(response))

    return {"success": success, "response": response, "tags": tags}

def extract_tags(response):
    return re.findall(r'DOC:\d+', response)
