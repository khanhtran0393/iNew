import re

with open('d:/iNew/app/services/voice_studio.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the split_text_into_speech_chunks function
# The function starts at def split_text_into_speech_chunks

old_function = '''def split_text_into_speech_chunks(text: str, max_chars: int = 1000) -> List[str]:
    """Chia nhỏ văn bản dài thành các đoạn an toàn cho TTS (ngắt theo câu hoặc đoạn văn)."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    paragraphs = text.split('\\n\\n')
    
    current_chunk = ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        
        # If adding this paragraph exceeds the limit
        if len(current_chunk) + len(paragraph) + 2 > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                # Paragraph itself is too long, split by sentences
                sentences = re.split(r'([.!?]\\s+)', paragraph)
                sentence_chunk = ""
                for i in range(0, len(sentences) - 1, 2):
                    sentence = sentences[i] + sentences[i + 1] if i + 1 < len(sentences) else sentences[i]
                    if len(sentence_chunk) + len(sentence) + 1 > max_chars and sentence_chunk:
                        chunks.append(sentence_chunk.strip())
                        sentence_chunk = sentence
                    else:
                        sentence_chunk += sentence
                if sentence_chunk:
                    chunks.append(sentence_chunk.strip())
        else:
            if current_chunk:
                current_chunk += "\\n\\n" + paragraph
            else:
                current_chunk = paragraph
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks'''

new_function = '''def split_text_into_speech_chunks(text: str, max_chars: int = 1000, target_duration_minutes: float = 10.0) -> List[str]:
    """Chia nhỏ văn bản dài thành các đoạn an toàn cho TTS (ngắt theo câu hoặc đoạn văn)."""
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    
    # Calculate target words per chunk based on target duration
    # ~160 words/minute for natural speech
    target_words_per_chunk = int(target_duration_minutes * 160)
    
    chunks = []
    paragraphs = text.split('\\n\\n')
    
    current_chunk = ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        
        # If adding this paragraph exceeds the limit
        if len(current_chunk) + len(paragraph) + 2 > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                # Paragraph itself is too long, split by sentences
                sentences = re.split(r'([.!?]\\s*)', paragraph)
                sentence_chunk = ""
                for i in range(0, len(sentences) - 1, 2):
                    sentence = sentences[i] + (sentences[i + 1] if i + 1 < len(sentences) else "")
                    if not sentence.strip():
                        continue
                    if len(sentence_chunk) + len(sentence) + 1 > target_words_per_chunk and sentence_chunk:
                        chunks.append(sentence_chunk.strip())
                        sentence_chunk = sentence
                    else:
                        sentence_chunk += sentence
                if sentence_chunk:
                    chunks.append(sentence_chunk.strip())
        else:
            if current_chunk:
                current_chunk += "\\n\\n" + paragraph
            else:
                current_chunk = paragraph
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks'''

if old_function in content:
    content = content.replace(old_function, new_function)
    print('Replaced split_text_into_speech_chunks')
else:
    print('old_function not found')
    # Try to find what's there
    import re
    match = re.search(r'def split_text_into_speech_chunks.*?return chunks', content, re.DOTALL)
    if match:
        print("Found function, here's what exists:")
        print(match.group()[:300])
    else:
        print("Could not find the function")

with open('d:/iNew/app/services/voice_studio.py', 'w', encoding='utf-8') as f:
    f.write(content)