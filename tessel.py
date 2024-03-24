# Imports
import collections
from collections import deque
import networkx as nx
import openai  # Assuming you have OpenAI API integration set up

# Define variables to store concepts and the LLM API endpoint
concepts = set()  # Set to store unique concepts encountered

# Function to query the LLM for related concepts (using OpenAI API)
openai.api_key = "none"
openai.api_base = "http://localhost:1234/v1"
#client = openai(base_url="http://localhost:1234/v1", api_key="not-needed")
def prompt_lm(prompt):
    print("inside")
    completion =     response = openai.ChatCompletion.create(model="local_model", 
      messages=[
        {"role": "system", "content": "Employ concepts as poles on an axis to find their perpendicular partners in a tessellating graph function for exploring concept spaces."},
        {"role": "user", "content": prompt}
      ],
      temperature=0.17,
      )
    print(completion)

    return [choice.text.strip() for choice in completion.choices]

# Function to build the concept space graph
def build_concept_graph(concept1, concept2):
  # Initialize an empty graph using NetworkX
  graph = nx.Graph()

  # Add seed concepts as nodes to the graph
  graph.add_node(concept1)
  graph.add_node(concept2)

  # Create a queue to manage exploration (FIFO)
  queue = deque([concept1, concept2])

  # Iterate while there are concepts in the queue
  while queue:
    current_concept = queue.popleft()
    concepts.add(current_concept)  # Add to set of encountered concepts

    # Query LLM for related concepts perpendicular to the current axis
    related_concepts_list = prompt_lm(f"Considering concepts '{concept1}' and '{concept2}' as opposing poles, what concepts are most perpendicular to this axis?")

    # Add retrieved concepts as nodes to the graph
    for related_concept in related_concepts_list:
      if related_concept not in graph.nodes:
        graph.add_node(related_concept)
      # Add edges between current concept and retrieved concepts
      graph.add_edge(current_concept, related_concept)

    # Add the retrieved concepts back to the queue for further exploration
    queue.extend(related_concepts_list)

  return graph

# Main program flow
if __name__ == "__main__":
  # Specify your seed concepts
  concept1 = "Cat"
  concept2 = "Dog"

  concept_graph = build_concept_graph(concept1, concept2)

  # Analyze or visualize the concept graph (using NetworkX or other libraries)
  # ...
# "Considering concepts '{concept1}' and '{concept2}' as opposing poles, what concepts are even more extreme versions of '{concept1}' along this axis?"


