from gemini import ask_gemini
from getImage import getImage

def getSubideas(concept):
    import json
    import re
    
    prompt = f"""
You are an AI that functions as a topic deconstruction tool and image brief generator. Your job is to analyze a given topic and extract 5-10 primary, enumerable subjects directly mentioned or implied by the title, and for each subject provide a concise image search query and goal.

The topic is:
{concept}

YOUR TASK
Return a list of 5-10 core subjects. For each subject, include:
- subject: the subject's name only (no extra words)
- imageSearch: a Google Images–ready query that would surface a representative photo
- goal: one short sentence describing what the image should convey

CRITICAL INSTRUCTIONS
1) Extract, don't brainstorm: Do NOT add related ideas, background, subtopics, or history. Only the items that make up the core subject set.
2) Target 5-10 subjects: Aim for 5-10 subjects total.
3) Preserve order: Keep the natural/canonical or stated order from the title when applicable.
4) Output format: Return a single JSON array of objects. No markdown, no trailing commentary.
5) Subject names: Plain strings only, correctly capitalized; no descriptors, dates, or parentheticals.
6) Focus on concrete objects/things: Extract actual physical objects, places, devices, weapons, vehicles, or tangible entities - NOT abstract concepts, ideas, or processes.
7) imageSearch rules:
   - Include the subject name plus 2–6 neutral descriptors that bias toward real, high-quality photos.
   - Prefer generic terms like photo, scene, landscape, museum, artifact, interior, exterior (where relevant).
   - Use simple tokens only (no quotes or punctuation). Add useful negatives to avoid junk:
     -logo -meme -clipart -infographic -diagram -text
   - Do NOT introduce new entities or time periods not inherent to the subject.
8) goal rules:
   - One clear sentence (8–20 words), imperative voice ("Show …", "Convey …").
   - Describe composition or vibe, not new facts or history.
   - Avoid proper nouns unless inherent to the subject.
9) Try your hardest to use 1-2 words for each subject, you can use acronyms if you need to.

OUTPUT SCHEMA (strict)
[
  {{
    "subject": "String",
    "imageSearch": "String",
    "goal": "String"
  }},
  ...
]

EXAMPLE INPUT
Explaining the four seasons

EXAMPLE OUTPUT
[
  {{
    "subject": "Spring",
    "imageSearch": "Spring photo blooming trees park -logo -meme -clipart -infographic -diagram -text",
    "goal": "Show fresh growth and blossoms to convey renewal and mild weather."
  }},
  {{
    "subject": "Summer",
    "imageSearch": "Summer photo beach sunshine people outdoors -logo -meme -clipart -infographic -diagram -text",
    "goal": "Show bright sun and outdoor activity to convey heat and long days."
  }},
  {{
    "subject": "Autumn",
    "imageSearch": "Autumn photo forest foliage orange red leaves -logo -meme -clipart -infographic -diagram -text",
    "goal": "Show colorful falling leaves to convey cooling weather and harvest time."
  }},
  {{
    "subject": "Winter",
    "imageSearch": "Winter photo snow landscape trees overcast -logo -meme -clipart -infographic -diagram -text",
    "goal": "Show snow and bare trees to convey cold, stillness, and dormancy."
  }}
]"""
    
    response = ask_gemini(prompt, model="gemini-2.5-pro")
    
    # Parse the response flexibly - look for JSON in markdown blocks or plain text
    parsed_data = None
    json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
    if json_match:
        try:
            parsed_data = json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON array in the response without markdown
    if not parsed_data:
        json_match = re.search(r'(\[.*?\])', response, re.DOTALL)
        if json_match:
            try:
                parsed_data = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
    
    # If no JSON found, raise an error
    if not parsed_data:
        raise ValueError(f"Could not parse JSON from response: {response}")
    
    # Now fetch images for each subject and return simplified array
    results = []
    for item in parsed_data:
        image_path = getImage(item["imageSearch"], item["goal"])
        results.append({
            "subject": item["subject"],
            "image": image_path
        })
    
    return results
