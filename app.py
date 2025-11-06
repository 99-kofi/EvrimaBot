# obala_twi_app.py
# Streamlit-based OBALA TWI chat with Gemini and Text-to-Speech output (Twi Error Messages)
# NOTE: This file contains a HARDCODED API KEY PLACEHOLDER for demo purposes.
# For production, store the key in an environment variable instead.

import streamlit as st
import requests
import json
from gradio_client import Client, handle_file
import os
import logging
from PIL import Image
import tempfile
from streamlit_mic_recorder import mic_recorder

# --- Configuration ---
GEMINI_API_KEY = "AIzaSyDpAmrLDJjDTKi7TD-IS3vqQlBAYVrUbv4" # <-- IMPORTANT: REPLACE THIS
MODEL_NAME = "gemini-2.0-flash"
TTS_MODEL = "Ghana-NLP/Southern-Ghana-TTS-Public"
STT_MODEL = "DarliAI/Evaluation" # <-- Re-adding the specialized Twi STT model

# Configure logging to show technical errors in the console (for the developer)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- Twi Error Messages for the User ---
TWI_ERRORS = {
    "TTS_CONNECTION_FAILED": "Mepakyɛw, me nsa nka kasa adwinnadeɛ no mprempren. Bɔ mmɔden bio akyire yi.",
    "STT_CONNECTION_FAILED": "Mepakyɛw, adwinnadeɛ a ɛsesɛ nne mu no nnyɛ adwuma seesei.",
    "TRANSCRIPTION_FAILED": "Mepakyɛw, mantumi ante deɛ wokaeɛ no yie. Bɔ mmɔden bio.",
    "GEMINI_API_FAILED": "Mepakyɛw, m'atwerɛ adwinnadeɛ no anyɛ adwuma yie. Bɔ mmɔden bio.",
    "AUDIO_GENERATION_FAILED": "Mepakyɛw, asɛm ato me wɔ ɛnne no a mɛpagya mu. Mantumi anyɛ no yie.",
    "INVALID_AUDIO_PATH": "Kasa adwinnadeɛ no de biribi a ɛnsɛ amena me. Mantumi annye ɛnne no.",
    "AUDIO_PATH_NOT_FOUND": "Me nsa kaa kwan no deɛ, nanso ɛnne no nni hɔ. Mepakyɛw.",
    "TRANSLATION_FAILED": "Mepakyɛw, menntumi nkyerɛ aseɛ."
}


# --- Main App ---

# Load the logo image
try:
    # Assuming the logo file is named 'evrimabot_logo.png'
    logo = Image.open("evrimabot_logo.png")
    st.set_page_config(page_title="EvrimaBot", page_icon=logo, layout="centered")
except FileNotFoundError:
    # If the logo file is not found, fall back to the emoji
    st.set_page_config(page_title="EvrimaBot", page_icon="🇬🇭", layout="centered")


# --- CUSTOM CSS FOR SMALLER BUTTONS ---
st.markdown("""
<style>
    /* Target the button specifically within Streamlit's structure */
    .stButton>button {
        padding: 0.25rem 0.75rem;
        font-size: 0.85rem;
        line-height: 1.5;
        border-radius: 0.5rem;
        min-height: 1rem;
    }
    .centered-text {
        text-align: center;
        font-size: 1.2rem;
        margin-top: 20px;
        margin-bottom: 30px;
    }
</style>
""", unsafe_allow_html=True)


# --- Helper Functions ---
@st.cache_resource
def init_tts_client():
    """Initializes the Gradio client for Text-to-Speech."""
    try:
        return Client(TTS_MODEL)
    except Exception as e:
        logging.error(f"Could not connect to the Text-to-Speech model: {e}")
        st.error(TWI_ERRORS["TTS_CONNECTION_FAILED"])
        return None

@st.cache_resource
def init_stt_client():
    """Initializes the Gradio client for Speech-to-Text."""
    try:
        return Client(STT_MODEL)
    except Exception as e:
        logging.error(f"STT client (DarliAI) connection failed: {e}")
        st.error(TWI_ERRORS["STT_CONNECTION_FAILED"])
        return None

