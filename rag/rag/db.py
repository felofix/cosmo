import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import glob
import torch
from collections import defaultdict
import cohere
import pickle

def _get_paragraphs(content, min_length=100):
    paragraphs = [para.strip() for para in content.split("\n\n") if len(para.strip()) >= min_length]
    return paragraphs


class Document:
    def __init__(self, url, chunks):
        self.url = url
        self.chunks = chunks

    def __repr__(self):
        return f"<Document: {len(self.chunks)} chunks from {self.url!r}>"

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, other):
        return self.url == other.url


class RagDatabase:
    def __init__(self, model="intfloat/multilingual-e5-large"):
        self.model = model
        self.st = SentenceTransformer(model)
        self.documents = []
        self.embeddings = None
        self.index = []

    def ingest(self, data_dir):
        self.documents = []
        for filename in glob.glob(os.path.join(data_dir, "**", "*.md")):
            with open(filename, "r", encoding="utf-8") as file:
                url = next(file).strip()
                doc = Document(url, _get_paragraphs(file.read()))
                self.documents.append(doc)
                print(f"Ingested {doc}")

    def ingest_json(self, json_path):
        by_url = defaultdict(list)
        with open(json_path) as f:
            chunks = json.load(f)
            for chunk in chunks:
                by_url[chunk["url"]].append(f"{chunk['content']}: {chunk['content']}")
        self.documents = [Document(url=url, chunks=chunks) for url, chunks in by_url.items()]

    def encode(self):
        chunks = []
        self.index = []
        for i, document in enumerate(self.documents):
            for j, chunk in enumerate(document.chunks):
                chunks.append(f"passage: {chunk}")
                self.index.append((i, j))
        self.embeddings = self.st.encode(chunks, normalize_embeddings=True, show_progress_bar=True)
        print(f"Encoded {len(self.documents)} docs, {len(chunks)} chunks -> {self.embeddings.shape} embeddings")

    def query(self, query, k=10):
        if self.embeddings is None:
            raise ValueError("Not initialized")
        encoded_query = self.st.encode(f"query: {query}", normalize=True)
        print(f"Running query {query!r}")
        similarity_scores = self.st.similarity(self.embeddings, encoded_query).squeeze()
        scores, indices = torch.topk(similarity_scores, k=min(k,len(similarity_scores)))

        chunks = []
        for i in indices:
            di, ci = self.index[i]
            doc = self.documents[di]
            chunks.append((self.documents[di], self.documents[di].chunks[ci]))
        return chunks

def rerank(question, sources, k):
    co = cohere.ClientV2()
    docs = [c for d, c in sources]

    response = co.rerank(
        model="rerank-v3.5",
        query=question,
        documents=docs,
        top_n=k,
    )
    ixs = [r.index for r in response.results]
    print("Rerank selected indices", ixs)
    return [sources[r.index] for r in response.results]


def make_db():
    db = RagDatabase()
    # db.ingest("../crawler/nordic-crawler/")
    #db.ingest_json("../crawler/nordic-crawler/output/udi_pages_rag.json")
    db.ingest_json("/home/ubuntu/cosmo/crawler/nordic-crawler/output/nordic_all.json")
    db.encode()
    return db


DB_PATH = os.path.expanduser("~/rag_database.pkl")
def pickle_db(db, filename=DB_PATH):
    with open(filename, "wb") as f:
        pickle.dump(db, f)

def load_pickled_db(filename=DB_PATH):
    try:
        with open(os.path.expanduser(filename), "rb") as f:
            return pickle.load(f)
    except:
        print(f"Recreating db and saving to {filename}")
        db = make_db()
        pickle_db(db, filename)
        return db