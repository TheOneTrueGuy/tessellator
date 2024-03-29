import collections
from collections import deque
import networkx as nx
import openai
import json

concepts = set()  # Set to store unique concepts encountered

client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

def prompt_lm(prompt):
    print("inside")
    completion = client.chat.completions.create(model="local_model", 
        model="local_model",
        messages=[
            {"role": "system", "content": "Employ concepts as poles on an axis to find their perpendicular partners in a tessellating graph function for exploring concept spaces. Return results in json format."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.17,
    )
    return completion.choices[0].message.content

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
    prompt = f"Considering concepts '{concept1}' and '{concept2}' as opposing poles, what concepts are most perpendicular to this axis? reply as concisely as possible in json format."
    response_json = prompt_lm(prompt)
    response_data = json.loads(response_json)

    # Extract the perpendicular concepts from the JSON response
    related_concepts_list = response_data.get("perpendicular_concepts", [])

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