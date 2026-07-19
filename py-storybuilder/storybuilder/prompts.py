WRITE_PARAGRAPH_SYSTEM = """You are a function that produces JSON containing the next paragraph of a novel.
Output ONLY a valid JSON object. No commentary, no markdown fences.
The JSON must match this exact schema:
{
  "paragraph_content": "<string>",
  "ending_suggested": <boolean>,
  "ending_reason": "<string or null>"
}
Set ending_suggested to true only if this paragraph brings the story to a natural
close given its arc so far. Otherwise false, with ending_reason null."""

WRITE_PARAGRAPH_USER = """<story_title>{title}</story_title>
<story_style>{style}</story_style>
<story_synopsis>{synopsis}</story_synopsis>
<world_facts>{world_facts}</world_facts>
<constraints>{constraints}</constraints>
<timeline_summary>{timeline_summary}</timeline_summary>
<current_chapter>{current_chapter}</current_chapter>
<previous_paragraphs>{previous_paragraphs}</previous_paragraphs>
<current_location>{current_location}</current_location>
<characters>{characters}</characters>

Write the next paragraph (max {max_words} words). Only use information provided
above. Write in the given style. Insert a line break before dialogue the first time
a character speaks. Do not contradict the timeline summary. Do not reference other
timelines unless explicitly mentioned above."""


DETECT_CHARACTERS_SYSTEM = """You are a function that identifies character names in a paragraph.
Output ONLY a valid JSON object. No commentary, no markdown fences.
The JSON must match this exact schema:
{ "characters": [ { "name": "<string>", "is_new": <boolean> } ] }
is_new is true only if the name is not present in <known_characters>."""

DETECT_CHARACTERS_USER = """<known_characters>{known_characters}</known_characters>
<paragraph>{paragraph}</paragraph>

Identify every character mentioned or present in the paragraph."""


DETECT_CHARACTER_ATTRIBUTES_SYSTEM = """You are a function that detects NEW character descriptions not already present.
Output ONLY a valid JSON object. No commentary, no markdown fences.
The JSON must match this exact schema:
{
  "characters": [{
    "name": "<string>",
    "is_new": <boolean>,
    "descriptions": [{
      "description_type": "Appearance|Goals|History|Aliases|Facts",
      "description": "<string>"
    }]
  }]
}
Rules:
- Only output characters present in <candidate_characters>.
- For a character with is_new=false, only output descriptions NOT already present
  in <existing_facts> for that character.
- For a character with is_new=true, output a full proposed profile instead of a diff.
- Output each character at most once."""

DETECT_CHARACTER_ATTRIBUTES_USER = """<paragraph>{paragraph}</paragraph>
<candidate_characters>{candidate_characters}</candidate_characters>
<existing_facts>{existing_facts}</existing_facts>

Identify new descriptions for the candidate characters that appear in the paragraph."""


DETECT_LOCATIONS_SYSTEM = """You are a function that identifies location names in a paragraph.
Output ONLY a valid JSON object. No commentary, no markdown fences.
The JSON must match this exact schema:
{ "locations": [ { "name": "<string>", "is_new": <boolean> } ] }
is_new is true only if the name is not present in <known_locations>."""

DETECT_LOCATIONS_USER = """<known_locations>{known_locations}</known_locations>
<paragraph>{paragraph}</paragraph>

Identify every location mentioned or present in the paragraph."""


DETECT_LOCATION_ATTRIBUTES_SYSTEM = """You are a function that detects NEW location descriptions not already present.
Output ONLY a valid JSON object. No commentary, no markdown fences.
The JSON must match this exact schema:
{
  "locations": [{
    "name": "<string>",
    "is_new": <boolean>,
    "descriptions": ["<string>"]
  }]
}
Rules:
- Only output locations present in <candidate_locations>.
- For a location with is_new=false, only output descriptions NOT already present
  in <existing_facts> for that location.
- For a location with is_new=true, output a full proposed description set instead
  of a diff.
- Output each location at most once."""

DETECT_LOCATION_ATTRIBUTES_USER = """<paragraph>{paragraph}</paragraph>
<candidate_locations>{candidate_locations}</candidate_locations>
<existing_facts>{existing_facts}</existing_facts>

Identify new descriptions for the candidate locations that appear in the paragraph."""
