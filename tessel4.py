import networkx as nx
from openai import OpenAI
import json
from pyvis.network import Network

# OpenAI client setup
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

def prompt_lm(prompt):
    try:
        completion = client.chat.completions.create(
            model="local_model",
            messages=[
                {"role": "system", "content": "Employ concepts as poles on an axis to find their perpendicular partners in a tessellating graph function for exploring concept spaces."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.17,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Error in LLM query: {e}")
        return "[]"

def parse_concepts(response):
    try:
        # First, try to parse as JSON
        concepts = json.loads(response)
        if isinstance(concepts, list):
            return concepts
        elif isinstance(concepts, dict) and "perpendicular_concepts" in concepts:
            return concepts["perpendicular_concepts"]
    except json.JSONDecodeError:
        # If not JSON, treat as a list of concepts separated by newlines
        return [concept.strip() for concept in response.split("\n") if concept.strip()]

def build_concept_graph(concept1, concept2, depth=0, max_depth=3, graph=None):
    if graph is None:
        graph = nx.Graph()
    
    graph.add_node(concept1)
    graph.add_node(concept2)
    graph.add_edge(concept1, concept2)

    if depth >= max_depth:
        return graph

    prompt = f"Considering concepts '{concept1}' and '{concept2}' as points on a line, what concepts are most perpendicular to this line? Provide a concise list of 2-4 concepts."
    response = prompt_lm(prompt)
    related_concepts = parse_concepts(response)

    for related_concept in related_concepts:
        if related_concept not in graph.nodes:
            graph.add_node(related_concept)
            graph.add_edge(concept1, related_concept)
            graph.add_edge(concept2, related_concept)

            # Recursively explore new axes
            build_concept_graph(concept1, related_concept, depth=depth+1, max_depth=max_depth, graph=graph)
            build_concept_graph(concept2, related_concept, depth=depth+1, max_depth=max_depth, graph=graph)

    return graph

def visualize_concept_graph(concept_graph):
    net = Network(notebook=True, height='750px', width='100%', bgcolor='#222222', font_color='white')
    net.from_nx(concept_graph)
    net.show('concept_graph.html')

if __name__ == "__main__":
    concept1 = "Artificial Intelligence"
    concept2 = "Natural Intelligence"
    max_depth = 3

    concept_graph = build_concept_graph(concept1, concept2, max_depth=max_depth)
    visualize_concept_graph(concept_graph)

    # Optional: Save graph data
    nx.write_gexf(concept_graph, "concept_graph.gexf")