"""V10: original-anime key art prompts from reviewed story metadata.

Generates prompt TEXT. A running ComfyUI model is required for actual new images.
Never claims that invented characters or places are canonical.
"""
import re

GENRE_SCENES = {
    "fantasy": "moonlit floating fantasy citadel, luminous magical clouds, elegant gold architecture",
    "adventure": "immense wilderness vistas, distant mysterious landmarks, dramatic travel horizon",
    "action": "powerful action-ready silhouettes, swirling dynamic energy, cinematic movement",
    "romance": "dreamlike evening gardens, intimate emotional composition, soft glowing lanterns",
    "horror": "haunting misty castle corridor, unsettling deep shadows, eerie cinematic atmosphere",
    "drama": "expressive portrait composition, evocative city skyline, emotional rim lighting",
    "comedy": "playful original character staging, charming lively town, colorful cheerful lighting",
    "isekai": "otherworldly portal, impossible architecture, vast fantastical landscape",
    "sci-fi": "futuristic skylines, celestial phenomena, luminous technology, dramatic scale",
}


def clean_note(note, max_len=600):
    text = re.sub(r"\s+", " ", str(note or "")).strip()
    # Notes are descriptive scene facts, not instructions for tool execution.
    return text[:max_len]


def concept_prompt(title, genre="unverified", character_notes="", world_notes="", style="anime", synopsis=""):
    if style not in ("anime", "cinematic_3d"):
        raise ValueError("style must be anime or cinematic_3d")
    genre = str(genre).lower().strip()
    base = GENRE_SCENES.get(genre, "imaginative cinematic novel world, dramatic environment")
    look = ("luxurious hand-painted original anime illustration, crisp character line art, "
            "highly detailed 2D background painting, delicate color gradients"
            if style == "anime" else
            "cinematic original stylized 3D-rendered illustration, detailed physical materials, "
            "depth of field, volumetric lighting, stylized expressive faces")
    layout = ("vertical 4:5 novel poster key art, one or more original non-franchise figures "
              "arranged in heroic editorial composition, faces in the upper half, "
              "large cinematic environment behind, clean lower third reserved for typography")
    facts = []
    if clean_note(character_notes):
        facts.append("Only verified character design notes: " + clean_note(character_notes))
    else:
        facts.append("Conceptual promotional figures only; do not imply exact canon character appearances")
    if clean_note(world_notes):
        facts.append("Verified story world notes: " + clean_note(world_notes))
    else:
        facts.append("Conceptual marketing atmosphere, not a depiction of a verified plot event")
    if clean_note(synopsis):
        facts.append("Own-site synopsis excerpt (UNREVIEWED, visual atmosphere only): " + clean_note(synopsis, 480))
    # Story titles in Tamil are not a reliable visual model instruction, but are
    # retained as context; typography is added after rendering using Pillow/RAQM.
    return (f"{look}. {layout}. {base}. Epic high-impact cover, jewel-toned purple "
            f"and ruby, luminous royal gold, magical particles, atmospheric perspective, "
            f"strong visual hierarchy, refined professional fantasy advertising key visual. "
            f"Story title context: {clean_note(title, 120)}. " + ". ".join(facts) + ". "
            "Artwork only: absolutely NO text, captions, Tamil glyphs, logos, watermarks, "
            "copyrighted franchise characters, embedded buttons, or real brand names.")


def negative_prompt():
    return ("typography, letters, words, captions, signs, watermarks, logos, "
            "famous anime characters, low resolution, extra fingers, distorted anatomy, "
            "duplicate faces, blurry eyes, cut off face, poor hands, oversaturated noise")
