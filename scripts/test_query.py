"""
Interactive CLI for testing retrieval.
"""
import sys
from pathlib import Path
import logging

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.retrieval.retriever import retrieve, assemble_context

def main():
    logging.basicConfig(level=logging.ERROR) # Only show errors to keep CLI clean
    
    print("Mutual Fund Retrieval Test CLI")
    print("Type 'exit' or 'quit' to stop.\n")
    
    while True:
        try:
            query = input("\nEnter query: ")
            if query.lower() in ['exit', 'quit']:
                break
                
            if not query.strip():
                continue
                
            print("\nRetrieving...")
            chunks = retrieve(query)
            print(f"\nFound {len(chunks)} relevant chunks.")
            
            if chunks:
                print("\n--- Assembled Context ---\n")
                print(assemble_context(chunks))
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            
if __name__ == "__main__":
    main()
