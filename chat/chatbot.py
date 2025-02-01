import os
import json
import requests
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class QueryRequest(BaseModel):
    query: str
    k: int = 10
    rerank: bool = False

class NorwegianImmigrationAssistant:
    def __init__(self):
        """Initialize the Norwegian Immigration Assistant."""
        self.conversation_history = []
        self.query_url = "http://localhost:8888/query"
        
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content
        })

    def get_response(self) -> str:
        """Get a response based on the latest user message."""
        if not self.conversation_history:
            return "Hello! How can I help you with immigration to Norway?"

        # Get the last user message
        last_message = self.conversation_history[-1]["content"]
        
        try:
            # Query the local endpoint with just the last message
            response = requests.post(
                self.query_url,
                json=QueryRequest(
                    query=last_message,
                    k=10,
                    rerank=True
                ).dict()
            )
            
            if response.status_code == 200:
                data = response.json()
                if data["success"]:
                    return data["response"]
                else:
                    return "I apologize, but I couldn't process your request. Please try again."
            else:
                return "I encountered an error processing your request. Please try again."
                
        except Exception as e:
            print(f"Error getting response: {str(e)}")
            return "I apologize, but I'm having trouble connecting to my knowledge base. Please try again in a moment."

    def generate_roadmap(self) -> str:
        """Generate a roadmap based on the conversation history."""
        if not self.conversation_history:
            return "Please start a conversation first so I can provide relevant guidance."

        # Get the last user message
        last_message = self.conversation_history[-1]["content"]
        
        try:
            # Query the local endpoint for roadmap information with just the last query
            response = requests.post(
                self.query_url,
                json=QueryRequest(
                    query=f"What are the specific steps and requirements for: {last_message}",
                    k=10,
                    rerank=True
                ).dict()
            )
            
            if response.status_code != 200:
                raise Exception("Failed to get roadmap information")
                
            data = response.json()
            if not data["success"]:
                raise Exception("Query was not successful")
                
            # Extract relevant information from docs
            docs = data["docs"]
            
            # Format the roadmap sections
            sections = {
                "IMMEDIATE ACTIONS": [],
                "REQUIRED DOCUMENTS": [],
                "HELPFUL RESOURCES": [],
                "IMPORTANT DEADLINES": []
            }
            
            # Process each document
            for doc in docs.values():
                content = doc["content"]
                url = doc["url"]
                
                # Look for actions
                if any(word in content.lower() for word in ["must", "need to", "should", "can", "have to"]):
                    sections["IMMEDIATE ACTIONS"].append(f"- {content}")
                
                # Look for documents
                if any(word in content.lower() for word in ["document", "form", "card", "id", "passport"]):
                    sections["REQUIRED DOCUMENTS"].append(f"• {content}")
                
                # Add resource
                sections["HELPFUL RESOURCES"].append(f"• {url.replace('https://', '')}")
                
                # Look for deadlines
                if any(word in content.lower() for word in ["deadline", "within", "by", "before", "after"]):
                    sections["IMPORTANT DEADLINES"].append(f"• {content}")
            
            # Format the roadmap text
            roadmap = []
            for section, items in sections.items():
                if items:
                    roadmap.append(f"\n{section}:")
                    roadmap.extend(items)
            
            return "\n".join(roadmap)
                
        except Exception as e:
            print(f"Error generating roadmap: {str(e)}")
            return """IMMEDIATE ACTIONS:
• Contact appropriate authorities for guidance
• Review official documentation requirements

HELPFUL RESOURCES:
• udi.no/en
• norway.no/en"""

def main():
    """Main function to run the chatbot."""
    print("Norwegian Immigration Assistant")
    print("Type 'quit' to exit\n")
    
    chatbot = NorwegianImmigrationAssistant()
    
    try:
        while True:
            # Get user input
            user_input = input("\nYou: ").strip()
            if user_input.lower() == 'quit':
                break
                
            # Add user message and get response
            chatbot.add_message("user", user_input)
            response = chatbot.get_response()
            chatbot.add_message("assistant", response)
            
            # Print response
            print("\nAssistant:", response)
            
            roadmap = chatbot.generate_roadmap()
            print("\nRoadmap:")
            print(roadmap)

    except KeyboardInterrupt:
        print("\nGoodbye!")

if __name__ == "__main__":
    main()
