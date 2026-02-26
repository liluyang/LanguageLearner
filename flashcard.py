import random
from datetime import date

import streamlit as st

from file_util import (
    load_dictionary,
    load_review_words,
    load_due_words,
    remove_word_from_practice_file,
    upsert_word_in_difficult_file,
    remove_word_from_difficult_file,
    move_word_between_difficult_files,
    # NEW: today.txt helpers
    load_today_words,
    add_word_to_today_file,
    remove_word_from_today_file,
    # NEW: new_words.txt helpers
    load_new_words,
    merge_new_words_to_dictionary,
)

DICTIONARY_FILE = "data/dictionary.txt"
PRACTICE_FILE = "data/to_practice.txt"
DIFFICULT_5_FILE = "data/difficult_5.txt"
DIFFICULT_15_FILE = "data/difficult_15.txt"
TODAY_FILE = "data/today.txt"
NEW_WORDS_FILE = "data/new_words.txt"


def render_header(icon_path: str = "data/icon.png", title: str = "Palabra Español"):
    """Render a small icon next to the app title with vertical centering."""
    try:
        col1, col2 = st.columns([0.08, 0.92])
        with col1:
            st.image(icon_path, width=40)
        with col2:
            # Use a small HTML container to veritically center the title
            st.markdown(
                f"<div style='display:flex; align-items:center; height:48px;'><h1 style='margin:0'>{title}</h1></div>",
                unsafe_allow_html=True,
            )
    except Exception:
        # Fall back to simple title if image can't be loaded
        st.title(title)


def load_words_for_mode(mode: str):
    today = date.today()
    if mode == "New words":
        return list(load_new_words(NEW_WORDS_FILE).keys())
    if mode == "Review":
        return load_review_words(PRACTICE_FILE, st.session_state.dictionary)
    if mode == "5 Day":
        return load_due_words(
            DIFFICULT_5_FILE,
            interval_days=5,
            dictionary=st.session_state.dictionary,
            today=today,
        )
    if mode == "15 Day":
        return load_due_words(
            DIFFICULT_15_FILE,
            interval_days=15,
            dictionary=st.session_state.dictionary,
            today=today,
        )
    if mode == "Today":
        return load_today_words(TODAY_FILE, st.session_state.dictionary)

    return load_review_words(PRACTICE_FILE, st.session_state.dictionary)


def reset_session_for_new_wordlist(words):
    st.session_state.practice_words = words
    st.session_state.current_word = random.choice(words) if words else None
    st.session_state.show_hint = False
    st.session_state.show_answer = False
    st.session_state.pending_dont_know = False  # waiting for OK?
    st.session_state.show_verify = False


def ensure_initialized():
    if "dictionary" not in st.session_state:
        st.session_state.dictionary = load_dictionary(DICTIONARY_FILE)

    if "new_words" not in st.session_state:
        st.session_state.new_words = load_new_words(NEW_WORDS_FILE)

    if "mode" not in st.session_state:
        st.session_state.mode = "New words"

    if "practice_words" not in st.session_state:
        words = load_words_for_mode(st.session_state.mode)
        reset_session_for_new_wordlist(words)

    if "show_hint" not in st.session_state:
        st.session_state.show_hint = False

    if "show_answer" not in st.session_state:
        st.session_state.show_answer = False

    if "pending_dont_know" not in st.session_state:
        st.session_state.pending_dont_know = False
    if "show_verify" not in st.session_state:
        st.session_state.show_verify = False


def reload_current_mode_words(keep_current_word: bool = False):
    """
    Reload current mode word list from disk after file updates.
    Optionally keep the current word if it still exists in the list.
    """
    current = st.session_state.current_word
    words = load_words_for_mode(st.session_state.mode)

    st.session_state.practice_words = words
    st.session_state.show_hint = False
    st.session_state.show_answer = False
    st.session_state.pending_dont_know = False
    st.session_state.show_verify = False

    if not words:
        st.session_state.current_word = None
        return

    if keep_current_word and current in words:
        st.session_state.current_word = current
    else:
        st.session_state.current_word = random.choice(words)


def all_reviewed_view():
    render_header()
    st.success("You have reviewed everything, great job!")
    st.stop()


def handle_i_know(word: str):
    """
    Apply "I know" effects immediately, then reload current mode list.
    """
    today = date.today()
    mode = st.session_state.mode

    if mode == "New words":
        # Merge new word into dictionary and remove from new_words
        merge_new_words_to_dictionary(NEW_WORDS_FILE, DICTIONARY_FILE, word)
        # Reload new_words in session
        st.session_state.new_words = load_new_words(NEW_WORDS_FILE)
        # Reload dictionary
        st.session_state.dictionary = load_dictionary(DICTIONARY_FILE)

    elif mode == "Review":
        remove_word_from_practice_file(PRACTICE_FILE, word)

    elif mode == "5 Day":
        move_word_between_difficult_files(DIFFICULT_5_FILE, DIFFICULT_15_FILE, word, today)

    elif mode == "15 Day":
        remove_word_from_difficult_file(DIFFICULT_15_FILE, word)
        remove_word_from_practice_file(PRACTICE_FILE, word)

    elif mode == "Today":
        remove_word_from_today_file(TODAY_FILE, word)

    reload_current_mode_words()


