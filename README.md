June 20th, 2024 update:
Added tessel4.py module, web_interface2_app.py for flask server interface and index.html for user interface. No testing yet but all the code looks good.

The idea behind this code and text is to find a decent way to explore and volumize a concept space from a single or few concepts
which are arranged as axis or linear relationships and then either perpendicular and/or supernominal concepts are establsihed in 
a graph network around these seed cencepts. Once a primary (depth-of-n) graph is created I want to add a visual interface that would allow
the selection of distant graph nodes so that the concept space between them could be spanned by an interpolation process and the intervening
encoding/embedded spaces could be extracted by reverse token look-up.

I would also like to either replace or augment the LLM by turning each concept subject heading into an embedding so that exactly geometric relationships 
could be established if possible.
![
IMG_20240319_170422.jpg contains the original middle-of-the-night post-dream scribble that inspired this design of intention.Alt text](IMG_20240319_170422.jpg)


Currently uses the OpenAI API and LM Studio for access to free local models ensuring your privacy.

reuires pip install OpenAI but I'm making plans to adopt Groq, OpenAI API and/or GPT4ALL for various reasons and adaptibility.
