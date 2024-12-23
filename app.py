import streamlit as st
import os
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import CouldNotRetrieveTranscript
import google.generativeai as genai
from googletrans import Translator
import re
from io import BytesIO
from fpdf import FPDF
from pytube import YouTube
import whisper

# Load environment variables
load_dotenv()

# Configure Google Generative AI
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Initialize the translator
translator = Translator()

# Base prompt for summarization
base_prompt = """
You are a YouTube video summarizer. Take the transcript text and summarize 
the video as per the selected format. Format: {summary_format}.
Please provide the summary of the text given here:
"""

# Function to extract video ID from URL
def extract_video_id(youtube_url):
    try:
        pattern = r"(?:v=|youtu\\.be/|embed/|v/|watch\\?v=|shorts/|e/|^)([A-Za-z0-9_-]{11})"
        match = re.search(pattern, youtube_url)
        if match:
            return match.group(1)
        else:
            st.error("Invalid YouTube URL. Please enter a valid link.")
            return None
    except Exception as e:
        st.error(f"Error parsing YouTube URL: {e}")
        return None

# Function to extract transcript details
def extract_transcript_details(video_id):
    try:
        transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
        transcript = " ".join([entry["text"] for entry in transcript_data])
        return transcript
    except CouldNotRetrieveTranscript as e:
        st.warning(f"Could not retrieve a transcript for this video. Attempting to download audio... {str(e)}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None

# Function to download audio from YouTube
def download_audio(youtube_url):
    try:
        yt = YouTube(youtube_url)
        stream = yt.streams.filter(only_audio=True).first()
        audio_path = stream.download(filename="video_audio.mp4")
        return audio_path
    except Exception as e:
        st.error(f"Error downloading audio: {e}")
        return None

# Function to process audio and generate transcript using Whisper (local model)
def process_audio_with_whisper(audio_path):
    try:
        model = whisper.load_model("base")
        with st.spinner("Processing audio with Whisper..."):
            result = model.transcribe(audio_path)
            return result.get("text", "")
    except Exception as e:
        st.error(f"Error processing audio with Whisper: {e}")
        return None

# Function to translate text
def translate_text(text, src_lang, dest_lang="en"):
    try:
        if not text:
            st.error("No text provided for translation.")
            return None

        if src_lang.lower() == "english":
            src_lang = None  # Auto-detect source language

        translation = translator.translate(text, src=src_lang, dest=dest_lang)
        return translation.text
    except Exception as e:
        st.error(f"Error translating text: {e}")
        return None

# Function to generate summary using AI
def generate_genmini_content(transcript_text, prompt):
    try:
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt + transcript_text)
        return response.text
    except Exception as e:
        st.error(f"Error generating summary: {e}")
        return None

# Function to generate PDF
def generate_pdf(summary_text):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Add a Unicode font (use a font file that supports Unicode characters)
    font_path = "C:/Users/subha/Pictures/font/ttf/NotoSerif-Regular.ttf"  # Replace with the path to your font file
    pdf.add_font("DejaVu", "", font_path, uni=True)
    pdf.set_font("DejaVu", size=12)

    # Add the text
    pdf.multi_cell(0, 10, summary_text)

    return pdf.output(dest="S").encode("latin1")

# Streamlit app
st.markdown(
    """
    <div style="text-align: center;">
        <h1>
            <img src="https://upload.wikimedia.org/wikipedia/commons/4/42/YouTube_icon_%282013-2017%29.png" alt="YouTube Logo" width="60" style="vertical-align: middle; margin-right: 10px;"> 
            YouTube Summarizer
        </h1>
    </div>
    """,
    unsafe_allow_html=True
)

# User input for YouTube link
youtube_link = st.text_input("Enter YouTube Video Link")

# User input for language options
st.subheader("Language Options")
video_language = st.selectbox(
    "Select the video's language:",
    options=["English", "Kannada", "Hindi", "Telugu", "Tamil", "Malayalam", "Other"]
)
summary_language = st.selectbox(
    "Select the summary's language:",
    options=["English", "Kannada", "Hindi", "Telugu", "Tamil", "Malayalam", "Other"]
)

# User input for summary size
summary_size = st.number_input(
    "Enter the desired summary size in words:",
    min_value=100,
    max_value=5000,
    step=50,
    value=1000
)

# User input for summary type
summary_format = st.radio(
    "Select the summary format:",
    options=["Bullet Points", "Sentences", "Paragraphs", "Report", "Essay", "Review"],
    index=2
)

# Adjust the prompt based on input size and format
summary_prompt = base_prompt.format(summary_format=summary_format) + f" in {summary_size} words:"

# Extract video ID and display thumbnail
video_id = None
if youtube_link:
    video_id = extract_video_id(youtube_link)
    if video_id:
        st.markdown(
            f"<div style='text-align: center;'><img src='http://img.youtube.com/vi/{video_id}/0.jpg' width='300'></div>",
            unsafe_allow_html=True
        )

# Button to generate summary
if st.button("Generate Summary"):
    if not youtube_link:
        st.error("Please enter a YouTube link.")
        st.stop()

    if not video_id:
        st.error("Invalid YouTube URL. Please enter a valid link.")
        st.stop()

    # Extract transcript or process audio if no transcript
    transcript_text = extract_transcript_details(video_id)
    if not transcript_text:
        st.warning("Transcript not available. Attempting to download and process audio...")
        audio_path = download_audio(youtube_link)
        if not audio_path:
            st.error("Failed to download audio. Please try another video.")
            st.stop()

        # Process audio through Whisper
        transcript_text = process_audio_with_whisper(audio_path)
        if not transcript_text:
            st.error("Failed to process audio. Please try again later.")
            st.stop()

    # Translate transcript if video language is not English
    if video_language != "English":
        transcript_text = translate_text(transcript_text, src_lang=video_language.lower(), dest_lang="en")
        if not transcript_text:
            st.error("Failed to translate transcript.")
            st.stop()

    # Generate summary in English
    summary = generate_genmini_content(transcript_text, summary_prompt)
    if not summary:
        st.error("Failed to generate summary. Please try again.")
        st.stop()

    # Translate summary to the desired language
    if summary_language != "English":
        summary = translate_text(summary, src_lang="en", dest_lang=summary_language.lower())
        if not summary:
            st.error("Failed to translate summary.")
            st.stop()

    # Display summary
    st.subheader(f"Video Summary ({summary_format}) - {summary_language}")
    st.write(summary)

    # Provide download options
    col1, col2 = st.columns(2)
    with col1:
        # Download as TXT
        txt_data = BytesIO()
        txt_data.write(summary.encode("utf-8"))
        txt_data.seek(0)
        st.download_button(
            label="Download as TXT",
            data=txt_data,
            file_name=f"summary_{summary_format.lower()}.txt",
            mime="text/plain"
        )
    with col2:
        # Download as PDF
        pdf_data = BytesIO(generate_pdf(summary))
        st.download_button(
            label="Download as PDF",
            data=pdf_data,
            file_name=f"summary_{summary_format.lower()}.pdf",
            mime="application/pdf"
        )
