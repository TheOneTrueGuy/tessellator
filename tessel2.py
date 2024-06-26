#this code doesn't work, generated by Claude and Gemini


from collections import deque
import networkx as nx
import openai


# Set up OpenAI API key
openai.api_key = "none"
openai.api_base = "http://localhost:1234/v1"
#client = openai(base_url="http://localhost:1234/v1", api_key="not-needed")
def prompt_lm(prompt):
    print("inside")
    completion =     response = openai.ChatCompletion.create(model="local_model", 
      messages=[
        {"role": "system", "content": "Employ concepts as poles on an axis to find their perpendicular partners in a tessellating graph function for exploring concept spaces. reply concisely with as few words as possible."},
        {"role": "user", "content": prompt}
      ],
      temperature=0.17,
      )
    print(completion)

    return [choice.text.strip() for choice in completion.choices]



from collections import deque
import networkx as nx
import openai  # Assuming you have OpenAI API integration set up

# Function to represent a concept with optional depth information
class SubjectEntry:
  def __init__(self, subject, depth=0):
    self.subject = subject
    self.depth = depth

def explore_concept_space(initial_subject, opposite_subject, max_depth=2):
  """
  Explore concept space using recursion and LLM.

  Args:
    initial_subject: The starting concept.
    opposite_subject: The concept on the opposite axis.
    max_depth: Maximum exploration depth (default: 2).

  Returns:
    A NetworkX graph representing the explored concept space.
  """  
  graph = nx.Graph()

  # Add seed concepts as nodes
  graph.add_node(initial_subject)
  graph.add_node(opposite_subject)
  graph.add_edge(initial_subject, opposite_subject)

  # Create a queue for depth-first exploration
  queue = deque([SubjectEntry(initial_subject), SubjectEntry(opposite_subject)])

  while queue:
    current_entry = queue.popleft()

    # Stop exploring if max depth reached
    if current_entry.depth >= max_depth:
      continue

    # Construct prompt based on current concept (avoid unpacking tuples)
    prompt = f"Suggest ideas that are perpendicular to the axis formed by '{current_entry.subject}'"

    # Use LLM function to find related concepts
    related_concepts = prompt_lm(prompt)

    # Add retrieved concepts as nodes and edges
    for new_subject in related_concepts:
      if new_subject not in graph.nodes:
        graph.add_node(new_subject)
      graph.add_edge(current_entry.subject, new_subject)

      # Recursively explore deeper for valid concepts
      queue.append(SubjectEntry(new_subject, current_entry.depth + 1))

  return graph

# Example usage
graph = explore_concept_space("Cat", "Dog", max_depth=4)

# Analyze or visualize the graph using NetworkX
# ...
