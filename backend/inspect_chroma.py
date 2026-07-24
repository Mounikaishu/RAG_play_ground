import sys
sys.path.insert(0, 'backend')
from knowledge_base.collections import get_collection

collection = get_collection("student_resumes")
print(f"Collection count: {collection.count()}")
all_docs = collection.get(include=["metadatas", "documents"])
print(f"Retrieved {len(all_docs.get('ids', []))} IDs.")
for i in range(min(5, len(all_docs.get('ids', [])))):
    doc_id = all_docs['ids'][i]
    meta = all_docs['metadatas'][i]
    doc = all_docs['documents'][i]
    print(f"Doc ID: {doc_id}")
    print(f"  Metadata: {meta}")
    print(f"  Content Preview: {doc[:100]}...\n")
