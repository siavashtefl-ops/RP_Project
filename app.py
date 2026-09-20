import streamlit as st
import parselmouth
import os
import asyncio
import edge_tts
from audio_recorder_streamlit import audio_recorder

# Word Dictionary with human baseline averages
word_bank = {
    "nurse": {
        "baseline_f1": 619.9,
        "baseline_f2": 1762.1,
        "baseline_dur": 0.994
    },
    "bath": {
        "baseline_f1": 700.0,
        "baseline_f2": 1400.0,
        "baseline_dur": 0.850
    }
}

st.set_page_config(page_title="RP Pronunciation Coach", layout="centered")

st.title("🇬🇧 British RP Pronunciation Coach")
st.markdown("Type a target word, listen to the native audio, record your voice, and get instant biomechanical feedback.")

target_word = st.text_input("Type your target word:").strip().lower()

if target_word:
    # Fallback dictionary entry if word isn't pre-configured
    if target_word not in word_bank:
        word_bank[target_word] = {
            "baseline_f1": 650.0,
            "baseline_f2": 1700.0,
            "baseline_dur": 0.900
        }
    
    baseline = word_bank[target_word]
    st.success(f"Target Loaded: **{target_word.capitalize()}**")

    # 1. Native Reference Audio Player
    st.subheader("1. Listen to Native Reference")
    native_audio_path = f"ref_{target_word}.mp3"
    
    # Automatically generate reference audio via edge-tts if it doesn't exist
    if not os.path.exists(native_audio_path):
        async def create_ref():
            communicate = edge_tts.Communicate(target_word, "en-GB-SoniaNeural")
            await communicate.save(native_audio_path)
        asyncio.run(create_ref())
        
    st.audio(native_audio_path, format="audio/mp3")

    # 2. User Recording Widget
    st.subheader("2. Record Your Pronunciation")
    audio_bytes = audio_recorder(pause_threshold=2.0, sample_rate=44100)
    
    if audio_bytes:
        st.subheader("3. Evaluation & Your Recording")
        st.audio(audio_bytes, format="audio/wav")
        
        temp_filename = "temp_web_upload.wav"
        with open(temp_filename, "wb") as f:
            f.write(audio_bytes)
            
        st.info("Analyzing acoustic signature...")
        
        try:
            sound = parselmouth.Sound(temp_filename)
            
            # Silence Removal Logic (50 dB Threshold)
            intensity = sound.to_intensity()
            intensity_values = intensity.values[0]
            time_steps = intensity.xs()
            speech_times = [time_steps[i] for i, vol in enumerate(intensity_values) if vol > 50]
            
            if speech_times:
                actual_duration = speech_times[-1] - speech_times[0]
                mid_time = speech_times[0] + (actual_duration / 2.0)
            else:
                actual_duration = sound.get_total_duration()
                mid_time = actual_duration / 2.0
                
            formant = sound.to_formant_burg(time_step=0.01)
            f1 = formant.get_value_at_time(1, mid_time)
            f2 = formant.get_value_at_time(2, mid_time)
            
            # Math & Scoring Calculations
            f1_diff = abs(f1 - baseline["baseline_f1"]) / baseline["baseline_f1"] * 100
            f2_diff = abs(f2 - baseline["baseline_f2"]) / baseline["baseline_f2"] * 100
            dur_diff = abs(actual_duration - baseline["baseline_dur"]) / baseline["baseline_dur"] * 100
            
            score = max(0, 100 - ((f1_diff + f2_diff + dur_diff) / 3))
            
            st.subheader(f"Overall Match Score: {score:.1f} / 100")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Duration", f"{actual_duration:.3f}s", f"{dur_diff:.1f}% diff", delta_color="inverse")
            col2.metric("F1 (Jaw Height)", f"{f1:.1f} Hz", f"{f1_diff:.1f}% diff", delta_color="inverse")
            col3.metric("F2 (Tongue Position)", f"{f2:.1f} Hz", f"{f2_diff:.1f}% diff", delta_color="inverse")
            
            # Directional Coaching Feedback
            st.markdown("### Coaching Feedback")
            
            if dur_diff < 30:
                st.info("⏱️ **Vowel Length:** Great match! Native-like duration.")
            elif actual_duration > baseline["baseline_dur"]:
                st.warning("⏱️ **Vowel Length:** A bit too long. Try clipping the vowel slightly faster.")
            else:
                st.warning("⏱️ **Vowel Length:** A bit too short. Try holding the vowel a fraction longer.")
                
            if f1_diff < 15:
                st.info("👄 **Tongue Height:** Excellent! Perfect RP vertical placement.")
            elif f1 > baseline["baseline_f1"]:
                st.error("👄 **Tongue Height:** Your jaw is too dropped. Try raising your jaw.")
            else:
                st.error("👄 **Tongue Height:** Your jaw is too high. Try dropping your jaw slightly.")
                
            if f2_diff < 15:
                st.info("👅 **Tongue Position:** Excellent! Perfect front-to-back placement.")
            elif f2 > baseline["baseline_f2"]:
                st.error("👅 **Tongue Position:** Your tongue is too far forward. Try pulling it back.")
            else:
                st.error("👅 **Tongue Position:** Your tongue is too far back. Try pushing it slightly forward.")
                
        finally:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)