def apply_dont_know_effect(word: str):
    """
    File mutations for "Don't know" (applied when user clicks OK),
    including the new rule: in ALL modes except Today, also add to today.txt.
    """
    today = date.today()
    mode = st.session_state.mode

    if mode == "New words":
        # Merge new word into dictionary and remove from new_words
        merge_new_words_to_dictionary(NEW_WORDS_FILE, DICTIONARY_FILE, word)
        # Also add to difficult_5.txt and today.txt with today's date
        upsert_word_in_difficult_file(DIFFICULT_5_FILE, word, today)
        add_word_to_today_file(TODAY_FILE, word)
        # Reload new_words in session
        st.session_state.new_words = load_new_words(NEW_WORDS_FILE)
        # Reload dictionary
        st.session_state.dictionary = load_dictionary(DICTIONARY_FILE)

    elif mode == "Review":
        upsert_word_in_difficult_file(DIFFICULT_5_FILE, word, today)
        add_word_to_today_file(TODAY_FILE, word)

    elif mode == "5 Day":
        upsert_word_in_difficult_file(DIFFICULT_5_FILE, word, today)
        add_word_to_today_file(TODAY_FILE, word)

    elif mode == "15 Day":
        upsert_word_in_difficult_file(DIFFICULT_15_FILE, word, today)
        add_word_to_today_file(TODAY_FILE, word)

    elif mode == "Today":
        # Today mode: DON'T add to today.txt again; just show answer then OK → next word
        # No file change required for Don't know.
        pass

    reload_current_mode_words()


# ---------- App ----------

st.set_page_config(page_title="Palabra Español", page_icon="data/icon.png")


def apply_background(color: str = "#F6F7FB") -> None:
    try:
        with open("data/theme.css", "r", encoding="utf-8") as fh:
            css = fh.read()
            st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        # Fallback: inject minimal CSS to set background color
        css = f"""
        <style>
        body {{ background-color: {color}; }}
        .stApp {{
            background-color: {color};
        }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)


try:
    ensure_initialized()
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()

# Apply requested background color
apply_background("#F6F7FB")

# Sidebar: mode switching + due counter
st.sidebar.header("Mode")

changed = False
disable_mode_switch = st.session_state.pending_dont_know

if st.sidebar.button("New words", use_container_width=True, disabled=disable_mode_switch):
    st.session_state.mode = "New words"
    changed = True
if st.sidebar.button("Review", use_container_width=True, disabled=disable_mode_switch):
    st.session_state.mode = "Review"
    changed = True
if st.sidebar.button("5 Day", use_container_width=True, disabled=disable_mode_switch):
    st.session_state.mode = "5 Day"
    changed = True
if st.sidebar.button("15 Day", use_container_width=True, disabled=disable_mode_switch):
    st.session_state.mode = "15 Day"
    changed = True
if st.sidebar.button("Today", use_container_width=True, disabled=disable_mode_switch):
    st.session_state.mode = "Today"
    changed = True

if changed:
    reload_current_mode_words()

due_count = len(st.session_state.practice_words) if st.session_state.practice_words else 0
st.sidebar.caption(f"Current: **{st.session_state.mode}**")
st.sidebar.metric("Due", due_count)

if st.sidebar.button("🔄 Reload files", use_container_width=True, disabled=disable_mode_switch):
    for k in ["dictionary", "practice_words", "current_word", "show_hint", "show_answer", "pending_dont_know", "mode"]:
        st.session_state.pop(k, None)
    st.rerun()

# If nothing due, celebrate and stop
if not st.session_state.practice_words:
    all_reviewed_view()

# Main UI
render_header()


word = st.session_state.current_word
if word is None:
    all_reviewed_view()

# Get card: from dictionary if available, else from new_words
if word in st.session_state.dictionary and word in st.session_state.new_words:
    # Merge both cards for display
    from file_util import merge_new_word_into_dictionary
    card = merge_new_word_into_dictionary(st.session_state.new_words[word], st.session_state.dictionary)
elif word in st.session_state.dictionary:
    card = st.session_state.dictionary[word]
elif word in st.session_state.new_words:
    card = st.session_state.new_words[word]
else:
    # Word not found in either; skip
    st.error(f"Word '{word}' not found in any source.")
    st.stop()
st.markdown(f"## {word}")

# Two-step flow for "Don't know": show answer, then OK applies effects and moves on.
if st.session_state.pending_dont_know:
    st.success(f"Meaning: {card.meaning}")
    # Show all example sentences
    examples = [e.strip() for e in card.example.split('|') if e.strip()]
    if examples:
        st.markdown("**Examples:**")
        for ex in examples:
            st.info(ex)

    if st.button("OK"):
        apply_dont_know_effect(word)
        st.rerun()
else:
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("✅ I know"):
            handle_i_know(word)
            st.rerun()

    with col2:
        # Hint is optional in Today mode too; it only shows example sentence (no file changes)
        if st.button("💡 Hint"):
            st.session_state.show_hint = True

    with col3:
        if st.button("🔍 Verify"):
            # Show meaning + example only; no other side effects
            st.session_state.show_verify = True
            st.session_state.show_hint = False
            st.session_state.show_answer = False
            st.session_state.pending_dont_know = False
            st.rerun()

    with col4:
        if st.button("❌ Don't know"):
            # Show answer now; file updates (except Today mode) happen when user clicks OK
            st.session_state.pending_dont_know = True
            st.session_state.show_answer = True
            st.session_state.show_hint = False
            st.rerun()
    if st.session_state.show_hint:
        examples = [e.strip() for e in card.example.split('|') if e.strip()]
        if examples:
            st.markdown("**Example:**")
            for ex in examples:
                st.info(ex)

    if st.session_state.show_verify:
        st.success(f"Meaning: {card.meaning}")
        examples = [e.strip() for e in card.example.split('|') if e.strip()]
        if examples:
            st.markdown("**Examples:**")
            for ex in examples:
                st.info(ex)
