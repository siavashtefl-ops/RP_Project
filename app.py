import streamlit as st
import parselmouth
import json
import os
import asyncio
import edge_tts
from audio_recorder_streamlit import audio_recorder

# Load the Phoneme Database
if os.path.exists("phoneme_bank.json"):
    with open("phoneme_bank.json", "r", encoding="utf-8") as f:
        phoneme_bank = json.load(f)
else:
    st.error("Could not find phoneme_bank.json. Please ensure it exists.")
    st.stop()

st.set_page_config(page_title="RP Pronunciation Coach", layout="centered")
st.title("🇬🇧 British RP Pronunciation Coach")
st.markdown("Type a target word, listen to the native audio, and record your voice to get instant feedback.")

target_word = st.text_input("Type your target word:").strip().lower()

if target_word:
    target_phoneme = "ɜː" # default fallback
    for p in phoneme_bank.keys():
        if p in target_word: 
            target_phoneme = p
            break
            
    if target_phoneme not in phoneme_bank:
        target_phoneme = list(phoneme_bank.keys())[0]

    baseline = phoneme_bank[target_phoneme]
    st.success(f"Target Loaded: **{target_word.capitalize()}** (Vowel: /{target_phoneme}/)")

    # --- SIDE-BY-SIDE DASHBOARD ---
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🔊 Native Reference")
        with st.container(border=True):
            st.markdown("Listen to how a native speaker pronounces this word:")
            native_audio_path = f"ref_{target_word}.mp3"
            if not os.path.exists(native_audio_path):
                async def create_ref():
                    communicate = edge_tts.Communicate(target_word, "en-GB-SoniaNeural")
                    await communicate.save(native_audio_path)
                asyncio.run(create_ref())
            st.audio(native_audio_path, format="audio/mp3")

    with col2:
        st.markdown("### 🎙️ Interactive Recorder")
        # Visual Card Container for the Recorder to make it prominent
        with st.container(border=True):
            st.markdown("**Step 2:** Click the microphone to record:")
            audio_bytes = audio_recorder(pause_threshold=2.0, sample_rate=44100, icon_size="36px")
            if not audio_bytes:
                st.caption("🔴 *Mic is active. Click to record.*")

    if audio_bytes:
        st.divider()
        st.subheader("📊 Your Recording & Evaluation")
        st.audio(audio_bytes, format="audio/wav")
        
        temp_filename = "temp_web_upload.wav"
        with open(temp_filename, "wb") as f:
            f.write(audio_bytes)
            
        try:
            sound = parselmouth.Sound(temp_filename)
            
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
            
            f1_diff = abs(f1 - baseline["baseline_f1"]) / baseline["baseline_f1"] * 100
            f2_diff = abs(f2 - baseline["baseline_f2"]) / baseline["baseline_f2"] * 100
            dur_diff = abs(actual_duration - baseline["baseline_dur"]) / baseline["baseline_dur"] * 100
            
            score = max(0, 100 - ((f1_diff + f2_diff + dur_diff) / 3))
            
            st.subheader(f"Overall Match Score: {score:.1f} / 100")
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Duration", f"{actual_duration:.3f}s", f"{dur_diff:.1f}% diff", delta_color="inverse")
            m2.metric("F1 (Jaw Height)", f"{f1:.1f} Hz", f"{f1_diff:.1f}% diff", delta_color="inverse")
            m3.metric("F2 (Tongue Position)", f"{f2:.1f} Hz", f"{f2_diff:.1f}% diff", delta_color="inverse")
            
            st.markdown("### Coaching Feedback")
            if dur_diff < 30:
                st.info("⏱️ **Vowel Length:** Great match!")
            elif actual_duration > baseline["baseline_dur"]:
                st.warning("⏱️ **Vowel Length:** Too long. Clip it slightly faster.")
            else:
                st.warning("⏱️ **Vowel Length:** Too short. Hold it longer.")
                
            if f1_diff < 15:
                st.info("👄 **Tongue Height:** Excellent placement!")
            elif f1 > baseline["baseline_f1"]:
                st.error("👄 **Tongue Height:** Jaw is too dropped. Raise your jaw.")
            else:
                st.error("👄 **Tongue Height:** Jaw is too high. Drop your jaw.")
                
            if f2_diff < 15:
                st.info("👅 **Tongue Position:** Excellent front-to-back placement!")
            elif f2 > baseline["baseline_f2"]:
                st.error("👅 **Tongue Position:** Tongue is too far forward. Pull it back.")
            else:
                st.error("👅 **Tongue Position:** Tongue is too far back. Push it forward.")
                
        finally:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
