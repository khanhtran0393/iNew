import re

with open('d:/iNew/app/services/voice_studio.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the function and add target_words_per_chunk
# We'll search for the specific pattern and add the line

# First, let's find where "target_words_per_chunk" already exists
if 'target_words_per_chunk' in content:
    print('Already modified')
else:
    # Find the split_text function and add the line
    # Look for the pattern: def split_text_into_speech_chunks
    # and add the target_words_per_chunk calculation after the if len(text) block
    
    # Pattern to find and replace
    old_pattern = '''def split_text_into_speech_chunks(text: str, max_chars: int = 1000) -> List[str]:
    """Chia nhỏ văn bản dài thành các đoạn an toàn cho TTS (ngắt theo câu hoặc đoạn văn)."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    
    chunks = []'''
    
    new_pattern = '''def split_text_into_speech_chunks(text: str, max_chars: int = 1000, target_duration_minutes: float = 10.0) -> List[str]:
    """Chia nhỏ văn bản dài thành các đoạn an toàn cho TTS (ngắt theo câu hoặc đoạn văn)."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    
    # Calculate target words per chunk based on target duration
    # ~160 words/minute for natural speech
    target_words_per_chunk = int(target_duration_minutes * 160)
    
    chunks = []'''
    
    if old_pattern in content:
        content = content.replace(old_pattern, new_pattern)
        print('Modified split_text function')
    else:
        print('Pattern not found - trying alternative')
        # Try to find just the function definition
        import re
        match = re.search(r'def split_text_into_speech_chunks.*?chunks = \[\]', content, re.DOTALL)
        if match:
            print("Found function, here's the start:")
            print(match.group()[:200])
        else:
            print("Could not find function")

with open('d:/iNew/app/services/voice_studio.py', 'w', encoding='utf-8') as f:
    f.write(content)