def translate_text(text_to_translate, target_language="English"):
    """Translates text using the Gemini API."""
    try:
        prompt = f"Translate the following Akan Twi text to {target_language}. Do not add any preamble, just the translation: '{text_to_translate}'"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400}
        }
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
        res = requests.post(api_url, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
        res.raise_for_status()
        data = res.json()
        translated_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", TWI_ERRORS["TRANSLATION_FAILED"])
        return translated_text.strip()
    except Exception as e:
        logging.error(f"Translation API call failed: {e}")
        return TWI_ERRORS["TRANSLATION_FAILED"]

# --- Main Application Logic ---
st.title("🇬🇭 EvrimaBot — Your AI Assistant that speak and hears your language")
st.caption("O- Omniscient • B- Bilingual • A- Akan • L- LLM • A- Agent")
st.caption("From WAIT ❤")
st.info("You can type your prompts in either Twi or English.")

tts_client = init_tts_client()
stt_client = init_stt_client() # Initialize the STT client

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Afehyia pa! Me din de EvrimaBot. Mɛtumi aboa wo sɛn?"}
    ]

# --- Display Chat History ---
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "audio" in msg and msg["audio"]:
            if isinstance(msg["audio"], str) and os.path.isfile(msg["audio"]):
                st.audio(msg["audio"])

        # --- Translation Toggle Logic (for assistant messages only) ---
        if msg["role"] == "assistant" and msg["content"] not in TWI_ERRORS.values():
            visibility_key = f"translation_visible_{i}"
            if visibility_key not in st.session_state:
                st.session_state[visibility_key] = False

            button_text = "Hide Translation" if st.session_state[visibility_key] else "See Translation"

            if st.button(button_text, key=f"translate_btn_{i}"):
                st.session_state[visibility_key] = not st.session_state[visibility_key]
                st.rerun()

            if st.session_state[visibility_key]:
                with st.spinner("Translating..."):
                    translation_cache_key = f"translation_text_{i}"
                    if translation_cache_key not in st.session_state:
                        st.session_state[translation_cache_key] = translate_text(msg["content"])
                    st.info(st.session_state[translation_cache_key])


# --- VOICE AND TEXT INPUT SECTION ---
audio_info = mic_recorder(start_prompt="🎤 Kasa (Speak)", stop_prompt="⏹️ Gyae (Stop)", just_once=True, key='recorder')
prompt = st.chat_input("Kyerɛw wo asɛm wɔ Twi mu...")

# Handle voice input
if audio_info and audio_info['bytes']:
    audio_bytes = audio_info['bytes']
    with st.spinner("Meresesɛ wo nne mu... (Transcribing...)"):
        transcribed_text = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_audio_file:
                tmp_audio_file.write(audio_bytes)
                tmp_audio_filepath = tmp_audio_file.name

            if stt_client:
                result = stt_client.predict(
                    audio_path=handle_file(tmp_audio_filepath),
                    language="Akan (Asante Twi)",
                    api_name="/_transcribe_and_store"
                )
                transcribed_text = result if isinstance(result, str) else str(result)

            os.remove(tmp_audio_filepath)

        except Exception as e:
            logging.error(f"An unexpected transcription error occurred: {e}")
            st.error(TWI_ERRORS["TRANSCRIPTION_FAILED"])

        if transcribed_text and transcribed_text.strip():
            st.session_state.messages.append({"role": "user", "content": transcribed_text})
            st.rerun()

# Handle text input
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()


