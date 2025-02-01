from rag.db import make_db, rerank, pickle_db, load_pickled_db
from rag.query import query_with_context
import pprint

def query_loop():
#    db = make_db()
#    pickle_db(db)
    db =  load_pickled_db()

    query = "hoe vraag ik asiel aan"
    do_rerank = True
    while True:
        sources = db.query(query, k=100)
        if do_rerank:
            sources = rerank(query, sources, k=10)

        response = query_with_context(query, sources)
        pprint.pprint(response)

        query = input("\nQuery? ")
        if query.lower() == "exit":
            break


query_loop()
