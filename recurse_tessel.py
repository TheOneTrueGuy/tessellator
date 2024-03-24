import collections
from collections import deque
import networkx as nx
import openai

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

# Recursive function to build the concept graph
def build_concept_graph(concept1, concept2, depth=0, max_depth=3):
    # Initialize an empty graph using NetworkX
    graph = nx.Graph()

    # Add seed concepts as nodes to the graph
    graph.add_node(concept1)
    graph.add_node(concept2)

    # Base case: if maximum depth is reached, return the graph
    if depth >= max_depth:
        return graph

    # Query LLM for related concepts perpendicular to the current axis
    #related_concepts_list = prompt_lm(f"Considering concepts '{concept1}' and '{concept2}' as opposing poles, what concepts are most perpendicular to this axis?")
    related_concepts_list = prompt_lm(f"Considering concepts '{concept1}' and '{concept2}' as points some distance apart on a line, what concepts are most perpendicular to this line? Answer concisely with a subject heading title sentence for each subject on its own line in a list.")

    # Add retrieved concepts as nodes to the graph
    for related_concept in related_concepts_list:
        if related_concept not in graph.nodes:
            graph.add_node(related_concept)

        # Add edges between current concepts and retrieved concepts
        graph.add_edge(concept1, related_concept)
        graph.add_edge(concept2, related_concept)

        # Recursively call the function with the new perpendicular concept
        child_graph = build_concept_graph(concept1, related_concept, depth=depth+1, max_depth=max_depth)
        child_graph = build_concept_graph(concept2, related_concept, depth=depth+1, max_depth=max_depth)

        # Merge the child graphs into the main graph
        graph = nx.compose(graph, child_graph)

    return graph

# Main program flow
if __name__ == "__main__":
    # Specify your seed concepts
    concept1 = "Cat"
    concept2 = "Dog"

    # Set the maximum depth for the recursive exploration
    max_depth = 3

    concept_graph = build_concept_graph(concept1, concept2, max_depth=max_depth)

    # Analyze or visualize the concept graph (using NetworkX or other libraries)
    # ...