# --- Generate and Display AI Response (if last message was from user) ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("EvrimaBot redwene ho..."):
            text_reply = ""
            try:
                system_prompt = """You are EvrimaBot, a friendly, patient, and knowledgeable AI assistant from WAIT mfiridwuma ho nimdeɛ. Your purpose is to be a general-purpose helper. You can answer questions on a wide variety of topics, explain complex subjects, summarize text, help with creative tasks like writing poems or stories, and engage in general conversation. Your primary language is Akan Twi. You MUST ALWAYS reply in Akan Twi, regardless of the user's language (English or Twi). Understand the user's input and provide a helpful, relevant response in Akan Twi. To make the conversation more engaging and helpful, ask a relevant follow-up question after your main answer when it feels natural to continue the dialogue. For longer answers, use formatting like lists to make it clear. Be concise and emulate the user's conversational style. If you do not know the answer, politely say 'Mepa wo kyɛw, mennim'. Decline any requests that are harmful or unethical.

Here's information about the Evrima app, which you can use to answer questions related to it:

Evrima is a mobile-first discovery app for Ghana that helps users find places (restaurants, bars, co-working, markets), events and parties near them, filtered by budget, distance, vibe, and time. It includes social and discoverability features such as event listing & booking, user reviews & photos, saved places, creator-hosted events, and a personalized recommendations feed.

Key user personas for Evrima are:
• Young professionals (21–30) looking for events & budget places.
• Students who want cheap eats & parties.
• Travelers & expats seeking curated, local spots.

Core features in the current update include:
• Bottom navigation (Home / Explore / Create / Saved / Profile)
• Explore/Discovery feed with AI-style recommendations (based on budget + interests)
• Event detail + booking + RSVPs (for both free and paid events)
• Place detail (showing photos, price tier, opening hours, contact information, map, and similar places)
• Reviews & photo uploads by users
• Social share & invite friends functionality
• Onboarding + user profile with preferences and payment method setup
• A basic Admin dashboard (web serverless) for event approval & analytics

The high-level screen map & user flow is:
1. Splash → Onboarding (3 slides: what Evrima does, permissions: location + notifications, set budget & interests)
2. Auth: Login (email/phone OTP) / Sign up (Google/Apple optional)
3. Home (personalized feed: events + recommended places)
4. Explore (search + filters: budget, distance, category, date/time, vibe)
5. Place Detail (photos, price tier, map, hours, reviews, save, share)
6. Event Detail (info, host, ticketing / RSVP, calendar + share)
7. Create (create event/place — form + media upload)
8. Saved (bookmarks: places & events)
9. Profile (settings, payment methods, my events, verification)
10. Admin (web serverless: moderate events, view stats)

Primary user flows are:
• Discover → Filter → Open → Save / Book / Share
• Create event → Upload images → Publish (optional admin approval)
• User signs up → sets budget & interests → receives tailored discovery feed

Reusable components in Evrima:
• AppShell (BottomNav + SafeArea)
• Header (search bar or title)
• LocationPermissionBanner
• HorizontalCategoryScroller
• CardPlace / CardEvent (image, title, priceTier, rating, tags)
• FilterModal (chips for budget, distance slider, date picker)
• MapViewWithPins
• MediaCarousel
• ReviewList + ReviewItem
• BookingModal / PaymentSheet
• CreateForm (multi-step)
• Avatar + ProfileCard
• Toast / Snackbars
• Loading + Empty states
"""
                
                gemini_messages = [{"role": ("model" if m["role"] == "assistant" else "user"), "parts": [{"text": m["content"]}]} for m in st.session_state.messages]

                payload = {"contents": gemini_messages, "system_instruction": {"parts": [{"text": system_prompt}]}, "generationConfig": {"temperature": 0.4, "maxOutputTokens": 400}}
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
                res = requests.post(api_url, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
                res.raise_for_status()
                data = res.json()
                text_reply = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", TWI_ERRORS["GEMINI_API_FAILED"])
            except Exception as e:
                logging.error(f"Gemini API call failed: {e}")
                text_reply = TWI_ERRORS["GEMINI_API_FAILED"]
                st.error(text_reply)

        if text_reply and text_reply != TWI_ERRORS["GEMINI_API_FAILED"]:
             st.markdown(text_reply)

        # 2. Generate audio for the new response
        audio_path_to_store = None
        if text_reply and tts_client and text_reply != TWI_ERRORS["GEMINI_API_FAILED"]:
            with st.spinner("EvrimaBot rekasa..."):
                audio_result = None
                try:
                    filepath_str = None
                    audio_result = tts_client.predict(text=text_reply, lang="Asante Twi", speaker="Male (Low)", api_name="/predict")

                    if isinstance(audio_result, str):
                        filepath_str = audio_result
                    elif isinstance(audio_result, dict) and 'name' in audio_result and isinstance(audio_result['name'], str):
                        filepath_str = audio_result['name']

                    if filepath_str:
                        if os.path.isfile(filepath_str):
                            st.audio(filepath_str)
                            audio_path_to_store = filepath_str
                        else:
                            logging.warning(f"Audio generation failed: Path is not a valid file -> '{filepath_str}'")
                            st.warning(TWI_ERRORS["AUDIO_PATH_NOT_FOUND"])
                    else:
                        logging.warning(f"Audio generation failed: Could not extract filepath from TTS response. Received: {audio_result}")
                        st.warning(TWI_ERRORS["INVALID_AUDIO_PATH"])

                except Exception as e:
                    logging.error(f"An error occurred during audio generation: {e}")
                    logging.error(f"The raw data from TTS that caused the error was: {audio_result}")
                    st.error(TWI_ERRORS["AUDIO_GENERATION_FAILED"])

        # 3. Add the complete AI response to history
        st.session_state.messages.append({"role": "assistant", "content": text_reply, "audio": audio_path_to_store})
        st.rerun()
