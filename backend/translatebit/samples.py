"""Authored demo fixtures; independent bilingual review is still pending."""

SAMPLES = [
    {"id": "hi-headache", "language": "hi", "source": "मुझे पिछले तीन दिनों से सिरदर्द हो रहा है।", "translation": "I've had a headache for the last three days.", "label": "Describe a symptom"},
    {"id": "en-medication", "language": "en", "source": "Have you taken any medication for it?", "translation": "क्या आपने इसके लिए कोई दवा ली है?", "label": "Ask about medication"},
    {"id": "hi-negation", "language": "hi", "source": "नहीं, मैंने अभी तक कोई दवा नहीं ली है।", "translation": "No, I haven't taken any medication yet.", "label": "Preserve a negation"},
    {"id": "en-onset", "language": "en", "source": "Does the pain come and go, or is it constant?", "translation": "क्या दर्द आता-जाता है, या लगातार रहता है?", "label": "Ask a follow-up"},
    {"id": "hi-correction", "language": "hi", "source": "माफ़ कीजिए, तीन नहीं, दो दिनों से।", "translation": "Sorry, for two days, not three.", "label": "Correct an earlier detail"},
    {"id": "en-confirm", "language": "en", "source": "Let me confirm: the headache started two days ago?", "translation": "मैं पुष्टि कर लूँ: सिरदर्द दो दिन पहले शुरू हुआ था?", "label": "Confirm the correction"},
]
