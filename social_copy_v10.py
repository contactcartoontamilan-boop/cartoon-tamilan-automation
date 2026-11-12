"""Audience-first captions for original CartoonTamilan stories.

Does not invent plot facts. Stronger copy can use reviewed Tamil/English
synopses stored privately in the story approvals file.
"""
from social_content_v5 import make_social_pack, hashtags

TAMIL_HOOK = {
    "fantasy": "✨ கற்பனை உலகக் கதைகளை விரும்புகிறீர்களா?",
    "adventure": "🗺️ ஒரு புதிய வாசிப்புப் பயணத்துக்குத் தயாரா?",
    "action": "⚡ அதிரடி கதைகளை விரும்பும் வாசகர்களுக்காக!",
    "romance": "💖 காதல் கதைகளை விரும்புபவர்களுக்காக!",
    "horror": "🌑 திகில் கதைகள் பிடிக்குமா?",
    "drama": "🎭 உணர்வுப்பூர்வமான கதைகளை விரும்புகிறீர்களா?",
    "comedy": "😄 சிரிக்கவைக்கும் கதைகள் பிடிக்குமா?",
    "isekai": "🌌 வேறொரு உலகைப் பற்றிய கதைகள் பிடிக்குமா?",
}
ENGLISH_HOOK = {
    "fantasy": "✨ Love fantasy fiction?",
    "adventure": "🗺️ Looking for your next reading adventure?",
    "action": "⚡ Into action-packed fiction?",
    "romance": "💖 Enjoy romantic fiction?",
    "horror": "🌑 Love a suspenseful read?",
    "drama": "🎭 Looking for an emotional story?",
    "comedy": "😄 Want a fun story to read?",
    "isekai": "🌌 Enjoy otherworldly stories?",
}


def premium_copy(item, approval=None, art_mode="cover"):
    approved = approval or {}
    genre_list = [str(x).lower() for x in approved.get("genres", []) if str(x).strip()]
    first = genre_list[0] if genre_list else None
    pack = make_social_pack(
        item, genres=genre_list,
        verified_intro_ta=approved.get("intro_ta", ""),
        verified_intro_en=approved.get("intro_en", ""),
    )
    t_hook = TAMIL_HOOK.get(first, "📚 அடுத்த கதையைத் தேடுகிறீர்களா?")
    e_hook = ENGLISH_HOOK.get(first, "📖 Discover an original story.")
    title = item["title"].strip()
    ta_intro = pack["intro_tamil"]
    en_intro = pack["intro_english"]
    tag_text = hashtags(genre_list)
    fb_link = pack["facebook"]["link"]
    ig_link = pack["instagram"]["tracked_link_for_bio"]
    pack["facebook"]["caption"] = (
        f"{t_hook}\n\n📚 {title}\n\n{ta_intro}\n\n"
        f"🌍 {en_intro}\n\n👉 முழுக் கதையை இங்கே படியுங்கள்:\n{fb_link}\n\n{tag_text}"
    )
    pack["instagram"]["caption"] = (
        f"{t_hook}\n\n📖 {title}\n\n{ta_intro}\n\n"
        f"{e_hook}\n{en_intro}\n\n"
        f"🔗 Full story: link in our profile bio.\n💬 உங்கள் கருத்தை சொல்லுங்கள்!\n\n{tag_text}"
    )
    pack["instagram"]["tracked_link_for_bio"] = ig_link
    pack["instagram"]["bio_link_setup_required"] = True
    pack["facebook"]["pinned_comment"] = (
        "📖 Read the full story on CartoonTamilan:\n" + fb_link
    )
    pack["alt_text_en"] = (
        ("Original AI-assisted concept illustration" if art_mode == "comfyui"
         else "Promotional graphic using the existing story cover")
        + " for CartoonTamilan original story: " + title
    )
    pack["alt_text_ta"] = title + " — கார்ட்டூன் தமிழன் அசல் கதை விளம்பரப் படம்"
    pack["copy_source"] = "reviewed_synopsis" if (
        approved.get("intro_ta") and approved.get("intro_en")) else "title_based_template"
    pack["requires_editorial_review"] = pack["copy_source"] != "reviewed_synopsis"
    return pack
